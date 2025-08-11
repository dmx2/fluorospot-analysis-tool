"""Progress dialog for showing analysis progress and results."""

import tkinter as tk
from tkinter import ttk
from typing import Optional


class ProgressDialog:
  """Dialog for showing analysis progress."""
  
  def __init__(self, parent, title: str = "Analysis Progress"):
    self.parent = parent
    self.title = title
    self.dialog = None
    self.progress_var = None
    self.status_text = None
    self.cancel_callback = None
    self.is_cancelled = False
  
  def show(self, cancel_callback: Optional[callable] = None):
    """Show the progress dialog."""
    self.cancel_callback = cancel_callback
    self.is_cancelled = False
    
    # Create dialog window
    self.dialog = tk.Toplevel(self.parent)
    self.dialog.title(self.title)
    self.dialog.geometry("500x300")
    self.dialog.resizable(False, False)
    self.dialog.transient(self.parent)
    self.dialog.grab_set()
    
    # Center the dialog
    self.center_dialog()
    
    # Create UI
    self.setup_ui()
    
    # Prevent closing with X button if analysis is running
    self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
    
    # Store reference to title label for updates
    self.title_label = None
  
  def setup_ui(self):
    """Create the progress dialog UI."""
    main_frame = ttk.Frame(self.dialog, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Configure grid
    self.dialog.columnconfigure(0, weight=1)
    self.dialog.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    
    # Title
    self.title_label = ttk.Label(
      main_frame,
      text="FluoroSpot Analysis in Progress...",
      font=('TkDefaultFont', 12, 'bold')
    )
    self.title_label.grid(row=0, column=0, pady=(0, 20))
    
    # Status text area
    text_frame = ttk.Frame(main_frame)
    text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
    text_frame.columnconfigure(0, weight=1)
    text_frame.rowconfigure(0, weight=1)
    
    self.status_text = tk.Text(
      text_frame,
      wrap=tk.WORD,
      state=tk.DISABLED,
      height=10,
      font=('TkDefaultFont', 9)
    )
    
    scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.status_text.yview)
    self.status_text.configure(yscrollcommand=scrollbar.set)
    
    self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Progress bar
    progress_frame = ttk.Frame(main_frame)
    progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
    progress_frame.columnconfigure(0, weight=1)
    
    ttk.Label(progress_frame, text="Progress:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
    
    self.progress_var = tk.DoubleVar()
    self.progress_bar = ttk.Progressbar(
      progress_frame,
      variable=self.progress_var,
      maximum=100,
      length=400
    )
    self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
    
    self.progress_label = ttk.Label(progress_frame, text="0%")
    self.progress_label.grid(row=1, column=1, padx=(10, 0))
    
    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=3, column=0)
    
    self.cancel_btn = ttk.Button(
      button_frame,
      text="Cancel",
      command=self.cancel_analysis
    )
    self.cancel_btn.grid(row=0, column=0, padx=(0, 10))
    
    self.close_btn = ttk.Button(
      button_frame,
      text="Close",
      command=self.close_dialog,
      state='disabled'
    )
    self.close_btn.grid(row=0, column=1)
    
    # Initial status
    self.add_status_message("Initializing analysis...")
  
  def center_dialog(self):
    """Center the dialog on the parent window."""
    self.dialog.update_idletasks()
    
    # Get parent window position and size
    parent_x = self.parent.winfo_x()
    parent_y = self.parent.winfo_y()
    parent_width = self.parent.winfo_width()
    parent_height = self.parent.winfo_height()
    
    # Get dialog size
    dialog_width = self.dialog.winfo_reqwidth()
    dialog_height = self.dialog.winfo_reqheight()
    
    # Calculate center position
    x = parent_x + (parent_width // 2) - (dialog_width // 2)
    y = parent_y + (parent_height // 2) - (dialog_height // 2)
    
    self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
  
  def add_status_message(self, message: str):
    """Add a status message to the text area."""
    if self.status_text:
      self.status_text.config(state=tk.NORMAL)
      
      # Add timestamp
      from datetime import datetime
      timestamp = datetime.now().strftime("%H:%M:%S")
      full_message = f"[{timestamp}] {message}\n"
      
      self.status_text.insert(tk.END, full_message)
      self.status_text.see(tk.END)
      self.status_text.config(state=tk.DISABLED)
      
      # Update the dialog
      self.dialog.update_idletasks()
  
  def update_progress(self, value: float, status: str = ""):
    """Update the progress bar and optional status."""
    if self.progress_var:
      self.progress_var.set(value)
      self.progress_label.config(text=f"{value:.0f}%")
      
      if status:
        self.add_status_message(status)
      
      self.dialog.update_idletasks()
  
  def set_completed(self, success: bool, message: str = ""):
    """Mark the analysis as completed."""
    if success:
      self.progress_var.set(100)
      self.progress_label.config(text="100%")
      self.add_status_message("✅ Analysis completed successfully!")
      if message:
        self.add_status_message(message)
    else:
      self.add_status_message("❌ Analysis failed!")
      if message:
        self.add_status_message(f"Error: {message}")
    
    # Enable close button, disable cancel
    self.close_btn.config(state='normal')
    self.cancel_btn.config(state='disabled')
    
    # Change title
    title_text = "Analysis Complete" if success else "Analysis Failed"
    if self.title_label:
      self.title_label.config(text=title_text)
  
  def cancel_analysis(self):
    """Cancel the analysis."""
    if self.cancel_callback and not self.is_cancelled:
      self.is_cancelled = True
      self.cancel_btn.config(state='disabled')
      self.add_status_message("🚫 Cancelling analysis...")
      
      # Call the cancel callback
      self.cancel_callback()
  
  def close_dialog(self):
    """Close the progress dialog."""
    if self.dialog:
      self.dialog.grab_release()
      self.dialog.destroy()
      self.dialog = None
  
  def on_close(self):
    """Handle window close button."""
    # Only allow closing if analysis is complete
    if self.close_btn and self.close_btn['state'] == 'normal':
      self.close_dialog()
    else:
      # Ask if user wants to cancel
      from tkinter import messagebox
      result = messagebox.askyesno(
        "Cancel Analysis",
        "Analysis is still running. Do you want to cancel it?",
        parent=self.dialog
      )
      if result:
        self.cancel_analysis()
  
  def get_cancelled_status(self) -> bool:
    """Check if the analysis was cancelled."""
    return self.is_cancelled