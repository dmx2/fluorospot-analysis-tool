"""Configuration validation for FluoroSpot analysis settings."""

import re
from typing import Dict, Any, List, Tuple
from pathlib import Path


class ConfigValidator:
  """Validator for FluoroSpot analysis configuration."""
  
  LED_PATTERN = re.compile(r'^LED\d{3}$')
  FILENAME_PATTERN = re.compile(r'^[^<>:"/\\|?*]+$')  # Valid filename characters
  
  def __init__(self):
    self.validation_results = []
  
  def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate the complete configuration."""
    self.validation_results = []
    valid = True
    
    # Validate basic settings
    if not self.validate_basic_settings(config):
      valid = False
    
    # Validate mappings
    if not self.validate_mappings(config):
      valid = False
    
    # Validate experimental conditions
    if not self.validate_experimental_conditions(config):
      valid = False
    
    # Validate output settings
    if not self.validate_output_settings(config):
      valid = False
    
    return valid, self.validation_results
  
  def validate_basic_settings(self, config: Dict[str, Any]) -> bool:
    """Validate basic configuration settings."""
    valid = True
    
    # Validate cell count
    if 'cells_per_well' not in config:
      self.validation_results.append("❌ Missing cell count")
      valid = False
    else:
      try:
        cells_per_well = int(config['cells_per_well'])
        if cells_per_well <= 0:
          self.validation_results.append("❌ Cell count must be positive")
          valid = False
        elif cells_per_well < 1000:
          self.validation_results.append(f"⚠️ Cell count is very low ({cells_per_well})")
        else:
          self.validation_results.append(f"✅ Cells plated: {cells_per_well:,}")
      except (ValueError, TypeError):
        self.validation_results.append("❌ Cell count must be a valid integer")
        valid = False
    
    # Validate SFC cutoff
    if 'sfc_cutoff' not in config:
      self.validation_results.append("❌ Missing SFC cutoff")
      valid = False
    else:
      try:
        sfc_cutoff = int(config['sfc_cutoff'])
        if sfc_cutoff < 0:
          self.validation_results.append("❌ SFC cutoff cannot be negative")
          valid = False
        else:
          self.validation_results.append(f"✅ SFC cutoff: {sfc_cutoff}")
      except (ValueError, TypeError):
        self.validation_results.append("❌ SFC cutoff must be a valid integer")
        valid = False
    
    # Validate control stimulus
    if 'control_stim' not in config:
      self.validation_results.append("❌ Missing control stimulus")
      valid = False
    else:
      control_stim = config['control_stim']
      if not control_stim or not str(control_stim).strip():
        self.validation_results.append("❌ Control stimulus cannot be empty")
        valid = False
      else:
        self.validation_results.append(f"✅ Control stimulus: '{control_stim}'")
    
    return valid
  
  def validate_mappings(self, config: Dict[str, Any]) -> bool:
    """Validate cytokine and plate mappings."""
    valid = True
    
    # Validate cytokine mappings
    if 'cytokines' not in config:
      self.validation_results.append("❌ Missing cytokine mappings")
      valid = False
    else:
      cytokines = config['cytokines']
      if not isinstance(cytokines, dict):
        self.validation_results.append("❌ Cytokine mappings must be a dictionary")
        valid = False
      elif not cytokines:
        self.validation_results.append("❌ At least one cytokine mapping is required")
        valid = False
      else:
        valid_cytokines = 0
        for cytokine, led in cytokines.items():
          if not cytokine or not str(cytokine).strip():
            self.validation_results.append("⚠️ Empty cytokine name found")
            continue
          
          if not led or not str(led).strip():
            self.validation_results.append(f"⚠️ Empty LED mapping for cytokine '{cytokine}'")
            continue
          
          if not self.LED_PATTERN.match(str(led)):
            self.validation_results.append(f"⚠️ Invalid LED format for '{cytokine}': '{led}' (expected LED###)")
            continue
          
          valid_cytokines += 1
        
        if valid_cytokines == 0:
          self.validation_results.append("❌ No valid cytokine mappings found")
          valid = False
        else:
          self.validation_results.append(f"✅ Found {valid_cytokines} valid cytokine mapping(s)")
        
        # Check for duplicate LEDs
        led_values = [led for led in cytokines.values() if led]
        if len(led_values) != len(set(led_values)):
          self.validation_results.append("⚠️ Duplicate LED mappings found")
    
    # Validate plate mappings
    if 'plates' not in config:
      self.validation_results.append("❌ Missing plate mappings")
      valid = False
    else:
      plates = config['plates']
      if not isinstance(plates, dict):
        self.validation_results.append("❌ Plate mappings must be a dictionary")
        valid = False
      elif not plates:
        self.validation_results.append("❌ At least one plate mapping is required")
        valid = False
      else:
        valid_plates = 0
        for plate_id, species in plates.items():
          if not plate_id or not str(plate_id).strip():
            self.validation_results.append("⚠️ Empty plate ID found")
            continue
          
          if not species or not str(species).strip():
            self.validation_results.append(f"⚠️ Empty species for plate '{plate_id}'")
            continue
          
          valid_plates += 1
        
        if valid_plates == 0:
          self.validation_results.append("❌ No valid plate mappings found")
          valid = False
        else:
          self.validation_results.append(f"✅ Found {valid_plates} valid plate mapping(s)")
    
    return valid
  
  def validate_experimental_conditions(self, config: Dict[str, Any]) -> bool:
    """Validate experimental conditions configuration."""
    if 'experimental_conditions' not in config or not config['experimental_conditions']:
      self.validation_results.append("ℹ️ No experimental conditions specified (using simple mode)")
      return True
    
    valid = True
    exp_conditions = config['experimental_conditions']
    
    if not isinstance(exp_conditions, dict):
      self.validation_results.append("❌ Experimental conditions must be a dictionary")
      return False
    
    total_groups = 0
    for plate_id, plate_conditions in exp_conditions.items():
      if not plate_id or not str(plate_id).strip():
        self.validation_results.append("⚠️ Empty plate ID in experimental conditions")
        continue
      
      if not isinstance(plate_conditions, dict):
        self.validation_results.append(f"❌ Conditions for plate '{plate_id}' must be a dictionary")
        valid = False
        continue
      
      plate_groups = 0
      for group_name, group_config in plate_conditions.items():
        if not group_name or not str(group_name).strip():
          self.validation_results.append(f"⚠️ Empty group name in plate '{plate_id}'")
          continue
        
        if not isinstance(group_config, dict):
          self.validation_results.append(f"❌ Group '{group_name}' in plate '{plate_id}' must be a dictionary")
          valid = False
          continue
        
        # Validate control
        if 'control' not in group_config:
          self.validation_results.append(f"❌ Missing control for group '{group_name}' in plate '{plate_id}'")
          valid = False
          continue
        
        control = group_config['control']
        if not control or not str(control).strip():
          self.validation_results.append(f"❌ Empty control for group '{group_name}' in plate '{plate_id}'")
          valid = False
          continue
        
        # Validate stimuli
        if 'stimuli' not in group_config:
          self.validation_results.append(f"❌ Missing stimuli for group '{group_name}' in plate '{plate_id}'")
          valid = False
          continue
        
        stimuli = group_config['stimuli']
        if not isinstance(stimuli, list):
          self.validation_results.append(f"❌ Stimuli for group '{group_name}' in plate '{plate_id}' must be a list")
          valid = False
          continue
        
        if not stimuli:
          self.validation_results.append(f"❌ At least one stimulus required for group '{group_name}' in plate '{plate_id}'")
          valid = False
          continue
        
        # Check for empty stimuli
        valid_stimuli = [s for s in stimuli if s and str(s).strip()]
        if len(valid_stimuli) != len(stimuli):
          self.validation_results.append(f"⚠️ Empty stimulus names found in group '{group_name}', plate '{plate_id}'")
        
        if not valid_stimuli:
          self.validation_results.append(f"❌ No valid stimuli for group '{group_name}' in plate '{plate_id}'")
          valid = False
          continue
        
        plate_groups += 1
      
      if plate_groups == 0:
        self.validation_results.append(f"❌ No valid groups found for plate '{plate_id}'")
        valid = False
      else:
        total_groups += plate_groups
    
    if total_groups == 0:
      self.validation_results.append("❌ No valid experimental groups found")
      valid = False
    else:
      self.validation_results.append(f"✅ Found {total_groups} experimental group(s)")
    
    return valid
  
  def validate_output_settings(self, config: Dict[str, Any]) -> bool:
    """Validate output configuration settings."""
    valid = True
    
    # Validate output directory
    if 'output_dir' not in config:
      self.validation_results.append("❌ Missing output directory")
      valid = False
    else:
      output_dir = Path(config['output_dir'])
      try:
        # Check if parent directory exists and is writable
        parent_dir = output_dir.parent
        if not parent_dir.exists():
          self.validation_results.append(f"❌ Parent directory does not exist: {parent_dir}")
          valid = False
        elif not parent_dir.is_dir():
          self.validation_results.append(f"❌ Parent path is not a directory: {parent_dir}")
          valid = False
        else:
          import os
          if not os.access(str(parent_dir), os.W_OK):
            self.validation_results.append(f"❌ No write permission to directory: {parent_dir}")
            valid = False
          else:
            self.validation_results.append(f"✅ Output directory: {output_dir}")
      except Exception as e:
        self.validation_results.append(f"❌ Invalid output directory path: {str(e)}")
        valid = False
    
    # Validate results filename
    if 'results_filename' not in config:
      self.validation_results.append("❌ Missing results filename")
      valid = False
    else:
      filename = config['results_filename']
      if not filename or not str(filename).strip():
        self.validation_results.append("❌ Results filename cannot be empty")
        valid = False
      elif not self.FILENAME_PATTERN.match(str(filename)):
        self.validation_results.append("❌ Results filename contains invalid characters")
        valid = False
      elif not str(filename).endswith('.xlsx'):
        self.validation_results.append("⚠️ Results filename should end with .xlsx")
      else:
        self.validation_results.append(f"✅ Results filename: {filename}")
    
    return valid
  
  def validate_config_for_data(self, config: Dict[str, Any], data_summary: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate configuration against actual data summary."""
    results = []
    valid = True
    
    # Check control stimulus exists in data
    if 'control_stim' in config and 'stimuli' in data_summary:
      control_stim = config['control_stim']
      data_stimuli = data_summary['stimuli']
      
      if control_stim in data_stimuli:
        results.append(f"✅ Control stimulus '{control_stim}' found in data")
      else:
        # Look for partial matches
        partial_matches = [s for s in data_stimuli if control_stim in str(s)]
        if partial_matches:
          results.append(f"⚠️ Control stimulus '{control_stim}' not found exactly, similar: {', '.join(map(str, partial_matches[:3]))}")
        else:
          results.append(f"❌ Control stimulus '{control_stim}' not found in data")
          valid = False
    
    # Check plate mappings
    if 'plates' in config and 'plates' in data_summary:
      config_plates = set(config['plates'].keys())
      data_plates = set(map(str, data_summary['plates']))
      
      missing_plates = config_plates - data_plates
      if missing_plates:
        results.append(f"⚠️ Plates in config but not in data: {', '.join(missing_plates)}")
      
      matching_plates = config_plates & data_plates
      if matching_plates:
        results.append(f"✅ Matching plates: {', '.join(matching_plates)}")
      else:
        results.append(f"❌ No matching plates between config and data")
        valid = False
    
    # Check LED mappings
    if 'cytokines' in config and 'led_populations' in data_summary:
      config_leds = set(config['cytokines'].values())
      data_leds = set(pop.replace(' Total', '') for pop in data_summary['led_populations'] if ' Total' in pop)
      
      missing_leds = config_leds - data_leds
      if missing_leds:
        results.append(f"⚠️ LEDs in config but not in data: {', '.join(missing_leds)}")
      
      matching_leds = config_leds & data_leds
      if matching_leds:
        results.append(f"✅ Matching LEDs: {', '.join(matching_leds)}")
    
    return valid, results
  
  def suggest_configuration_from_data(self, data_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest configuration values based on data content."""
    suggestions = {}
    
    # Suggest control stimulus
    if 'stimuli' in data_summary:
      stimuli = data_summary['stimuli']
      control_candidates = ['DMSO', 'Control', 'Negative', 'PBS', 'Medium']
      
      for candidate in control_candidates:
        matching = [s for s in stimuli if candidate.lower() in str(s).lower()]
        if matching:
          suggestions['control_stim'] = matching[0]
          break
    
    # Suggest cytokine mappings from LED populations
    if 'led_populations' in data_summary:
      led_populations = data_summary['led_populations']
      leds = [pop.replace(' Total', '') for pop in led_populations if ' Total' in pop]
      
      # Common LED to cytokine mappings
      common_mappings = {
        'LED490': 'IFNg',
        'LED550': 'IL-10',
        'LED640': 'IL-17',
        'LED700': 'TNFa'
      }
      
      suggested_cytokines = {}
      for led in leds:
        if led in common_mappings:
          suggested_cytokines[common_mappings[led]] = led
        else:
          # Generic mapping
          cytokine_name = f"Cytokine_{led.replace('LED', '')}"
          suggested_cytokines[cytokine_name] = led
      
      if suggested_cytokines:
        suggestions['cytokines'] = suggested_cytokines
    
    # Suggest plate mappings
    if 'plates' in data_summary:
      plates = data_summary['plates']
      suggested_plates = {}
      for plate in plates:
        suggested_plates[str(plate)] = "Unknown species"
      suggestions['plates'] = suggested_plates
    
    return suggestions