"""Study area for the guidance: from a polygon layer or drawn in the map.

The result is always one polygon geometry in the CRS chosen in step 1.  The
pipeline receives it as WKT (ARBEITSPLAN W3 / interface S1).  QGIS is only
imported inside the functions, so the text helpers stay testable without QGIS.
"""

DRAWN_LAYER_NAME = "Untersuchungsgebiet (gezeichnet)"
DRAW_INSTRUCTIONS = (
    "Linksklick setzt einen Punkt, Rücktaste entfernt den letzten Punkt, "
    "Rechtsklick schließt das Polygon ab, Esc bricht ab."
)


class StudyAreaError(ValueError):
    """The chosen study area cannot be used; the message says how to fix it."""


def format_hectares(area_m2):
    """Format an area in m² as hectares with a German decimal comma."""
    text = f"{area_m2 / 10000:,.1f}"
    return text.replace(",", " ").replace(".", ",")


def area_summary_text(polygon_count, area_m2, crs_authid):
    """Short feedback below the selection, e.g. '1 Polygon, 84,3 ha'."""
    noun = "Polygon" if polygon_count == 1 else "Polygone"
    return (
        f"Gebiet: {polygon_count} {noun}, {format_hectares(area_m2)} ha "
        f"(im CRS {crs_authid})"
    )


def study_area_from_layer(layer, target_crs, *, selected_only):
    """Merge the polygons of ``layer`` into one geometry in ``target_crs``.

    Returns ``(geometry, polygon_count)``.  Raises ``StudyAreaError`` with a
    German message instead of silently repairing or skipping anything.
    """
    from qgis.core import (
        Qgis,
        QgsCoordinateTransform,
        QgsCsException,
        QgsGeometry,
        QgsProject,
    )

    if layer is None:
        raise StudyAreaError(
            "Es ist kein Polygon-Layer gewählt. Bitte einen Layer auswählen oder "
            "ein neues Polygon zeichnen."
        )
    if not layer.crs().isValid():
        raise StudyAreaError(
            f"Der Layer „{layer.name()}“ hat kein gültiges Koordinatensystem. "
            "Bitte in den Layereigenschaften ein CRS zuweisen."
        )
    if selected_only:
        features = layer.selectedFeatures()
        if not features:
            raise StudyAreaError(
                f"Im Layer „{layer.name()}“ sind keine Objekte ausgewählt. Bitte "
                "Objekte auswählen oder „Nur ausgewählte Objekte“ abwählen."
            )
    else:
        features = list(layer.getFeatures())
        if not features:
            raise StudyAreaError(f"Der Layer „{layer.name()}“ enthält keine Objekte.")

    geometries = []
    invalid = 0
    for feature in features:
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        if not geometry.isGeosValid():
            invalid += 1
            continue
        geometries.append(geometry)
    if invalid:
        raise StudyAreaError(
            f"{invalid} Objekt(e) im Layer „{layer.name()}“ haben eine ungültige "
            "Geometrie (z. B. eine Selbstüberschneidung). Bitte mit dem QGIS-Werkzeug "
            "„Geometrien reparieren“ korrigieren oder das Gebiet neu zeichnen."
        )
    if not geometries:
        raise StudyAreaError(
            f"Die gewählten Objekte im Layer „{layer.name()}“ haben keine Geometrie."
        )

    area = QgsGeometry.unaryUnion(geometries)
    if area is None or area.isEmpty() or area.type() != Qgis.GeometryType.Polygon:
        raise StudyAreaError(
            "Aus den gewählten Objekten ließ sich kein zusammenhängendes "
            "Polygon-Gebiet bilden."
        )

    if layer.crs() != target_crs:
        transform = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())
        try:
            result = area.transform(transform)
        except QgsCsException as error:
            raise StudyAreaError(
                f"Das Gebiet konnte nicht von {layer.crs().authid()} nach "
                f"{target_crs.authid()} umgerechnet werden: {error}"
            ) from error
        if result != Qgis.GeometryOperationResult.Success:
            raise StudyAreaError(
                f"Das Gebiet konnte nicht von {layer.crs().authid()} nach "
                f"{target_crs.authid()} umgerechnet werden."
            )
    return area, len(geometries)


def add_drawn_area_layer(geometry, crs):
    """Store a drawn polygon as a new temporary layer in the QGIS project."""
    from qgis.core import QgsFeature, QgsProject, QgsVectorLayer

    layer = QgsVectorLayer("Polygon", DRAWN_LAYER_NAME, "memory")
    layer.setCrs(crs)
    feature = QgsFeature()
    feature.setGeometry(geometry)
    if not layer.dataProvider().addFeatures([feature])[0]:
        raise StudyAreaError("Das gezeichnete Polygon konnte nicht gespeichert werden.")
    layer.updateExtents()
    QgsProject.instance().addMapLayer(layer)
    return layer


def create_polygon_draw_tool(canvas, on_finished, on_canceled):
    """Map tool to draw one polygon; calls back with a geometry in canvas CRS."""
    from qgis.core import Qgis, QgsGeometry
    from qgis.gui import QgsMapTool, QgsRubberBand
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor

    class PolygonDrawTool(QgsMapTool):
        def __init__(self):
            super().__init__(canvas)
            self.points = []
            self.band = QgsRubberBand(canvas, Qgis.GeometryType.Polygon)
            self.band.setStrokeColor(QColor(31, 111, 178, 220))
            self.band.setFillColor(QColor(31, 111, 178, 60))
            self.band.setWidth(2)
            self.setCursor(Qt.CrossCursor)

        def _show(self, extra_point=None):
            points = self.points + ([extra_point] if extra_point is not None else [])
            self.band.reset(Qgis.GeometryType.Polygon)
            for point in points:
                self.band.addPoint(point, False)
            self.band.show()
            self.band.updatePosition()
            self.band.update()

        def canvasMoveEvent(self, event):
            if self.points:
                self._show(event.mapPoint())

        def canvasReleaseEvent(self, event):
            if event.button() == Qt.LeftButton:
                self.points.append(event.mapPoint())
                self._show()
            elif event.button() == Qt.RightButton:
                self.finish()

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_Escape:
                self.cancel("Zeichnen abgebrochen. Es wurde kein Polygon gespeichert.")
            elif event.key() == Qt.Key_Backspace and self.points:
                self.points.pop()
                self._show()

        def finish(self):
            if len(self.points) < 3:
                self.cancel(
                    "Ein Polygon braucht mindestens 3 Punkte. Bitte erneut zeichnen."
                )
                return
            geometry = QgsGeometry.fromPolygonXY([list(self.points)])
            self.clear()
            on_finished(geometry)

        def cancel(self, message):
            self.clear()
            on_canceled(message)

        def clear(self):
            self.points = []
            self.band.reset(Qgis.GeometryType.Polygon)

        def deactivate(self):
            self.clear()
            super().deactivate()

    return PolygonDrawTool()
