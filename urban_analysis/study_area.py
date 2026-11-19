"""Study area for the guidance: from a polygon layer or drawn in the map.

The result is always one polygon geometry in the CRS chosen in step 1.  The
pipeline receives it as WKT (ARBEITSPLAN W3 / interface S1).  QGIS is only
imported inside the functions, so the text helpers stay testable without QGIS.
"""

from .theme import DRAW_FILL_RGBA, DRAW_STROKE_RGBA

DRAWN_LAYER_NAME = "Untersuchungsgebiet (gezeichnet)"
DRAW_INSTRUCTIONS = (
    "Linksklick setzt einen Punkt, Rücktaste entfernt den letzten Punkt, "
    "Rechtsklick schließt das Polygon ab, Esc bricht ab."
)
RECTANGLE_INSTRUCTIONS = (
    "Erster Klick setzt eine Ecke, zweiter Klick die gegenüberliegende Ecke. "
    "Rechtsklick oder Esc bricht ab."
)
DRAW_BOTH_INSTRUCTIONS = (
    "Polygon: Linksklick setzt Punkte, Rechtsklick schließt ab. Rechteck: erster Klick "
    "eine Ecke, zweiter Klick die gegenüberliegende Ecke. Esc bricht ab."
)
# Download rectangle (E17) in the map: grey dashed, only while steps 2/3 are open
DOWNLOAD_BOX_COLOR = (90, 90, 90, 220)


def rectangle_ring(first, second):
    """Closed ring of the rectangle between two corner points (x, y), or
    None if it has no area (a click without dragging)."""
    (x1, y1), (x2, y2) = first, second
    xmin, xmax = sorted((x1, x2))
    ymin, ymax = sorted((y1, y2))
    if xmax - xmin <= 0 or ymax - ymin <= 0:
        return None
    return [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]


def download_box(xmin, ymin, xmax, ymax, buffer_meters):
    """The download rectangle: bounding box of the area grown by the buffer."""
    return (xmin - buffer_meters, ymin - buffer_meters,
            xmax + buffer_meters, ymax + buffer_meters)


# The study area is drawn as a simple line (no fill), in map and PDF.
AREA_OUTLINE_STYLE = {
    "color": "0,0,0,0", "outline_color": "#d0473b", "outline_width": "0.6",
    "outline_style": "solid",
}


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


# E13/E17: OSM/ALKIS are downloaded for the rectangle around area + buffer.
# Above 25 km² a warning (takes long, large files), above 50 km² no download
# (user decision 18.11.2026, changes E13 – to be confirmed by Person Mac).
# The values live in sources_catalog.json (one place for step 2 and sources.py).
def _limits():
    from .sources import area_limits, load_catalog

    return area_limits(load_catalog())


LARGE_AREA_KM2, MAX_DOWNLOAD_KM2 = _limits()
LARGE_AREA_TEXT = f"{LARGE_AREA_KM2:g}".replace(".", ",")
MAX_DOWNLOAD_TEXT = f"{MAX_DOWNLOAD_KM2:g}".replace(".", ",")


def download_box_km2(xmin, ymin, xmax, ymax, buffer_meters):
    """Size of the download rectangle (bounding box grown by the buffer) in km²."""
    width = (xmax - xmin) + 2 * buffer_meters
    height = (ymax - ymin) + 2 * buffer_meters
    return max(width, 0) * max(height, 0) / 1_000_000


def format_km2(km2):
    """'6,1' – one decimal with a German comma."""
    return f"{km2:,.1f}".replace(",", " ").replace(".", ",")


def download_size_text(km2):
    """Line below the area, e.g. 'Gebiet mit Puffer: 6,1 km² von höchstens 25 km²'."""
    return (
        f"Gebiet mit Puffer: {format_km2(km2)} km² von höchstens "
        f"{MAX_DOWNLOAD_TEXT} km² (Rechteck für den Download, grau gestrichelt in der Karte)"
    )


def is_large(km2):
    """Above 25 km²: warn in step 2, continuing stays possible."""
    return km2 > LARGE_AREA_KM2


def is_oversized(km2):
    """Above 50 km²: OSM/ALKIS cannot be downloaded (step 3)."""
    return km2 > MAX_DOWNLOAD_KM2


def oversize_warning_text(km2):
    """Yellow hint in step 2 for a large area; continuing stays possible."""
    size = format_km2(km2)
    if is_oversized(km2):
        return (
            f"Das Gebiet ist mit Puffer {size} km² groß, also größer als "
            f"{MAX_DOWNLOAD_TEXT} km². OSM- und ALKIS-Daten können dafür nicht "
            "heruntergeladen werden; eine eigene Datei geht, wird aber sehr groß "
            "und langsam. Du kannst trotzdem weitermachen; verkleinere sonst das "
            "Gebiet oder den Puffer."
        )
    return (
        f"Großes Gebiet: {size} km² (über {LARGE_AREA_TEXT} km²). Das Laden der "
        "Daten kann lange dauern und die Dateien werden groß. Du kannst trotzdem "
        "weitermachen."
    )


def oversize_question_text(km2):
    """Question on 'Weiter' when the area is large."""
    size = format_km2(km2)
    if is_oversized(km2):
        return (
            f"Das Gebiet ist mit Puffer {size} km² groß (höchstens "
            f"{MAX_DOWNLOAD_TEXT} km² für OSM und ALKIS).\n\n"
            "OSM und ALKIS können dafür nicht heruntergeladen werden; eine eigene "
            "Datei wird sehr groß und langsam. Trotzdem fortfahren?"
        )
    return (
        f"Das Gebiet ist mit Puffer {size} km² groß.\n\n"
        "Das Laden der Daten kann lange dauern und die Dateien werden groß. "
        "Trotzdem fortfahren?"
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
    from qgis.core import (
        QgsFeature, QgsFillSymbol, QgsProject, QgsSingleSymbolRenderer, QgsVectorLayer,
    )

    layer = QgsVectorLayer("Polygon", DRAWN_LAYER_NAME, "memory")
    layer.setCrs(crs)
    # only the outline, so the map below stays visible
    layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(AREA_OUTLINE_STYLE)))
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
            self.band.setStrokeColor(QColor(*DRAW_STROKE_RGBA))
            self.band.setFillColor(QColor(*DRAW_FILL_RGBA))
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


def create_rectangle_draw_tool(canvas, on_finished, on_canceled):
    """Map tool to drag one rectangle; calls back with a geometry in canvas CRS."""
    from qgis.core import Qgis, QgsGeometry, QgsPointXY
    from qgis.gui import QgsMapTool, QgsRubberBand
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor

    class RectangleDrawTool(QgsMapTool):
        def __init__(self):
            super().__init__(canvas)
            self.start = None
            self.band = QgsRubberBand(canvas, Qgis.GeometryType.Polygon)
            self.band.setStrokeColor(QColor(*DRAW_STROKE_RGBA))
            self.band.setFillColor(QColor(*DRAW_FILL_RGBA))
            self.band.setWidth(2)
            self.setCursor(Qt.CrossCursor)

        def _ring(self, end):
            ring = rectangle_ring((self.start.x(), self.start.y()), (end.x(), end.y()))
            return [QgsPointXY(x, y) for x, y in ring] if ring else None

        # Two clicks: the first sets one corner, the rectangle follows the
        # mouse, the second click sets the opposite (diagonal) corner.
        def canvasMoveEvent(self, event):
            if self.start is None:
                return
            ring = self._ring(event.mapPoint())
            self.band.reset(Qgis.GeometryType.Polygon)
            for point in ring or ():
                self.band.addPoint(point, False)
            self.band.show()
            self.band.updatePosition()
            self.band.update()

        def canvasReleaseEvent(self, event):
            if event.button() == Qt.RightButton:
                self.clear()
                on_canceled("Zeichnen abgebrochen. Es wurde kein Rechteck gespeichert.")
                return
            if event.button() != Qt.LeftButton:
                return
            if self.start is None:  # first click: one corner
                self.start = event.mapPoint()
                return
            ring = self._ring(event.mapPoint())  # second click: the diagonal corner
            if ring is None:
                return  # same point clicked twice: keep waiting for the second corner
            self.clear()
            on_finished(QgsGeometry.fromPolygonXY([ring]))

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_Escape:
                self.clear()
                on_canceled("Zeichnen abgebrochen. Es wurde kein Rechteck gespeichert.")

        def clear(self):
            self.start = None
            self.band.reset(Qgis.GeometryType.Polygon)

        def deactivate(self):
            self.clear()
            super().deactivate()

    return RectangleDrawTool()


class DownloadBoxMarker:
    """Grey dashed rectangle in the map: what OSM/ALKIS download (E17)."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.band = None

    def show(self, box, crs):
        """``box`` = (xmin, ymin, xmax, ymax) in ``crs``."""
        from qgis.core import (
            Qgis, QgsCoordinateTransform, QgsCsException, QgsGeometry, QgsProject, QgsRectangle,
        )
        from qgis.gui import QgsRubberBand
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QColor

        geometry = QgsGeometry.fromRect(QgsRectangle(*box))
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if crs != canvas_crs:
            try:
                geometry.transform(QgsCoordinateTransform(crs, canvas_crs, QgsProject.instance()))
            except QgsCsException:
                self.hide()
                return
        if self.band is None:
            self.band = QgsRubberBand(self.canvas, Qgis.GeometryType.Polygon)
            self.band.setStrokeColor(QColor(*DOWNLOAD_BOX_COLOR))
            self.band.setFillColor(QColor(0, 0, 0, 0))
            self.band.setWidth(2)
            self.band.setLineStyle(Qt.DashLine)
        self.band.setToGeometry(geometry, None)
        self.band.show()

    def hide(self):
        if self.band is not None:
            self.band.hide()

    def remove(self):
        if self.band is not None:
            self.canvas.scene().removeItem(self.band)
            self.band = None
