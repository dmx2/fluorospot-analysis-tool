import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch
import yaml

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from fluorospot_analysis import (
  AnalysisConfig,
  AnalysisResult,
  FluoroSpotAnalyzer,
  DataLoader
)


class TestDataLoader:
  def test_load_config_reads_populations_and_defaults(self, tmp_path):
    config_file = tmp_path / 'config.yaml'
    config_file.write_text(yaml.dump({
      'cells_per_well': 200000,
      'sfc_cutoff': 20,
      'control_stim': 'DMSO',
      'cytokines': {'IFNg': 'LED490'},
      'plates': {'plate_1': 'S. pneumoniae'},
      'populations': ['LED490 Total', 'LED490+LED550'],
    }))

    config = DataLoader.load_config(config_file)

    assert config.populations == ['LED490 Total', 'LED490+LED550']
    assert config.experimental_conditions is None

  def test_load_config_without_populations_keeps_totals_default(self, tmp_path):
    config_file = tmp_path / 'config.yaml'
    config_file.write_text(yaml.dump({
      'cells_per_well': 200000,
      'sfc_cutoff': 20,
      'control_stim': 'DMSO',
      'cytokines': {'IFNg': 'LED490'},
      'plates': {'plate_1': 'S. pneumoniae'},
    }))

    config = DataLoader.load_config(config_file)

    assert config.populations is None
    endpoints = FluoroSpotAnalyzer(config).endpoints_for(pd.DataFrame({
      'Analyte Secreting Population': ['LED490 Total']
    }))
    assert [endpoint.label for endpoint in endpoints] == ['LED490 Total']

  def test_breakout_donor_dfs(self):
    df = pd.DataFrame({
      'Layout-Donor': ['D001', 'D001', 'D002', 'D002'],
      'Plate': ['plate_1', 'plate_1', 'plate_1', 'plate_1'],
      'Layout-Stimuli': ['DMSO', 'PHA', 'DMSO', 'PHA'],
      'Spot Forming Units (SFU)': [10, 50, 15, 60],
      'Analyte Secreting Population': ['LED490 Total'] * 4
    })
    
    donor_data = DataLoader._breakout_donor_dfs(df)
    assert len(donor_data) == 2
    assert donor_data[0][0] == 'D001'
    assert donor_data[1][0] == 'D002'
    assert len(donor_data[0][1]) == 2
    assert len(donor_data[1][1]) == 2

  @patch('pandas.read_excel')
  def test_load_donor_data_single_file(self, mock_read_excel):
    mock_df = pd.DataFrame({
      'Layout-Donor': ['D001', 'D001'],
      'Plate': ['plate_1', 'plate_1'],
      'Layout-Stimuli': ['DMSO', 'PHA'],
      'Spot Forming Units (SFU)': [10, 50],
      'Analyte Secreting Population': ['LED490 Total'] * 2
    })
    mock_read_excel.return_value = mock_df
    
    donor_data = DataLoader.load_donor_data(all_raw_data=Path('test.xlsx'))
    assert len(donor_data) == 1
    assert donor_data[0][0] == 'D001'

  def test_load_donor_data_no_args_raises_error(self):
    with pytest.raises(ValueError, match="Either all_raw_data or donor_dir must be provided"):
      DataLoader.load_donor_data()


class TestFluoroSpotAnalyzer:
  @pytest.fixture
  def config(self):
    return AnalysisConfig(
      cells_per_well=200000,
      sfc_cutoff=20,
      control_stim="DMSO",
      cytokines={"IFNg": "LED490", "IL-10": "LED550"},
      plates={"plate_1": "S. pneumoniae"}
    )

  @pytest.fixture
  def analyzer(self, config):
    return FluoroSpotAnalyzer(config)

  @pytest.fixture
  def sample_data(self):
    return pd.DataFrame({
      'Layout-Donor': ['D001'] * 6,
      'Plate': ['plate_1'] * 6,
      'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA'],
      'Spot Forming Units (SFU)': [10, 12, 11, 45, 50, 48],
      'Analyte Secreting Population': ['LED490 Total'] * 6
    })

  def test_calculate_statistics_basic(self, analyzer):
    control_values = np.array([10, 12, 11])
    stim_values = np.array([45, 50, 48])
    
    result = analyzer._calculate_statistics(control_values, stim_values)
    
    assert isinstance(result, AnalysisResult)
    assert result.t_test_p < 1.0
    assert result.si > 1.0
    assert len(result.poisson_p_values) == 3
    assert result.sfc_value > 0

  def test_calculate_statistics_empty_arrays(self, analyzer):
    control_values = np.array([])
    stim_values = np.array([])
    
    result = analyzer._calculate_statistics(control_values, stim_values)
    
    assert result.t_test_p == 1.0
    assert result.si == 0.0
    assert result.sfc_value == 0.0

  def test_calculate_statistics_with_nan_values(self, analyzer):
    control_values = np.array([10, np.nan, 12])
    stim_values = np.array([45, 50, np.nan])
    
    result = analyzer._calculate_statistics(control_values, stim_values)
    
    assert not np.isnan(result.t_test_p)
    assert not np.isnan(result.si)
    assert not np.isnan(result.sfc_value)

  def test_analyze_single_donor_simple_mode(self, analyzer, sample_data):
    result_df = analyzer._analyze_single_donor('D001', sample_data)
    
    assert not result_df.empty
    assert 'Donor ID' in result_df.columns
    assert 'Stimulus' in result_df.columns
    assert 'Positive Response' in result_df.columns
    
    control_rows = result_df[result_df['Stimulus'] == 'DMSO']
    stim_rows = result_df[result_df['Stimulus'] == 'PHA']
    assert len(control_rows) == 1
    assert len(stim_rows) == 1

  def test_analyze_donor_data(self, analyzer, sample_data):
    donor_data = [('D001', sample_data)]
    
    result_df = analyzer.analyze_donor_data(donor_data)
    
    assert not result_df.empty
    assert 'D001' in result_df['Donor ID'].values

  def test_create_result_row(self, analyzer, sample_data):
    stim_values = np.array([45, 50, 48])
    stats = AnalysisResult(0.01, 4.0, [0.001, 0.002, 0.003], 150.0)
    
    result_row = analyzer._create_result_row(
      'D001', 'IFNg', 'PHA', stim_values, stats, sample_data, 'default'
    )
    
    assert not result_row.empty
    assert result_row['Donor ID'].iloc[0] == 'D001'
    assert result_row['Cytokine'].iloc[0] == 'IFNg'
    assert result_row['Stimulus'].iloc[0] == 'PHA'
    assert result_row['SI'].iloc[0] == 4.0
    assert 'Positive Response' in result_row.columns

  def test_positive_response_calculation(self, analyzer, sample_data):
    stim_values = np.array([45, 50, 48])
    
    # Test case that should be positive (high SI, low p-value, high SFC)
    stats = AnalysisResult(0.01, 4.0, [0.001, 0.002, 0.003], 150.0)
    result_row = analyzer._create_result_row(
      'D001', 'IFNg', 'PHA', stim_values, stats, sample_data, 'default'
    )
    assert result_row['Positive Response'].iloc[0] == True
    
    # Test case that should be negative (low SI)
    stats = AnalysisResult(0.01, 1.0, [0.001, 0.002, 0.003], 150.0)
    result_row = analyzer._create_result_row(
      'D001', 'IFNg', 'PHA', stim_values, stats, sample_data, 'default'
    )
    assert result_row['Positive Response'].iloc[0] == False

  def test_analyze_plate_experimental_conditions(self, config, sample_data):
    # Test with experimental conditions
    config.experimental_conditions = {
      'plate_1': {
        'test_condition': {
          'control': 'DMSO',
          'stimuli': ['PHA']
        }
      }
    }
    analyzer = FluoroSpotAnalyzer(config)
    
    result_df = analyzer._analyze_plate('D001', 'IFNg', sample_data)
    
    assert not result_df.empty
    assert 'test_condition' in result_df['Experimental Condition'].values

  def test_analyze_plate_without_control_is_not_evaluable(self, analyzer, sample_data):
    # No row matches the configured control stimulus at all
    modified_data = sample_data.copy()
    modified_data.loc[modified_data['Layout-Stimuli'] == 'DMSO', 'Layout-Stimuli'] = 'OTHER'

    result_df = analyzer._analyze_plate('D001', 'IFNg', modified_data)

    scored = result_df[result_df['Stimulus'] == 'OTHER']
    assert len(scored) == 1
    assert scored['Evaluable'].iloc[0] == False
    assert pd.isna(scored['Positive Response'].iloc[0])
    assert 'No replicate rows' in scored['Not Evaluable Reason'].iloc[0]

  def test_analyze_plate_with_numerical_stimuli(self, analyzer):
    # Test with numerical stimuli values like 4990.67
    numerical_data = pd.DataFrame({
      'Layout-Donor': ['D001'] * 8,
      'Plate': ['plate_1'] * 8,
      'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 4990.67, 4990.67, 4990.67, 4990.67],
      'Spot Forming Units (SFU)': [10, 12, 11, 9, 45, 50, 48, 52],
      'Analyte Secreting Population': ['LED490 Total'] * 8
    })
    
    result_df = analyzer._analyze_plate('D001', 'IFNg', numerical_data)
    
    assert not result_df.empty
    # Should have both control and numerical stimulus entries
    stimuli_in_results = set(result_df['Stimulus'].values)
    assert 'DMSO' in stimuli_in_results
    assert '4990.67' in stimuli_in_results  # Numerical stimulus should be converted to string

  def test_breakout_donor_dfs_with_multiple_donors(self):
    # Test splitting data with multiple donors
    multi_donor_data = pd.DataFrame({
      'Layout-Donor': ['DONOR_A'] * 4 + ['DONOR_B'] * 4,
      'Plate': ['plate_1'] * 8,
      'Layout-Stimuli': ['DMSO', 'DMSO', 'PHA', 'PHA'] * 2,
      'Spot Forming Units (SFU)': [10, 12, 50, 55, 15, 18, 75, 80],
      'Analyte Secreting Population': ['LED490 Total'] * 8
    })
    
    donor_data = DataLoader._breakout_donor_dfs(multi_donor_data)
    
    assert len(donor_data) == 2
    donors = [donor_id for donor_id, _ in donor_data]
    assert 'DONOR_A' in donors
    assert 'DONOR_B' in donors
    
    # Check that each donor has their correct data
    for donor_id, donor_df in donor_data:
      assert all(donor_df['Layout-Donor'] == donor_id)
      assert len(donor_df) == 4  # Each donor should have 4 rows


class TestIntegration:
  def test_full_analysis_pipeline(self):
    # Create test data
    test_data = pd.DataFrame({
      'Layout-Donor': ['D001'] * 8,
      'Plate': ['plate_1'] * 8,
      'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
      'Spot Forming Units (SFU)': [5, 8, 10, 12, 40, 45, 50, 55],
      'Analyte Secreting Population': ['LED490 Total'] * 4 + ['LED550 Total'] * 4
    })
    
    config = AnalysisConfig(
      cells_per_well=200000,
      sfc_cutoff=20,
      control_stim="DMSO",
      cytokines={"IFNg": "LED490", "IL-10": "LED550"},
      plates={"plate_1": "S. pneumoniae"}
    )
    
    analyzer = FluoroSpotAnalyzer(config)
    donor_data = [('D001', test_data)]
    
    results = analyzer.analyze_donor_data(donor_data)
    
    assert not results.empty
    # Should have results for both cytokines, but actual count depends on analysis logic
    assert len(results) >= 2  # At least some results for both cytokines
    assert 'IFNg' in results['Cytokine'].values
    assert 'IL-10' in results['Cytokine'].values
    # Check that we have both control and stimulus entries
    unique_stimuli = set(results['Stimulus'].values)
    assert any('DMSO' in stimulus for stimulus in unique_stimuli)
    assert 'PHA' in unique_stimuli


def multiplex_donor_data():
  """Three channels with Totals, exact doubles and the exact triple."""
  populations = [
    'LED490 Total', 'LED550 Total', 'LED640 Total',
    'LED490+LED550', 'LED490+LED550+LED640',
  ]
  stimuli = ['DMSO'] * 3 + ['PHA'] * 3
  counts = {
    'LED490 Total': [10, 12, 11, 60, 65, 62],
    'LED550 Total': [8, 9, 7, 40, 44, 42],
    'LED640 Total': [3, 4, 2, 6, 5, 7],
    'LED490+LED550': [0, 1, 0, 25, 30, 28],
    'LED490+LED550+LED640': [0, 0, 0, 0, 0, 0],
  }
  frames = []
  for population in populations:
    frames.append(pd.DataFrame({
      'Layout-Donor': ['D001'] * 6,
      'Plate': ['plate_1'] * 6,
      'Layout-Stimuli': stimuli,
      'Spot Forming Units (SFU)': counts[population],
      'Analyte Secreting Population': [population] * 6,
    }))
  return pd.concat(frames, ignore_index=True)


def multiplex_config(populations=None):
  return AnalysisConfig(
    cells_per_well=200000,
    sfc_cutoff=20,
    control_stim='DMSO',
    cytokines={'IFNg': 'LED490', 'IL-10': 'LED550', 'IL-17': 'LED640'},
    plates={'plate_1': 'S. pneumoniae'},
    populations=populations,
  )


class TestPopulationEndpoints:
  def test_default_selection_analyzes_totals_only(self):
    results = FluoroSpotAnalyzer(multiplex_config()).analyze_donor_data(
      [('D001', multiplex_donor_data())]
    )
    assert sorted(results['Population'].unique()) == [
      'LED490 Total', 'LED550 Total', 'LED640 Total'
    ]
    assert sorted(results['Cytokine'].unique()) == ['IFNg', 'IL-10', 'IL-17']

  def test_exact_double_and_triple_are_separate_endpoints(self):
    config = multiplex_config(['LED490 Total', 'LED490+LED550', 'LED490+LED550+LED640'])
    results = FluoroSpotAnalyzer(config).analyze_donor_data([('D001', multiplex_donor_data())])

    pha = results[results['Stimulus'] == 'PHA'].set_index('Population')
    assert set(pha.index) == {'LED490 Total', 'LED490+LED550', 'LED490+LED550+LED640'}
    assert pha.loc['LED490+LED550', 'Cytokine'] == 'IFNg + IL-10 only'
    assert pha.loc['LED490+LED550', 'Population Scope'] == 'Exact double-secretors'
    assert pha.loc['LED490+LED550+LED640', 'Cytokine'] == 'IFNg + IL-10 + IL-17 only'

    # Each endpoint uses only its own population rows - no summing, no double counting
    assert pha.loc['LED490 Total', 'Average'] == pytest.approx((60 + 65 + 62) / 3)
    assert pha.loc['LED490+LED550', 'Average'] == pytest.approx((25 + 30 + 28) / 3)

    # The measured all-zero triple is reported as a real negative, not skipped
    assert pha.loc['LED490+LED550+LED640', 'Evaluable'] == True
    assert pha.loc['LED490+LED550+LED640', 'Positive Response'] == False
    assert pha.loc['LED490+LED550', 'Positive Response'] == True

  def test_selection_alone_is_not_positivity(self):
    config = multiplex_config(['LED640 Total'])
    results = FluoroSpotAnalyzer(config).analyze_donor_data([('D001', multiplex_donor_data())])
    pha = results[results['Stimulus'] == 'PHA'].iloc[0]
    # Selected and present, but the criterion is not met
    assert pha['Population'] == 'LED640 Total'
    assert pha['Positive Response'] == False

  def test_unavailable_population_is_reported_not_scored(self):
    config = multiplex_config(['LED490 Total', 'LED550+LED640'])
    analyzer = FluoroSpotAnalyzer(config)
    results = analyzer.analyze_donor_data([('D001', multiplex_donor_data())])

    assert set(results['Population'].unique()) == {'LED490 Total'}
    assert len(analyzer.population_problems) == 1
    assert 'LED550+LED640' in analyzer.population_problems[0]

  def test_missing_counts_are_not_negatives(self):
    data = multiplex_donor_data()
    missing = (data['Analyte Secreting Population'] == 'LED490+LED550') & (data['Layout-Stimuli'] == 'PHA')
    data.loc[missing, 'Spot Forming Units (SFU)'] = np.nan

    config = multiplex_config(['LED490+LED550'])
    results = FluoroSpotAnalyzer(config).analyze_donor_data([('D001', data)])
    pha = results[results['Stimulus'] == 'PHA'].iloc[0]

    assert pha['Measured Replicates'] == 0
    assert pha['Missing SFU Values'] == 3
    assert pha['Evaluable'] == False
    assert pd.isna(pha['Positive Response'])
    assert 'missing' in pha['Not Evaluable Reason']

  def test_partial_missing_counts_are_excluded_from_statistics(self):
    data = multiplex_donor_data()
    target = (data['Analyte Secreting Population'] == 'LED490 Total') & (data['Layout-Stimuli'] == 'PHA')
    indexes = data[target].index
    data.loc[indexes[0], 'Spot Forming Units (SFU)'] = np.nan

    results = FluoroSpotAnalyzer(multiplex_config(['LED490 Total'])).analyze_donor_data([('D001', data)])
    pha = results[results['Stimulus'] == 'PHA'].iloc[0]

    assert pha['Measured Replicates'] == 2
    assert pha['Missing SFU Values'] == 1
    assert pha['Evaluable'] == True
    assert pha['SI'] == pytest.approx(((65 + 62) / 2) / 11.0)

  def test_control_matching_is_literal_not_regex(self):
    data = multiplex_donor_data()
    data['Layout-Stimuli'] = data['Layout-Stimuli'].replace({'DMSO': 'DMSO(1)'})

    literal = multiplex_config(['LED490 Total'])
    literal.control_stim = 'DMSO(1)'
    results = FluoroSpotAnalyzer(literal).analyze_donor_data([('D001', data)])
    pha = results[results['Stimulus'] == 'PHA'].iloc[0]
    assert pha['Control Measured Replicates'] == 3
    assert pha['Evaluable'] == True

    # A regex-looking control name must not match a different stimulus name
    regexish = multiplex_config(['LED490 Total'])
    regexish.control_stim = 'D.SO(1)'
    results = FluoroSpotAnalyzer(regexish).analyze_donor_data([('D001', data)])
    scored = results[results['Stimulus'] == 'PHA'].iloc[0]
    assert scored['Control Measured Replicates'] == 0
    assert scored['Evaluable'] == False

if __name__ == '__main__':
  pytest.main([__file__])