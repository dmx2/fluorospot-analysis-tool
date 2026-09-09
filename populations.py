"""Shared discovery, classification and labeling of exported FluoroSpot populations.

One module used by the CLI analyzer, the GUI and the validators so that
discovery, label parsing and endpoint resolution can never disagree.

Semantics of the Mabtech Apex export labels (see report_fluorospot_design.md):
  'LEDx Total'                -> that channel with or without other channels
                                 (co-secretors included)
  'LEDx Single'               -> that channel only
  'LEDx+LEDy'                 -> exact double secretors (third channel absent)
  'LEDx+LEDy+LEDz'            -> exact triple secretors
Exact populations are mutually exclusive; Totals overlap them. Overlapping
populations are never summed here - each selected population is analyzed as its
own endpoint.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import re

import pandas as pd

POPULATION_COLUMN = 'Analyte Secreting Population'
SFU_COLUMN = 'Spot Forming Units (SFU)'
ANALYTE_COLUMN = 'Layout-Analyte'

LED_PATTERN = re.compile(r'^LED\d{3}$')

SCOPE_TOTAL = 'total'
SCOPE_SINGLE = 'single'
SCOPE_EXACT_DOUBLE = 'exact_double'
SCOPE_EXACT_TRIPLE = 'exact_triple'
SCOPE_EXACT_MULTI = 'exact_multi'
SCOPE_UNKNOWN = 'unknown'

SCOPE_DESCRIPTIONS = {
  SCOPE_TOTAL: 'Total (includes co-secretors)',
  SCOPE_SINGLE: 'Single-secretors only',
  SCOPE_EXACT_DOUBLE: 'Exact double-secretors',
  SCOPE_EXACT_TRIPLE: 'Exact triple-secretors',
  SCOPE_EXACT_MULTI: 'Exact multi-secretors',
  SCOPE_UNKNOWN: 'Unclassified population label',
}

SCOPE_GROUP_TITLES = {
  SCOPE_TOTAL: 'Cytokine totals (include co-secretors)',
  SCOPE_SINGLE: 'Single-secretors only',
  SCOPE_EXACT_DOUBLE: 'Exact doubles',
  SCOPE_EXACT_TRIPLE: 'Exact triples',
  SCOPE_EXACT_MULTI: 'Exact multi-secretors',
  SCOPE_UNKNOWN: 'Unrecognized populations',
}

SCOPE_ORDER = [SCOPE_TOTAL, SCOPE_SINGLE, SCOPE_EXACT_DOUBLE,
               SCOPE_EXACT_TRIPLE, SCOPE_EXACT_MULTI, SCOPE_UNKNOWN]

MULTI_SCOPES = (SCOPE_EXACT_DOUBLE, SCOPE_EXACT_TRIPLE, SCOPE_EXACT_MULTI)


@dataclass(frozen=True)
class PopulationSpec:
  """A parsed population label exactly as exported."""
  label: str
  channels: Tuple[str, ...]
  scope: str

  @property
  def is_exact(self) -> bool:
    return self.scope in (SCOPE_SINGLE,) + MULTI_SCOPES

  @property
  def scope_description(self) -> str:
    return SCOPE_DESCRIPTIONS.get(self.scope, SCOPE_DESCRIPTIONS[SCOPE_UNKNOWN])


def parse_population_label(label: str) -> PopulationSpec:
  """Classify one exported population label. Never guesses cytokine identity."""
  text = str(label).strip()

  suffix_scopes = ((' Total', SCOPE_TOTAL), (' Single', SCOPE_SINGLE))
  for suffix, scope in suffix_scopes:
    if text.endswith(suffix):
      channel = text[: -len(suffix)].strip()
      if LED_PATTERN.match(channel):
        return PopulationSpec(text, (channel,), scope)
      return PopulationSpec(text, (), SCOPE_UNKNOWN)

  if '+' in text:
    parts = [part.strip() for part in text.split('+')]
    if all(LED_PATTERN.match(part) for part in parts) and len(set(parts)) == len(parts):
      scope = {2: SCOPE_EXACT_DOUBLE, 3: SCOPE_EXACT_TRIPLE}.get(len(parts), SCOPE_EXACT_MULTI)
      return PopulationSpec(text, tuple(parts), scope)

  return PopulationSpec(text, (), SCOPE_UNKNOWN)


def friendly_label(
  spec: PopulationSpec,
  channel_names: Optional[Dict[str, str]] = None,
  panel: Optional[Sequence[str]] = None,
) -> str:
  """Readable endpoint name. Unmapped channels keep their raw LED identity.

  When the measured `panel` is supplied, exact multi-secretor labels state which
  measured channels are excluded - exactness is relative to the measured panel.
  """
  names = channel_names or {}
  if not spec.channels:
    return spec.label
  parts = [names.get(channel, channel) for channel in spec.channels]

  if spec.scope == SCOPE_TOTAL:
    return parts[0]
  if spec.scope == SCOPE_SINGLE:
    label = f'{parts[0]} only'
  elif spec.scope in MULTI_SCOPES:
    label = ' + '.join(parts) + ' only'
  else:
    return spec.label

  if panel:
    excluded = [names.get(channel, channel) for channel in panel if channel not in spec.channels]
    if excluded:
      label += ' - excludes ' + ', '.join(excluded)
  return label


def channel_names_from_cytokines(cytokines: Optional[Dict[str, str]]) -> Dict[str, str]:
  """Invert the configured cytokine->LED mapping into LED->cytokine."""
  mapping: Dict[str, str] = {}
  for cytokine, led in (cytokines or {}).items():
    if cytokine and led:
      mapping[str(led).strip()] = str(cytokine).strip()
  return mapping


@dataclass
class PopulationInfo:
  """Availability of one exported population in an inspected file."""
  spec: PopulationSpec
  rows: int = 0
  measured: int = 0
  missing: int = 0
  nonzero: int = 0
  files_present: int = 1
  files_total: int = 1

  @property
  def label(self) -> str:
    return self.spec.label

  @property
  def scope(self) -> str:
    return self.spec.scope

  @property
  def availability(self) -> str:
    if self.rows == 0:
      text = 'not exported'
    elif self.measured == 0:
      text = 'exported, all counts missing'
    elif self.missing:
      text = f'{self.measured} measured, {self.missing} missing'
    else:
      text = f'{self.measured} measured'
    if self.files_total > 1 and self.files_present < self.files_total:
      text += f'; absent from {self.files_total - self.files_present} of {self.files_total} files'
    return text


@dataclass
class PopulationInventory:
  """What an export actually contains - no invented populations."""
  populations: List[PopulationInfo] = field(default_factory=list)
  channels: List[str] = field(default_factory=list)
  analyte_metadata: Dict[str, str] = field(default_factory=dict)
  has_analyte_metadata: bool = False

  @property
  def labels(self) -> List[str]:
    return [info.label for info in self.populations]

  def by_scope(self, scope: str) -> List[PopulationInfo]:
    return [info for info in self.populations if info.scope == scope]

  def get(self, label: str) -> Optional[PopulationInfo]:
    for info in self.populations:
      if info.label == label:
        return info
    return None

  def multi_labels(self) -> List[str]:
    """Every exact double/triple present in the file, in export order."""
    return [info.label for info in self.populations if info.scope in MULTI_SCOPES]

  def total_labels(self) -> List[str]:
    return [info.label for info in self.populations if info.scope == SCOPE_TOTAL]


def discover_populations(df: pd.DataFrame) -> PopulationInventory:
  """Discover the populations actually present in a loaded plate DataFrame."""
  inventory = PopulationInventory()
  if POPULATION_COLUMN not in df.columns:
    return inventory

  labels = [str(label) for label in df[POPULATION_COLUMN].dropna().unique()]
  specs = [parse_population_label(label) for label in labels]
  specs.sort(key=lambda spec: (SCOPE_ORDER.index(spec.scope), spec.channels, spec.label))

  values = None
  if SFU_COLUMN in df.columns:
    values = pd.to_numeric(df[SFU_COLUMN], errors='coerce')

  channels: List[str] = []
  for spec in specs:
    mask = df[POPULATION_COLUMN].astype(str) == spec.label
    info = PopulationInfo(spec=spec, rows=int(mask.sum()))
    if values is not None:
      population_values = values[mask]
      info.measured = int(population_values.notna().sum())
      info.missing = int(population_values.isna().sum())
      info.nonzero = int((population_values.fillna(0) > 0).sum())
    inventory.populations.append(info)
    for channel in spec.channels:
      if channel not in channels:
        channels.append(channel)

  inventory.channels = sorted(channels)

  if ANALYTE_COLUMN in df.columns and 'LED Filter' in df.columns:
    pairs = df[[ 'LED Filter', ANALYTE_COLUMN]].dropna()
    for led, analyte in pairs.itertuples(index=False):
      led_text, analyte_text = str(led).strip(), str(analyte).strip()
      if led_text and analyte_text:
        inventory.analyte_metadata.setdefault(led_text, analyte_text)
  inventory.has_analyte_metadata = bool(inventory.analyte_metadata)

  return inventory


def merge_inventories(inventories: Sequence[PopulationInventory]) -> PopulationInventory:
  """Combine per-file inventories, keeping cross-file availability visible."""
  present = [inv for inv in inventories if inv.populations]
  if not present:
    return PopulationInventory()
  if len(present) == 1:
    return present[0]

  merged = PopulationInventory()
  total_files = len(present)
  by_label: Dict[str, PopulationInfo] = {}
  for inventory in present:
    for info in inventory.populations:
      existing = by_label.get(info.label)
      if existing is None:
        by_label[info.label] = PopulationInfo(
          spec=info.spec, rows=info.rows, measured=info.measured,
          missing=info.missing, nonzero=info.nonzero,
          files_present=1, files_total=total_files,
        )
      else:
        existing.rows += info.rows
        existing.measured += info.measured
        existing.missing += info.missing
        existing.nonzero += info.nonzero
        existing.files_present += 1
    for led, analyte in inventory.analyte_metadata.items():
      merged.analyte_metadata.setdefault(led, analyte)

  merged.populations = sorted(
    by_label.values(),
    key=lambda info: (SCOPE_ORDER.index(info.scope), info.spec.channels, info.label),
  )
  channels: List[str] = []
  for info in merged.populations:
    for channel in info.spec.channels:
      if channel not in channels:
        channels.append(channel)
  merged.channels = sorted(channels)
  merged.has_analyte_metadata = bool(merged.analyte_metadata)
  return merged


@dataclass(frozen=True)
class Endpoint:
  """One population to analyze: readable name plus the exact exported label."""
  name: str
  label: Optional[str] = None
  scope: str = SCOPE_UNKNOWN

  @property
  def scope_description(self) -> str:
    return SCOPE_DESCRIPTIONS.get(self.scope, SCOPE_DESCRIPTIONS[SCOPE_UNKNOWN])


def default_population_labels(cytokines: Optional[Dict[str, str]]) -> List[str]:
  """Existing default endpoints: one Total per configured cytokine."""
  labels = []
  for cytokine, led in (cytokines or {}).items():
    if cytokine and led:
      labels.append(f'{str(led).strip()} Total')
  return labels


def resolve_endpoints(
  cytokines: Optional[Dict[str, str]],
  populations: Optional[Sequence[str]] = None,
  available_labels: Optional[Sequence[str]] = None,
) -> Tuple[List[Endpoint], List[str]]:
  """Turn configuration into endpoints, rejecting populations the data lacks.

  Returns (endpoints, problems). Missing populations are reported as problems and
  dropped - they are never analyzed as zero counts.
  """
  channel_names = channel_names_from_cytokines(cytokines)
  requested = [str(label).strip() for label in (populations or []) if str(label).strip()]
  if not requested:
    requested = default_population_labels(cytokines)

  available = None if available_labels is None else {str(label) for label in available_labels}

  endpoints: List[Endpoint] = []
  problems: List[str] = []
  seen = set()

  for label in requested:
    if label in seen:
      continue
    seen.add(label)
    spec = parse_population_label(label)
    if available is not None and label not in available:
      problems.append(f"Population '{label}' is not present in the data and was skipped "
                      f"(missing data is not reported as a negative response).")
      continue
    endpoints.append(Endpoint(
      name=friendly_label(spec, channel_names),
      label=label,
      scope=spec.scope,
    ))

  return endpoints, problems
