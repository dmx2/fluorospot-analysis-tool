"""Main GUI controller for handling analysis operations."""

import sys
import threading
import queue
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

from fluorospot_analysis import FluoroSpotAnalyzer, DataLoader
from gui.validation.data_validator import DataValidator
from gui.validation.config_validator import ConfigValidator
from gui.core.config_builder import ConfigBuilder


class GUIController:
  """Main controller for GUI operations and analysis integration."""
  
  def __init__(self):
    self.data_validator = DataValidator()
    self.config_validator = ConfigValidator()
    self.config_builder = ConfigBuilder()
    self.current_analysis_thread = None
    self.cancel_requested = False
  
  def validate_input_path(self, file_path: str, is_directory: bool) -> tuple[bool, bool, list[str]]:
    """Validate the input file or directory.
    
    Returns:
      tuple: (has_critical_errors, has_warnings, validation_messages)
    """
    
    try:
      path = Path(file_path)
      
      if is_directory:
        valid, results = self.data_validator.validate_directory(path)
      else:
        valid, results = self.data_validator.validate_file(path)
      
      # Analyze results to distinguish critical errors from warnings
      has_critical_errors = False
      has_warnings = False
      
      for result in results:
        if result.startswith("❌"):
          # Check if this is a critical error that should prevent analysis
          critical_errors = [
            "does not exist",
            "Cannot read Excel file",
            "DataFrame is empty",
            "Missing required columns",
            "No valid SFU values found"
          ]
          if any(error in result for error in critical_errors):
            has_critical_errors = True
        elif result.startswith("⚠️"):
          has_warnings = True
      
      return has_critical_errors, has_warnings, results
      
    except Exception as e:
      error_msg = f"Validation error: {str(e)}"
      return True, False, [f"❌ {error_msg}"]
  
  def validate_configuration(self, config: Dict[str, Any], file_path: str, is_directory: bool) -> tuple[bool, bool, list[str]]:
    """Validate the complete configuration including compatibility with data.
    
    Returns:
      tuple: (has_critical_errors, has_warnings, validation_messages)
    """
    
    try:
      all_results = []
      has_critical_errors = False
      has_warnings = False
      
      # First validate the configuration itself
      config_valid, config_results = self.config_validator.validate_configuration(config)
      all_results.extend(config_results)
      
      # Analyze config results
      for result in config_results:
        if result.startswith("❌"):
          # Only some config errors are critical
          critical_config_errors = [
            "Missing cell count",
            "Missing SFC cutoff", 
            "Missing control stimulus",
            "Missing cytokine mappings",
            "Missing plate mappings",
            "Cell count must be positive",
            "SFC cutoff cannot be negative"
          ]
          if any(error in result for error in critical_config_errors):
            has_critical_errors = True
        elif result.startswith("⚠️"):
          has_warnings = True
      
      # Then validate against the data
      if file_path:
        # Load a sample of the data to check compatibility
        path = Path(file_path)
        
        if is_directory:
          # Find first Excel file in directory
          excel_files = list(path.glob("*.xlsx")) + list(path.glob("*.xls"))
          excel_files = [f for f in excel_files if not f.name.startswith('~')]
          
          if excel_files:
            sample_file = excel_files[0]
            all_results.append(f"📁 Using sample file: {sample_file.name}")
          else:
            all_results.append("❌ No Excel files found in directory")
            return True, False, all_results
        else:
          sample_file = path
        
        try:
          # Load sample data
          import pandas as pd
          df = pd.read_excel(sample_file, sheet_name=1, engine='openpyxl')
          
          # Get data summary
          data_summary = self.data_validator.get_data_summary(df)
          
          # Validate config against data
          data_compat_valid, data_results = self.config_validator.validate_config_for_data(config, data_summary)
          all_results.extend(data_results)
          
          # Most data compatibility issues are warnings, not critical errors
          for result in data_results:
            if result.startswith("⚠️"):
              has_warnings = True
            elif result.startswith("❌"):
              # Only complete mismatches are critical
              if "No matching plates" in result or "Control stimulus" in result and "not found in data" in result:
                has_critical_errors = True
          
        except Exception as e:
          error_msg = f"Error validating against data: {str(e)}"
          all_results.append(f"⚠️ {error_msg}")
          has_warnings = True
      
      return has_critical_errors, has_warnings, all_results
      
    except Exception as e:
      error_msg = f"Configuration validation error: {str(e)}"
      return True, False, [f"❌ {error_msg}"]
  
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
    
    # Combine all results
    import pandas as pd
    if all_results:
      final_results = pd.concat(all_results, ignore_index=True)
      message_queue.put({'type': 'progress', 'value': 85})
      message_queue.put({'type': 'status', 'content': f'Analysis complete. Generated {len(final_results)} result rows.', 'level': 'info'})
      return final_results
    else:
      return pd.DataFrame()
  
  def cancel_analysis(self):
    """Cancel the currently running analysis."""
    self.cancel_requested = True
  
  def get_data_summary(self, file_path: str, is_directory: bool) -> Optional[Dict[str, Any]]:
    """Get a summary of the data for display purposes."""
    
    try:
      path = Path(file_path)
      
      if is_directory:
        # Find first Excel file in directory
        excel_files = list(path.glob("*.xlsx")) + list(path.glob("*.xls"))
        excel_files = [f for f in excel_files if not f.name.startswith('~')]
        
        if not excel_files:
          return None
        
        sample_file = excel_files[0]
      else:
        sample_file = path
      
      # Load sample data
      import pandas as pd
      df = pd.read_excel(sample_file, sheet_name=1, engine='openpyxl')
      
      return self.data_validator.get_data_summary(df)
      
    except Exception as e:
      print(f"Error getting data summary: {str(e)}")
      return None
  
  def suggest_configuration_from_data(self, file_path: str, is_directory: bool) -> Optional[Dict[str, Any]]:
    """Suggest configuration values based on the data content."""
    
    data_summary = self.get_data_summary(file_path, is_directory)
    
    if data_summary:
      return self.config_validator.suggest_configuration_from_data(data_summary)
    
    return None