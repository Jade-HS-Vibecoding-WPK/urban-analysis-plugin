"""OSM download in QGIS (W11, interface S10).

``sources.py`` (Person Mac) plans the download; this module does it inside
QGIS: send the Overpass query through the QGIS network (proxy settings of the
university apply), store the delivered file unchanged, convert it into one
GeoPackage in the project CRS.  It runs inside a ``QgsTask``.

The helpers at the top are QGIS-free and tested with plain pytest; QGIS is only
imported inside the functions that need it.
"""

import time
from pathlib import Path
from urllib.parse import urlencode

# Overpass is often busy (HTTP 429/502/503/504): try again after these pauses
# (seconds), then give up with a clear message (E15).
RETRY_PAUSES_S = (10, 30, 60)
RETRY_STATUS = (429, 502, 503, 504)
OSM_LAYERS = ("points", "lines", "multipolygons")  # as GDAL reads .osm files


class DownloadError(RuntimeError):
    """The download failed; the message says what happened and what to do."""


class DownloadCanceled(Exception):
    """'Laden abbrechen' was pressed during the download."""


def unique_path(folder, name):
    """``folder/name`` – or name_2, name_3 … if it exists: raw data are never
    overwritten."""
    folder = Path(folder)
    path = folder / name
    stem, suffix = path.stem, path.suffix
    number = 2
    while path.exists():
        path = folder / f"{stem}_{number}{suffix}"
        number += 1
    return path


def retry_text(pause_s, attempt, total):
    """Visible hint while waiting for a busy server."""
    return (
        f"Der OSM-Server ist gerade überlastet – neuer Versuch in {pause_s} s "
        f"({attempt} von {total})."
    )


def download_error_text(status, reason, attempts):
    """Readable message after the download finally failed (E15: no reuse of
    old downloads, the user decides what to do)."""
    if not status:
        return (
            "Die OSM-Daten konnten nicht geladen werden: keine Verbindung zum "
            f"OSM-Server ({reason or 'keine Antwort'}).\n"
            "Was tun: Internetverbindung prüfen (an der Hochschule ggf. den Proxy in "
            "QGIS unter Einstellungen → Netzwerk) und erneut „Daten laden“ klicken."
        )
    if status in RETRY_STATUS:
        return (
            f"Der OSM-Server ist überlastet (Fehler {status}); auch nach {attempts} "
            "Versuchen kam keine Antwort.\n"
            "Was tun: in ein paar Minuten erneut „Daten laden“ klicken oder das "
            "Gebiet verkleinern."
        )
    return (
        f"Der OSM-Server hat die Anfrage abgelehnt (Fehler {status}: {reason}).\n"
        "Was tun: erneut versuchen; bleibt der Fehler, bitte die Meldung an das "
        "Team weitergeben."
    )


def post_body(query):
    """Overpass expects the query as form field 'data'."""
    return urlencode({"data": query}).encode("utf-8")


# --- QGIS part ---------------------------------------------------------------


def lonlat_box(geometry, buffer_meters, project_crs, transform_context):
    """Rectangle of study area + buffer, converted to EPSG:4326 as
    (west, south, east, north) – the form ``sources.plan_osm_download`` needs."""
    from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

    box = geometry.boundingBox()
    box.grow(buffer_meters)
    transform = QgsCoordinateTransform(
        project_crs, QgsCoordinateReferenceSystem("EPSG:4326"), transform_context
    )
    lonlat = transform.transformBoundingBox(box)
    return (lonlat.xMinimum(), lonlat.yMinimum(), lonlat.xMaximum(), lonlat.yMaximum())


def fetch(request, feedback, is_canceled, report, sleep=time.sleep):
    """POST the Overpass query; retry a busy server.  Returns the bytes.

    ``report(text)`` shows a hint (e.g. retry countdown); ``feedback`` is a
    QgsFeedback that 'Laden abbrechen' cancels.
    """
    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    total = len(RETRY_PAUSES_S) + 1
    for attempt in range(1, total + 1):
        if is_canceled():
            raise DownloadCanceled()
        network = QNetworkRequest(QUrl(request.url))
        network.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        blocking = QgsBlockingNetworkRequest()
        error = blocking.post(network, post_body(request.query), True, feedback)
        if is_canceled():
            raise DownloadCanceled()
        reply = blocking.reply()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        status = int(status) if status else 0
        if error == QgsBlockingNetworkRequest.NoError and status in (0, 200):
            return bytes(reply.content())
        reason = blocking.errorMessage() or reply.errorString()
        if status not in RETRY_STATUS or attempt == total:
            raise DownloadError(download_error_text(status, reason, attempt))
        pause = RETRY_PAUSES_S[attempt - 1]
        for left in range(pause, 0, -1):  # visible countdown, cancel stays possible
            if is_canceled():
                raise DownloadCanceled()
            report(retry_text(left, attempt + 1, total))
            sleep(1)
        report("Neuer Versuch, OSM-Daten werden geladen …")
    raise DownloadError(download_error_text(0, "", total))  # not reached


def convert_to_geopackage(raw_path, gpkg_path, project_crs, transform_context):
    """Read the .osm file with GDAL (points, lines, multipolygons) and write
    them into one new GeoPackage in the project CRS.  Returns the written
    layer names; empty layers are left out."""
    from qgis.core import (
        QgsCoordinateTransform,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )

    written = []
    for name in OSM_LAYERS:
        layer = QgsVectorLayer(f"{raw_path}|layername={name}", name, "ogr")
        if not layer.isValid() or layer.featureCount() == 0:
            continue
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.layerName = name
        options.ct = QgsCoordinateTransform(layer.crs(), project_crs, transform_context)
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteLayer if written
            else QgsVectorFileWriter.CreateOrOverwriteFile
        )
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(gpkg_path), transform_context, options
        )
        if result[0] != QgsVectorFileWriter.NoError:
            raise DownloadError(
                f"Die OSM-Daten konnten nicht als GeoPackage gespeichert werden "
                f"(Layer „{name}“: {result[1]}).\nWas tun: einen anderen Ordner wählen "
                "(Schreibrechte, freier Speicherplatz) und erneut laden."
            )
        written.append(name)
    if not written:
        raise DownloadError(
            "Im gewählten Gebiet wurden keine OSM-Objekte gefunden.\n"
            "Was tun: Gebiet in Schritt 2 prüfen oder vergrößern."
        )
    return written


def reprojected_name(path, crs_authid):
    """'daten.gpkg' -> 'daten_EPSG25832.gpkg' (copy in the project CRS)."""
    path = Path(path)
    return f"{path.stem}_{crs_authid.replace(':', '')}.gpkg"


def ensure_project_crs(path, project_crs, transform_context, folder):
    """Return ``(path, changed_layers)``: the file itself if all layers are in
    ``project_crs``, else a new GeoPackage in ``folder`` with every layer
    converted.  The original file is never changed."""
    from osgeo import ogr
    from qgis.core import QgsCoordinateTransform, QgsVectorFileWriter, QgsVectorLayer

    source = ogr.Open(str(path))
    if source is None:
        return Path(path), []  # the pipeline reports unreadable files itself
    names = [source.GetLayer(i).GetName() for i in range(source.GetLayerCount())]
    source = None
    layers = [(name, QgsVectorLayer(f"{path}|layername={name}", name, "ogr")) for name in names]
    changed = [name for name, layer in layers
               if layer.isValid() and layer.crs().isValid() and layer.crs() != project_crs]
    if not changed:
        return Path(path), []
    Path(folder).mkdir(parents=True, exist_ok=True)
    target = unique_path(folder, reprojected_name(path, project_crs.authid()))
    first = True
    for name, layer in layers:
        if not layer.isValid():
            continue
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.layerName = name
        if name in changed:
            options.ct = QgsCoordinateTransform(layer.crs(), project_crs, transform_context)
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(target), transform_context, options)
        if result[0] != QgsVectorFileWriter.NoError:
            raise DownloadError(
                f"Die Datei konnte nicht ins Projekt-KBS umgerechnet werden (Layer „{name}“: "
                f"{result[1]}).\nWas tun: freien Speicherplatz prüfen und erneut laden."
            )
        first = False
    return target, changed


def run_download(request, folder, project_crs, transform_context, feedback,
                 is_canceled, report, progress):
    """Whole download for one OSM job (runs inside a QgsTask).

    Returns the path of the GeoPackage.  The raw file stays unchanged next to
    it.  ``progress(percent)`` moves the loading bar."""
    progress(5)
    report("OSM-Daten werden vom Server geladen … Das kann bei großen Gebieten "
           "einige Minuten dauern.")
    data = fetch(request, feedback, is_canceled, report)
    progress(60)
    raw_path = unique_path(folder, request.raw_file_name)
    try:
        raw_path.write_bytes(data)
    except OSError as error:
        raise DownloadError(
            f"Die OSM-Rohdatei konnte nicht gespeichert werden: {error}\n"
            "Was tun: einen anderen Ordner wählen (Schreibrechte, freier Speicherplatz)."
        ) from error
    if is_canceled():
        raise DownloadCanceled()
    report("OSM-Daten werden ins Projekt-KBS umgerechnet und gespeichert …")
    gpkg_path = unique_path(folder, request.geopackage_name)
    convert_to_geopackage(raw_path, gpkg_path, project_crs, transform_context)
    progress(100)
    return gpkg_path
