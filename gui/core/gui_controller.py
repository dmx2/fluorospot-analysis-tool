"""Main GUI controller for handling analysis operations."""

import sys
import threading
import queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
import traceback

import pandas as pd

from fluorospot_analysis import FluoroSpotAnalyzer, DataLoader
from populations import (
  MULTI_SCOPES,
  PopulationInventory,
  discover_populations,
  merge_inventories,
)
from gui.validation.data_validator import DataValidator
from gui.validation.config_validator import ConfigValidator
from gui.core.config_builder import ConfigBuilder


@dataclass
class ValidationOutcome:
  """Result of one validation pass.

  `blocking` holds the problems that genuinely prevent the analysis from
  producing results, each already phrased as an instruction the user can follow.
  """
  messages: List[str] = field(default_factory=list)
  blocking: List[str] = field(default_factory=list)
  has_warnings: bool = False

  @property
  def has_critical_errors(self) -> bool:
    return bool(self.blocking)


@dataclass
class InputSummary:
  """What the selected file/directory actually contains."""
  files: List[Path] = field(default_factory=list)
  inventory: Optional[PopulationInventory] = None
  data_summary: Dict[str, Any] = field(default_factory=dict)
  messages: List[str] = field(default_factory=list)
  blocking: List[str] = field(default_factory=list)


class GUIController:
  """Main controller for GUI operations and analysis integration."""
  
  def __init__(self):
    self.data_validator = DataValidator()
    self.config_validator = ConfigValidator()
    self.config_builder = ConfigBuilder()
    self.current_analysis_thread = None
    self.cancel_requested = False
    self._input_cache = {}

  def excel_files(self, file_path: str, is_directory: bool) -> List[Path]:
    """Every export the analysis will read, in a deterministic order."""
    path = Path(file_path)
    if not is_directory:
      return [path]
    files = sorted(set(path.glob('*.xlsx')) | set(path.glob('*.xls')))
    return [f for f in files if not f.name.startswith('~')]

  def read_input(self, file_path: str, is_directory: bool) -> InputSummary:
    """Inspect every selected export once and summarize all of them together.

    Population discovery and configuration validation must agree, so both use
    this union of the whole selection instead of one arbitrary sample file.
    """
    files = self.excel_files(file_path, is_directory)
    fingerprint = (str(file_path), is_directory, tuple(
      (str(f), f.stat().st_mtime_ns, f.stat().st_size) if f.exists() else (str(f), 0, 0)
      for f in files
    ))
    cached = self._input_cache.get(fingerprint)
    if cached is not None:
      return cached

    summary = InputSummary(files=files)
    if not files:
      summary.blocking.append(
        f'No Excel exports found in {file_path}. Choose a folder containing the .xlsx '
        f'exports, or switch to "Single file".'
      )
      summary.messages.append(f'❌ {summary.blocking[-1]}')
      self._input_cache[fingerprint] = summary
      return summary

    inventories = []
    per_file_summaries = []
    for excel_file in files:
      try:
        df = pd.read_excel(excel_file, sheet_name=1, engine='openpyxl')
      except Exception as error:
        summary.messages.append(f'⚠️ Could not inspect {excel_file.name}: {error}')
        continue
      inventories.append(discover_populations(df))
      per_file_summaries.append(self.data_validator.get_data_summary(df))

    if not per_file_summaries:
      summary.blocking.append(
        'None of the selected export(s) could be read. Re-export the plate database from '
        'Mabtech Apex and select it again.'
      )
      summary.messages.append(f'❌ {summary.blocking[-1]}')
      self._input_cache[fingerprint] = summary
      return summary

    summary.inventory = merge_inventories(inventories)
    summary.data_summary = self.merge_data_summaries(per_file_summaries, summary.inventory)
    self._input_cache[fingerprint] = summary
    return summary

  def merge_data_summaries(
    self, summaries: List[Dict[str, Any]], inventory: PopulationInventory
  ) -> Dict[str, Any]:
    """Union of every inspected file, so nothing present is reported as absent."""
    merged: Dict[str, Any] = {
      'total_rows': sum(int(s.get('total_rows', 0)) for s in summaries),
      'files': len(summaries),
    }
    for key in ('donors', 'plates', 'stimuli', 'led_populations'):
      values = []
      for summary in summaries:
        for value in summary.get(key, []):
          if value not in values:
            values.append(value)
      if values:
        merged[key] = values

    if inventory is not None and inventory.populations:
      merged['population_labels'] = inventory.labels
      merged['population_details'] = [
        {
          'label': info.label,
          'scope': info.scope,
          'rows': info.rows,
          'measured': info.measured,
          'missing': info.missing,
        }
        for info in inventory.populations
      ]
    return merged

  def validate_input_path(self, file_path: str, is_directory: bool) -> ValidationOutcome:
    """Validate the input file or directory."""

    try:
      path = Path(file_path)

      if is_directory:
        _, results = self.data_validator.validate_directory(path)
      else:
        _, results = self.data_validator.validate_file(path)

      return ValidationOutcome(
        messages=results,
        blocking=list(self.data_validator.blocking_problems),
        has_warnings=any(result.startswith("⚠️") for result in results),
      )

    except Exception as e:
      problem = (f"The selected input could not be validated ({e}). Select the Mabtech Apex "
                 f"export again.")
      return ValidationOutcome(messages=[f"❌ {problem}"], blocking=[problem])

  def validate_configuration(self, config: Dict[str, Any], file_path: str,
                             is_directory: bool) -> ValidationOutcome:
    """Validate the complete configuration including compatibility with data."""

    try:
      all_results = []
      blocking = []

      # First validate the configuration itself
      _, config_results = self.config_validator.validate_configuration(config)
      all_results.extend(config_results)
      blocking.extend(self.config_validator.blocking_problems)

      # Then validate against every selected export
      if file_path:
        summary = self.read_input(file_path, is_directory)
        all_results.extend(summary.messages)
        blocking.extend(summary.blocking)

        if summary.data_summary:
          if len(summary.files) > 1:
            all_results.append(f"📁 Checked the configuration against {len(summary.files)} export(s)")
          _, data_results, data_blocking = self.config_validator.validate_config_for_data(
            config, summary.data_summary
          )
          all_results.extend(data_results)
          blocking.extend(data_blocking)

      return ValidationOutcome(
        messages=all_results,
        blocking=list(dict.fromkeys(blocking)),
        has_warnings=any(result.startswith("⚠️") for result in all_results),
      )

    except Exception as e:
      problem = f"The configuration could not be validated ({e})."
      return ValidationOutcome(messages=[f"❌ {problem}"], blocking=[problem])
  
  def run_analysis(self, config: Dict[str, Any], file_path: str, is_directory: bool, message_queue: queue.Queue):
    """Run the FluoroSpot analysis in a background thread."""
    
    self.cancel_requested = False
    temp_config_file = None
    
    try:
      # Send initial progress
      message_queue.put({'type': 'progress', 'value': 0})
      message_queue.put({'type': 'status', 'content': 'Preparing analysis...', 'level': 'info'})
      
      # Create temporary configuration file
      temp_config_file = self.config_builder.create_temp_config_file(config)
      
      # Build analysis configuration
      analysis_config = self.config_builder.build_analysis_config(config)
      
      message_queue.put({'type': 'progress', 'value': 10})
      message_queue.put({'type': 'status', 'content': 'Loading data...', 'level': 'info'})
      
      # Load donor data
      path = Path(file_path)
      if is_directory:
        donor_data = DataLoader.load_donor_data(donor_dir=path)
      else:
        donor_data = DataLoader.load_donor_data(all_raw_data=path)
      
      if self.cancel_requested:
        message_queue.put({'type': 'status', 'content': 'Analysis cancelled', 'level': 'info'})
        return
      
      message_queue.put({'type': 'progress', 'value': 20})
      message_queue.put({'type': 'status', 'content': f'Loaded data for {len(donor_data)} donor(s)', 'level': 'info'})
      
      # Create analyzer
      analyzer = FluoroSpotAnalyzer(analysis_config)
      
      message_queue.put({'type': 'progress', 'value': 30})
      message_queue.put({'type': 'status', 'content': 'Starting analysis...', 'level': 'info'})
      
      # Run analysis with progress tracking
      results = self.run_analysis_with_progress(analyzer, donor_data, message_queue)
      
      if self.cancel_requested:
        message_queue.put({'type': 'status', 'content': 'Analysis cancelled', 'level': 'info'})
        return
      
      if results.empty:
        message_queue.put({'type': 'error', 'content': 'Analysis completed but no results were generated. Please check your data and configuration.'})
        return
      
      message_queue.put({'type': 'progress', 'value': 90})
      message_queue.put({'type': 'status', 'content': 'Saving results...', 'level': 'info'})
      
      # Save results
      output_path = self.config_builder.get_output_path(config)
      results.to_excel(output_path, index=False, engine='openpyxl')
      
      message_queue.put({'type': 'progress', 'value': 100})
      message_queue.put({'type': 'complete', 'success': True, 'content': str(output_path)})
      
    except Exception as e:
      error_msg = f"Analysis failed: {str(e)}\n\n{traceback.format_exc()}"
      message_queue.put({'type': 'error', 'content': error_msg})
      
    finally:
      # Clean up temporary config file
      if temp_config_file:
        self.config_builder.cleanup_temp_file(temp_config_file)
  
  def run_analysis_with_progress(self, analyzer, donor_data, message_queue) -> Any:
    """Run analysis with progress updates."""
    
    total_donors = len(donor_data)
    all_results = []
    
    for i, (donor_id, donor_df) in enumerate(donor_data):
      if self.cancel_requested:
        break
        
      # Update progress
      progress = 30 + (i / total_donors) * 50  # 30-80% for donor processing
      message_queue.put({'type': 'progress', 'value': progress})
      message_queue.put({'type': 'status', 'content': f'Analyzing donor {i+1}/{total_donors}: {donor_id}', 'level': 'info'})
      
      # Analyze single donor
      try:
        donor_results = analyzer._analyze_single_donor(donor_id, donor_df)
        if not donor_results.empty:
          all_results.append(donor_results)
          message_queue.put({'type': 'status', 'content': f'✅ Completed analysis for donor: {donor_id}', 'level': 'info'})
        else:
          message_queue.put({'type': 'status', 'content': f'⚠️ No results for donor: {donor_id}', 'level': 'warning'})
      except Exception as e:
        message_queue.put({'type': 'status', 'content': f'❌ Error analyzing donor {donor_id}: {str(e)}', 'level': 'error'})
        continue

      for problem in analyzer.population_problems:
        message_queue.put({'type': 'status', 'content': f'⚠️ {problem}', 'level': 'warning'})
      analyzer.population_problems.clear()
    
    # Combine all results
    import pandas as pd
    if all_results:
      final_results = pd.concat(all_results, ignore_index=True)
      message_queue.put({'type': 'progress', 'value': 85})
      message_queue.put({'type': 'status', 'content': f'Analysis complete. Generated {len(final_results)} result rows.', 'level': 'info'})
      populations = [str(label) for label in final_results['Population'].dropna().unique() if str(label)]
      if populations:
        message_queue.put({'type': 'status',
                           'content': f'Endpoints analyzed separately: {", ".join(populations)}',
                           'level': 'info'})
      not_evaluable = int((final_results.get('Evaluable') == False).sum()) if 'Evaluable' in final_results else 0
      if not_evaluable:
        message_queue.put({'type': 'status',
                           'content': f'⚠️ {not_evaluable} endpoint result(s) were not evaluable '
                                      '(missing counts are reported, not treated as negatives)',
                           'level': 'warning'})
      return final_results
    else:
      return pd.DataFrame()
  
  def cancel_analysis(self):
    """Cancel the currently running analysis."""
    self.cancel_requested = True
  
  def get_data_summary(self, file_path: str, is_directory: bool) -> Optional[Dict[str, Any]]:
    """Get a summary of the whole selection for display purposes."""

    try:
      summary = self.read_input(file_path, is_directory)
      return summary.data_summary or None

    except Exception as e:
      print(f"Error getting data summary: {str(e)}")
      return None
  
  def suggest_configuration_from_data(self, file_path: str, is_directory: bool) -> Optional[Dict[str, Any]]:
    """Suggest configuration values based on the data content."""
    
    data_summary = self.get_data_summary(file_path, is_directory)
    
    if data_summary:
      return self.config_validator.suggest_configuration_from_data(data_summary)
    
    return None

  def discover_populations(self, file_path: str, is_directory: bool):
    """Discover exported populations across the selected file(s).

    Returns (inventory, messages). Every Excel file in a directory is inspected
    so that populations missing from some files stay visible.
    """
    try:
      summary = self.read_input(file_path, is_directory)
      messages = list(summary.messages)
      inventory = summary.inventory
      if inventory is None or not inventory.populations:
        messages.append('⚠️ No exported populations found in the selected data')
        return inventory, messages

      multi = [info for info in inventory.populations if info.scope in MULTI_SCOPES]
      messages.append(
        f'✅ Discovered {len(inventory.populations)} population(s) across '
        f'{len(summary.files)} file(s); '
        f'{len(multi)} exact double/triple population(s) available'
      )
      if not inventory.has_analyte_metadata:
        messages.append(
          '⚠️ The export carries no channel-to-cytokine metadata; confirm the mapping on the '
          'Populations tab before selecting double/triple endpoints'
        )
      incomplete = [info.label for info in inventory.populations
                    if info.files_present < info.files_total or info.measured == 0]
      if incomplete:
        messages.append(f'⚠️ Populations with incomplete coverage: {", ".join(incomplete)}')
      return inventory, messages

    except Exception as error:
      return None, [f'❌ Population discovery failed: {error}']