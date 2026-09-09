"""Tests for GUI configuration handling of population endpoints."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent))

from gui.core.config_builder import ConfigBuilder  # noqa: E402
from gui.validation.config_validator import ConfigValidator  # noqa: E402
from gui.validation.data_validator import DataValidator  # noqa: E402
from populations import discover_populations  # noqa: E402

BASE_CONFIG = {
  'cells_per_well': 200000,
  'sfc_cutoff': 20,
  'control_stim': 'DMSO',
  'cytokines': {'IFNg': 'LED490', 'IL-10': 'LED550'},
  'plates': {'plate_1': 'S. pneumoniae'},
  'output_dir': '/tmp',
  'results_filename': 'results.xlsx',
}


def sample_df():
  labels = ['LED490 Total', 'LED550 Total', 'LED490+LED550']
  rows = []
  for label in labels:
    for stimulus, value in (('DMSO', 3), ('PHA', 30)):
      rows.append({
        'Layout-Donor': 'D1', 'Plate': 'plate_1', 'Layout-Stimuli': stimulus,
        'Spot Forming Units (SFU)': value, 'Analyte Secreting Population': label,
      })
  return pd.DataFrame(rows)


class TestConfigBuilderRoundtrip:
  def test_populations_survive_save_and_load(self, tmp_path):
    builder = ConfigBuilder()
    config = dict(BASE_CONFIG, populations=['LED490 Total', 'LED490+LED550'],
                  mapping_confirmed=True)
    target = tmp_path / 'saved.yaml'

    builder.save_config(config, str(target))
    loaded = builder.load_config(str(target))

    assert loaded['populations'] == ['LED490 Total', 'LED490+LED550']
    # GUI-only confirmation state is not written into the analysis config file
    assert 'mapping_confirmed' not in target.read_text()

  def test_analysis_config_receives_selected_populations(self):
    builder = ConfigBuilder()
    analysis_config = builder.build_analysis_config(
      dict(BASE_CONFIG, populations=['LED490+LED550'])
    )
    assert analysis_config.populations == ['LED490+LED550']

  def test_empty_selection_keeps_totals_default(self):
    builder = ConfigBuilder()
    analysis_config = builder.build_analysis_config(dict(BASE_CONFIG, populations=[]))
    assert analysis_config.populations is None

  def test_temp_config_file_carries_populations(self, tmp_path):
    builder = ConfigBuilder()
    temp_path = builder.create_temp_config_file(
      dict(BASE_CONFIG, populations=['LED490+LED550'])
    )
    try:
      assert 'LED490+LED550' in temp_path.read_text()
    finally:
      builder.cleanup_temp_file(temp_path)


class TestValidation:
  def test_selected_population_absent_from_data_is_an_error(self):
    summary = DataValidator().get_data_summary(sample_df())
    valid, results = ConfigValidator().validate_config_for_data(
      dict(BASE_CONFIG, populations=['LED490+LED550', 'LED550+LED640']), summary
    )
    assert valid is False
    assert any('LED550+LED640' in message and message.startswith('❌') for message in results)

  def test_unconfirmed_mapping_warns_for_multi_endpoints(self):
    _, results = ConfigValidator().validate_configuration(
      dict(BASE_CONFIG, populations=['LED490+LED550'], mapping_confirmed=False)
    )
    assert any('mapping is not confirmed' in message for message in results)

  def test_confirmed_mapping_has_no_mapping_warning(self):
    _, results = ConfigValidator().validate_configuration(
      dict(BASE_CONFIG, populations=['LED490+LED550'], mapping_confirmed=True)
    )
    assert not any('mapping is not confirmed' in message for message in results)

  def test_data_summary_exposes_population_details(self):
    summary = DataValidator().get_data_summary(sample_df())
    labels = {entry['label']: entry for entry in summary['population_details']}
    assert labels['LED490+LED550']['scope'] == 'exact_double'
    assert labels['LED490+LED550']['measured'] == 2
    assert labels['LED490+LED550']['missing'] == 0


tk = pytest.importorskip('tkinter')
display_missing = not os.environ.get('DISPLAY')


@pytest.mark.skipif(display_missing, reason='no X display for Tkinter widgets')
class TestPopulationSelectorWidget:
  @pytest.fixture
  def widget(self):
    from gui.widgets.population_selector import PopulationSelectorWidget
    root = tk.Tk()
    root.withdraw()
    selector = PopulationSelectorWidget(root)
    yield selector
    root.destroy()

  def test_defaults_to_totals_and_gates_multi_until_confirmed(self, widget):
    widget.set_inventory(discover_populations(sample_df()),
                         {'LED490': 'IFNg', 'LED550': 'IL-10'})

    assert widget.get_selected_labels() == ['LED490 Total', 'LED550 Total']
    assert widget.mapping_confirmed() is False
    assert str(widget.checkbuttons['LED490+LED550'].cget('state')) == 'disabled'

    # Bulk action does nothing while the mapping is unconfirmed
    widget.select_all_multi()
    assert 'LED490+LED550' not in widget.get_selected_labels()

  def test_select_all_doubles_and_triples_after_confirmation(self, widget):
    widget.set_inventory(discover_populations(sample_df()),
                         {'LED490': 'IFNg', 'LED550': 'IL-10'})
    widget.mapping_confirmed_var.set(True)
    widget.on_mapping_confirmation_changed()

    widget.select_all_multi()
    assert widget.get_selected_labels() == ['LED490 Total', 'LED550 Total', 'LED490+LED550']

    widget.select_totals_only()
    assert widget.get_selected_labels() == ['LED490 Total', 'LED550 Total']

  def test_saved_selection_is_applied_after_discovery(self, widget):
    widget.set_selected_labels(['LED490+LED550'])
    assert widget.get_selected_labels() == ['LED490+LED550']  # pending

    widget.set_inventory(discover_populations(sample_df()),
                         {'LED490': 'IFNg', 'LED550': 'IL-10'})
    assert widget.get_selected_labels() == ['LED490+LED550']
    assert widget.mapping_confirmed() is True


@pytest.mark.skipif(display_missing, reason='no X display for Tkinter widgets')
class TestConfigPanelRoundtrip:
  def test_panel_reports_and_restores_population_selection(self):
    from gui.widgets.config_panel import ConfigPanel
    root = tk.Tk()
    root.withdraw()
    try:
      panel = ConfigPanel(root)
      panel.set_population_inventory(discover_populations(sample_df()))
      panel.population_widget.mapping_confirmed_var.set(True)
      panel.population_widget.on_mapping_confirmation_changed()
      panel.population_widget.select_all_multi()

      config = panel.get_configuration()
      assert 'LED490+LED550' in config['populations']
      assert config['mapping_confirmed'] is True

      panel.set_configuration(dict(config, populations=['LED550 Total']))
      assert panel.get_configuration()['populations'] == ['LED550 Total']
    finally:
      root.destroy()
