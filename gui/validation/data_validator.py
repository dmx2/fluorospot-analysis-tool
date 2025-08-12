"""Data validation for Excel files and FluoroSpot data."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import re


class DataValidator:
  """Validator for FluoroSpot Excel data files."""
  
  REQUIRED_COLUMNS = [
    'Layout-Donor',
    'Plate',
    'Layout-Stimuli', 
    'Spot Forming Units (SFU)',
    'Analyte Secreting Population'
  ]
  
  LED_PATTERN = re.compile(r'LED\d{3} Total')
  
  def __init__(self):
    self.validation_results = []
  
  def validate_file(self, file_path: Path) -> Tuple[bool, List[str]]:
    """Validate a single Excel file."""
    self.validation_results = []
    
    try:
      # Check file existence and extension
      if not file_path.exists():
        self.validation_results.append(f"❌ File does not exist: {file_path}")
        return False, self.validation_results
      
      if file_path.suffix.lower() not in ['.xlsx', '.xls']:
        self.validation_results.append(f"⚠️ File is not an Excel file: {file_path}")
      
      # Try to read the Excel file
      try:
        df = pd.read_excel(file_path, sheet_name=1, engine='openpyxl')
        self.validation_results.append(f"✅ Successfully loaded Excel file (sheet 1)")
      except Exception as e:
        try:
          # Try sheet 0 if sheet 1 fails
          df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
          self.validation_results.append(f"⚠️ Using sheet 0 instead of sheet 1")
        except Exception as e2:
          self.validation_results.append(f"❌ Cannot read Excel file: {str(e)}")
          return False, self.validation_results
      
      # Validate DataFrame structure
      return self.validate_dataframe(df, str(file_path))
      
    except Exception as e:
      self.validation_results.append(f"❌ Validation error: {str(e)}")
      return False, self.validation_results
  
  def validate_directory(self, directory: Path) -> Tuple[bool, List[str]]:
    """Validate a directory containing Excel files."""
    self.validation_results = []
    
    if not directory.exists():
      self.validation_results.append(f"❌ Directory does not exist: {directory}")
      return False, self.validation_results
    
    if not directory.is_dir():
      self.validation_results.append(f"❌ Path is not a directory: {directory}")
      return False, self.validation_results
    
    # Find Excel files
    excel_files = list(directory.glob("*.xlsx")) + list(directory.glob("*.xls"))
    
    # Filter out temporary files
    excel_files = [f for f in excel_files if not f.name.startswith('~')]
    
    if not excel_files:
      self.validation_results.append(f"❌ No Excel files found in directory: {directory}")
      return False, self.validation_results
    
    self.validation_results.append(f"✅ Found {len(excel_files)} Excel file(s)")
    
    # Do lightweight validation of each file (just basic checks, no full data loading)
    all_valid = True
    for excel_file in excel_files:
      file_valid, file_results = self.validate_file_lightweight(excel_file)
      if not file_valid:
        all_valid = False
      
      # Add file-specific results with filename prefix
      for result in file_results:
        self.validation_results.append(f"  {excel_file.name}: {result}")
    
    return all_valid, self.validation_results
  
  def validate_file_lightweight(self, file_path: Path) -> Tuple[bool, List[str]]:
    """Validate a file without loading all data - for directory scanning."""
    results = []
    
    try:
      # Check file existence and extension
      if not file_path.exists():
        results.append(f"❌ File does not exist")
        return False, results
      
      if file_path.suffix.lower() not in ['.xlsx', '.xls']:
        results.append(f"⚠️ File is not an Excel file")
        return False, results
      
      # Check file size
      file_size = file_path.stat().st_size
      if file_size == 0:
        results.append(f"❌ File is empty")
        return False, results
      elif file_size > 100 * 1024 * 1024:  # 100MB
        results.append(f"⚠️ Large file ({file_size / (1024*1024):.1f} MB)")
      else:
        results.append(f"✅ Valid Excel file ({file_size / 1024:.0f} KB)")
      
      # Try to open file to check if it's corrupted (just check structure, don't load data)
      try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sheet_count = len(wb.worksheets)
        results.append(f"✅ File readable with {sheet_count} sheet(s)")
        wb.close()
        return True, results
      except Exception as e:
        results.append(f"❌ Cannot open Excel file: {str(e)}")
        return False, results
        
    except Exception as e:
      results.append(f"❌ Validation error: {str(e)}")
      return False, results
  
  def validate_dataframe(self, df: pd.DataFrame, source_name: str = "") -> Tuple[bool, List[str]]:
    """Validate the structure and content of a DataFrame."""
    valid = True
    
    # Check if DataFrame is empty
    if df.empty:
      self.validation_results.append(f"❌ DataFrame is empty")
      return False, self.validation_results
    
    self.validation_results.append(f"✅ DataFrame has {len(df)} rows and {len(df.columns)} columns")
    
    # Check for required columns
    missing_columns = []
    for col in self.REQUIRED_COLUMNS:
      if col not in df.columns:
        missing_columns.append(col)
    
    if missing_columns:
      # Check if any critical columns are missing
      critical_columns = ['Layout-Donor', 'Spot Forming Units (SFU)']
      missing_critical = [col for col in missing_columns if col in critical_columns]
      missing_non_critical = [col for col in missing_columns if col not in critical_columns]
      
      if missing_critical:
        self.validation_results.append(f"❌ Missing critical required columns: {', '.join(missing_critical)}")
        valid = False
      
      if missing_non_critical:
        self.validation_results.append(f"⚠️ Missing optional columns: {', '.join(missing_non_critical)}")
        # Don't mark as invalid for optional columns
    else:
      self.validation_results.append(f"✅ All required columns present")
    
    # Check data types and content
    if valid:
      valid = self.validate_column_content(df) and valid
    
    return valid, self.validation_results
  
  def validate_column_content(self, df: pd.DataFrame) -> bool:
    """Validate the content of specific columns."""
    valid = True
    
    # Check Layout-Donor column
    if 'Layout-Donor' in df.columns:
      unique_donors = df['Layout-Donor'].dropna().unique()
      if len(unique_donors) == 0:
        self.validation_results.append(f"❌ No donor IDs found")
        valid = False
      else:
        self.validation_results.append(f"✅ Found {len(unique_donors)} unique donor(s): {', '.join(map(str, unique_donors))}")
    
    # Check Plate column
    if 'Plate' in df.columns:
      unique_plates = df['Plate'].dropna().unique()
      if len(unique_plates) == 0:
        self.validation_results.append(f"❌ No plate IDs found")
        valid = False
      else:
        self.validation_results.append(f"✅ Found {len(unique_plates)} unique plate(s): {', '.join(map(str, unique_plates))}")
    
    # Check Layout-Stimuli column
    if 'Layout-Stimuli' in df.columns:
      unique_stimuli = df['Layout-Stimuli'].dropna().unique()
      if len(unique_stimuli) == 0:
        self.validation_results.append(f"❌ No stimuli found")
        valid = False
      else:
        self.validation_results.append(f"✅ Found {len(unique_stimuli)} unique stimuli")
        
        # Check for common control stimuli
        control_stimuli = ['DMSO', 'Control', 'Negative', 'PBS']
        found_controls = [s for s in unique_stimuli if any(control in str(s) for control in control_stimuli)]
        if found_controls:
          self.validation_results.append(f"✅ Found potential control stimuli: {', '.join(map(str, found_controls))}")
    
    # Check Spot Forming Units (SFU) column
    if 'Spot Forming Units (SFU)' in df.columns:
      sfu_col = df['Spot Forming Units (SFU)']
      numeric_values = pd.to_numeric(sfu_col, errors='coerce')
      non_numeric_count = numeric_values.isna().sum() - sfu_col.isna().sum()
      
      if non_numeric_count > 0:
        self.validation_results.append(f"⚠️ Found {non_numeric_count} non-numeric SFU values")
      
      valid_sfu_values = numeric_values.dropna()
      if len(valid_sfu_values) > 0:
        self.validation_results.append(f"✅ SFU values range: {valid_sfu_values.min():.1f} - {valid_sfu_values.max():.1f}")
      else:
        self.validation_results.append(f"❌ No valid SFU values found")
        valid = False
    
    # Check Analyte Secreting Population column (LED format)
    if 'Analyte Secreting Population' in df.columns:
      unique_populations = df['Analyte Secreting Population'].dropna().unique()
      led_populations = [pop for pop in unique_populations if self.LED_PATTERN.match(str(pop))]
      
      if not led_populations:
        self.validation_results.append(f"⚠️ No LED populations found (expected format: 'LED### Total')")
        # Don't mark as invalid - this is just a warning
      else:
        self.validation_results.append(f"✅ Found LED populations: {', '.join(led_populations)}")
    
    return valid
  
  def validate_configuration_compatibility(self, df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that the configuration is compatible with the data."""
    results = []
    valid = True
    
    # Check if control stimulus exists in data
    if 'control_stim' in config and 'Layout-Stimuli' in df.columns:
      control_stim = config['control_stim']
      stimuli = df['Layout-Stimuli'].dropna().unique()
      
      # Check for exact match or partial match
      exact_match = control_stim in stimuli
      partial_matches = [s for s in stimuli if control_stim in str(s)]
      
      if exact_match:
        results.append(f"✅ Control stimulus '{control_stim}' found in data")
      elif partial_matches:
        results.append(f"⚠️ Control stimulus '{control_stim}' not found exactly, but found similar: {', '.join(map(str, partial_matches))}")
      else:
        results.append(f"❌ Control stimulus '{control_stim}' not found in data")
        valid = False
    
    # Check if plate IDs match
    if 'plates' in config and 'Plate' in df.columns:
      config_plates = set(config['plates'].keys())
      data_plates = set(df['Plate'].dropna().unique())
      
      missing_plates = config_plates - data_plates
      extra_plates = data_plates - config_plates
      
      if missing_plates:
        results.append(f"⚠️ Plates in config but not in data: {', '.join(missing_plates)}")
      
      if extra_plates:
        results.append(f"⚠️ Plates in data but not in config: {', '.join(map(str, extra_plates))}")
      
      matching_plates = config_plates & data_plates
      if matching_plates:
        results.append(f"✅ Matching plates: {', '.join(matching_plates)}")
      else:
        results.append(f"❌ No matching plates between config and data")
        valid = False
    
    # Check LED mappings
    if 'cytokines' in config and 'Analyte Secreting Population' in df.columns:
      config_leds = set(config['cytokines'].values())
      data_populations = df['Analyte Secreting Population'].dropna().unique()
      data_leds = set(pop.replace(' Total', '') for pop in data_populations if ' Total' in str(pop))
      
      missing_leds = config_leds - data_leds
      if missing_leds:
        results.append(f"⚠️ LEDs in config but not in data: {', '.join(missing_leds)}")
      
      matching_leds = config_leds & data_leds
      if matching_leds:
        results.append(f"✅ Matching LEDs: {', '.join(matching_leds)}")
    
    # Check experimental conditions if present
    if 'experimental_conditions' in config and config['experimental_conditions']:
      exp_conditions = config['experimental_conditions']
      
      for plate_id, plate_conditions in exp_conditions.items():
        # Check if plate exists in data
        if 'Plate' in df.columns:
          data_plates = df['Plate'].dropna().unique()
          if plate_id not in data_plates:
            results.append(f"⚠️ Experimental condition plate '{plate_id}' not found in data")
            continue
        
        # Check controls and stimuli for this plate
        plate_data = df[df['Plate'] == plate_id] if 'Plate' in df.columns else df
        plate_stimuli = plate_data['Layout-Stimuli'].dropna().unique() if 'Layout-Stimuli' in plate_data.columns else []
        
        for group_name, group_config in plate_conditions.items():
          control = group_config.get('control')
          stimuli = group_config.get('stimuli', [])
          
          # Check control
          if control and control not in plate_stimuli:
            results.append(f"⚠️ Control '{control}' for group '{group_name}' not found in plate '{plate_id}'")
          
          # Check stimuli
          for stimulus in stimuli:
            if stimulus not in plate_stimuli:
              results.append(f"⚠️ Stimulus '{stimulus}' for group '{group_name}' not found in plate '{plate_id}'")
    
    return valid, results
  
  def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
    """Get a summary of the data for display purposes."""
    summary = {
      'total_rows': len(df),
      'total_columns': len(df.columns),
    }
    
    if 'Layout-Donor' in df.columns:
      summary['donors'] = df['Layout-Donor'].dropna().unique().tolist()
    
    if 'Plate' in df.columns:
      summary['plates'] = df['Plate'].dropna().unique().tolist()
    
    if 'Layout-Stimuli' in df.columns:
      summary['stimuli'] = df['Layout-Stimuli'].dropna().unique().tolist()
    
    if 'Analyte Secreting Population' in df.columns:
      populations = df['Analyte Secreting Population'].dropna().unique()
      summary['led_populations'] = [pop for pop in populations if 'LED' in str(pop)]
    
    if 'Spot Forming Units (SFU)' in df.columns:
      sfu_values = pd.to_numeric(df['Spot Forming Units (SFU)'], errors='coerce').dropna()
      if len(sfu_values) > 0:
        summary['sfu_stats'] = {
          'min': float(sfu_values.min()),
          'max': float(sfu_values.max()),
          'mean': float(sfu_values.mean()),
          'count': int(len(sfu_values))
        }
    
    return summary