"""OSM download in QGIS (W11, interface S10).

``sources.py`` (Person Mac) plans the download; this module does it inside
QGIS: send the Overpass query through the QGIS network (proxy settings of the
university apply), store the delivered file unchanged, convert it into one
GeoPackage in the project CRS.  It runs inside a ``QgsTask``.

The helpers at the top are QGIS-free and tested with plain pytest; QGIS is only
imported inside the functions that need it.
"""

import gzip
import json
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


class OsmServerError(DownloadError):
    """The OSM server did not deliver (busy, no answer, timeout, refused).
    Only then the Niedersachsen-Cache may stand in (W11b, E35)."""


class CacheOffer(Exception):
    """Overpass failed and the Niedersachsen-Cache covers the area: the user
    decides whether to use it (never silently, E35)."""

    def __init__(self, error_text, data_date):
        super().__init__(error_text)
        self.error_text = error_text
        self.data_date = data_date


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


# --- Niedersachsen-Cache (W11b, E35) -----------------------------------------

CACHE_BUTTON_TEXT = "Stattdessen Niedersachsen-Cache verwenden"


def readable_date(iso):
    """'2026-11-17T21:24:30Z' -> '17.11.2026' (unchanged if not a date)."""
    text = str(iso or "")
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return f"{text[8:10]}.{text[5:7]}.{text[0:4]}"
    return text or "unbekannt"


def cache_question_text(error_text, data_date):
    """Question after Overpass failed and the cache covers the area."""
    return (
        f"{error_text}\n\n"
        "Das Gebiet liegt im Niedersachsen-Cache des Teams: OSM-Daten der Großstädte "
        "Niedersachsens und der Gemeinden rund um Oldenburg, jede Woche neu gebaut "
        f"(Stand {readable_date(data_date)}). Einige Merkmale fehlen dort, z. B. Zäune "
        "und Hecken; Schritt 4 zeigt, welche.\n\n"
        "Stattdessen den Niedersachsen-Cache verwenden?"
    )


def cache_unusable_text(error_text, reason):
    """Error after Overpass failed and the cache cannot stand in."""
    return f"{error_text}\n\nDer Niedersachsen-Cache kann nicht einspringen: {reason}"


def unpack(data):
    """Cache tiles are gzip files; plain JSON is taken as it is."""
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def fetch_url(url, feedback, is_canceled, what):
    """GET one file of the cache (GitHub Pages, no retries needed)."""
    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    if is_canceled():
        raise DownloadCanceled()
    blocking = QgsBlockingNetworkRequest()
    error = blocking.get(QNetworkRequest(QUrl(url)), True, feedback)
    if is_canceled():
        raise DownloadCanceled()
    reply = blocking.reply()
    status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    status = int(status) if status else 0
    if error != QgsBlockingNetworkRequest.NoError or status not in (0, 200):
        reason = blocking.errorMessage() or reply.errorString() or f"Fehler {status}"
        raise DownloadError(
            f"Der Niedersachsen-Cache ist nicht erreichbar ({what}: {reason}).\n"
            "Was tun: Internetverbindung prüfen und später erneut „Daten laden“ klicken."
        )
    return bytes(reply.content())


def cache_plan(box, feedback, is_canceled, catalog=None):
    """Plan of the cache for the 4326 rectangle (manifest fetched first)."""
    from .osm_cache import manifest_url, plan_cache_download
    from .sources import load_catalog

    catalog = catalog if catalog is not None else load_catalog()
    data = fetch_url(manifest_url(catalog), feedback, is_canceled, "Übersicht")
    try:
        manifest = json.loads(unpack(data).decode("utf-8"))
    except (ValueError, OSError) as error:
        raise DownloadError(
            f"Die Übersicht des Niedersachsen-Caches ist nicht lesbar ({error}).\n"
            "Was tun: später erneut versuchen und die Meldung an das Team weitergeben."
        ) from error
    return plan_cache_download(tuple(box), manifest, catalog)


def cache_offer_or_error(box, error_text, feedback, is_canceled, plan=None):
    """After Overpass failed: ``CacheOffer`` if the cache covers the area,
    else a ``DownloadError`` that names why it cannot stand in."""
    if plan is None:
        try:
            plan = cache_plan(box, feedback, is_canceled)
        except DownloadError as error:
            return DownloadError(cache_unusable_text(error_text, str(error).split("\n")[0]))
    if not plan.usable:
        return DownloadError(cache_unusable_text(error_text, plan.reason))
    return CacheOffer(error_text, plan.data_date)


def run_cache_download(box, folder, project_crs, transform_context, feedback,
                       is_canceled, report, progress, plan=None):
    """OSM from the Niedersachsen-Cache instead of Overpass (runs inside a
    QgsTask).  Raw tiles are kept as one unchanged JSON file; the layers
    points/lines/multipolygons go into one GeoPackage in the project CRS, so
    the OSM profile of the pipeline works as after an Overpass download.

    Returns ``(gpkg_path, issue)``; ``issue`` is the visible info hint (E35)."""
    from .osm_cache import cache_issue, elements_to_layers, merge_tiles
    from .sources import load_catalog

    catalog = load_catalog()
    progress(2)
    report("Niedersachsen-Cache wird geprüft …")
    if plan is None:
        plan = cache_plan(box, feedback, is_canceled, catalog)
    if not plan.usable:
        raise DownloadError(
            f"Der Niedersachsen-Cache kann nicht einspringen: {plan.reason}\n"
            "Was tun: später erneut „Daten laden“ klicken, wenn der OSM-Server wieder antwortet."
        )
    tiles = []
    total = len(plan.tile_urls)
    for number, url in enumerate(plan.tile_urls, start=1):
        report(f"OSM-Daten werden aus dem Niedersachsen-Cache geladen (Teil {number} von {total}) …")
        data = fetch_url(url, feedback, is_canceled, f"Teil {number}")
        try:
            tiles.append(json.loads(unpack(data).decode("utf-8")))
        except (ValueError, OSError) as error:
            raise DownloadError(
                f"Ein Teil des Niedersachsen-Caches ist nicht lesbar (Teil {number}: {error}).\n"
                "Was tun: später erneut versuchen und die Meldung an das Team weitergeben."
            ) from error
        progress(2 + 60 * number / total)
    elements = merge_tiles(tiles)
    raw_path = unique_path(folder, plan.raw_file_name)
    try:
        raw_path.write_text(json.dumps({"datenstand": plan.data_date, "elements": elements}),
                            encoding="utf-8")
    except OSError as error:
        raise DownloadError(
            f"Die Rohdatei aus dem Cache konnte nicht gespeichert werden: {error}\n"
            "Was tun: einen anderen Ordner wählen (Schreibrechte, freier Speicherplatz)."
        ) from error
    if is_canceled():
        raise DownloadCanceled()
    report("OSM-Daten aus dem Cache werden ins Projekt-KBS umgerechnet und gespeichert …")
    layers, skipped = elements_to_layers(elements, catalog["osm"]["abfrage"]["schluessel"])
    parts = []
    for name in OSM_LAYERS:
        if not layers[name]["features"]:
            continue
        path = unique_path(folder, plan.geojson_name.replace("{layer}", name))
        try:
            path.write_text(json.dumps(layers[name]), encoding="utf-8")
        except OSError as error:
            raise DownloadError(
                f"Die Cache-Daten konnten nicht gespeichert werden: {error}\n"
                "Was tun: einen anderen Ordner wählen (Schreibrechte, freier Speicherplatz)."
            ) from error
        parts.append((name, str(path)))
    gpkg_path = unique_path(folder, plan.geopackage_name)
    write_layers(parts, gpkg_path, project_crs, transform_context)
    progress(100)
    return gpkg_path, cache_issue(plan, catalog, skipped)


# --- ALKIS (W10 part 2, M10b): WFS in tiles ------------------------------------

ALKIS_LAYER_NAMES = {  # GeoPackage layer -> readable name in messages
    "GebaeudeBauwerk": "Gebäude",
    "Nutzung": "Nutzung",
    "Flurstueck": "Flurstücke",
}


def alkis_error_text(status, reason, attempts):
    """Readable message after an ALKIS request finally failed."""
    if not status:
        return (
            "Die ALKIS-Daten konnten nicht geladen werden: keine Verbindung zum Dienst "
            f"des Bundeslands ({reason or 'keine Antwort'}).\n"
            "Was tun: Internetverbindung prüfen (an der Hochschule ggf. den Proxy in QGIS "
            "unter Einstellungen → Netzwerk) und erneut „Daten laden“ klicken."
        )
    if status in RETRY_STATUS:
        return (
            f"Der ALKIS-Dienst ist überlastet (Fehler {status}); auch nach {attempts} "
            "Versuchen kam keine Antwort.\n"
            "Was tun: in ein paar Minuten erneut „Daten laden“ klicken oder das Gebiet verkleinern."
        )
    return (
        f"Der ALKIS-Dienst hat die Anfrage abgelehnt (Fehler {status}: {reason}).\n"
        "Was tun: erneut versuchen; bleibt der Fehler, ohne ALKIS (nur OSM) weiterarbeiten "
        "und die Meldung an das Team weitergeben."
    )


def wfs_exception_text(data):
    """The error text of a WFS 'ExceptionReport' (delivered with status 200),
    or None if ``data`` is not one.  An HTML page instead of data (e.g. a
    maintenance page of the service) is an error, too."""
    head = data[:4000].decode("utf-8", "replace")
    start = head.lstrip().lower()
    if start.startswith("<!doctype html") or start.startswith("<html"):
        return ("Der Dienst hat statt Daten eine Webseite geschickt – er ist wahrscheinlich "
                "gerade in Wartung oder nicht erreichbar")
    if "ExceptionReport" not in head:
        return None
    start = head.find("<ows:ExceptionText>")
    end = head.find("</ows:ExceptionText>")
    if start >= 0 and end > start:
        return head[start + len("<ows:ExceptionText>"):end].strip()
    return "unbekannter Fehler des Dienstes"


def truncated_text(layer_name, part, parts, limit):
    """Hint for a tile that probably did not deliver everything."""
    name = ALKIS_LAYER_NAMES.get(layer_name, layer_name)
    return (
        f"ALKIS – {name}: Teil {part} von {parts} hat genau {limit} Objekte geliefert, das ist "
        "die Obergrenze des Dienstes. Wahrscheinlich fehlen dort Objekte.\n"
        "Was tun: das Gebiet in Schritt 2 verkleinern."
    )


def alkis_progress_text(layer_name, part, parts):
    name = ALKIS_LAYER_NAMES.get(layer_name, layer_name)
    return f"ALKIS – {name} wird geladen (Teil {part} von {parts}) …"


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
            raise OsmServerError(download_error_text(status, reason, attempt))
        pause = RETRY_PAUSES_S[attempt - 1]
        for left in range(pause, 0, -1):  # visible countdown, cancel stays possible
            if is_canceled():
                raise DownloadCanceled()
            report(retry_text(left, attempt + 1, total))
            sleep(1)
        report("Neuer Versuch, OSM-Daten werden geladen …")
    raise OsmServerError(download_error_text(0, "", total))  # not reached


def convert_to_geopackage(raw_path, gpkg_path, project_crs, transform_context):
    """Read the .osm file with GDAL (points, lines, multipolygons) and write
    them into one new GeoPackage in the project CRS.  Returns the written
    layer names; empty layers are left out."""
    parts = [(name, f"{raw_path}|layername={name}") for name in OSM_LAYERS]
    return write_layers(parts, gpkg_path, project_crs, transform_context)


def write_layers(parts, gpkg_path, project_crs, transform_context):
    """Write ``(layer name, OGR source)`` pairs into one new GeoPackage in the
    project CRS.  Returns the written names; empty layers are left out."""
    from qgis.core import (
        QgsCoordinateTransform,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )

    written = []
    for name, uri in parts:
        layer = QgsVectorLayer(uri, name, "ogr")
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


def fetch_get(request, feedback, is_canceled, report, sleep=time.sleep):
    """GET one WFS request (ALKIS); retry a busy server.  Returns the bytes."""
    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    total = len(RETRY_PAUSES_S) + 1
    for attempt in range(1, total + 1):
        if is_canceled():
            raise DownloadCanceled()
        blocking = QgsBlockingNetworkRequest()
        error = blocking.get(QNetworkRequest(QUrl(request.url)), True, feedback)
        if is_canceled():
            raise DownloadCanceled()
        reply = blocking.reply()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        status = int(status) if status else 0
        if error == QgsBlockingNetworkRequest.NoError and status in (0, 200):
            data = bytes(reply.content())
            problem = wfs_exception_text(data)
            if problem:
                raise DownloadError(
                    f"Der ALKIS-Dienst meldet einen Fehler: {problem}\n"
                    "Was tun: erneut versuchen oder ohne ALKIS (nur OSM) weiterarbeiten.")
            return data
        reason = blocking.errorMessage() or reply.errorString()
        if status not in RETRY_STATUS or attempt == total:
            raise DownloadError(alkis_error_text(status, reason, attempt))
        pause = RETRY_PAUSES_S[attempt - 1]
        for left in range(pause, 0, -1):
            if is_canceled():
                raise DownloadCanceled()
            report(f"Der ALKIS-Dienst ist gerade überlastet – neuer Versuch in {left} s "
                   f"({attempt + 1} von {total}).")
            sleep(1)
    raise DownloadError(alkis_error_text(0, "", total))  # not reached


def run_alkis_download(requests, folder, project_crs, transform_context, feedback,
                       is_canceled, report, progress):
    """Whole ALKIS download (runs inside a QgsTask): every tile of every
    layer, raw files kept unchanged, tiles merged per layer (objects on the
    tile edges only once, by object ID), one GeoPackage in the project CRS.

    Returns ``(gpkg_path, notes)``; ``notes`` are visible hints (e.g. a
    tile that hit the limit of the service)."""
    from qgis.core import (
        QgsCoordinateTransform, QgsFeature, QgsVectorFileWriter, QgsVectorLayer,
    )

    if not requests:
        raise DownloadError("Für dieses Gebiet gibt es keinen ALKIS-Auftrag.")
    notes = []
    merged = {}  # layer name -> (memory layer, seen ids)
    total = len(requests)
    for number, request in enumerate(requests, start=1):
        report(alkis_progress_text(request.layer_name, request.part, request.parts))
        data = fetch_get(request, feedback, is_canceled, report)
        raw_path = unique_path(folder, request.raw_file_name)
        try:
            raw_path.write_bytes(data)
        except OSError as error:
            raise DownloadError(
                f"Die ALKIS-Rohdatei konnte nicht gespeichert werden: {error}\n"
                "Was tun: einen anderen Ordner wählen (Schreibrechte, freier Speicherplatz)."
            ) from error
        tile = QgsVectorLayer(str(raw_path), request.layer_name, "ogr")
        count = tile.featureCount() if tile.isValid() else 0
        if request.max_features and count >= request.max_features:
            notes.append(truncated_text(request.layer_name, request.part, request.parts,
                                        request.max_features))
        if count:
            target, seen = merged.get(request.layer_name, (None, set()))
            if target is None:
                wkb = tile.wkbType()
                from qgis.core import QgsWkbTypes

                type_name = QgsWkbTypes.displayString(QgsWkbTypes.multiType(wkb))
                target = QgsVectorLayer(f"{type_name}?crs={tile.crs().authid()}",
                                        request.layer_name, "memory")
            provider = target.dataProvider()
            new_fields = [f for f in tile.fields() if target.fields().indexOf(f.name()) < 0]
            if new_fields:
                provider.addAttributes(new_fields)
                target.updateFields()
            names = [f.name() for f in tile.fields()]
            features = []
            for original in tile.getFeatures():
                key = original[request.id_field] if request.id_field in names else None
                if key not in (None, ""):
                    if key in seen:
                        continue  # same object from the neighbouring tile
                    seen.add(key)
                feature = QgsFeature(target.fields())
                geometry = original.geometry()
                geometry.convertToMultiType()
                feature.setGeometry(geometry)
                for name in names:
                    feature[name] = original[name]
                features.append(feature)
            provider.addFeatures(features)
            merged[request.layer_name] = (target, seen)
        if is_canceled():
            raise DownloadCanceled()
        progress(5 + 80 * number / total)
    if not merged:
        raise DownloadError(
            "Im gewählten Gebiet hat der ALKIS-Dienst keine Objekte geliefert.\n"
            "Was tun: Gebiet und Bundesland prüfen."
        )
    report("ALKIS-Daten werden ins Projekt-KBS umgerechnet und gespeichert …")
    gpkg_path = unique_path(folder, requests[0].geopackage_name)
    first = True
    for name, (layer, _seen) in merged.items():
        layer.updateExtents()
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        options.layerName = name  # no prefix: the pipeline profile knows these names
        options.ct = QgsCoordinateTransform(layer.crs(), project_crs, transform_context)
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(gpkg_path), transform_context, options)
        if result[0] != QgsVectorFileWriter.NoError:
            raise DownloadError(
                f"Die ALKIS-Daten konnten nicht als GeoPackage gespeichert werden "
                f"(Layer „{name}“: {result[1]}).\nWas tun: einen anderen Ordner wählen "
                "(Schreibrechte, freier Speicherplatz) und erneut laden."
            )
        first = False
    progress(90)
    return gpkg_path, notes


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
