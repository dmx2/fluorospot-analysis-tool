"""Configuration validation for FluoroSpot analysis settings."""

import os
import re
from typing import Dict, Any, List, Tuple
from pathlib import Path

from populations import LED_PATTERN, MULTI_SCOPES, SCOPE_UNKNOWN, parse_population_label


class ConfigValidator:
  """Validator for FluoroSpot analysis configuration."""
  
  LED_PATTERN = LED_PATTERN
  FILENAME_PATTERN = re.compile(r'^[^<>:"/\\|?*]+$')  # Valid filename characters
  
  def __init__(self):
    self.validation_results = []
    # Problems that genuinely prevent the analysis from producing results, each
    # phrased as something the user can act on.
    self.blocking_problems = []

  def block(self, problem: str):
    """Record an actionable problem that must be fixed before analysis."""
    self.validation_results.append(f"❌ {problem}")
    if problem not in self.blocking_problems:
      self.blocking_problems.append(problem)

  def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate the complete configuration."""
    self.validation_results = []
    self.blocking_problems = []
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

    # Validate selected populations
    if not self.validate_populations(config):
      valid = False

    # Validate output settings
    if not self.validate_output_settings(config):
      valid = False

    return valid, self.validation_results
  
  def validate_populations(self, config: Dict[str, Any]) -> bool:
    """Validate the selected population endpoints."""
    populations = config.get('populations') or []
    if not populations:
      self.validation_results.append(
        "ℹ️ No population selection: analyzing one Total per configured cytokine (default)"
      )
      return True

    specs = [parse_population_label(label) for label in populations]
    unknown = [spec.label for spec in specs if spec.scope == SCOPE_UNKNOWN]
    if unknown:
      self.validation_results.append(
        f"⚠️ Unrecognized population label(s) kept as-is: {', '.join(unknown)}"
      )

    multi = [spec for spec in specs if spec.scope in MULTI_SCOPES]
    if multi and not config.get('mapping_confirmed', False):
      self.validation_results.append(
        "⚠️ Cytokine/LED mapping is not confirmed; exact double/triple labels are unverified"
      )

    self.validation_results.append(
      f"✅ {len(populations)} population endpoint(s) selected, {len(multi)} exact multi-secretor"
    )
    return True

  def validate_basic_settings(self, config: Dict[str, Any]) -> bool:
    """Validate basic configuration settings."""
    valid = True

    # Validate cell count
    if 'cells_per_well' not in config:
      self.block("Missing cell count. Enter the cells plated per well on the Basic Settings tab.")
      valid = False
    else:
      try:
        cells_per_well = int(config['cells_per_well'])
        if cells_per_well <= 0:
          self.block("Cell count must be positive. Enter the cells plated per well "
                     "(e.g. 200000) on the Basic Settings tab.")
          valid = False
        elif cells_per_well < 1000:
          self.validation_results.append(f"⚠️ Cell count is very low ({cells_per_well})")
        else:
          self.validation_results.append(f"✅ Cells plated: {cells_per_well:,}")
      except (ValueError, TypeError):
        self.block("Cell count must be a whole number. Fix 'Cells Plated per Well' "
                   "on the Basic Settings tab.")
        valid = False

    # Validate SFC cutoff
    if 'sfc_cutoff' not in config:
      self.block("Missing SFC cutoff. Enter it on the Basic Settings tab.")
      valid = False
    else:
      try:
        sfc_cutoff = int(config['sfc_cutoff'])
        if sfc_cutoff < 0:
          self.block("SFC cutoff cannot be negative. Enter 0 or a positive value on the "
                     "Basic Settings tab.")
          valid = False
        else:
          self.validation_results.append(f"✅ SFC cutoff: {sfc_cutoff}")
      except (ValueError, TypeError):
        self.block("SFC cutoff must be a whole number. Fix it on the Basic Settings tab.")
        valid = False

    # Validate control stimulus
    if 'control_stim' not in config or not str(config.get('control_stim') or '').strip():
      self.block("Control stimulus is empty. Enter the negative-control stimulus name used "
                 "in your data (e.g. DMSO) on the Basic Settings tab.")
      valid = False
    else:
      self.validation_results.append(f"✅ Control stimulus: '{config['control_stim']}'")

    return valid
  
  def validate_mappings(self, config: Dict[str, Any]) -> bool:
    """Validate cytokine and plate mappings.

    A cytokine mapping is only required when no populations are selected: the
    default endpoints are one Total per configured cytokine. The plate mapping
    supplies the Species label, which the analysis does not need in order to
    produce statistics, so a missing one is a warning about blank Species.
    """
    valid = True
    has_selection = bool(config.get('populations'))

    # Validate cytokine mappings
    cytokines = config.get('cytokines')
    if not isinstance(cytokines, dict):
      cytokines = {}
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

    if valid_cytokines:
      self.validation_results.append(f"✅ Found {valid_cytokines} valid cytokine mapping(s)")
    elif has_selection:
      self.validation_results.append(
        "⚠️ No cytokine name is mapped to an LED channel; selected populations keep their "
        "raw LED labels in the results"
      )
    else:
      self.block("No cytokine is mapped to an LED channel, so there is nothing to analyze. "
                 "Add a cytokine name and its LED (e.g. IFNg / LED490) on the Cytokines tab, "
                 "or select populations on the Populations tab.")
      valid = False

    # Check for duplicate LEDs
    led_values = [led for led in cytokines.values() if led]
    if len(led_values) != len(set(led_values)):
      self.validation_results.append("⚠️ Duplicate LED mappings found")

    # Validate plate mappings
    plates = config.get('plates')
    if not isinstance(plates, dict):
      plates = {}
    valid_plates = 0
    for plate_id, species in plates.items():
      if not plate_id or not str(plate_id).strip():
        self.validation_results.append("⚠️ Empty plate ID found")
        continue

      if not species or not str(species).strip():
        # The data-aware check names the plate labels and the consequence; keep
        # this one quiet so the same problem is not reported twice.
        continue

      valid_plates += 1

    if valid_plates:
      self.validation_results.append(f"✅ Found {valid_plates} valid plate mapping(s)")
    else:
      self.validation_results.append(
        "ℹ️ No plate → species mapping yet: the analysis runs, but the Species column stays "
        "blank until a plate label from the data is given a species on the Plates tab."
      )

    return valid
  
  def validate_experimental_conditions(self, config: Dict[str, Any]) -> bool:
    """Validate experimental conditions configuration.

    The analyzer reads the control and stimuli of every configured group, so a
    structurally incomplete group is a real blocker, not cosmetic.
    """
    if 'experimental_conditions' not in config or not config['experimental_conditions']:
      self.validation_results.append("ℹ️ No experimental conditions specified (using simple mode)")
      return True

    valid = True
    exp_conditions = config['experimental_conditions']
    where = "Experimental Conditions tab"

    if not isinstance(exp_conditions, dict):
      self.block(f"Experimental conditions are malformed (expected plate → groups). "
                 f"Fix them on the {where}, or untick it to use simple mode.")
      return False

    total_groups = 0
    for plate_id, plate_conditions in exp_conditions.items():
      if not plate_id or not str(plate_id).strip():
        self.validation_results.append("⚠️ Empty plate ID in experimental conditions")
        continue

      if not isinstance(plate_conditions, dict):
        self.block(f"Conditions for plate '{plate_id}' are malformed. Fix them on the {where}.")
        valid = False
        continue

      plate_groups = 0
      for group_name, group_config in plate_conditions.items():
        if not group_name or not str(group_name).strip():
          self.validation_results.append(f"⚠️ Empty group name in plate '{plate_id}'")
          continue

        if not isinstance(group_config, dict):
          self.block(f"Group '{group_name}' of plate '{plate_id}' is malformed. "
                     f"Fix it on the {where}.")
          valid = False
          continue

        control = group_config.get('control')
        if not control or not str(control).strip():
          self.block(f"Group '{group_name}' of plate '{plate_id}' has no control stimulus. "
                     f"Enter the control well name (exactly as in the data) on the {where}, "
                     f"or remove the group.")
          valid = False
          continue

        stimuli = group_config.get('stimuli')
        if stimuli is None:
          self.block(f"Group '{group_name}' of plate '{plate_id}' has no stimuli. Add at least "
                     f"one stimulus name on the {where}, or remove the group.")
          valid = False
          continue

        if not isinstance(stimuli, list):
          self.block(f"Stimuli of group '{group_name}' in plate '{plate_id}' are malformed "
                     f"(expected a list). Fix them on the {where}.")
          valid = False
          continue

        valid_stimuli = [s for s in stimuli if s and str(s).strip()]
        if len(valid_stimuli) != len(stimuli):
          self.validation_results.append(f"⚠️ Empty stimulus names found in group '{group_name}', plate '{plate_id}'")

        if not valid_stimuli:
          self.block(f"Group '{group_name}' of plate '{plate_id}' has no stimulus name. Add at "
                     f"least one stimulus (exactly as in the data) on the {where}, or remove "
                     f"the group.")
          valid = False
          continue

        plate_groups += 1

      if plate_groups == 0:
        self.block(f"Plate '{plate_id}' has no usable experimental group. Complete a group on "
                   f"the {where}, or untick experimental conditions to use simple mode.")
        valid = False
      else:
        total_groups += plate_groups

    if total_groups == 0:
      self.block("Experimental conditions are enabled but no usable group is configured. "
                 f"Complete a group on the {where}, or untick it to use simple mode "
                 "(all non-control wells versus the control stimulus).")
      valid = False
    else:
      self.validation_results.append(f"✅ Found {total_groups} experimental group(s)")

    return valid
  
  def validate_output_settings(self, config: Dict[str, Any]) -> bool:
    """Validate output configuration settings.

    The analysis creates the output directory (including parents), so a
    not-yet-existing directory is fine; only an unwritable location blocks.
    """
    valid = True

    # Validate output directory
    if 'output_dir' not in config or not str(config.get('output_dir') or '').strip():
      self.block("No output directory. Choose where results should be written on the Output tab.")
      valid = False
    else:
      output_dir = Path(str(config['output_dir']).strip())
      try:
        existing = output_dir
        while not existing.exists() and existing != existing.parent:
          existing = existing.parent
        if not existing.is_dir():
          self.block(f"Output path '{output_dir}' is not usable: '{existing}' is a file, not a "
                     "folder. Choose another folder on the Output tab.")
          valid = False
        elif not os.access(str(existing), os.W_OK):
          self.block(f"No write permission for '{existing}'. Choose a writable output folder "
                     "on the Output tab.")
          valid = False
        elif output_dir.exists():
          self.validation_results.append(f"✅ Output directory: {output_dir}")
        else:
          self.validation_results.append(f"✅ Output directory (will be created): {output_dir}")
      except OSError as error:
        self.block(f"Output directory cannot be used ({error}). Choose another folder on the "
                   "Output tab.")
        valid = False

    # Validate results filename
    filename = str(config.get('results_filename') or '').strip()
    if not filename:
      self.block("Results filename is empty. Enter a name such as fluorospot-results.xlsx on "
                 "the Output tab.")
      valid = False
    elif not self.FILENAME_PATTERN.match(filename):
      self.block("Results filename contains characters that cannot be used in a filename "
                 "(< > : \" / \\ | ? *). Rename it on the Output tab.")
      valid = False
    elif not filename.endswith('.xlsx'):
      self.validation_results.append("⚠️ Results filename should end with .xlsx")
    else:
      self.validation_results.append(f"✅ Results filename: {filename}")

    return valid

  def validate_config_for_data(
    self, config: Dict[str, Any], data_summary: Dict[str, Any]
  ) -> Tuple[bool, List[str], List[str]]:
    """Validate configuration against the actual data.

    Returns (valid, messages, blocking). Only mismatches that leave the analysis
    with nothing to compute block it; everything else is a warning that names
    what the data actually contains so the user can fix the configuration.
    """
    results = []
    blocking = []

    def block(problem):
      results.append(f"❌ {problem}")
      if problem not in blocking:
        blocking.append(problem)

    # Check control stimulus exists in data. Simple mode matches control wells by
    # substring, so a partial match still works; no match at all leaves every
    # comparison without a control.
    if 'control_stim' in config and 'stimuli' in data_summary:
      control_stim = str(config['control_stim'])
      data_stimuli = [str(s) for s in data_summary['stimuli']]

      if control_stim in data_stimuli:
        results.append(f"✅ Control stimulus '{control_stim}' found in data")
      else:
        partial_matches = [s for s in data_stimuli if control_stim in s]
        if partial_matches:
          results.append(
            f"⚠️ Control stimulus '{control_stim}' is not an exact well name; matching "
            f"control wells: {', '.join(partial_matches[:5])}"
          )
        else:
          block(f"Control stimulus '{control_stim}' does not appear in this data, so there is "
                f"nothing to compare stimuli against. Set 'Control Stimulus' on the Basic "
                f"Settings tab to one of the well names in the data: "
                f"{', '.join(sorted(data_stimuli)[:10])}")

    # Check plate mappings. The mapping only supplies the Species label, so a
    # mismatch is a labeling warning rather than a reason to refuse the analysis.
    if 'plates' in config and 'plates' in data_summary:
      config_plates = {str(plate) for plate in config['plates'].keys()}
      data_plates = {str(plate) for plate in data_summary['plates']}

      unmapped = sorted(data_plates - config_plates)
      matching_plates = sorted(config_plates & data_plates)
      if matching_plates:
        results.append(f"✅ Matching plates: {', '.join(matching_plates)}")
      missing_plates = sorted(config_plates - data_plates)
      if missing_plates:
        results.append(
          f"⚠️ Plate mapping(s) that do not occur in this data (ignored): "
          f"{', '.join(missing_plates)}"
        )
      if unmapped:
        consequence = ("their results will have a blank Species column"
                       if not config.get('experimental_conditions') else
                       "their results will have a blank Species column and any experimental "
                       "conditions keyed by another plate label will not apply")
        results.append(
          f"⚠️ Plate label(s) in the data without a species mapping: {', '.join(unmapped)} - "
          f"{consequence}. Add them on the Plates tab (copy the label exactly)."
        )

    # Check LED mappings
    if 'cytokines' in config and 'led_populations' in data_summary:
      config_leds = {str(led) for led in config['cytokines'].values() if led}
      data_leds = set(
        str(pop).replace(' Total', '') for pop in data_summary['led_populations']
        if ' Total' in str(pop)
      )

      missing_leds = sorted(config_leds - data_leds)
      if missing_leds:
        results.append(
          f"⚠️ LED channel(s) configured but not exported by this data: {', '.join(missing_leds)}"
          f" (available: {', '.join(sorted(data_leds)) or 'none'})"
        )

      matching_leds = sorted(config_leds & data_leds)
      if matching_leds:
        results.append(f"✅ Matching LEDs: {', '.join(matching_leds)}")
      elif not config.get('populations'):
        block("None of the configured LED channels are exported by this data, so the default "
              f"cytokine-Total endpoints do not exist here. Available channel totals: "
              f"{', '.join(sorted(data_leds)) or 'none'}. Fix the LED numbers on the Cytokines "
              "tab or pick populations on the Populations tab.")

    # Check selected populations exist in the data
    available = data_summary.get('population_labels')
    if config.get('populations') and available is not None:
      data_populations = {str(label) for label in available}
      selected = [str(label) for label in config['populations']]
      absent = [label for label in selected if label not in data_populations]
      present = [label for label in selected if label in data_populations]
      if present:
        results.append(f"✅ {len(present)} selected population(s) found in data")
      if absent and present:
        results.append(
          f"⚠️ Selected population(s) this data does not export are skipped, not scored as "
          f"negative: {', '.join(absent)}"
        )
      elif absent:
        block("None of the selected populations exist in this data, so the analysis would "
              f"produce no results. Selected: {', '.join(absent)}. Available: "
              f"{', '.join(sorted(data_populations)) or 'none'}. Choose populations on the "
              "Populations tab.")

    return not blocking, results, blocking
  
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