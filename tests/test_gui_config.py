"""Tests for GUI configuration handling of population endpoints."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent))

from gui.core.config_builder import ConfigBuilder  # noqa: E402
from gui.core.gui_controller import GUIController  # noqa: E402
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
  return export_df(['LED490 Total', 'LED550 Total', 'LED490+LED550'])


def export_df(labels, plate='plate_1', stimuli=(('DMSO', 3), ('PHA', 30))):
  rows = []
  for label in labels:
    for stimulus, value in stimuli:
      rows.append({
        'Layout-Donor': 'D1', 'Plate': plate, 'Layout-Stimuli': stimulus,
        'Spot Forming Units (SFU)': value, 'Analyte Secreting Population': label,
      })
  return pd.DataFrame(rows)


def write_export(path, labels, plate='plate_1', stimuli=(('DMSO', 3), ('PHA', 30))):
  """Write a workbook shaped like a Mabtech export: data on the second sheet."""
  with pd.ExcelWriter(path, engine='openpyxl') as writer:
    pd.DataFrame({'Info': ['Mabtech Apex export']}).to_excel(
      writer, sheet_name='Info', index=False)
    export_df(labels, plate=plate, stimuli=stimuli).to_excel(
      writer, sheet_name='Plate Database', index=False)
  return path


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
  def test_absent_population_is_skipped_not_blocked_when_others_exist(self):
    summary = DataValidator().get_data_summary(sample_df())
    valid, results, blocking = ConfigValidator().validate_config_for_data(
      dict(BASE_CONFIG, populations=['LED490+LED550', 'LED550+LED640']), summary
    )
    # The analyzer skips what the data lacks and analyzes the rest, so this runs
    assert valid is True
    assert blocking == []
    assert any('LED550+LED640' in message and message.startswith('⚠️') for message in results)

  def test_all_populations_absent_blocks_and_names_what_is_available(self):
    summary = DataValidator().get_data_summary(sample_df())
    valid, _, blocking = ConfigValidator().validate_config_for_data(
      dict(BASE_CONFIG, populations=['LED550+LED640']), summary
    )
    assert valid is False
    assert len(blocking) == 1
    assert 'LED490 Total' in blocking[0] and 'Populations tab' in blocking[0]

  def test_plate_label_without_species_mapping_warns_but_runs(self):
    summary = DataValidator().get_data_summary(export_df(['LED490 Total'], plate='Donor plate A'))
    valid, results, blocking = ConfigValidator().validate_config_for_data(BASE_CONFIG, summary)
    assert (valid, blocking) == (True, [])
    warning = next(m for m in results if 'Donor plate A' in m)
    assert warning.startswith('⚠️') and 'Plates tab' in warning

  def test_missing_control_stimulus_blocks_and_lists_the_data_wells(self):
    summary = DataValidator().get_data_summary(
      export_df(['LED490 Total'], stimuli=(('PBS', 3), ('PHA', 30)))
    )
    valid, _, blocking = ConfigValidator().validate_config_for_data(BASE_CONFIG, summary)
    assert valid is False
    assert 'PBS' in blocking[0] and 'Basic Settings tab' in blocking[0]

  def test_output_directory_that_does_not_exist_yet_is_accepted(self, tmp_path):
    validator = ConfigValidator()
    valid, results = validator.validate_configuration(
      dict(BASE_CONFIG, output_dir=str(tmp_path / 'new' / 'results'))
    )
    assert valid is True
    assert validator.blocking_problems == []
    assert any('will be created' in message for message in results)

  def test_unwritable_output_directory_blocks_with_a_remedy(self, tmp_path):
    readonly = tmp_path / 'readonly'
    readonly.mkdir()
    readonly.chmod(0o500)
    try:
      validator = ConfigValidator()
      valid, _ = validator.validate_configuration(
        dict(BASE_CONFIG, output_dir=str(readonly / 'results'))
      )
      assert valid is False
      assert any('write permission' in problem and 'Output tab' in problem
                 for problem in validator.blocking_problems)
    finally:
      readonly.chmod(0o700)

  def test_incomplete_experimental_group_blocks_with_a_remedy(self):
    validator = ConfigValidator()
    valid, _ = validator.validate_configuration(dict(
      BASE_CONFIG,
      experimental_conditions={'plate_1': {'group_a': {'control': 'DMSO', 'stimuli': []}}},
    ))
    assert valid is False
    assert any('group_a' in problem and 'stimulus' in problem
               for problem in validator.blocking_problems)

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


class TestInputValidationAcrossFiles:
  def test_directory_is_validated_against_every_export(self, tmp_path):
    """A selection spanning several exports must not be reported as absent.

    Discovery merges every file in the folder, so validating one arbitrary
    sample file used to reject populations that other files do export.
    """
    write_export(tmp_path / 'plate_a.xlsx', ['LED490 Total'])
    write_export(tmp_path / 'plate_b.xlsx', ['LED640 Total'], plate='plate_2')
    controller = GUIController()

    outcome = controller.validate_configuration(
      dict(BASE_CONFIG,
           cytokines={'IFNg': 'LED490', 'IL-17': 'LED640'},
           plates={'plate_1': 'S. pneumoniae', 'plate_2': 'S. aureus'},
           populations=['LED490 Total', 'LED640 Total']),
      str(tmp_path), True
    )

    assert outcome.blocking == []
    assert any('2 selected population(s) found in data' in m for m in outcome.messages)
    assert not any('not in data' in m for m in outcome.messages)

  def test_data_summary_unions_the_whole_directory(self, tmp_path):
    write_export(tmp_path / 'plate_a.xlsx', ['LED490 Total'])
    write_export(tmp_path / 'plate_b.xlsx', ['LED640 Total'], plate='plate_2')

    summary = GUIController().get_data_summary(str(tmp_path), True)

    assert sorted(map(str, summary['plates'])) == ['plate_1', 'plate_2']
    assert sorted(summary['population_labels']) == ['LED490 Total', 'LED640 Total']

  def test_unreadable_export_blocks_with_a_remedy(self, tmp_path):
    broken = tmp_path / 'broken.xlsx'
    broken.write_text('not really a workbook')
    outcome = GUIController().validate_input_path(str(broken), False)

    assert outcome.has_critical_errors is True
    assert any('Mabtech Apex' in problem for problem in outcome.blocking)


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


@pytest.mark.skipif(display_missing, reason='no X display for Tkinter widgets')
class TestPlateAdoption:
  def test_placeholder_plate_row_is_replaced_by_the_data_labels(self):
    from gui.widgets.config_panel import ConfigPanel
    root = tk.Tk()
    root.withdraw()
    try:
      panel = ConfigPanel(root)
      assert panel.get_configuration()['plates'] == {'plate_1': 'S. pneumoniae'}

      assert panel.adopt_data_plates(['Donor plate A']) == ['Donor plate A']
      assert [row[0] for row in panel.plate_widget.get_values()] == ['Donor plate A']
      # Species is the user's information, so it is left blank on purpose
      assert panel.get_configuration()['plates'] == {}
    finally:
      root.destroy()

  def test_user_entered_plate_mapping_is_kept(self):
    from gui.widgets.config_panel import ConfigPanel
    root = tk.Tk()
    root.withdraw()
    try:
      panel = ConfigPanel(root)
      panel.plate_widget.set_plate_dict({'my_plate': 'S. aureus'})

      assert panel.adopt_data_plates(['Donor plate A']) == []
      assert panel.get_configuration()['plates'] == {'my_plate': 'S. aureus'}
    finally:
      root.destroy()

  def test_loaded_configuration_plates_survive_file_selection(self):
    from gui.widgets.config_panel import ConfigPanel
    root = tk.Tk()
    root.withdraw()
    try:
      panel = ConfigPanel(root)
      panel.set_configuration(dict(BASE_CONFIG, plates={'plate_1': 'S. pneumoniae'}))

      assert panel.adopt_data_plates(['Donor plate A']) == []
      assert panel.get_configuration()['plates'] == {'plate_1': 'S. pneumoniae'}
    finally:
      root.destroy()

  def test_second_file_replaces_the_labels_filled_in_from_the_first(self):
    from gui.widgets.config_panel import ConfigPanel
    root = tk.Tk()
    root.withdraw()
    try:
      panel = ConfigPanel(root)
      panel.adopt_data_plates(['Donor plate A'])

      assert panel.adopt_data_plates(['plate_1']) == ['plate_1']
      assert [row[0] for row in panel.plate_widget.get_values()] == ['plate_1']
    finally:
      root.destroy()


@pytest.mark.skipif(display_missing, reason='no X display for Tkinter widgets')
class TestBlockingVerdictIsActionable:
  def test_validate_states_the_reason_and_the_fix(self, tmp_path):
    """A blocked run must show what to fix, not just that it is blocked."""
    from gui.main import FluoroSpotGUI
    export = write_export(tmp_path / 'export.xlsx', ['LED490 Total'],
                          stimuli=(('PBS', 3), ('PHA', 30)))
    app = FluoroSpotGUI()
    try:
      app.root.withdraw()
      app.file_selector.set_selected_path(str(export), False)
      app.config_panel.output_dir_var.set(str(tmp_path / 'results'))
      app.status_text.config(state=tk.NORMAL)
      app.status_text.delete('1.0', tk.END)
      app.status_text.config(state=tk.DISABLED)

      app.validate_configuration()

      log = app.status_text.get('1.0', tk.END)
      assert 'Cannot run the analysis yet' in log
      assert "Set 'Control Stimulus'" in log and 'PBS' in log
      assert str(app.run_btn.cget('state')) == 'disabled'
    finally:
      app.root.destroy()
