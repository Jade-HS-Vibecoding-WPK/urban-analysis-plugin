"""QGIS plugin entry point."""

if __package__:
    from .urban_analysis import classFactory
else:
    from urban_analysis import classFactory

__all__ = ["classFactory"]
