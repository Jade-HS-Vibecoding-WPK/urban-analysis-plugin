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
    if plan.blocked:
        return plan
    plan.requests.append(osm_request(tuple(lonlat_box), catalog, today))
    return plan
