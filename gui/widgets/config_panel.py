"""Configuration panel for FluoroSpot analysis settings."""

import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, Any, Callable, Optional
from pathlib import Path
import os

from gui.widgets.dynamic_lists import CytokineListWidget, PlateListWidget, ExperimentalConditionsWidget


class ConfigPanel(ttk.Frame):
  """Main configuration panel containing all analysis settings."""
  
  def __init__(self, parent, callback: Optional[Callable] = None):
    super().__init__(parent)
    self.callback = callback
    
    self.setup_ui()
    self.load_defaults()
  
  def setup_ui(self):
    """Create the configuration interface."""
    # Create notebook for tabbed interface
    self.notebook = ttk.Notebook(self)
    self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Configure grid
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)
    
    # Create tabs
    self.create_basic_settings_tab()
    self.create_mappings_tab()
    self.create_experimental_tab()
    self.create_output_tab()
  
  def create_basic_settings_tab(self):
    """Create the basic settings tab."""
    basic_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(basic_frame, text="Basic Settings")
    
    # Configure grid
    basic_frame.columnconfigure(1, weight=1)
    
    # Cells Plated Count
    ttk.Label(basic_frame, text="Cells Plated per Well:").grid(
      row=0, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 10)
    )
    self.sfc_count_var = tk.StringVar(value="200000")
    self.sfc_count_entry = ttk.Entry(basic_frame, textvariable=self.sfc_count_var, width=15)
    self.sfc_count_entry.grid(row=0, column=1, sticky=tk.W, pady=(0, 10))
    
    ttk.Label(basic_frame, text="(Total number of cells plated per well)", 
         font=('TkDefaultFont', 8), foreground='gray').grid(
      row=0, column=2, sticky=tk.W, padx=(10, 0), pady=(0, 10)
    )
    
    # SFC Cutoff
    ttk.Label(basic_frame, text="SFC Cutoff:").grid(
      row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 10)
    )
    self.sfc_cutoff_var = tk.StringVar(value="20")
    self.sfc_cutoff_entry = ttk.Entry(basic_frame, textvariable=self.sfc_cutoff_var, width=15)
    self.sfc_cutoff_entry.grid(row=1, column=1, sticky=tk.W, pady=(0, 10))
    
    ttk.Label(basic_frame, text="(Threshold for positivity criteria)", 
         font=('TkDefaultFont', 8), foreground='gray').grid(
      row=1, column=2, sticky=tk.W, padx=(10, 0), pady=(0, 10)
    )
    
    # Control Stimulus
    ttk.Label(basic_frame, text="Control Stimulus:").grid(
      row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 10)
    )
    self.control_stim_var = tk.StringVar(value="DMSO")
    self.control_stim_entry = ttk.Entry(basic_frame, textvariable=self.control_stim_var, width=15)
    self.control_stim_entry.grid(row=2, column=1, sticky=tk.W, pady=(0, 10))
    
    ttk.Label(basic_frame, text="(Name of control stimulus in your data)", 
         font=('TkDefaultFont', 8), foreground='gray').grid(
      row=2, column=2, sticky=tk.W, padx=(10, 0), pady=(0, 10)
    )
    
    # Validation indicators
    self.create_validation_indicators(basic_frame)
    
    # Bind validation events
    self.sfc_count_var.trace('w', lambda *args: self.validate_basic_settings())
    self.sfc_cutoff_var.trace('w', lambda *args: self.validate_basic_settings())
    self.control_stim_var.trace('w', lambda *args: self.validate_basic_settings())
  
  def create_validation_indicators(self, parent):
    """Create validation status indicators."""
    validation_frame = ttk.LabelFrame(parent, text="Validation Status", padding="5")
    validation_frame.grid(row=10, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(20, 0))
    validation_frame.columnconfigure(1, weight=1)
    
    # Cells Plated Count validation
    self.sfc_count_status = ttk.Label(validation_frame, text="")
    self.sfc_count_status.grid(row=0, column=0, padx=(0, 5))
    
    self.sfc_count_msg = ttk.Label(validation_frame, text="", font=('TkDefaultFont', 8))
    self.sfc_count_msg.grid(row=0, column=1, sticky=tk.W)
    
    # SFC Cutoff validation
    self.sfc_cutoff_status = ttk.Label(validation_frame, text="")
    self.sfc_cutoff_status.grid(row=1, column=0, padx=(0, 5))
    
    self.sfc_cutoff_msg = ttk.Label(validation_frame, text="", font=('TkDefaultFont', 8))
    self.sfc_cutoff_msg.grid(row=1, column=1, sticky=tk.W)
    
    # Control stimulus validation
    self.control_stim_status = ttk.Label(validation_frame, text="")
    self.control_stim_status.grid(row=2, column=0, padx=(0, 5))
    
    self.control_stim_msg = ttk.Label(validation_frame, text="", font=('TkDefaultFont', 8))
    self.control_stim_msg.grid(row=2, column=1, sticky=tk.W)
  
  def create_mappings_tab(self):
    """Create the mappings tab for cytokines and plates."""
    mappings_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(mappings_frame, text="Mappings")
    
    # Configure grid - give more weight to allow better space distribution
    mappings_frame.columnconfigure(0, weight=1)
    mappings_frame.rowconfigure(0, weight=1)
    mappings_frame.rowconfigure(1, weight=1)
    
    # Cytokine mappings
    self.cytokine_widget = CytokineListWidget(mappings_frame, self.on_config_changed)
    self.cytokine_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    
    # Plate mappings
    self.plate_widget = PlateListWidget(mappings_frame, self.on_config_changed)
    self.plate_widget.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
  
  def create_experimental_tab(self):
    """Create the experimental conditions tab."""
    exp_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(exp_frame, text="Experimental Conditions")
    
    # Configure grid
    exp_frame.columnconfigure(0, weight=1)
    exp_frame.rowconfigure(0, weight=1)
    
    # Experimental conditions widget
    self.experimental_widget = ExperimentalConditionsWidget(exp_frame, self.on_config_changed)
    self.experimental_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
  
  def create_output_tab(self):
    """Create the output settings tab."""
    output_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(output_frame, text="Output")
    
    # Configure grid
    output_frame.columnconfigure(1, weight=1)
    
    # Output directory
    ttk.Label(output_frame, text="Output Directory:").grid(
      row=0, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 10)
    )
    
    self.output_dir_var = tk.StringVar(value=str(Path.home() / "FluoroSpot_Results"))
    self.output_dir_entry = ttk.Entry(output_frame, textvariable=self.output_dir_var, width=40)
    self.output_dir_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(0, 10))
    
    self.browse_output_btn = ttk.Button(
      output_frame,
      text="Browse...",
      command=self.browse_output_directory
    )
    self.browse_output_btn.grid(row=0, column=2, pady=(0, 10))
    
    # Results filename
    ttk.Label(output_frame, text="Results Filename:").grid(
      row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 10)
    )
    
    self.results_filename_var = tk.StringVar(value="fluorospot-results.xlsx")
    self.results_filename_entry = ttk.Entry(output_frame, textvariable=self.results_filename_var, width=30)
    self.results_filename_entry.grid(row=1, column=1, sticky=tk.W, pady=(0, 10))
    
    ttk.Label(output_frame, text="(.xlsx will be added if not present)", 
         font=('TkDefaultFont', 8), foreground='gray').grid(
      row=1, column=2, sticky=tk.W, padx=(10, 0), pady=(0, 10)
    )
    
    # Output validation
    self.output_status = ttk.Label(output_frame, text="")
    self.output_status.grid(row=2, column=0, padx=(0, 5), pady=(10, 0))
    
    self.output_msg = ttk.Label(output_frame, text="", font=('TkDefaultFont', 8))
    self.output_msg.grid(row=2, column=1, sticky=tk.W, pady=(10, 0))
    
    # Bind validation
    self.output_dir_var.trace('w', lambda *args: self.validate_output_settings())
    self.results_filename_var.trace('w', lambda *args: self.validate_output_settings())
  
  def browse_output_directory(self):
    """Browse for output directory."""
    directory = filedialog.askdirectory(
      title="Select Output Directory",
      initialdir=self.output_dir_var.get()
    )
    if directory:
      self.output_dir_var.set(directory)
  
  def load_defaults(self):
    """Load default configuration values."""
    # Defaults are already set in the widget creation
    # Run initial validation
    self.validate_basic_settings()
    self.validate_output_settings()
  
  def validate_basic_settings(self):
    """Validate basic settings and update indicators."""
    valid = True
    
    # Validate SFC Count
    try:
      sfc_count = int(self.sfc_count_var.get())
      if sfc_count <= 0:
        raise ValueError("Must be positive")
      elif sfc_count < 1000:
        self.set_validation_status(self.sfc_count_status, self.sfc_count_msg, 
                     "⚠️", f"Low cell count ({sfc_count}). Consider using higher values.", "orange")
      else:
        self.set_validation_status(self.sfc_count_status, self.sfc_count_msg, 
                     "✅", f"Cells plated: {sfc_count:,}", "green")
    except ValueError:
      self.set_validation_status(self.sfc_count_status, self.sfc_count_msg, 
                   "❌", "Cell count must be a positive integer", "red")
      valid = False
    
    # Validate SFC Cutoff
    try:
      sfc_cutoff = int(self.sfc_cutoff_var.get())
      if sfc_cutoff < 0:
        raise ValueError("Cannot be negative")
      else:
        self.set_validation_status(self.sfc_cutoff_status, self.sfc_cutoff_msg, 
                     "✅", f"SFC cutoff: {sfc_cutoff}", "green")
    except ValueError:
      self.set_validation_status(self.sfc_cutoff_status, self.sfc_cutoff_msg, 
                   "❌", "SFC cutoff must be a non-negative integer", "red")
      valid = False
    
    # Validate Control Stimulus
    control_stim = self.control_stim_var.get().strip()
    if not control_stim:
      self.set_validation_status(self.control_stim_status, self.control_stim_msg, 
                   "❌", "Control stimulus name cannot be empty", "red")
      valid = False
    else:
      self.set_validation_status(self.control_stim_status, self.control_stim_msg, 
                   "✅", f"Control stimulus: '{control_stim}'", "green")
    
    self.on_config_changed()
    return valid
  
  def validate_output_settings(self):
    """Validate output settings."""
    valid = True
    
    # Validate output directory
    output_dir = Path(self.output_dir_var.get())
    try:
      # Check if parent directory exists (we can create the final directory)
      if not output_dir.parent.exists():
        self.set_validation_status(self.output_status, self.output_msg, 
                     "❌", "Parent directory does not exist", "red")
        valid = False
      elif not os.access(str(output_dir.parent), os.W_OK):
        self.set_validation_status(self.output_status, self.output_msg, 
                     "❌", "No write permission to parent directory", "red")
        valid = False
      else:
        self.set_validation_status(self.output_status, self.output_msg, 
                     "✅", f"Output will be saved to: {output_dir}", "green")
    except:
      self.set_validation_status(self.output_status, self.output_msg, 
                   "❌", "Invalid output directory path", "red")
      valid = False
    
    # Validate filename
    filename = self.results_filename_var.get().strip()
    if not filename:
      self.set_validation_status(self.output_status, self.output_msg, 
                   "❌", "Results filename cannot be empty", "red")
      valid = False
    elif not filename.endswith('.xlsx'):
      # Auto-add .xlsx extension
      corrected_filename = filename + '.xlsx'
      self.results_filename_var.set(corrected_filename)
    
    return valid
  
  def set_validation_status(self, status_label, msg_label, icon, message, color):
    """Set validation status for a field."""
    status_label.configure(text=icon)
    msg_label.configure(text=message, foreground=color)
  
  def on_config_changed(self, values=None):
    """Handle configuration changes."""
    if self.callback:
      try:
        config = self.get_configuration()
        self.callback(config)
      except:
        pass  # Ignore errors during intermediate states
  
  def get_configuration(self) -> Dict[str, Any]:
    """Get the current configuration as a dictionary."""
    config = {
      'sfc_count': int(self.sfc_count_var.get()),
      'sfc_cutoff': int(self.sfc_cutoff_var.get()),
      'control_stim': self.control_stim_var.get().strip(),
      'cytokines': self.cytokine_widget.get_cytokine_dict(),
      'plates': self.plate_widget.get_plate_dict(),
      'output_dir': self.output_dir_var.get().strip(),
      'results_filename': self.results_filename_var.get().strip()
    }
    
    # Add experimental conditions if enabled
    exp_conditions = self.experimental_widget.get_configuration()
    if exp_conditions:
      config['experimental_conditions'] = exp_conditions
    
    return config
  
  def set_configuration(self, config: Dict[str, Any]):
    """Set the configuration from a dictionary."""
    # Basic settings
    if 'sfc_count' in config:
      self.sfc_count_var.set(str(config['sfc_count']))
    if 'sfc_cutoff' in config:
      self.sfc_cutoff_var.set(str(config['sfc_cutoff']))
    if 'control_stim' in config:
      self.control_stim_var.set(config['control_stim'])
    
    # Mappings
    if 'cytokines' in config:
      self.cytokine_widget.set_cytokine_dict(config['cytokines'])
    if 'plates' in config:
      self.plate_widget.set_plate_dict(config['plates'])
    
    # Experimental conditions
    if 'experimental_conditions' in config:
      self.experimental_widget.set_configuration(config['experimental_conditions'])
    else:
      self.experimental_widget.reset()
    
    # Output settings
    if 'output_dir' in config:
      self.output_dir_var.set(config['output_dir'])
    if 'results_filename' in config:
      self.results_filename_var.set(config['results_filename'])
    
    # Revalidate
    self.validate_basic_settings()
    self.validate_output_settings()
  
  def validate_all(self) -> bool:
    """Validate all configuration settings."""
    basic_valid = self.validate_basic_settings()
    output_valid = self.validate_output_settings()
    
    # Check cytokines and plates have entries
    cytokines = self.cytokine_widget.get_cytokine_dict()
    plates = self.plate_widget.get_plate_dict()
    
    if not cytokines:
      return False
    if not plates:
      return False
    
    return basic_valid and output_valid
  
  def reset(self):
    """Reset all configuration to default values."""
    # Reset basic settings
    self.sfc_count_var.set("200000")
    self.sfc_cutoff_var.set("20")
    self.control_stim_var.set("DMSO")
    
    # Reset mappings
    self.cytokine_widget.reset()
    self.plate_widget.reset()
    
    # Reset experimental conditions
    self.experimental_widget.reset()
    
    # Reset output settings
    self.output_dir_var.set(str(Path.home() / "FluoroSpot_Results"))
    self.results_filename_var.set("fluorospot-results.xlsx")
    
    # Revalidate
    self.validate_basic_settings()
    self.validate_output_settings()
  
  def set_enabled(self, enabled: bool):
    """Enable or disable all configuration controls."""
    state = 'normal' if enabled else 'disabled'
    
    # Basic settings
    self.sfc_count_entry.configure(state=state)
    self.sfc_cutoff_entry.configure(state=state)
    self.control_stim_entry.configure(state=state)
    
    # Mappings
    self.cytokine_widget.set_enabled(enabled)
    self.plate_widget.set_enabled(enabled)
    
    # Experimental conditions
    self.experimental_widget.set_enabled(enabled)
    
    # Output settings
    self.output_dir_entry.configure(state=state)
    self.results_filename_entry.configure(state=state)
    self.browse_output_btn.configure(state=state)