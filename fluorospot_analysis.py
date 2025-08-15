import argparse
import yaml
import numpy as np
import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from scipy import stats
from scipy.stats import poisson, levene
from typing import List, Dict, Tuple, Optional

import warnings
warnings.filterwarnings('ignore')

@dataclass
class AnalysisConfig:
  """Configuration for FluoroSpot analysis."""
  cells_per_well: int
  sfc_cutoff: int
  control_stim: str
  cytokines: Dict[str, str]
  plates: Dict[str, str]
  experimental_conditions: Optional[Dict] = None

@dataclass
class AnalysisResult:
  """Container for statistical analysis results."""
  t_test_p: float
  si: float
  poisson_p_values: List[float]
  sfc_value: float

class FluoroSpotAnalyzer:
  """Main class for handling FluoroSpot data analysis."""
  def __init__(self, config: AnalysisConfig):
    self.config = config

  def analyze_donor_data(self, donor_data: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Analyze data for all donors."""
    all_results = []
    for donor_id, donor_df in donor_data:
      print(f'Analyzing data for donor: {donor_id}')
      donor_results = self._analyze_single_donor(donor_id, donor_df)
      all_results.append(donor_results)
    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

  def _analyze_single_donor(self, donor_id: str, donor_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze data for a single donor."""
    results = []
    for cytokine, led in self.config.cytokines.items():
      led_df = donor_df[donor_df['Analyte Secreting Population'] == f'{led} Total']
      plate_groups = led_df.groupby('Plate')
      for _, plate_df in plate_groups:
        plate_results = self._analyze_plate(donor_id, cytokine, plate_df)
        results.append(plate_results)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

  def _analyze_plate(self, donor_id: str, cytokine: str, plate_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze data for a single plate, supporting both simple and experimental conditions layouts."""
    results = []
    plate_name = plate_df['Plate'].iloc[0]

    plate_conditions = None
    if self.config.experimental_conditions:  # check that the plate number is specified in the data first
      plate_conditions = self.config.experimental_conditions.get(plate_name)
      if not plate_conditions:
        print(f"  - WARNING: Plate '{plate_name}' not found under 'experimental_conditions' in config.yaml. "
              f"Falling back to simple analysis mode for this plate.")

    if plate_conditions:
      for group_name, group_config in plate_conditions.items():
        control_stim_name = group_config['control']
        stimuli_names = group_config['stimuli']
        
        control_values = plate_df[plate_df['Layout-Stimuli'] == control_stim_name]['Spot Forming Units (SFU)'].values
        if len(control_values) == 0:
          print(f"  - WARNING: Control '{control_stim_name}' for group '{group_name}' not found on plate '{plate_name}'. Skipping group.")
          continue
        
        control_row = pd.DataFrame({
          'Donor ID': [donor_id], 'Plate': [plate_name], 'Experimental Condition': [group_name],
          'Species': [self.config.plates.get(plate_name, '')], 'Cytokine': [cytokine],
          'Stimulus': [control_stim_name], 'SFU Values': [control_values],
          'Average': control_values.mean(), 'STD': control_values.std()
        })
        results.append(control_row)

        for stimulus in stimuli_names:
          stim_values = plate_df[plate_df['Layout-Stimuli'] == stimulus]['Spot Forming Units (SFU)'].values
          if len(stim_values) == 0:
            print(f"  - WARNING: Stimulus '{stimulus}' for group '{group_name}' not found on plate '{plate_name}'. Skipping stimulus.")
            continue
          
          stats_result = self._calculate_statistics(control_values, stim_values)
          result_row = self._create_result_row(
              donor_id, cytokine, stimulus, stim_values, stats_result, plate_df, group_name
          )
          results.append(result_row)
    else:
      # --- "Simple" Mode (Fallback) ---
      stimuli = plate_df['Layout-Stimuli'].unique()
      control_stim = self.config.control_stim
      control_values = plate_df[plate_df['Layout-Stimuli'].str.contains(control_stim, na=False)]['Spot Forming Units (SFU)'].values
      
      control_row = pd.DataFrame({
        'Donor ID': [donor_id], 'Plate': [plate_name], 'Experimental Condition': ['default'],
        'Species': [self.config.plates.get(plate_name, '')], 'Cytokine': [cytokine],
        'Stimulus': [control_stim], 'SFU Values': [control_values],
        'Average': control_values.mean(), 'STD': control_values.std()
      })
      results.append(control_row)

      for stimulus in stimuli:
        if pd.isna(stimulus):
          continue
        stimulus_str = str(stimulus)
        if control_stim in stimulus_str:
          continue
        stim_values = plate_df[plate_df['Layout-Stimuli'] == stimulus]['Spot Forming Units (SFU)'].values
        stats_result = self._calculate_statistics(control_values, stim_values)
        result_row = self._create_result_row(
          donor_id, cytokine, stimulus_str, stim_values, stats_result, plate_df, 'default'
        )
        results.append(result_row)
        
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

  def _calculate_statistics(self, control_values: np.ndarray, stim_values: np.ndarray) -> AnalysisResult:
    """Calculate statistical measures for stimulus vs control."""
    if len(control_values) == 0 or len(stim_values) == 0:
      return AnalysisResult(1.0, 0.0, [1.0] * len(stim_values), 0.0)
    
    control_values = control_values[~np.isnan(control_values)]
    stim_values = stim_values[~np.isnan(stim_values)]
    control_avg = max(control_values.mean(), 1)
    
    sfc_norm = (stim_values.mean() - control_avg) * (1000000 / self.config.cells_per_well)
    sfc_value = max(sfc_norm, 0)
    
    lambda_poisson = max(control_avg, 2)
    poisson_p_values = [1 - poisson.cdf(value - 1, lambda_poisson) for value in stim_values]
    
    t_test_p = 1.0 # Default p-value
    try:
      if np.all(control_values == control_values[0]) and np.all(stim_values == stim_values[0]):
        t_test_p = 1.0 if stim_values[0] <= control_values[0] else 0.0
      else:
        equal_var = levene(control_values, stim_values).pvalue > 0.05
        _, t_test_p = stats.ttest_ind(
          control_values, stim_values,
          equal_var=equal_var,
          alternative='less',
          nan_policy='omit'
        )
        if np.isnan(t_test_p):
          t_test_p = 1.0
    except (ValueError, IndexError):
      t_test_p = 1.0 # Handle cases with insufficient data for t-test
      
    si = stim_values.mean() / control_avg if control_avg > 0 else 0.0
    return AnalysisResult(t_test_p, si, poisson_p_values, sfc_value)
    
  def _create_result_row(
    self,
    donor_id: str,
    cytokine: str,
    stimulus: str,
    stim_values: np.ndarray,
    stats: AnalysisResult,
    plate_df: pd.DataFrame,
    group_name: str
  ) -> pd.DataFrame:
    """Create a DataFrame row with analysis results."""
    plate_name = plate_df['Plate'].iloc[0]
    row_data = {
      'Donor ID': [donor_id],
      'Plate': [plate_name],
      'Experimental Condition': [group_name],
      'Species': [self.config.plates.get(plate_name, '')],
      'Cytokine': [cytokine],
      'Stimulus': [stimulus],
      'SFU Values': [stim_values],
      'Average': stim_values.mean(),
      'STD': stim_values.std(),
      't-test p-value': stats.t_test_p,
      'SI': stats.si,
      'SFCs Normalized Per Million Cells': stats.sfc_value,
    }
    for i, p_value in enumerate(stats.poisson_p_values):
      row_data[f'P{i+1}'] = p_value
    row_data['Poisson Average'] = np.mean(stats.poisson_p_values) if stats.poisson_p_values else np.nan
    df = pd.DataFrame(row_data)
    df['Positive Response'] = (
      (df['SFCs Normalized Per Million Cells'] > self.config.sfc_cutoff) &
      (df['SI'] > 2) &
      ((df['t-test p-value'] < 0.05) | (df['Poisson Average'] < 0.05))
    )
    return df

class DataLoader:
  """Handle loading and preprocessing of FluoroSpot data."""
  @staticmethod
  def load_config(config_path: Path) -> AnalysisConfig:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as file:
      config_data = yaml.safe_load(file)
    return AnalysisConfig(**config_data)

  @staticmethod
  def load_donor_data(
    all_raw_data: Optional[Path] = None,
    donor_dir: Optional[Path] = None
  ) -> List[Tuple[str, pd.DataFrame]]:
    """Load donor data from either a single file or directory."""
    if all_raw_data:
      all_raw_data_df = pd.read_excel(all_raw_data, sheet_name=1, engine='openpyxl')
      return DataLoader._breakout_donor_dfs(all_raw_data_df)
    elif donor_dir:
      return DataLoader._read_donor_files(donor_dir)
    else:
        raise ValueError("Either all_raw_data or donor_dir must be provided")

  @staticmethod
  def _breakout_donor_dfs(all_raw_data_df: pd.DataFrame) -> List[Tuple[str, pd.DataFrame]]:
    """Split combined DataFrame into separate DataFrames per donor."""
    return [(donor, df) for donor, df in all_raw_data_df.groupby('Layout-Donor')]

  @staticmethod
  def _read_donor_files(donor_dir: Path) -> List[Tuple[str, pd.DataFrame]]:
    """Read individual donor files from directory."""
    donor_data = []
    for file in donor_dir.iterdir():
      if file.name.startswith('~') or not (file.suffix in ['.xlsx', '.xls']): # skip temp files
        continue
      df = pd.read_excel(file, sheet_name=1, engine='openpyxl')
      
      unique_donors = df['Layout-Donor'].dropna().unique()
      if len(unique_donors) == 1:
        donor_data.append((unique_donors[0], df))
      else:
        # Multiple donors in one file - split them
        print(f"  - Found {len(unique_donors)} donors in file {file.name}: {list(unique_donors)}")
        for donor_id in unique_donors:
          donor_df = df[df['Layout-Donor'] == donor_id]
          donor_data.append((donor_id, donor_df))
    return donor_data

def main():
  parser = argparse.ArgumentParser(description='FluoroSpot Analysis Tool')
  parser.add_argument('-a', '--all_raw_data', type=Path, help='Combined raw donor data file.')
  parser.add_argument('-d', '--donor_dir', type=Path, help='Directory containing separate raw donor data files.')
  parser.add_argument('-r', '--results_dir', type=Path, required=True, help='Directory for storing analysis results.')
  parser.add_argument('-c', '--config', type=Path, default=Path(__file__).parent / 'config.yaml', help='Path to configuration file.')
  
  args = parser.parse_args()

  if not (args.all_raw_data or args.donor_dir):
    parser.error("Either --all_raw_data or --donor_dir must be specified")
  if args.all_raw_data and args.donor_dir:
    parser.error('Cannot specify both --all_raw_data and --donor_dir')

  args.results_dir.mkdir(exist_ok=True)
  
  config = DataLoader.load_config(args.config)
  donor_data = DataLoader.load_donor_data(args.all_raw_data, args.donor_dir)
  analyzer = FluoroSpotAnalyzer(config)
  results = analyzer.analyze_donor_data(donor_data)
  
  if not results.empty:
    results.to_excel(args.results_dir / 'fluorospot-results.xlsx', index=False, engine='openpyxl')
    print(f"\nAnalysis complete. Results saved to {args.results_dir / 'fluorospot-results.xlsx'}")
  else:
    print("\nAnalysis finished, but no results were generated. Please check your data and config files.")

if __name__ == "__main__":
  main()
