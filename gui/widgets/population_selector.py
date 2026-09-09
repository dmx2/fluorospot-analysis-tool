"""File-driven selection of exported FluoroSpot populations (endpoints)."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from populations import (
  MULTI_SCOPES,
  SCOPE_GROUP_TITLES,
  SCOPE_ORDER,
  SCOPE_TOTAL,
  PopulationInventory,
  friendly_label,
)


class PopulationSelectorWidget(ttk.Frame):
  """Checkbox selection of the populations a chosen export actually contains.

  Nothing is invented: checkboxes appear only for labels discovered in the data.
  Exact doubles/triples stay disabled until the channel-to-cytokine mapping is
  explicitly confirmed, because the export may carry no analyte metadata.
  """

  def __init__(self, parent, callback: Optional[Callable] = None):
    super().__init__(parent)
    self.callback = callback
    self.inventory: Optional[PopulationInventory] = None
    self.channel_names: Dict[str, str] = {}
    self.vars: Dict[str, tk.BooleanVar] = {}
    self.checkbuttons: Dict[str, ttk.Checkbutton] = {}
    self.pending_selection: Optional[List[str]] = None
    self.enabled = True
    self.dropped_labels: List[str] = []

    self.mapping_confirmed_var = tk.BooleanVar(value=False)
    self.setup_ui()

  # --- UI construction -------------------------------------------------
  def setup_ui(self):
    self.columnconfigure(0, weight=1)
    self.rowconfigure(2, weight=1)

    header = ttk.LabelFrame(self, text="Populations discovered in the selected data", padding="5")
    header.grid(row=0, column=0, sticky=(tk.W, tk.E))
    header.columnconfigure(0, weight=1)

    self.summary_label = ttk.Label(
      header,
      text="Select an input file or directory to discover the exported populations.",
      wraplength=760,
      justify=tk.LEFT,
    )
    self.summary_label.grid(row=0, column=0, sticky=tk.W)

    self.mapping_label = ttk.Label(header, text="", wraplength=760, justify=tk.LEFT,
                                   font=('TkDefaultFont', 8))
    self.mapping_label.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))

    self.mapping_check = ttk.Checkbutton(
      header,
      text="I confirm the cytokine \u2194 LED channel mapping on the Cytokines tab is correct for this data",
      variable=self.mapping_confirmed_var,
      command=self.on_mapping_confirmation_changed,
    )
    self.mapping_check.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))

    self.dropped_label = ttk.Label(header, text="", wraplength=760, justify=tk.LEFT,
                                   foreground='red', font=('TkDefaultFont', 8))
    self.dropped_label.grid(row=3, column=0, sticky=tk.W, pady=(4, 0))

    button_row = ttk.Frame(self)
    button_row.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(6, 4))

    self.select_multi_btn = ttk.Button(
      button_row,
      text="Select all available doubles and triples",
      command=self.select_all_multi,
      state='disabled',
    )
    self.select_multi_btn.grid(row=0, column=0, padx=(0, 8))

    self.totals_only_btn = ttk.Button(
      button_row,
      text="Totals only (default)",
      command=self.select_totals_only,
      state='disabled',
    )
    self.totals_only_btn.grid(row=0, column=1)

    canvas_frame = ttk.Frame(self)
    canvas_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    canvas_frame.columnconfigure(0, weight=1)
    canvas_frame.rowconfigure(0, weight=1)

    self.canvas = tk.Canvas(canvas_frame, height=240, highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
    self.list_frame = ttk.Frame(self.canvas)
    self.list_frame.bind(
      "<Configure>",
      lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    )
    self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
    self.canvas.configure(yscrollcommand=scrollbar.set)
    self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
    self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
    self.canvas.bind("<MouseWheel>",
                     lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

  # --- state -----------------------------------------------------------
  def set_channel_names(self, channel_names: Dict[str, str]):
    """Update LED -> cytokine names (from the Cytokines tab) and relabel."""
    if channel_names == self.channel_names:
      return
    self.channel_names = dict(channel_names)
    if self.inventory:
      self.rebuild(preserve_selection=True)

  def set_inventory(self, inventory: Optional[PopulationInventory],
                    channel_names: Optional[Dict[str, str]] = None):
    """Install a freshly discovered inventory for the selected input data."""
    self.inventory = inventory
    if channel_names is not None:
      self.channel_names = dict(channel_names)
    if inventory is not None and inventory.has_analyte_metadata:
      self.mapping_confirmed_var.set(True)
    self.rebuild(preserve_selection=True)

  def rebuild(self, preserve_selection: bool = False):
    previous = self.get_selected_labels() if preserve_selection else []
    if self.pending_selection is not None:
      previous = self.pending_selection

    # A saved selection of exact doubles/triples is itself an explicit confirmation
    if self.inventory and any(
      (self.inventory.get(label) and self.inventory.get(label).scope in MULTI_SCOPES)
      for label in previous
    ):
      self.mapping_confirmed_var.set(True)

    for child in self.list_frame.winfo_children():
      child.destroy()
    self.vars = {}
    self.checkbuttons = {}

    inventory = self.inventory
    if inventory is None or not inventory.populations:
      self.summary_label.configure(
        text="Select an input file or directory to discover the exported populations."
      )
      self.mapping_label.configure(text="")
      self.select_multi_btn.configure(state='disabled')
      self.totals_only_btn.configure(state='disabled')
      return

    self.summary_label.configure(text=(
      f"{len(inventory.populations)} population(s) exported; "
      f"channels detected: {', '.join(inventory.channels) or 'none'}. "
      "Each selected population is analyzed as its own endpoint with the same "
      "criterion; selecting a population does not make it positive."
    ))
    if inventory.has_analyte_metadata:
      pairs = ', '.join(f'{led}={analyte}' for led, analyte in sorted(inventory.analyte_metadata.items()))
      self.mapping_label.configure(
        text=f"Export analyte metadata found: {pairs}. Confirm it matches the Cytokines tab.",
        foreground='dark green',
      )
    else:
      self.mapping_label.configure(
        text=("This export carries no channel-to-cytokine metadata, so cytokine identity "
              "cannot be read from the file. Confirm the mapping to enable exact "
              "double/triple endpoints; LED numbers alone are not proof of cytokine identity."),
        foreground='dark orange',
      )

    row = 0
    for scope in SCOPE_ORDER:
      infos = inventory.by_scope(scope)
      if not infos:
        continue
      ttk.Label(self.list_frame, text=SCOPE_GROUP_TITLES[scope],
                font=('TkDefaultFont', 9, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=(8, 2))
      row += 1
      for info in infos:
        var = tk.BooleanVar(value=info.label in previous)
        text = self._entry_text(info)
        check = ttk.Checkbutton(self.list_frame, text=text, variable=var,
                                command=self.on_change)
        check.grid(row=row, column=0, sticky=tk.W, padx=(16, 0))
        self.vars[info.label] = var
        self.checkbuttons[info.label] = check
        row += 1

    if not previous:
      self.select_totals_only(notify=False)

    self.pending_selection = None
    self._report_dropped([label for label in previous if label not in self.vars])
    self.select_multi_btn.configure(state='normal' if inventory.multi_labels() else 'disabled')
    self.totals_only_btn.configure(state='normal')
    self.apply_gates()
    self.canvas.update_idletasks()
    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    self.on_change()

  def _entry_text(self, info) -> str:
    panel = self.inventory.channels if self.inventory else None
    if info.scope == SCOPE_TOTAL or self.mapping_confirmed_var.get():
      name = friendly_label(info.spec, self.channel_names, panel=panel)
    else:
      name = friendly_label(info.spec, {}, panel=panel)
    return f'{name}   [{info.label}]   {info.spec.scope_description} - {info.availability}'

  def apply_gates(self):
    """Disable endpoints that cannot honestly be offered."""
    confirmed = self.mapping_confirmed_var.get()
    for label, check in self.checkbuttons.items():
      info = self.inventory.get(label) if self.inventory else None
      reasons = []
      if info is not None and info.measured == 0:
        reasons.append('no measured counts')
      if info is not None and info.scope in MULTI_SCOPES and not confirmed:
        reasons.append('mapping not confirmed')
      if not self.enabled:
        reasons.append('busy')
      if reasons:
        if 'busy' not in reasons:
          self.vars[label].set(False)
        check.configure(state='disabled')
      else:
        check.configure(state='normal')
    self.select_multi_btn.configure(
      state='normal' if (self.enabled and confirmed and self.inventory
                         and self.inventory.multi_labels()) else 'disabled'
    )

  def on_mapping_confirmation_changed(self):
    self.rebuild(preserve_selection=True)

  def select_all_multi(self, notify: bool = True):
    """One-click: every exact double and triple the file actually contains."""
    if not self.inventory:
      return
    for label in self.inventory.multi_labels():
      info = self.inventory.get(label)
      if info and info.measured > 0 and self.mapping_confirmed_var.get():
        self.vars[label].set(True)
    if notify:
      self.on_change()

  def select_totals_only(self, notify: bool = True):
    """Restore the historical default: cytokine totals only."""
    if not self.inventory:
      return
    for label, var in self.vars.items():
      info = self.inventory.get(label)
      var.set(bool(info and info.scope == SCOPE_TOTAL and info.measured > 0))
    if notify:
      self.on_change()

  def get_selected_labels(self) -> List[str]:
    if self.pending_selection is not None:
      return list(self.pending_selection)
    if not self.inventory:
      return []
    return [info.label for info in self.inventory.populations
            if info.label in self.vars and self.vars[info.label].get()]

  def set_selected_labels(self, labels: Optional[List[str]]) -> List[str]:
    """Apply a saved selection; kept pending until a file is discovered.

    Returns the labels that the selected data does not contain; they are never
    silently analyzed as zero counts.
    """
    labels = [str(label) for label in (labels or [])]
    if not self.inventory:
      self.pending_selection = labels
      return []
    self.pending_selection = None
    dropped = [label for label in labels if label not in self.vars]
    if any(self.inventory.get(label) and self.inventory.get(label).scope in MULTI_SCOPES
           for label in labels):
      self.mapping_confirmed_var.set(True)
      self.apply_gates()
    for label, var in self.vars.items():
      var.set(label in labels)
    self._report_dropped(dropped)
    self.on_change()
    return dropped

  def _report_dropped(self, dropped: List[str]):
    """Show populations that were requested but are absent from this data."""
    self.dropped_labels = list(dropped)
    if dropped:
      self.dropped_label.configure(
        text=('Not available in this data and therefore not analyzed (no zero counts '
              'invented): ' + ', '.join(dropped))
      )
    else:
      self.dropped_label.configure(text='')

  def mapping_confirmed(self) -> bool:
    return bool(self.mapping_confirmed_var.get())

  def reset(self):
    self.inventory = None
    self.pending_selection = None
    self.mapping_confirmed_var.set(False)
    self.rebuild()

  def set_enabled(self, enabled: bool):
    self.enabled = enabled
    state = 'normal' if enabled else 'disabled'
    self.mapping_check.configure(state=state)
    self.totals_only_btn.configure(state=state if self.inventory else 'disabled')
    self.apply_gates()

  def on_change(self):
    if self.callback:
      self.callback(self.get_selected_labels())
