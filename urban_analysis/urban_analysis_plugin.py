"""Minimal QGIS plugin entry point shared by both feature branches."""

from qgis.PyQt.QtWidgets import QAction

from .contracts import PipelineResult
from .guided_dialog import report_unexpected_error, set_dock_visible
from .outputs import export_selected_outputs
from .user_guidance import GuidedWorkflow, OutputPlan


MENU_NAME = "&Urban Analysis"
TOOLBAR_ICON = "/mLayoutItemMap.svg"


class UrbanAnalysisPlugin:
    """Register the plugin action and expose the contract-backed MVP workflow."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.workflow = None

    def initGui(self):
        """Add a toggle action for the side panel to the menu and toolbar."""
        from qgis.core import QgsApplication

        self.action = QAction(
            QgsApplication.getThemeIcon(TOOLBAR_ICON),
            "Urban Analysis",
            self.iface.mainWindow(),
        )
        self.action.setObjectName("urbanAnalysisAction")
        self.action.setToolTip("Urban Analysis: Seitenfenster ein- oder ausblenden")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock)
        self.iface.addPluginToMenu(MENU_NAME, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the side panel, menu entry and toolbar button."""
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(MENU_NAME, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def toggle_dock(self, checked=False):
        """Show or hide the side panel (toolbar button and menu entry)."""
        self._set_dock_visible(bool(checked))

    def open_guided_dialog(self, *_args):
        """Show the side panel, with or without already loaded data."""
        self._set_dock_visible(True)

    def _set_dock_visible(self, visible):
        try:
            set_dock_visible(self, visible)
        except Exception as error:  # show every program error visibly
            report_unexpected_error(self, "Seitenfenster öffnen", error)
            if self.action is not None:
                self.action.setChecked(self.dock is not None and self.dock.isVisible())

    def _on_dock_visibility_changed(self, visible):
        """Keep the toolbar button in sync when the panel is closed via its X."""
        if self.action is not None:
            self.action.setChecked(bool(visible))

    def start_workflow(self, result: PipelineResult) -> GuidedWorkflow:
        """Create the guided workflow for a pipeline result."""
        self.workflow = GuidedWorkflow(result)
        return self.workflow

    def _require_workflow(self) -> GuidedWorkflow:
        if self.workflow is None:
            raise RuntimeError(
                "Es sind noch keine Daten geladen. Bitte zuerst in Schritt 3 ein "
                "GeoPackage laden."
            )
        return self.workflow

    def advance_workflow(self) -> str:
        """Advance the active workflow to its next contract-defined step."""
        return self._require_workflow().advance()

    def select_topic(self, topic, categories=None, *, confirm_missing=False):
        """Apply the user's topic selection to the active workflow."""
        return self._require_workflow().select_topic(
            topic, categories, confirm_missing=confirm_missing
        )

    def choose_output(
        self, *, save_cleaned_geopackage=False, create_pdf=False, data_source=None
    ):
        """Store output choices for the active workflow."""
        return self._require_workflow().choose_output(
            save_cleaned_geopackage=save_cleaned_geopackage,
            create_pdf=create_pdf,
            data_source=data_source,
        )

    def output_plan(self) -> OutputPlan:
        """Return the contract-backed plan for the selected outputs."""
        return self._require_workflow().output_plan()

    def export_outputs(self, *, layer_objects=None, geopackage_path=None, pdf_path=None):
        """Execute selected QGIS and optional file outputs."""
        workflow = self._require_workflow()
        return export_selected_outputs(
            self.iface,
            workflow.output_plan(),
            workflow.result.selected_layers(),
            layer_objects=layer_objects,
            geopackage_path=geopackage_path,
            pdf_path=pdf_path,
        )
