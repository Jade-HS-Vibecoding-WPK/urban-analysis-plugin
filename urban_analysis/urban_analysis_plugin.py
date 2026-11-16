"""Minimal QGIS plugin entry point shared by both feature branches."""

from qgis.PyQt.QtWidgets import QAction

from .contracts import PipelineResult
from .guided_dialog import show_guided_dialog
from .outputs import export_selected_outputs
from .user_guidance import GuidedWorkflow, OutputPlan


class UrbanAnalysisPlugin:
    """Register the plugin action and expose the contract-backed MVP workflow."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.workflow = None

    def initGui(self):
        """Add the plugin action to the QGIS plugin menu."""
        self.action = QAction("Urban Analysis", self.iface.mainWindow())
        self.action.setObjectName("urbanAnalysisAction")
        self.action.triggered.connect(self._show_workflow_status)
        self.iface.addPluginToMenu("&Urban Analysis", self.action)

    def unload(self):
        """Remove the plugin action from the QGIS plugin menu."""
        if self.action is not None:
            self.iface.removePluginMenu("&Urban Analysis", self.action)
            self.action.deleteLater()
            self.action = None

    def start_workflow(self, result: PipelineResult) -> GuidedWorkflow:
        """Create the guided workflow for a pipeline result."""
        self.workflow = GuidedWorkflow(result)
        return self.workflow

    def _require_workflow(self) -> GuidedWorkflow:
        if self.workflow is None:
            raise RuntimeError("Start a workflow with a PipelineResult first")
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

    def _show_workflow_status(self):
        """Report whether a contract-backed workflow has been started."""
        if self.workflow is None:
            self.iface.messageBar().pushInfo(
                "Urban Analysis",
                "PipelineResult für den Workflowstart erforderlich.",
            )
            return
        show_guided_dialog(self)
