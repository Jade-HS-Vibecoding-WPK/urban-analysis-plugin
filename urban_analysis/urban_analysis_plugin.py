"""Minimal QGIS plugin entry point shared by both feature branches."""

from qgis.PyQt.QtWidgets import QAction


class UrbanAnalysisPlugin:
    """Register the shared plugin action without implementing MVP features."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        """Add the plugin action to the QGIS plugin menu."""
        self.action = QAction("Urban Analysis", self.iface.mainWindow())
        self.action.setObjectName("urbanAnalysisAction")
        self.action.triggered.connect(self._show_not_ready_message)
        self.iface.addPluginToMenu("&Urban Analysis", self.action)

    def unload(self):
        """Remove the plugin action from the QGIS plugin menu."""
        if self.action is not None:
            self.iface.removePluginMenu("&Urban Analysis", self.action)
            self.action.deleteLater()
            self.action = None

    def _show_not_ready_message(self):
        """Keep the foundation explicit until the feature branches are integrated."""
        self.iface.messageBar().pushInfo(
            "Urban Analysis",
            "The shared plugin foundation is ready; MVP features are not implemented yet.",
        )
