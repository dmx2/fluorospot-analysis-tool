"""File selection widget with drag-and-drop support."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os


class FileSelector(ttk.Frame):
  """Widget for selecting input files or directories with validation."""
  
  def __init__(self, parent, callback=None):
    super().__init__(parent)
    self.callback = callback
    self.selected_path = None
    self.is_directory = False
    
    self.setup_ui()
  
  def setup_ui(self):
    """Create the file selection interface."""
    # Frame for file selector
    selector_frame = ttk.LabelFrame(self, text="Data Input", padding="10")
    selector_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=0, pady=0)
    
    # Configure grid
    selector_frame.columnconfigure(1, weight=1)
    self.columnconfigure(0, weight=1)
    
    # Radio buttons for input type
    self.input_type = tk.StringVar(value="file")
    
    type_frame = ttk.Frame(selector_frame)
    type_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
    
    ttk.Label(type_frame, text="Input Type:").grid(row=0, column=0, padx=(0, 10))
    
    ttk.Radiobutton(
      type_frame, 
      text="Single Excel File", 
      variable=self.input_type, 
      value="file",
      command=self.on_input_type_changed
    ).grid(row=0, column=1, padx=(0, 15))
    
    ttk.Radiobutton(
      type_frame, 
      text="Directory of Files", 
      variable=self.input_type, 
      value="directory",
      command=self.on_input_type_changed
    ).grid(row=0, column=2)
    
    # File path display and selection
    ttk.Label(selector_frame, text="Selected:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
    
    self.path_var = tk.StringVar(value="No file selected")
    self.path_entry = ttk.Entry(
      selector_frame, 
      textvariable=self.path_var,
      state='readonly',
      width=50
    )
    self.path_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
    
    self.browse_btn = ttk.Button(
      selector_frame,
      text="Browse...",
      command=self.browse_for_file
    )
    self.browse_btn.grid(row=1, column=2)
    
    # Validation status
    self.status_frame = ttk.Frame(selector_frame)
    self.status_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    self.status_frame.columnconfigure(1, weight=1)
    
    self.status_icon = ttk.Label(self.status_frame, text="")
    self.status_icon.grid(row=0, column=0, padx=(0, 5))
    
    self.status_label = ttk.Label(self.status_frame, text="", foreground="gray")
    self.status_label.grid(row=0, column=1, sticky=tk.W)
    
  
  def on_input_type_changed(self):
    """Handle input type change (file vs directory)."""
    # Clear current selection when type changes
    self.clear_selection()
  
  def browse_for_file(self):
    """Open file/directory browser dialog."""
    input_type = self.input_type.get()
    
    if input_type == "file":
      # Browse for Excel file
      file_path = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[
          ("Excel files", "*.xlsx *.xls"),
          ("Excel 2007+", "*.xlsx"),
          ("Excel 97-2003", "*.xls"),
          ("All files", "*.*")
        ]
      )
      if file_path:
        self.set_selected_path(file_path, False)
    else:
      # Browse for directory
      dir_path = filedialog.askdirectory(
        title="Select Directory Containing Excel Files"
      )
      if dir_path:
        self.set_selected_path(dir_path, True)
  
  def set_selected_path(self, path, is_directory):
    """Set the selected file or directory path."""
    self.selected_path = Path(path)
    self.is_directory = is_directory
    self.path_var.set(str(path))
    
    # Validate the selection
    self.validate_selection()
    
    # Call callback if provided
    if self.callback:
      self.callback(str(path), is_directory)
  
  def validate_selection(self):
    """Validate the selected path."""
    if not self.selected_path:
      self.set_status("", "No file selected", "gray")
      return False
    
    try:
      if not self.selected_path.exists():
        self.set_status("❌", "Path does not exist", "red")
        return False
      
      if self.is_directory:
        # Validate directory contains Excel files
        excel_files = list(self.selected_path.glob("*.xlsx")) + list(self.selected_path.glob("*.xls"))
        if not excel_files:
          self.set_status("⚠️", f"No Excel files found in directory", "orange")
          return False
        else:
          self.set_status("✅", f"Directory contains {len(excel_files)} Excel file(s)", "green")
          return True
      else:
        # Validate single file
        if self.selected_path.suffix.lower() not in ['.xlsx', '.xls']:
          self.set_status("⚠️", "File is not an Excel file (.xlsx or .xls)", "orange")
          return False
        
        # Check file size
        try:
          file_size = self.selected_path.stat().st_size
          if file_size == 0:
            self.set_status("❌", "File is empty", "red")
            return False
          elif file_size > 100 * 1024 * 1024:  # 100MB limit
            self.set_status("⚠️", f"Large file ({file_size / (1024*1024):.1f} MB) - may take time to process", "orange")
            return True
          else:
            self.set_status("✅", f"Valid Excel file ({file_size / 1024:.0f} KB)", "green")
            return True
        except:
          self.set_status("❌", "Cannot read file", "red")
          return False
    
    except Exception as e:
      self.set_status("❌", f"Validation error: {str(e)}", "red")
      return False
  
  def set_status(self, icon, message, color):
    """Update the status display."""
    self.status_icon.config(text=icon)
    self.status_label.config(text=message, foreground=color)
  
  def get_selected_path(self):
    """Get the currently selected path and type."""
    if self.selected_path:
      return str(self.selected_path), self.is_directory
    return None, False
  
  def clear_selection(self):
    """Clear the current selection."""
    self.selected_path = None
    self.is_directory = False
    self.path_var.set("No file selected")
    self.set_status("", "No file selected", "gray")
  
  def reset(self):
    """Reset the widget to default state."""
    self.input_type.set("file")
    self.clear_selection()
    self.on_input_type_changed()
  
  def set_enabled(self, enabled):
    """Enable or disable the widget."""
    state = 'normal' if enabled else 'disabled'
    self.browse_btn.config(state=state)