"""Which data to download for a study area (S9, M10a).

QGIS-free and without extra packages, like ``data_pipeline.py``.  This module
only *plans* downloads: it checks the size of the download rectangle (E13) and
builds the OpenStreetMap request from ``sources_catalog.json``.  The actual
download, the reprojection and saving as GeoPackage happen in QGIS (S10, W11).

Coordinates: the size is measured in the project CRS (metres), from the study
area plus buffer.  The rectangle for Overpass comes from QGIS already in
EPSG:4326 (longitude/latitude), so the pipeline never reprojects (decided with
Person Windows in PR #34).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import ValidationIssue
from .geometry import GeometryError, parse_wkt

CATALOG_PATH = Path(__file__).with_name("sources_catalog.json")

# (west, south, east, north) in degrees, EPSG:4326
LonLatBox = Tuple[float, float, float, float]


class SourcesCatalogError(ValueError):
    """``sources_catalog.json`` is missing or broken."""


@dataclass(frozen=True)
class DownloadRequest:
    """One download job for QGIS (W11): what to fetch and how to label it."""

    source_kind: str  # "OSM" or "ALKIS"
    url: str
    query: str  # Overpass QL; QGIS sends it as POST field "data"
    delivery_crs: str  # CRS of the delivered data, QGIS reprojects
    raw_file_name: str  # unchanged download, e.g. osm_2026-11-18.osm
    geopackage_name: str  # converted file in the project CRS
    licence: str
    licence_url: str
    attribution: str  # pre-fills "Datenquelle" (S8, E28)
    timeout_s: int
    # ALKIS (M10b): layer in the GeoPackage, e.g. "GebaeudeBauwerk"; one
    # layer can come in several parts (tiles) that are joined in QGIS,
    # dropping objects whose ``id_field`` value was already written.
    layer_name: str = ""
    part: int = 1
    parts: int = 1
    max_features: int = 0  # a part with this many objects is probably cut off
    id_field: str = ""


@dataclass
class SourcePlan:
    """Result of planning: the jobs, the visible hints and the area size."""

    requests: List[DownloadRequest] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    area_km2: Optional[float] = None

    @property
    def blocked(self) -> bool:
        """True if an error prevents any download."""
        return any(issue.severity == "error" for issue in self.issues)


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read ``sources_catalog.json``; a broken file is a clear error."""
    path = Path(path) if path is not None else CATALOG_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SourcesCatalogError(f"Der Quellen-Katalog „{path.name}“ ist nicht lesbar: {error}") from error


def area_limits(catalog: Mapping[str, Any]) -> Tuple[float, float]:
    """(warning, maximum) in km² from the catalog (E13)."""
    area = catalog.get("gebiet") or {}
    try:
        warning, maximum = float(area["warnung_km2"]), float(area["max_km2"])
    except (KeyError, TypeError, ValueError) as error:
        raise SourcesCatalogError("Im Quellen-Katalog fehlen die Grenzwerte für die Gebietsgröße.") from error
    if not 0 < warning <= maximum:
        raise SourcesCatalogError("Die Grenzwerte für die Gebietsgröße passen nicht zusammen.")
    return warning, maximum


def format_km2(km2: float) -> str:
    """'10,9' – one decimal with a German comma (same as step 2)."""
    return f"{km2:,.1f}".replace(",", " ").replace(".", ",")


def download_box_km2(study_area_wkt: str, buffer_meters: float) -> float:
    """Size of the rectangle around study area + buffer, in km².

    Same rule as step 2 (``study_area.download_box_km2``): the bounding box of
    the area, grown by the buffer on every side.  Needs a metric project CRS.
    """
    geometry = parse_wkt(study_area_wkt)
    box = geometry.bbox()
    if box is None:
        raise GeometryError("Das Untersuchungsgebiet ist leer.")
    xmin, ymin, xmax, ymax = box
    width = (xmax - xmin) + 2 * buffer_meters
    height = (ymax - ymin) + 2 * buffer_meters
    return max(width, 0.0) * max(height, 0.0) / 1_000_000


def check_area_size(km2: float, catalog: Mapping[str, Any]) -> Optional[ValidationIssue]:
    """Warning above the first limit, error above the maximum (E13)."""
    warning, maximum = area_limits(catalog)
    size = format_km2(km2)
    if km2 > maximum:
        return ValidationIssue(
            code="area-too-large",
            message=(
                f"Das Gebiet ist mit Puffer {size} km² groß. OSM- und ALKIS-Daten können "
                f"nur für höchstens {format_km2(maximum)} km² heruntergeladen werden. "
                "Bitte das Gebiet oder den Puffer verkleinern oder eine eigene Datei laden."
            ),
            severity="error",
            rule=f"Rechteck aus Gebiet und Puffer höchstens {format_km2(maximum)} km² (E13)",
        )
    if km2 > warning:
        return ValidationIssue(
            code="area-large",
            message=(
                f"Großes Gebiet: {size} km² (über {format_km2(warning)} km²). Das Laden "
                "kann lange dauern und die Dateien werden groß."
            ),
            severity="warning",
            requires_confirmation=True,
            rule=f"Warnung über {format_km2(warning)} km² (E13)",
        )
    return None


def check_lonlat_box(box: Sequence[float]) -> Optional[str]:
    """Error text if ``box`` is not (west, south, east, north) in degrees."""
    if len(box) != 4:
        return "Das Download-Rechteck braucht genau vier Werte (West, Süd, Ost, Nord)."
    west, south, east, north = box
    if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90):
        return (
            "Das Download-Rechteck ist nicht in Längen- und Breitengraden (EPSG:4326) "
            "angegeben. QGIS muss es vor der Übergabe umrechnen."
        )
    if not (west < east and south < north):
        return "Das Download-Rechteck ist leer oder vertauscht (West < Ost, Süd < Nord)."
    return None


def osm_query(box: LonLatBox, keys: Sequence[str], timeout_s: int) -> str:
    """Overpass QL for all objects with one of ``keys`` in ``box``.

    Nodes and ways with a key, plus area relations (multipolygons); ``>``
    adds the nodes and ways they are made of, so QGIS/GDAL can build the
    geometries (layers points, lines, multipolygons).
    """
    west, south, east, north = box
    bbox = f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}"
    parts = [f'  nw["{key}"];' for key in keys]
    parts.append('  rel["type"="multipolygon"];')
    return (
        f"[out:xml][timeout:{int(timeout_s)}][bbox:{bbox}];\n"
        "(\n" + "\n".join(parts) + "\n);\n"
        "(._;>;);\n"
        "out body qt;\n"
    )


def osm_request(box: LonLatBox, catalog: Mapping[str, Any], today: Optional[date] = None) -> DownloadRequest:
    """The OSM download job for ``box`` (EPSG:4326), labelled from the catalog."""
    osm = catalog["osm"]
    settings = osm["abfrage"]
    day = (today or date.today()).isoformat()
    return DownloadRequest(
        source_kind="OSM",
        url=osm["url"],
        query=osm_query(box, settings["schluessel"], settings["zeitlimit_s"]),
        delivery_crs=osm["crs_lieferung"],
        raw_file_name=settings["rohdatei"].format(datum=day),
        geopackage_name=settings["geopackage"].format(datum=day),
        licence=osm["lizenz"],
        licence_url=osm["lizenz_url"],
        attribution=osm["quellenvermerk"],
        timeout_s=int(settings["zeitlimit_s"]),
    )


def plan_osm_download(
    study_area_wkt: str,
    buffer_meters: float,
    lonlat_box: Sequence[float],
    *,
    catalog: Optional[Mapping[str, Any]] = None,
    today: Optional[date] = None,
) -> SourcePlan:
    """Check the size (E13) and build the OSM job (S9, part 1).

    ``study_area_wkt`` is in the (metric) project CRS; ``lonlat_box`` is the
    download rectangle (area + buffer) that QGIS already converted to
    EPSG:4326.  Problems never disappear silently: they come back as
    ``ValidationIssue`` and, for errors, without any download job.
    """
    catalog = catalog if catalog is not None else load_catalog()
    plan = _checked_plan(study_area_wkt, buffer_meters, lonlat_box, catalog)
    if not plan.blocked:
        plan.requests.append(osm_request(tuple(lonlat_box), catalog, today))
    return plan


def _checked_plan(
    study_area_wkt: str, buffer_meters: float, lonlat_box: Sequence[float], catalog: Mapping[str, Any]
) -> SourcePlan:
    """Plan with the size (E13) and the download rectangle checked, no jobs yet."""
    plan = SourcePlan()
    try:
        plan.area_km2 = download_box_km2(study_area_wkt, buffer_meters)
    except GeometryError as error:
        plan.issues.append(
            ValidationIssue(
                code="area-unreadable",
                message=f"Das Untersuchungsgebiet ist nicht lesbar: {error}",
                severity="error",
                rule="Untersuchungsgebiet als WKT im Projekt-KBS",
            )
        )
        return plan
    size_issue = check_area_size(plan.area_km2, catalog)
    if size_issue is not None:
        plan.issues.append(size_issue)
    box_problem = check_lonlat_box(lonlat_box)
    if box_problem:
        plan.issues.append(
            ValidationIssue(
                code="download-box-invalid",
                message=box_problem,
                severity="error",
                rule="Download-Rechteck in EPSG:4326 (West, Süd, Ost, Nord)",
            )
        )
    return plan


# --- ALKIS (M10b) -------------------------------------------------------------

STATE_READY = "verfügbar"
STATE_LATER = "kommt später"
STATE_BLOCKED = "gesperrt"


@dataclass(frozen=True)
class StateInfo:
    """One federal state for the choice in step 3 (the user picks it, E11)."""

    code: str  # "NI"
    name: str  # "Niedersachsen"
    status: str  # STATE_READY, STATE_LATER or STATE_BLOCKED
    note: str = ""  # why not ready, in plain language


def alkis_states(catalog: Optional[Mapping[str, Any]] = None) -> List[StateInfo]:
    """All 16 states, sorted by name, with whether ALKIS can be loaded there.

    Ready: the format has a profile in ``mapping_rules.json`` (M12). Later:
    another format (Berlin, Bavaria …). Blocked: licence not confirmed (E28).
    """
    catalog = catalog if catalog is not None else load_catalog()
    ready = set(catalog["alkis_abfrage"]["fertige_formate"])
    formats = catalog.get("alkis_formate", {})
    states = []
    for code, entry in catalog["alkis"].items():
        if code.startswith("_"):
            continue
        if entry.get("gesperrt"):
            status, note = STATE_BLOCKED, str(entry["gesperrt"])
        elif entry.get("format") in ready and entry.get("dienst") == "wfs":
            status, note = STATE_READY, ""
        else:
            name = formats.get(entry.get("format"), {}).get("name", entry.get("format", ""))
            status, note = STATE_LATER, f"Eigenes Datenformat ({name}), wird noch eingebaut."
        states.append(StateInfo(code, entry["land"], status, note))
    return sorted(states, key=lambda state: state.name)


def split_box(box: LonLatBox, tile_m: float) -> List[LonLatBox]:
    """Cut the download rectangle into parts of about ``tile_m`` × ``tile_m``.

    Only the rectangle is divided (degrees per metre at its middle); no data
    is reprojected.
    """
    west, south, east, north = box
    middle = math.radians((south + north) / 2)
    width_m = (east - west) * 111_320 * math.cos(middle)
    height_m = (north - south) * 110_574
    columns = max(1, math.ceil(width_m / tile_m))
    rows = max(1, math.ceil(height_m / tile_m))
    step_x, step_y = (east - west) / columns, (north - south) / rows
    return [
        (west + column * step_x, south + row * step_y, west + (column + 1) * step_x, south + (row + 1) * step_y)
        for row in range(rows)
        for column in range(columns)
    ]


def wfs_getfeature_url(url: str, type_name: str, box: LonLatBox, srs: str) -> str:
    """WFS 2.0 GetFeature for ``box`` given in EPSG:4326 (lat/lon order).

    The service selects in EPSG:4326 and delivers in its own ``srs``; QGIS
    converts to the project CRS afterwards (the pipeline never reprojects).
    """
    west, south, east, north = box
    code = srs.split(":")[-1]
    return (
        f"{url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={type_name}"
        f"&SRSNAME=urn:ogc:def:crs:EPSG::{code}"
        f"&BBOX={south:.6f},{west:.6f},{north:.6f},{east:.6f},urn:ogc:def:crs:EPSG::4326"
    )


def alkis_requests(
    state: str, box: LonLatBox, catalog: Mapping[str, Any], today: Optional[date] = None
) -> List[DownloadRequest]:
    """WFS jobs for one ready state: per layer (buildings, land use, parcels)
    one job per tile of the download rectangle."""
    entry = catalog["alkis"][state]
    settings = catalog["alkis_abfrage"]
    fmt = catalog["alkis_formate"][entry["format"]]
    day = (today or date.today()).isoformat()
    tiles = split_box(box, float(settings["kachel_m"]))
    attribution = str(entry["quellenvermerk"]).replace("{jahr}", day[:4])
    id_field = fmt.get("felder", {}).get("objekt_id", "")
    requests = []
    for layer in settings["ebenen"]:
        if layer not in entry.get("inhalt", ()) or layer not in fmt.get("layer", {}):
            continue
        type_name = fmt["layer"][layer]
        layer_name = type_name.split(":")[-1]
        for number, tile in enumerate(tiles, start=1):
            requests.append(
                DownloadRequest(
                    source_kind="ALKIS",
                    url=wfs_getfeature_url(entry["url"], type_name, tile, entry["crs"]),
                    query="",
                    delivery_crs=entry["crs"],
                    raw_file_name=settings["rohdatei"].format(
                        land=state, ebene=layer_name, teil=f"{number:02d}", datum=day
                    ),
                    geopackage_name=settings["geopackage"].format(land=state, datum=day),
                    licence=entry["lizenz"],
                    licence_url=LICENCE_URLS.get(entry["lizenz"], ""),
                    attribution=attribution,
                    timeout_s=int(settings["zeitlimit_s"]),
                    layer_name=layer_name,
                    part=number,
                    parts=len(tiles),
                    max_features=int(settings["max_objekte_je_abfrage"]),
                    id_field=id_field,
                )
            )
    return requests


LICENCE_URLS = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/deed.de",
    "dl-de/by-2-0": "https://www.govdata.de/dl-de/by-2-0",
    "dl-de/zero-2-0": "https://www.govdata.de/dl-de/zero-2-0",
}


def plan_alkis_download(
    study_area_wkt: str,
    buffer_meters: float,
    lonlat_box: Sequence[float],
    state: str,
    *,
    catalog: Optional[Mapping[str, Any]] = None,
    today: Optional[date] = None,
) -> SourcePlan:
    """Check the size (E13) and build the ALKIS jobs for the chosen state.

    States that are not ready get a visible hint and no jobs; the plugin then
    works with OSM (E6). Never Flurstücke in Bavaria (E28): Bavaria is not a
    WFS state, so it gets no jobs at all.
    """
    catalog = catalog if catalog is not None else load_catalog()
    plan = _checked_plan(study_area_wkt, buffer_meters, lonlat_box, catalog)
    if plan.blocked:
        return plan
    info = next((s for s in alkis_states(catalog) if s.code == state), None)
    if info is None:
        plan.issues.append(
            ValidationIssue(
                code="alkis-unknown-state",
                message=f"Unbekanntes Bundesland „{state}“. Bitte ein Land aus der Liste wählen.",
                severity="error",
                rule="Bundesland aus dem Quellen-Katalog",
            )
        )
        return plan
    if info.status != STATE_READY:
        plan.issues.append(
            ValidationIssue(
                code="alkis-not-available",
                message=(
                    f"ALKIS für {info.name} "
                    + ("ist gesperrt" if info.status == STATE_BLOCKED else "kommt später")
                    + f": {info.note} Das Plugin verwendet OSM."
                ),
                severity="warning",
                rule="ALKIS je Bundesland (E6, E28)",
                action="Mit OSM weiterarbeiten oder einen eigenen ALKIS-Export als Datei laden.",
            )
        )
        return plan
    plan.requests.extend(alkis_requests(state, tuple(lonlat_box), catalog, today))
    return plan
