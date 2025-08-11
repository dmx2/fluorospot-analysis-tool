#!/usr/bin/env python3
"""
FluoroSpot Analysis GUI - Main Application

A user-friendly interface for bench scientists to analyze FluoroSpot data
without requiring command-line knowledge.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
from pathlib import Path
import threading
import queue
import os

try:
  from .widgets.file_selector import FileSelector
  from .widgets.config_panel import ConfigPanel
  from .widgets.progress_dialog import ProgressDialog
  from .core.gui_controller import GUIController
  from .core.config_builder import ConfigBuilder
except ImportError:
  # Fallback for direct execution - add gui directory to path
  import sys
  from pathlib import Path
  gui_dir = Path(__file__).parent
  sys.path.insert(0, str(gui_dir))
  
  from widgets.file_selector import FileSelector
  from widgets.config_panel import ConfigPanel
  from widgets.progress_dialog import ProgressDialog
  from core.gui_controller import GUIController
  from core.config_builder import ConfigBuilder


class FluoroSpotGUI:
  """Main application window for FluoroSpot analysis."""
  
  def __init__(self):
    self.root = tk.Tk()
    self.root.title("FluoroSpot Analysis Tool")
    self.root.geometry("900x700")
    self.root.minsize(800, 600)
    
    # Initialize components
    self.controller = GUIController()
    self.config_builder = ConfigBuilder()
    self.progress_dialog = None
    
    # Validation state tracking
    self.file_has_critical_errors = False
    self.file_has_warnings = False
    self.config_has_critical_errors = False
    self.config_has_warnings = False
    
    # Message queue for thread communication
    self.message_queue = queue.Queue()
    
    self.setup_ui()
    self.setup_menu()
    self.center_window()
    
    # Start message queue processor
    self.process_messages()
  
  def setup_ui(self):
    """Create the main user interface."""
    # Create main container with padding
    main_frame = ttk.Frame(self.root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Configure grid weights for resizing
    self.root.columnconfigure(0, weight=1)
    self.root.rowconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=1)
    main_frame.rowconfigure(2, weight=1)
    
    # Header section
    self.create_header(main_frame)
    
    # File input section
    self.file_selector = FileSelector(main_frame, self.on_file_selected)
    self.file_selector.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    
    # Configuration panel (scrollable)
    self.config_panel = ConfigPanel(main_frame, self.on_config_changed)
    self.config_panel.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    
    # Action buttons
    self.create_action_buttons(main_frame)
    
    # Status panel
    self.create_status_panel(main_frame)
  
  def create_header(self, parent):
    """Create the application header."""
    header_frame = ttk.Frame(parent)
    header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
    
    title_label = ttk.Label(
      header_frame, 
      text="FluoroSpot Analysis Tool",
      font=('TkDefaultFont', 16, 'bold')
    )
    title_label.grid(row=0, column=0, sticky=tk.W)
    
    description_label = ttk.Label(
      header_frame,
      text="Analyze Mabtech FluoroSpot data with statistical analysis and export results.",
      font=('TkDefaultFont', 10)
    )
    description_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
  
  def create_action_buttons(self, parent):
    """Create the action buttons."""
    button_frame = ttk.Frame(parent)
    button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    # Configure button frame
    button_frame.columnconfigure(0, weight=1)
    
    # Button container for centering
    button_container = ttk.Frame(button_frame)
    button_container.grid(row=0, column=0)
    
    self.validate_btn = ttk.Button(
      button_container,
      text="Validate Configuration",
      command=self.validate_configuration,
      width=20
    )
    self.validate_btn.grid(row=0, column=0, padx=(0, 10))
    
    self.run_btn = ttk.Button(
      button_container,
      text="Run Analysis",
      command=self.run_analysis,
      width=15,
      style='Accent.TButton'
    )
    self.run_btn.grid(row=0, column=1, padx=(0, 10))
    
    self.reset_btn = ttk.Button(
      button_container,
      text="Reset",
      command=self.reset_form,
      width=10
    )
    self.reset_btn.grid(row=0, column=2)
  
  def create_status_panel(self, parent):
    """Create the status display panel."""
    status_frame = ttk.LabelFrame(parent, text="Status", padding="5")
    status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
    status_frame.columnconfigure(0, weight=1)
    status_frame.rowconfigure(0, weight=1)
    
    # Status text with scrollbar
    text_frame = ttk.Frame(status_frame)
    text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    text_frame.columnconfigure(0, weight=1)
    text_frame.rowconfigure(0, weight=1)
    
    self.status_text = tk.Text(
      text_frame,
      height=6,
      wrap=tk.WORD,
      state=tk.DISABLED,
      bg=self.root.cget('bg')
    )
    
    scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.status_text.yview)
    self.status_text.configure(yscrollcommand=scrollbar.set)
    
    self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Progress bar
    self.progress_var = tk.DoubleVar()
    self.progress_bar = ttk.Progressbar(
      status_frame,
      variable=self.progress_var,
      maximum=100
    )
    self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
    self.add_status_message("Ready to analyze FluoroSpot data.")
  
  def setup_menu(self):
    """Create the application menu."""
    menubar = tk.Menu(self.root)
    self.root.config(menu=menubar)
    
    # File menu
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Save Configuration...", command=self.save_configuration)
    file_menu.add_command(label="Load Configuration...", command=self.load_configuration)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=self.root.quit)
    
    # Help menu
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=self.show_about)
  
  def center_window(self):
    """Center the window on the screen."""
    self.root.update_idletasks()
    width = self.root.winfo_width()
    height = self.root.winfo_height()
    x = (self.root.winfo_screenwidth() // 2) - (width // 2)
    y = (self.root.winfo_screenheight() // 2) - (height // 2)
    self.root.geometry(f'{width}x{height}+{x}+{y}')
  
  # Event handlers
  def on_file_selected(self, file_path, is_directory):
    """Handle file selection."""
    self.add_status_message(f"Selected {'directory' if is_directory else 'file'}: {file_path}")
    
    # Validate the selected file/directory with detailed messages
    has_critical_errors, has_warnings, results = self.controller.validate_input_path(file_path, is_directory)
    
    # Display all validation results
    for result in results:
      if result.startswith("✅"):
        self.add_status_message(result, "success")
      elif result.startswith("⚠️"):
        self.add_status_message(result, "warning")
      elif result.startswith("❌"):
        self.add_status_message(result, "error")
      else:
        self.add_status_message(result, "info")
    
    # Store validation state for later use
    self.file_has_critical_errors = has_critical_errors
    self.file_has_warnings = has_warnings
    
    if has_critical_errors:
      self.add_status_message("❌ Critical errors found in input file. Cannot run analysis.", "error")
    elif has_warnings:
      self.add_status_message("⚠️ Warnings found in input file. You can still try to run analysis.", "warning")
    else:
      self.add_status_message("✅ Input file validation passed.", "success")
  
  def on_config_changed(self, config_data):
    """Handle configuration changes."""
    # Real-time validation could be added here
    pass
  
  def validate_configuration(self):
    """Validate the current configuration without running analysis."""
    try:
      config_data = self.config_panel.get_configuration()
      file_path, is_directory = self.file_selector.get_selected_path()
      
      if not file_path:
        self.add_status_message("❌ Please select an input file or directory.", "error")
        return
      
      # Validate configuration with detailed messages
      has_critical_errors, has_warnings, results = self.controller.validate_configuration(config_data, file_path, is_directory)
      
      # Display all validation results
      for result in results:
        if result.startswith("✅"):
          self.add_status_message(result, "success")
        elif result.startswith("⚠️"):
          self.add_status_message(result, "warning")
        elif result.startswith("❌"):
          self.add_status_message(result, "error")
        elif result.startswith("📁"):
          self.add_status_message(result, "info")
        else:
          self.add_status_message(result, "info")
      
      # Store validation state for later use
      self.config_has_critical_errors = has_critical_errors
      self.config_has_warnings = has_warnings
      
      # Update UI based on validation results
      file_has_critical_errors = getattr(self, 'file_has_critical_errors', False)
      overall_critical_errors = has_critical_errors or file_has_critical_errors
      overall_warnings = has_warnings or getattr(self, 'file_has_warnings', False)
      
      if overall_critical_errors:
        self.add_status_message("❌ Critical errors found. Cannot run analysis until resolved.", "error")
        self.run_btn.config(state='disabled')
      elif overall_warnings:
        self.add_status_message("⚠️ Warnings found, but you can still try to run analysis.", "warning")
        self.run_btn.config(state='normal')
      else:
        self.add_status_message("✅ Configuration validation passed. Ready to run analysis.", "success")
        self.run_btn.config(state='normal')
        
    except Exception as e:
      self.add_status_message(f"❌ Validation error: {str(e)}", "error")
  
  def run_analysis(self):
    """Run the FluoroSpot analysis in a background thread."""
    try:
      config_data = self.config_panel.get_configuration()
      file_path, is_directory = self.file_selector.get_selected_path()
      
      if not file_path:
        self.add_status_message("❌ Please select an input file or directory.", "error")
        return
      
      
      # Disable UI during analysis
      self.set_ui_state(False)
      self.progress_var.set(0)
      self.add_status_message("🚀 Starting FluoroSpot analysis...", "info")
      
      # Run analysis in background thread
      analysis_thread = threading.Thread(
        target=self.controller.run_analysis,
        args=(config_data, file_path, is_directory, self.message_queue),
        daemon=True
      )
      analysis_thread.start()
      
    except Exception as e:
      self.add_status_message(f"❌ Failed to start analysis: {str(e)}", "error")
      self.set_ui_state(True)
  
  def reset_form(self):
    """Reset the form to default values."""
    if messagebox.askyesno("Reset Form", "Are you sure you want to reset all settings to default values?"):
      self.file_selector.reset()
      self.config_panel.reset()
      self.progress_var.set(0)
      self.status_text.config(state=tk.NORMAL)
      self.status_text.delete(1.0, tk.END)
      self.status_text.config(state=tk.DISABLED)
      self.add_status_message("Form reset to default values.")
      self.run_btn.config(state='disabled')
  
  def save_configuration(self):
    """Save current configuration to a YAML file."""
    try:
      config_data = self.config_panel.get_configuration()
      filename = filedialog.asksaveasfilename(
        title="Save Configuration",
        defaultextension=".yaml",
        filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
      )
      if filename:
        self.config_builder.save_config(config_data, filename)
        self.add_status_message(f"✅ Configuration saved to {filename}", "success")
    except Exception as e:
      self.add_status_message(f"❌ Failed to save configuration: {str(e)}", "error")
  
  def load_configuration(self):
    """Load configuration from a YAML file."""
    try:
      filename = filedialog.askopenfilename(
        title="Load Configuration",
        filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
      )
      if filename:
        config_data = self.config_builder.load_config(filename)
        self.config_panel.set_configuration(config_data)
        self.add_status_message(f"✅ Configuration loaded from {filename}", "success")
    except Exception as e:
      self.add_status_message(f"❌ Failed to load configuration: {str(e)}", "error")
  
  def show_about(self):
    """Show the about dialog."""
    about_text = """FluoroSpot Analysis Tool v1.0.0

A user-friendly interface for analyzing Mabtech FluoroSpot data.

Developed by the IEDB Tools Team
For support, please contact the development team."""
    
    messagebox.showinfo("About", about_text)
  
  # Utility methods
  def add_status_message(self, message, level="info"):
    """Add a status message to the status panel with appropriate styling."""
    self.status_text.config(state=tk.NORMAL)
    
    # Add timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}\n"
    
    # Configure tag colors if not already configured
    if not hasattr(self, '_tags_configured'):
      self.status_text.tag_configure("success", foreground="green")
      self.status_text.tag_configure("error", foreground="red")
      self.status_text.tag_configure("warning", foreground="orange")
      self.status_text.tag_configure("info", foreground="black")
      self._tags_configured = True
    
    # Insert message with appropriate tag
    start_idx = self.status_text.index(tk.END)
    self.status_text.insert(tk.END, full_message)
    end_idx = self.status_text.index(tk.END)
    
    # Apply tag to the message
    if level in ["success", "error", "warning", "info"]:
      self.status_text.tag_add(level, start_idx, end_idx)
    
    self.status_text.see(tk.END)
    self.status_text.config(state=tk.DISABLED)
    
    # Update the UI
    self.root.update_idletasks()
  
  def set_ui_state(self, enabled):
    """Enable or disable UI elements during analysis."""
    state = 'normal' if enabled else 'disabled'
    self.validate_btn.config(state=state)
    self.run_btn.config(state=state)
    self.reset_btn.config(state=state)
    self.file_selector.set_enabled(enabled)
    self.config_panel.set_enabled(enabled)
  
  def process_messages(self):
    """Process messages from the analysis thread."""
    try:
      while True:
        message = self.message_queue.get_nowait()
        msg_type = message.get('type', 'info')
        content = message.get('content', '')
        
        if msg_type == 'progress':
          self.progress_var.set(message.get('value', 0))
        elif msg_type == 'status':
          self.add_status_message(content, message.get('level', 'info'))
        elif msg_type == 'complete':
          self.analysis_complete(message.get('success', False), content)
        elif msg_type == 'error':
          self.analysis_error(content)
          
    except queue.Empty:
      pass
    finally:
      # Schedule next check
      self.root.after(100, self.process_messages)
  
  def analysis_complete(self, success, result_path):
    """Handle analysis completion."""
    self.set_ui_state(True)
    self.progress_var.set(100)
    
    if success:
      self.add_status_message(f"✅ Analysis completed successfully! Results saved to: {result_path}", "success")
      
      # Ask if user wants to open the results folder
      if messagebox.askyesno("Analysis Complete", 
                   f"Analysis completed successfully!\n\nResults saved to:\n{result_path}\n\nWould you like to open the results folder?"):
        try:
          import subprocess
          import platform
          
          if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(Path(result_path).parent)])
          elif platform.system() == "Windows":
            subprocess.run(["explorer", str(Path(result_path).parent)])
          else:  # Linux
            subprocess.run(["xdg-open", str(Path(result_path).parent)])
        except:
          pass  # Silently fail if can't open folder
    else:
      self.add_status_message("❌ Analysis failed. Please check the error messages above.", "error")
  
  def analysis_error(self, error_message):
    """Handle analysis error."""
    self.set_ui_state(True)
    self.add_status_message(f"❌ Analysis error: {error_message}", "error")
    messagebox.showerror("Analysis Error", f"An error occurred during analysis:\n\n{error_message}")
  
  def run(self):
    """Start the GUI application."""
    self.root.mainloop()


def main():
  """Main entry point for the application."""
  try:
    # Check Python version
    if sys.version_info < (3, 7):
      messagebox.showerror("Python Version Error", 
                 "This application requires Python 3.7 or higher.\n"
                 f"Current version: {sys.version}")
      return
    
    # Create and run the application
    app = FluoroSpotGUI()
    app.run()
    
  except Exception as e:
    messagebox.showerror("Application Error", f"Failed to start the application:\n\n{str(e)}")


if __name__ == "__main__":
  main()