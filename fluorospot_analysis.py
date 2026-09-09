import argparse
import yaml
import numpy as np
import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from scipy import stats
from scipy.stats import poisson, levene
from typing import List, Dict, Tuple, Optional

from populations import (
  Endpoint,
  POPULATION_COLUMN,
  SCOPE_TOTAL,
  channel_names_from_cytokines,
  discover_populations,
  friendly_label,
  resolve_endpoints,
)

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
  populations: Optional[List[str]] = None

@dataclass
class AnalysisResult:
  """Container for statistical analysis results."""
  t_test_p: float
  si: float
  poisson_p_values: List[float]
  sfc_value: float
  replicates: int = 0
  missing_replicates: int = 0
  control_replicates: int = 0
  control_missing: int = 0
  evaluable: bool = True
  not_evaluable_reason: str = ''

class FluoroSpotAnalyzer:
  """Main class for handling FluoroSpot data analysis."""
  def __init__(self, config: AnalysisConfig):
    self.config = config
    self.population_problems: List[str] = []

  def analyze_donor_data(self, donor_data: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Analyze data for all donors."""
    all_results = []
    for donor_id, donor_df in donor_data:
      print(f'Analyzing data for donor: {donor_id}')
      donor_results = self._analyze_single_donor(donor_id, donor_df)
      all_results.append(donor_results)
    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

  def endpoints_for(self, donor_df: pd.DataFrame) -> List[Endpoint]:
    """Resolve the configured populations against what this data actually exports."""
    available = None
    if POPULATION_COLUMN in donor_df.columns:
      available = [str(label) for label in donor_df[POPULATION_COLUMN].dropna().unique()]
    endpoints, problems = resolve_endpoints(
      self.config.cytokines, self.config.populations, available
    )
    for problem in problems:
      if problem not in self.population_problems:
        self.population_problems.append(problem)
      print(f'  - WARNING: {problem}')
    return endpoints

  def _coerce_endpoint(self, endpoint) -> Endpoint:
    """Accept an Endpoint or a bare cytokine name (legacy call signature)."""
    if isinstance(endpoint, Endpoint):
      return endpoint
    name = str(endpoint)
    led = (self.config.cytokines or {}).get(name)
    if led:
      return Endpoint(name=name, label=f'{str(led).strip()} Total', scope=SCOPE_TOTAL)
    return Endpoint(name=name)

  def _analyze_single_donor(self, donor_id: str, donor_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze data for a single donor, one endpoint per selected population."""
    results = []
    for endpoint in self.endpoints_for(donor_df):
      population_df = donor_df[donor_df[POPULATION_COLUMN].astype(str) == endpoint.label]
      plate_groups = population_df.groupby('Plate')
      for _, plate_df in plate_groups:
        plate_results = self._analyze_plate(donor_id, endpoint, plate_df)
        results.append(plate_results)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

  def _analyze_plate(self, donor_id: str, endpoint, plate_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze one plate for one population endpoint (simple or conditions layout)."""
    results = []
    endpoint = self._coerce_endpoint(endpoint)
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

        results.append(self._create_control_row(
          donor_id, endpoint, plate_name, group_name, control_stim_name, control_values
        ))

        for stimulus in stimuli_names:
          stim_values = plate_df[plate_df['Layout-Stimuli'] == stimulus]['Spot Forming Units (SFU)'].values
          if len(stim_values) == 0:
            print(f"  - WARNING: Stimulus '{stimulus}' for group '{group_name}' not found on plate '{plate_name}'. Skipping stimulus.")
            continue

          stats_result = self._calculate_statistics(control_values, stim_values)
          result_row = self._create_result_row(
              donor_id, endpoint, stimulus, stim_values, stats_result, plate_df, group_name
          )
          results.append(result_row)
    else:
      # --- "Simple" Mode (Fallback) ---
      stimuli = plate_df['Layout-Stimuli'].unique()
      control_stim = self.config.control_stim
      stimuli_text = plate_df['Layout-Stimuli'].astype(str)
      control_mask = stimuli_text.str.contains(control_stim, na=False, regex=False)
      control_values = plate_df[control_mask]['Spot Forming Units (SFU)'].values

      results.append(self._create_control_row(
        donor_id, endpoint, plate_name, 'default', control_stim, control_values
      ))

      for stimulus in stimuli:
        if pd.isna(stimulus):
          continue
        stimulus_str = str(stimulus)
        if control_stim in stimulus_str:
          continue
        stim_values = plate_df[plate_df['Layout-Stimuli'] == stimulus]['Spot Forming Units (SFU)'].values
        stats_result = self._calculate_statistics(control_values, stim_values)
        result_row = self._create_result_row(
          donor_id, endpoint, stimulus_str, stim_values, stats_result, plate_df, 'default'
        )
        results.append(result_row)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()

  def _create_control_row(
    self,
    donor_id: str,
    endpoint: Endpoint,
    plate_name: str,
    group_name: str,
    control_stim_name: str,
    control_values: np.ndarray
  ) -> pd.DataFrame:
    """Create the reference row describing the control replicates of one endpoint."""
    numeric = pd.to_numeric(pd.Series(control_values), errors='coerce').values
    measured = int(np.count_nonzero(~np.isnan(numeric)))
    return pd.DataFrame({
      'Donor ID': [donor_id], 'Plate': [plate_name], 'Experimental Condition': [group_name],
      'Species': [self.config.plates.get(plate_name, '')], 'Cytokine': [endpoint.name],
      'Population': [endpoint.label or ''], 'Population Scope': [endpoint.scope_description],
      'Stimulus': [control_stim_name], 'SFU Values': [control_values],
      'Average': control_values.mean() if len(control_values) else np.nan,
      'STD': control_values.std() if len(control_values) else np.nan,
      'Measured Replicates': [measured],
      'Missing SFU Values': [int(len(numeric) - measured)],
    })

  def _calculate_statistics(self, control_values: np.ndarray, stim_values: np.ndarray) -> AnalysisResult:
    """Calculate statistical measures for stimulus vs control.

    Missing (NaN) counts are excluded from the statistics and reported; a group
    with no measured replicate is not evaluable rather than a negative result.
    """
    control_all = pd.to_numeric(pd.Series(control_values, dtype='object'), errors='coerce').values.astype(float)
    stim_all = pd.to_numeric(pd.Series(stim_values, dtype='object'), errors='coerce').values.astype(float)

    control_measured = control_all[~np.isnan(control_all)]
    stim_measured = stim_all[~np.isnan(stim_all)]

    counts = dict(
      replicates=int(len(stim_measured)),
      missing_replicates=int(len(stim_all) - len(stim_measured)),
      control_replicates=int(len(control_measured)),
      control_missing=int(len(control_all) - len(control_measured)),
    )

    if len(control_measured) == 0 or len(stim_measured) == 0:
      if len(control_all) == 0 or len(stim_all) == 0:
        reason = 'No replicate rows found for this population/stimulus'
      elif len(stim_measured) == 0:
        reason = 'All stimulus SFU counts are missing (not measured, not zero)'
      else:
        reason = 'All control SFU counts are missing (not measured, not zero)'
      return AnalysisResult(
        1.0, 0.0, [1.0] * len(stim_measured), 0.0,
        evaluable=False, not_evaluable_reason=reason, **counts
      )

    control_values = control_measured
    stim_values = stim_measured
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
    return AnalysisResult(t_test_p, si, poisson_p_values, sfc_value, **counts)
    
  def _create_result_row(
    self,
    donor_id: str,
    endpoint,
    stimulus: str,
    stim_values: np.ndarray,
    stats: AnalysisResult,
    plate_df: pd.DataFrame,
    group_name: str
  ) -> pd.DataFrame:
    """Create a DataFrame row with analysis results for one endpoint/stimulus."""
    endpoint = self._coerce_endpoint(endpoint)
    plate_name = plate_df['Plate'].iloc[0]
    row_data = {
      'Donor ID': [donor_id],
      'Plate': [plate_name],
      'Experimental Condition': [group_name],
      'Species': [self.config.plates.get(plate_name, '')],
      'Cytokine': [endpoint.name],
      'Population': [endpoint.label or ''],
      'Population Scope': [endpoint.scope_description],
      'Stimulus': [stimulus],
      'SFU Values': [stim_values],
      'Average': stim_values.mean(),
      'STD': stim_values.std(),
      'Measured Replicates': [stats.replicates],
      'Missing SFU Values': [stats.missing_replicates],
      'Control Measured Replicates': [stats.control_replicates],
      'Control Missing SFU Values': [stats.control_missing],
      't-test p-value': stats.t_test_p,
      'SI': stats.si,
      'SFCs Normalized Per Million Cells': stats.sfc_value,
    }
    for i, p_value in enumerate(stats.poisson_p_values):
      row_data[f'P{i+1}'] = p_value
    row_data['Poisson Average'] = np.mean(stats.poisson_p_values) if stats.poisson_p_values else np.nan
    df = pd.DataFrame(row_data)
    df['Criterion'] = (
      f'SFC/million >= {self.config.sfc_cutoff} AND SI > 2 AND '
      '(one-sided t-test p < 0.05 OR mean Poisson p < 0.05)'
    )
    df['Evaluable'] = stats.evaluable
    df['Not Evaluable Reason'] = stats.not_evaluable_reason
    positive = (
      (df['SFCs Normalized Per Million Cells'] >= self.config.sfc_cutoff) &
      (df['SI'] > 2) &
      ((df['t-test p-value'] < 0.05) | (df['Poisson Average'] < 0.05))
    )
    # object dtype so that a not-evaluable endpoint stays blank instead of False
    df['Positive Response'] = positive.astype(object) if stats.evaluable else None
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
  parser.add_argument('-r', '--results_dir', type=Path, help='Directory for storing analysis results.')
  parser.add_argument('-c', '--config', type=Path, default=Path(__file__).parent / 'config.yaml', help='Path to configuration file.')
  parser.add_argument('-l', '--list_populations', action='store_true',
                      help='List the populations actually exported by the input data and exit.')

  args = parser.parse_args()

  if not (args.all_raw_data or args.donor_dir):
    parser.error("Either --all_raw_data or --donor_dir must be specified")
  if args.all_raw_data and args.donor_dir:
    parser.error('Cannot specify both --all_raw_data and --donor_dir')
  if not (args.results_dir or args.list_populations):
    parser.error('--results_dir is required unless --list_populations is used')

  config = DataLoader.load_config(args.config)
  donor_data = DataLoader.load_donor_data(args.all_raw_data, args.donor_dir)

  if args.list_populations:
    channel_names = channel_names_from_cytokines(config.cytokines)
    for donor_id, donor_df in donor_data:
      inventory = discover_populations(donor_df)
      print(f'\nDonor {donor_id}: {len(inventory.populations)} exported population(s)')
      if not inventory.has_analyte_metadata:
        print('  NOTE: the export carries no channel-to-cytokine metadata; '
              'friendly names come from your configured cytokine mapping only.')
      for info in inventory.populations:
        name = friendly_label(info.spec, channel_names)
        print(f'  {info.label:<24} {info.spec.scope_description:<28} {name:<32} {info.availability}')
    return

  args.results_dir.mkdir(exist_ok=True)
  analyzer = FluoroSpotAnalyzer(config)
  results = analyzer.analyze_donor_data(donor_data)

  if not results.empty:
    results.to_excel(args.results_dir / 'fluorospot-results.xlsx', index=False, engine='openpyxl')
    print(f"\nAnalysis complete. Results saved to {args.results_dir / 'fluorospot-results.xlsx'}")
    populations = [str(label) for label in results['Population'].dropna().unique() if str(label)]
    if populations:
      print(f"Populations analyzed as separate endpoints: {', '.join(populations)}")
    for problem in analyzer.population_problems:
      print(f'WARNING: {problem}')
  else:
    print("\nAnalysis finished, but no results were generated. Please check your data and config files.")

if __name__ == "__main__":
  main()
