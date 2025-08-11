"""Dynamic list widgets with add/remove functionality."""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any, Callable, Optional


class DynamicListWidget(ttk.Frame):
  """Base class for dynamic list widgets with add/remove buttons."""
  
  def __init__(self, parent, title: str, columns: List[str], callback: Optional[Callable] = None):
    super().__init__(parent)
    self.title = title
    self.columns = columns
    self.callback = callback
    self.entries = []
    
    self.setup_ui()
  
  def setup_ui(self):
    """Create the UI for the dynamic list."""
    # Main frame
    main_frame = ttk.LabelFrame(self, text=self.title, padding="5")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Configure grid
    main_frame.columnconfigure(0, weight=1)
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)
    
    # Headers
    header_frame = ttk.Frame(main_frame)
    header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
    
    for i, column in enumerate(self.columns):
      ttk.Label(header_frame, text=column, font=('TkDefaultFont', 9, 'bold')).grid(
        row=0, column=i, padx=(0, 10), sticky=tk.W
      )
    
    # Scrollable frame for entries
    self.create_scrollable_frame(main_frame)
    
    # Add button
    add_btn = ttk.Button(main_frame, text="+ Add", command=self.add_entry)
    add_btn.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
  
  def create_scrollable_frame(self, parent):
    """Create a scrollable frame for the entries."""
    # Canvas and scrollbar for scrolling
    canvas_frame = ttk.Frame(parent)
    canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
    canvas_frame.columnconfigure(0, weight=1)
    canvas_frame.rowconfigure(0, weight=1)
    
    self.canvas = tk.Canvas(canvas_frame, height=120)  # Fixed height
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
    
    self.scrollable_frame = ttk.Frame(self.canvas)
    self.scrollable_frame.bind(
      "<Configure>",
      lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    )
    
    self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
    self.canvas.configure(yscrollcommand=scrollbar.set)
    
    self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Bind mousewheel to canvas
    self.canvas.bind("<MouseWheel>", self._on_mousewheel)
    self.canvas.bind("<Button-4>", self._on_mousewheel)
    self.canvas.bind("<Button-5>", self._on_mousewheel)
  
  def _on_mousewheel(self, event):
    """Handle mouse wheel scrolling."""
    if event.num == 4 or event.delta > 0:
      self.canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
      self.canvas.yview_scroll(1, "units")
  
  def add_entry(self, values: Optional[List[str]] = None):
    """Add a new entry row."""
    row_frame = ttk.Frame(self.scrollable_frame)
    row_frame.grid(row=len(self.entries), column=0, sticky=(tk.W, tk.E), pady=1)
    row_frame.columnconfigure(len(self.columns), weight=1)  # Make the last column expandable
    
    entry_widgets = []
    
    for i, column in enumerate(self.columns):
      entry = ttk.Entry(row_frame, width=15)
      entry.grid(row=0, column=i, padx=(0, 10), sticky=(tk.W, tk.E))
      
      # Set default value if provided
      if values and i < len(values):
        entry.insert(0, values[i])
      
      # Bind change event
      entry.bind('<KeyRelease>', lambda e: self.on_change())
      entry_widgets.append(entry)
    
    # Remove button
    remove_btn = ttk.Button(
      row_frame, 
      text="✕", 
      width=3,
      command=lambda idx=len(self.entries): self.remove_entry(idx)
    )
    remove_btn.grid(row=0, column=len(self.columns), padx=(10, 0))
    
    self.entries.append({
      'frame': row_frame,
      'entries': entry_widgets,
      'remove_btn': remove_btn
    })
    
    self.update_remove_buttons()
    self.update_canvas()
  
  def remove_entry(self, index: int):
    """Remove an entry at the specified index."""
    if 0 <= index < len(self.entries):
      # Destroy the widgets
      self.entries[index]['frame'].destroy()
      
      # Remove from list
      self.entries.pop(index)
      
      # Re-grid remaining entries and update remove button commands
      for i, entry in enumerate(self.entries):
        entry['frame'].grid(row=i, column=0, sticky=(tk.W, tk.E), pady=1)
        entry['remove_btn'].configure(command=lambda idx=i: self.remove_entry(idx))
      
      self.update_remove_buttons()
      self.update_canvas()
      self.on_change()
  
  def update_remove_buttons(self):
    """Update remove button states."""
    # Always enable remove buttons for dynamic lists
    for entry in self.entries:
      entry['remove_btn'].configure(state='normal')
  
  def update_canvas(self):
    """Update the canvas scroll region."""
    self.canvas.update_idletasks()
    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
  
  def on_change(self):
    """Called when any entry value changes."""
    # Check if we need to add a new empty entry
    self.ensure_empty_entry()
    
    if self.callback:
      self.callback(self.get_values())
  
  def ensure_empty_entry(self):
    """Ensure there's always one empty entry at the end for adding new items."""
    # Check if the last entry is empty
    if self.entries:
      last_entry = self.entries[-1]
      last_values = [entry.get().strip() for entry in last_entry['entries']]
      
      # If the last entry is not empty, add a new empty one
      if any(val for val in last_values):
        self.add_entry()
    else:
      # If no entries exist, add one empty entry
      self.add_entry()
  
  def get_values(self) -> List[List[str]]:
    """Get all entry values."""
    values = []
    for entry_data in self.entries:
      row_values = [entry.get().strip() for entry in entry_data['entries']]
      # Only include non-empty rows
      if any(val for val in row_values):
        values.append(row_values)
    return values
  
  def set_values(self, values: List[List[str]]):
    """Set the values for the list."""
    # Clear existing entries
    self.clear()
    
    # Add new entries
    for value_row in values:
      self.add_entry(value_row)
    
    # Ensure at least one empty entry
    if not self.entries:
      self.add_entry()
  
  def clear(self):
    """Clear all entries."""
    for entry_data in self.entries:
      entry_data['frame'].destroy()
    self.entries = []
  
  def reset(self):
    """Reset to default state with one empty entry."""
    self.clear()
    self.add_entry()
  
  def set_enabled(self, enabled: bool):
    """Enable or disable all entries."""
    state = 'normal' if enabled else 'disabled'
    for entry_data in self.entries:
      for entry in entry_data['entries']:
        entry.configure(state=state)
      entry_data['remove_btn'].configure(state=state)


class CytokineListWidget(DynamicListWidget):
  """Widget for managing cytokine to LED mappings."""
  
  def __init__(self, parent, callback: Optional[Callable] = None):
    super().__init__(parent, "Cytokine Mappings", ["Cytokine Name", "LED Number"], callback)
    
    # Add default entries
    self.add_default_entries()
  
  def add_default_entries(self):
    """Add default cytokine entries."""
    defaults = [
      ["IFNg", "LED490"],
      ["IL-10", "LED550"],
      ["IL-17", "LED640"]
    ]
    
    for default in defaults:
      self.add_entry(default)
    
    # Add one empty entry for adding new cytokines
    self.add_entry()
  
  def get_cytokine_dict(self) -> Dict[str, str]:
    """Get cytokine mappings as a dictionary."""
    result = {}
    for row in self.get_values():
      if len(row) >= 2 and row[0] and row[1]:
        result[row[0]] = row[1]
    return result
  
  def set_cytokine_dict(self, cytokines: Dict[str, str]):
    """Set cytokine mappings from a dictionary."""
    values = [[name, led] for name, led in cytokines.items()]
    self.set_values(values)


class PlateListWidget(DynamicListWidget):
  """Widget for managing plate to species mappings."""
  
  def __init__(self, parent, callback: Optional[Callable] = None):
    super().__init__(parent, "Plate Mappings", ["Plate ID", "Species"], callback)
    
    # Add default entry
    self.add_entry(["plate_1", "S. pneumoniae"])
    
    # Add one empty entry for adding new plates
    self.add_entry()
  
  def get_plate_dict(self) -> Dict[str, str]:
    """Get plate mappings as a dictionary."""
    result = {}
    for row in self.get_values():
      if len(row) >= 2 and row[0] and row[1]:
        result[row[0]] = row[1]
    return result
  
  def set_plate_dict(self, plates: Dict[str, str]):
    """Set plate mappings from a dictionary."""
    values = [[plate_id, species] for plate_id, species in plates.items()]
    self.set_values(values)


class ExperimentalConditionsWidget(ttk.Frame):
  """Complex widget for managing experimental conditions."""
  
  def __init__(self, parent, callback: Optional[Callable] = None):
    super().__init__(parent)
    self.callback = callback
    self.conditions = {}  # plate_id -> {group_name: {control: str, stimuli: List[str]}}
    
    self.setup_ui()
  
  def setup_ui(self):
    """Create the experimental conditions UI."""
    main_frame = ttk.LabelFrame(self, text="Experimental Conditions (Optional)", padding="5")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Configure grid
    main_frame.columnconfigure(0, weight=1)
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)
    
    # Enable checkbox
    self.enabled_var = tk.BooleanVar()
    self.enable_cb = ttk.Checkbutton(
      main_frame,
      text="Enable experimental conditions",
      variable=self.enabled_var,
      command=self.toggle_enabled
    )
    self.enable_cb.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
    
    # Warning label
    warning_label = ttk.Label(
      main_frame,
      text="⚠️ Use this only for plates with multiple control/stimuli groups. Names must EXACTLY match the data.",
      foreground="orange",
      font=('TkDefaultFont', 8)
    )
    warning_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
    
    # Conditions frame (scrollable)
    self.conditions_frame = ttk.Frame(main_frame)
    self.conditions_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    self.conditions_frame.columnconfigure(0, weight=1)
    
    # Initially disabled
    self.toggle_enabled()
  
  def toggle_enabled(self):
    """Toggle the experimental conditions section."""
    enabled = self.enabled_var.get()
    
    # Clear existing widgets
    for widget in self.conditions_frame.winfo_children():
      widget.destroy()
    
    if enabled:
      self.create_conditions_interface()
    
    if self.callback:
      self.callback()
  
  def create_conditions_interface(self):
    """Create the interface for managing conditions."""
    # Instructions
    instructions = ttk.Label(
      self.conditions_frame,
      text="Add plates and their experimental groups. Each group needs one control and one or more stimuli.",
      font=('TkDefaultFont', 8),
      foreground="gray"
    )
    instructions.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
    
    # Scrollable canvas for plates
    canvas_frame = ttk.Frame(self.conditions_frame)
    canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    canvas_frame.columnconfigure(0, weight=1)
    canvas_frame.rowconfigure(0, weight=1)
    
    self.canvas = tk.Canvas(canvas_frame, height=200)
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
    
    self.scrollable_frame = ttk.Frame(self.canvas)
    self.scrollable_frame.bind(
      "<Configure>",
      lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    )
    
    self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
    self.canvas.configure(yscrollcommand=scrollbar.set)
    
    self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Add plate button
    add_plate_btn = ttk.Button(
      self.conditions_frame,
      text="+ Add Plate",
      command=self.add_plate
    )
    add_plate_btn.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    
    # Add default plate if none exist
    if not self.conditions:
      self.add_plate()
  
  def add_plate(self, plate_id: str = "plate_1"):
    """Add a new plate configuration."""
    plate_frame = ttk.LabelFrame(self.scrollable_frame, text=f"Plate: {plate_id}", padding="5")
    plate_frame.grid(row=len(self.conditions), column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
    plate_frame.columnconfigure(0, weight=1)
    
    # Plate ID entry
    id_frame = ttk.Frame(plate_frame)
    id_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    
    ttk.Label(id_frame, text="Plate ID:").grid(row=0, column=0, padx=(0, 5))
    
    plate_id_var = tk.StringVar(value=plate_id)
    plate_id_entry = ttk.Entry(id_frame, textvariable=plate_id_var, width=20)
    plate_id_entry.grid(row=0, column=1, padx=(0, 10))
    
    # Remove plate button
    remove_plate_btn = ttk.Button(
      id_frame,
      text="Remove Plate",
      command=lambda: self.remove_plate(plate_id)
    )
    remove_plate_btn.grid(row=0, column=2)
    
    # Groups frame
    groups_frame = ttk.Frame(plate_frame)
    groups_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
    groups_frame.columnconfigure(0, weight=1)
    
    # Add group button
    add_group_btn = ttk.Button(
      plate_frame,
      text="+ Add Group",
      command=lambda: self.add_group(plate_id, groups_frame)
    )
    add_group_btn.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    
    # Initialize plate data
    self.conditions[plate_id] = {
      'frame': plate_frame,
      'id_var': plate_id_var,
      'groups_frame': groups_frame,
      'groups': {},
      'add_btn': add_group_btn,
      'remove_btn': remove_plate_btn
    }
    
    # Bind plate ID changes
    plate_id_var.trace('w', lambda *args: self.on_plate_id_changed(plate_id, plate_id_var.get()))
    
    # Add default group
    self.add_group(plate_id, groups_frame)
    
    self.update_canvas()
  
  def remove_plate(self, plate_id: str):
    """Remove a plate configuration."""
    if plate_id in self.conditions:
      self.conditions[plate_id]['frame'].destroy()
      del self.conditions[plate_id]
      self.reindex_plates()
      self.update_canvas()
      if self.callback:
        self.callback()
  
  def add_group(self, plate_id: str, groups_frame: ttk.Frame):
    """Add a new experimental group to a plate."""
    if plate_id not in self.conditions:
      return
    
    groups = self.conditions[plate_id]['groups']
    group_name = f"group_{len(groups) + 1}"
    
    group_frame = ttk.LabelFrame(groups_frame, text=f"Group: {group_name}", padding="5")
    group_frame.grid(row=len(groups), column=0, sticky=(tk.W, tk.E), pady=2)
    group_frame.columnconfigure(1, weight=1)
    
    # Group name
    ttk.Label(group_frame, text="Group Name:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
    group_name_var = tk.StringVar(value=group_name)
    group_name_entry = ttk.Entry(group_frame, textvariable=group_name_var, width=20)
    group_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
    
    # Control
    ttk.Label(group_frame, text="Control:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
    control_var = tk.StringVar(value="DMSO")
    control_entry = ttk.Entry(group_frame, textvariable=control_var, width=20)
    control_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
    
    # Stimuli
    ttk.Label(group_frame, text="Stimuli:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
    
    stimuli_frame = ttk.Frame(group_frame)
    stimuli_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
    stimuli_frame.columnconfigure(0, weight=1)
    
    stimuli_vars = []
    
    def add_stimulus():
      stimulus_var = tk.StringVar()
      stimulus_entry = ttk.Entry(stimuli_frame, textvariable=stimulus_var, width=20)
      stimulus_entry.grid(row=len(stimuli_vars), column=0, sticky=(tk.W, tk.E), pady=1)
      stimuli_vars.append(stimulus_var)
      return stimulus_var
    
    # Add default stimuli
    add_stimulus().set("stimulus_1")
    add_stimulus().set("stimulus_2")
    
    add_stimulus_btn = ttk.Button(stimuli_frame, text="+ Add Stimulus", command=add_stimulus)
    add_stimulus_btn.grid(row=100, column=0, sticky=tk.W, pady=(5, 0))
    
    # Remove group button
    remove_group_btn = ttk.Button(
      group_frame,
      text="Remove Group",
      command=lambda: self.remove_group(plate_id, group_name)
    )
    remove_group_btn.grid(row=0, column=2, padx=(10, 0))
    
    # Store group data
    groups[group_name] = {
      'frame': group_frame,
      'name_var': group_name_var,
      'control_var': control_var,
      'stimuli_vars': stimuli_vars,
      'stimuli_frame': stimuli_frame,
      'add_stimulus_btn': add_stimulus_btn,
      'remove_btn': remove_group_btn
    }
    
    self.update_canvas()
  
  def remove_group(self, plate_id: str, group_name: str):
    """Remove an experimental group."""
    if plate_id in self.conditions and group_name in self.conditions[plate_id]['groups']:
      group_data = self.conditions[plate_id]['groups'][group_name]
      group_data['frame'].destroy()
      del self.conditions[plate_id]['groups'][group_name]
      self.reindex_groups(plate_id)
      self.update_canvas()
      if self.callback:
        self.callback()
  
  def reindex_plates(self):
    """Reindex plate positions."""
    for i, (plate_id, plate_data) in enumerate(self.conditions.items()):
      plate_data['frame'].grid(row=i, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
  
  def reindex_groups(self, plate_id: str):
    """Reindex group positions for a plate."""
    if plate_id in self.conditions:
      groups = self.conditions[plate_id]['groups']
      for i, (group_name, group_data) in enumerate(groups.items()):
        group_data['frame'].grid(row=i, column=0, sticky=(tk.W, tk.E), pady=2)
  
  def on_plate_id_changed(self, old_id: str, new_id: str):
    """Handle plate ID changes."""
    if old_id != new_id and old_id in self.conditions:
      # Update internal references
      self.conditions[new_id] = self.conditions.pop(old_id)
      # Update label
      self.conditions[new_id]['frame'].configure(text=f"Plate: {new_id}")
      
      if self.callback:
        self.callback()
  
  def update_canvas(self):
    """Update the canvas scroll region."""
    if hasattr(self, 'canvas'):
      self.canvas.update_idletasks()
      self.canvas.configure(scrollregion=self.canvas.bbox("all"))
  
  def get_configuration(self) -> Dict[str, Any]:
    """Get the experimental conditions configuration."""
    if not self.enabled_var.get():
      return {}
    
    result = {}
    for plate_id, plate_data in self.conditions.items():
      current_plate_id = plate_data['id_var'].get()
      if current_plate_id:
        plate_config = {}
        for group_name, group_data in plate_data['groups'].items():
          current_group_name = group_data['name_var'].get()
          if current_group_name:
            control = group_data['control_var'].get()
            stimuli = [var.get() for var in group_data['stimuli_vars'] if var.get()]
            
            if control and stimuli:
              plate_config[current_group_name] = {
                'control': control,
                'stimuli': stimuli
              }
        
        if plate_config:
          result[current_plate_id] = plate_config
    
    return result
  
  def set_configuration(self, config: Dict[str, Any]):
    """Set the experimental conditions configuration."""
    if not config:
      self.enabled_var.set(False)
      self.toggle_enabled()
      return
    
    self.enabled_var.set(True)
    self.toggle_enabled()
    
    # Clear existing conditions
    self.conditions.clear()
    
    # Add plates from config
    for plate_id, plate_config in config.items():
      self.add_plate(plate_id)
      
      # Clear default group
      plate_data = self.conditions[plate_id]
      for group_name in list(plate_data['groups'].keys()):
        self.remove_group(plate_id, group_name)
      
      # Add groups from config
      for group_name, group_config in plate_config.items():
        groups_frame = plate_data['groups_frame']
        self.add_group(plate_id, groups_frame)
        
        # Set group data
        group_data = list(plate_data['groups'].values())[-1]
        group_data['name_var'].set(group_name)
        group_data['control_var'].set(group_config['control'])
        
        # Set stimuli
        stimuli = group_config['stimuli']
        for i, stimulus in enumerate(stimuli):
          if i < len(group_data['stimuli_vars']):
            group_data['stimuli_vars'][i].set(stimulus)
          else:
            # Add more stimulus entries if needed
            new_var = self.add_stimulus_to_group(group_data)
            new_var.set(stimulus)
  
  def add_stimulus_to_group(self, group_data):
    """Add a stimulus entry to an existing group."""
    stimulus_var = tk.StringVar()
    stimuli_frame = group_data['stimuli_frame']
    stimulus_entry = ttk.Entry(stimuli_frame, textvariable=stimulus_var, width=20)
    stimulus_entry.grid(row=len(group_data['stimuli_vars']), column=0, sticky=(tk.W, tk.E), pady=1)
    group_data['stimuli_vars'].append(stimulus_var)
    
    # Move the add button
    group_data['add_stimulus_btn'].grid(row=len(group_data['stimuli_vars']), column=0, sticky=tk.W, pady=(5, 0))
    
    return stimulus_var
  
  def reset(self):
    """Reset to default state."""
    self.enabled_var.set(False)
    self.toggle_enabled()
  
  def set_enabled(self, enabled: bool):
    """Enable or disable the widget."""
    state = 'normal' if enabled else 'disabled'
    self.enable_cb.configure(state=state)
    
    # Disable all child widgets if disabled
    if not enabled:
      for widget in self.conditions_frame.winfo_children():
        self._disable_widget_recursive(widget)
  
  def _disable_widget_recursive(self, widget):
    """Recursively disable a widget and its children."""
    try:
      widget.configure(state='disabled')
    except:
      pass
    
    for child in widget.winfo_children():
      self._disable_widget_recursive(child)