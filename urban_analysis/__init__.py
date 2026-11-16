"""QGIS plugin package for the urban analysis MVP."""


def classFactory(iface):
    """Create the plugin instance for QGIS."""
    from .urban_analysis_plugin import UrbanAnalysisPlugin

    return UrbanAnalysisPlugin(iface)
