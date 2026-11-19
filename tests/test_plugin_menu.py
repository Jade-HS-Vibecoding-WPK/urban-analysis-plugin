"""Toolbar button and side panel for the guidance (ARBEITSPLAN W2)."""

import sys
import types

from urban_analysis.contracts import MVP_UI_STEPS, PipelineResult
from urban_analysis.guided_dialog import (
    PAGE_ACTIONS,
    busy_label_text,
    error_text,
    pipeline_reports_progress,
    progress_text,
    step_counter_text,
    unexpected_error_text,
)


class FakeAction:
    def __init__(self, *args):
        self.callback = None
        self.checked = False
        self.triggered = types.SimpleNamespace(connect=self._connect)

    def _connect(self, callback):
        self.callback = callback

    def setObjectName(self, name):
        self.object_name = name

    def setToolTip(self, text):
        self.tool_tip = text

    def setCheckable(self, checkable):
        self.checkable = checkable

    def setChecked(self, checked):
        self.checked = checked

    def deleteLater(self):
        pass


class FakeIface:
    def __init__(self):
        self.menu_action = None
        self.toolbar_action = None

    def mainWindow(self):
        return None

    def addPluginToMenu(self, menu, action):
        self.menu_action = action

    def addToolBarIcon(self, action):
        self.toolbar_action = action

    def removePluginMenu(self, menu, action):
        self.menu_action = None

    def removeToolBarIcon(self, action):
        self.toolbar_action = None


def load_plugin_module(monkeypatch):
    qtwidgets = types.SimpleNamespace(QAction=FakeAction)
    qtgui = types.SimpleNamespace(QIcon=lambda path: path)
    monkeypatch.setitem(sys.modules, "qgis", types.ModuleType("qgis"))
    monkeypatch.setitem(sys.modules, "qgis.PyQt", types.ModuleType("qgis.PyQt"))
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qtgui)
    from urban_analysis import urban_analysis_plugin

    monkeypatch.setattr(urban_analysis_plugin, "QAction", FakeAction)
    return urban_analysis_plugin


def record_dock_calls(monkeypatch, plugin_module):
    calls = []
    monkeypatch.setattr(
        plugin_module,
        "set_dock_visible",
        lambda plugin, visible: calls.append((plugin.workflow, visible)),
    )
    return calls


def test_toolbar_button_and_menu_share_one_toggle_action(monkeypatch):
    plugin_module = load_plugin_module(monkeypatch)
    iface = FakeIface()
    plugin = plugin_module.UrbanAnalysisPlugin(iface)

    plugin.initGui()

    assert iface.toolbar_action is plugin.action
    assert iface.menu_action is plugin.action
    assert plugin.action.checkable is True


def test_button_shows_and_hides_panel_without_loaded_data(monkeypatch):
    plugin_module = load_plugin_module(monkeypatch)
    plugin = plugin_module.UrbanAnalysisPlugin(FakeIface())
    calls = record_dock_calls(monkeypatch, plugin_module)
    plugin.initGui()

    plugin.action.callback(True)  # QAction.triggered sends "checked"
    plugin.action.callback(False)

    assert calls == [(None, True), (None, False)]


def test_panel_opens_with_console_loaded_data(monkeypatch):
    plugin_module = load_plugin_module(monkeypatch)
    plugin = plugin_module.UrbanAnalysisPlugin(FakeIface())
    calls = record_dock_calls(monkeypatch, plugin_module)
    workflow = plugin.start_workflow(
        PipelineResult(
            contract_version="1.0",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )
    )

    plugin.open_guided_dialog()

    assert calls == [(workflow, True)]


def test_closing_the_panel_unchecks_the_toolbar_button(monkeypatch):
    plugin_module = load_plugin_module(monkeypatch)
    plugin = plugin_module.UrbanAnalysisPlugin(FakeIface())
    plugin.initGui()
    plugin.action.setChecked(True)

    plugin._on_dock_visibility_changed(False)

    assert plugin.action.checked is False


def test_every_step_has_one_main_action_and_progress_label():
    assert len(PAGE_ACTIONS) == len(MVP_UI_STEPS)
    assert PAGE_ACTIONS[-1] == "Verarbeitung starten"
    assert step_counter_text(4) == "Schritt 5 von 8"
    assert progress_text(0) == "Schritt 1 von 8\u00a0– Projekt-CRS"
    assert progress_text(7) == "Schritt 8 von 8\u00a0– Verarbeitung starten"


def test_unexpected_errors_are_described_with_step_type_and_log_hint():
    text = unexpected_error_text("Daten laden", ZeroDivisionError("division by zero"))

    assert "Daten laden" in text
    assert "ZeroDivisionError: division by zero" in text
    assert "Protokollmeldungen" in text
    assert "Urban Analysis" in text


def test_busy_text_shows_real_progress_only_when_known():
    assert busy_label_text("Lade a.gpkg …", None) == "Lade a.gpkg …"
    assert busy_label_text("Lade a.gpkg …", 42.7) == "Lade a.gpkg … 42 %"


def test_progress_is_used_only_if_the_pipeline_offers_a_callback():
    class Old:
        def import_file(self, path, *, project_crs, study_area_wkt, buffer_meters=500):
            pass

    class New:
        def import_file(self, path, *, project_crs, study_area_wkt, buffer_meters=500, progress=None):
            pass

    assert pipeline_reports_progress(Old()) is False
    assert pipeline_reports_progress(New()) is True


def test_reset_forgets_loaded_data(monkeypatch):
    plugin_module = load_plugin_module(monkeypatch)
    plugin = plugin_module.UrbanAnalysisPlugin(FakeIface())
    plugin.start_workflow(
        PipelineResult(contract_version="1.0", project_crs="EPSG:25832", study_area_wkt="POLYGON EMPTY")
    )

    plugin.reset_workflow()

    assert plugin.workflow is None


def test_key_errors_are_shown_without_python_quotes():
    assert error_text(KeyError("Feld fehlt")) == "Feld fehlt"
