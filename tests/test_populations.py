"""Tests for exported-population discovery, labeling and endpoint resolution."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent))

from populations import (  # noqa: E402
  SCOPE_EXACT_DOUBLE,
  SCOPE_EXACT_TRIPLE,
  SCOPE_SINGLE,
  SCOPE_TOTAL,
  SCOPE_UNKNOWN,
  discover_populations,
  friendly_label,
  merge_inventories,
  parse_population_label,
  resolve_endpoints,
)

SAMPLE_FILE = Path(__file__).parent / 'test_plate.xlsx'


def make_df(labels, sfu=None, stimuli=None):
  rows = len(labels)
  return pd.DataFrame({
    'Layout-Donor': ['D1'] * rows,
    'Plate': ['plate_1'] * rows,
    'Layout-Stimuli': stimuli if stimuli is not None else ['DMSO'] * rows,
    'Spot Forming Units (SFU)': sfu if sfu is not None else [1] * rows,
    'Analyte Secreting Population': labels,
  })


class TestLabelParsing:
  @pytest.mark.parametrize('label,scope,channels', [
    ('LED490 Total', SCOPE_TOTAL, ('LED490',)),
    ('LED490 Single', SCOPE_SINGLE, ('LED490',)),
    ('LED490+LED550', SCOPE_EXACT_DOUBLE, ('LED490', 'LED550')),
    ('LED490+LED550+LED640', SCOPE_EXACT_TRIPLE, ('LED490', 'LED550', 'LED640')),
  ])
  def test_exported_labels_are_classified(self, label, scope, channels):
    spec = parse_population_label(label)
    assert spec.scope == scope
    assert spec.channels == channels

  @pytest.mark.parametrize('label', ['Total', 'IFNg Total', 'LED490+LED490', 'anything else'])
  def test_unrecognized_labels_stay_unclassified(self, label):
    spec = parse_population_label(label)
    assert spec.scope == SCOPE_UNKNOWN
    assert spec.channels == ()
    # An unknown label is never renamed or guessed at
    assert friendly_label(spec, {'LED490': 'IFNg'}) == label

  def test_friendly_label_uses_only_confirmed_mapping(self):
    spec = parse_population_label('LED490+LED550')
    # LED550 unmapped: it keeps its raw channel identity, no inference from wavelength
    assert friendly_label(spec, {'LED490': 'IFNg'}) == 'IFNg + LED550 only'
    assert friendly_label(spec, {}) == 'LED490 + LED550 only'

  def test_exactness_is_relative_to_the_measured_panel(self):
    spec = parse_population_label('LED490+LED550')
    label = friendly_label(spec, {'LED490': 'IFNg', 'LED550': 'IL-10', 'LED640': 'IL-17'},
                           panel=['LED490', 'LED550', 'LED640'])
    assert label == 'IFNg + IL-10 only - excludes IL-17'


class TestDiscovery:
  def test_missing_counts_are_not_zeros(self):
    df = make_df(
      ['LED490 Total', 'LED490 Total', 'LED490+LED550', 'LED490+LED550'],
      sfu=[5, np.nan, 0, np.nan],
    )
    inventory = discover_populations(df)
    total = inventory.get('LED490 Total')
    pair = inventory.get('LED490+LED550')

    assert (total.rows, total.measured, total.missing) == (2, 1, 1)
    assert (pair.rows, pair.measured, pair.missing, pair.nonzero) == (2, 1, 1, 0)
    assert 'missing' in pair.availability

  def test_channels_and_metadata_absence(self):
    inventory = discover_populations(make_df(['LED490 Total', 'LED550+LED640']))
    assert inventory.channels == ['LED490', 'LED550', 'LED640']
    assert inventory.has_analyte_metadata is False

  def test_analyte_metadata_is_used_when_explicit(self):
    df = make_df(['LED490 Total', 'LED550 Total'])
    df['LED Filter'] = ['LED490', 'LED550']
    df['Layout-Analyte'] = ['IFN-g', 'IL-10']
    inventory = discover_populations(df)
    assert inventory.has_analyte_metadata is True
    assert inventory.analyte_metadata == {'LED490': 'IFN-g', 'LED550': 'IL-10'}

  def test_merge_reports_populations_absent_from_some_files(self):
    first = discover_populations(make_df(['LED490 Total', 'LED490+LED550']))
    second = discover_populations(make_df(['LED490 Total']))
    merged = merge_inventories([first, second])

    total = merged.get('LED490 Total')
    pair = merged.get('LED490+LED550')
    assert total.files_present == 2 and total.files_total == 2
    assert pair.files_present == 1
    assert 'absent from 1 of 2 files' in pair.availability

  @pytest.mark.skipif(not SAMPLE_FILE.exists(), reason='sample export not available')
  def test_real_sample_export_inventory(self):
    df = pd.read_excel(SAMPLE_FILE, sheet_name=1, engine='openpyxl')
    inventory = discover_populations(df)

    assert inventory.labels == [
      'LED490 Total', 'LED550 Total', 'LED640 Total',
      'LED490 Single', 'LED550 Single', 'LED640 Single',
      'LED490+LED550', 'LED490+LED640', 'LED550+LED640',
      'LED490+LED550+LED640',
    ]
    assert inventory.multi_labels() == [
      'LED490+LED550', 'LED490+LED640', 'LED550+LED640', 'LED490+LED550+LED640'
    ]
    # Six wells have no SFU value at all: missing, not zero
    assert all(info.missing == 6 and info.measured == 90 for info in inventory.populations)
    assert inventory.has_analyte_metadata is False


class TestEndpointResolution:
  def test_default_is_one_total_per_cytokine(self):
    endpoints, problems = resolve_endpoints({'IFNg': 'LED490', 'IL-10': 'LED550'})
    assert [(e.name, e.label) for e in endpoints] == [
      ('IFNg', 'LED490 Total'), ('IL-10', 'LED550 Total')
    ]
    assert problems == []

  def test_selected_populations_replace_the_default(self):
    endpoints, problems = resolve_endpoints(
      {'IFNg': 'LED490', 'IL-10': 'LED550'},
      populations=['LED490+LED550'],
      available_labels=['LED490 Total', 'LED490+LED550'],
    )
    assert [(e.name, e.label, e.scope) for e in endpoints] == [
      ('IFNg + IL-10 only', 'LED490+LED550', SCOPE_EXACT_DOUBLE)
    ]
    assert problems == []

  def test_unavailable_population_is_rejected_not_zeroed(self):
    endpoints, problems = resolve_endpoints(
      {'IFNg': 'LED490'},
      populations=['LED490 Total', 'LED490+LED700'],
      available_labels=['LED490 Total'],
    )
    assert [e.label for e in endpoints] == ['LED490 Total']
    assert len(problems) == 1
    assert 'LED490+LED700' in problems[0]

  def test_duplicate_selection_analyzed_once(self):
    endpoints, _ = resolve_endpoints(
      {'IFNg': 'LED490'}, populations=['LED490 Total', 'LED490 Total']
    )
    assert len(endpoints) == 1
