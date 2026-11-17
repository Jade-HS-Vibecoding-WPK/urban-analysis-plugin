"""GeoPackage import and normalization for the urban-analysis MVP.

The module deliberately keeps the data pipeline independent from the guided
workflow.  It uses the GeoPackage SQLite metadata directly, so import tests
can run without a QGIS installation.  A QGIS project can consume the returned
``PipelineResult`` through the existing contract.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    AttributeSuggestion,
    LayerDescriptor,
    MVP_DEFAULT_BUFFER_METERS,
    PipelineResult,
    ValidationIssue,
)
from .geometry import (
    Geometry,
    GeometryError,
    bboxes_within,
    gpkg_envelope,
    parse_wkt,
    read_geometry,
    validate_study_area,
    within_distance,
)


TARGET_FIELDS = ("source_name", "object_type", "category", "status", "area_m2", "year", "source")
TARGET_FIELD_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "object_type": (
        "object_type",
        "objecttype",
        "type",
        "typ",
        "haltestellenart",
        "ken__bez",
    ),
    "category": (
        "category",
        "categorie",
        "kategorie",
        "art",
        "klasse",
        "nutzung",
        "bwf__bez",
    ),
    "status": ("status", "zustand", "state", "untermerkmal"),
    "area_m2": ("area_m2", "area", "fläche", "flaeche", "shape_area"),
    "year": ("year", "jahr", "baujahr"),
    "source": ("source", "quelle", "data_source"),
}
class GeoPackageImportError(ValueError):
    """Raised when a path is not a readable GeoPackage."""


@dataclass(frozen=True)
class MappingRule:
    """Documented source-to-target mapping rule."""

    source_field: str
    target_field: str
    confidence: float


@dataclass(frozen=True)
class HarmonizedRecord:
    """A normalized row retained for later QGIS or export processing."""

    layer_id: str
    source_row_id: Any
    attributes: Mapping[str, Any]
    geometry: Any = None


@dataclass(frozen=True)
class GeoPackageLayer:
    """Metadata and rows imported from one GeoPackage feature table."""

    table_name: str
    geometry_type: str
    source_srs: Optional[str]
    fields: Tuple[str, ...]
    rows: Tuple[Mapping[str, Any], ...]
    geometry_column: Optional[str] = None


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


@dataclass(frozen=True)
class StudyArea:
    """Parsed study-area polygon with the buffer used for clipping."""

    geometry: Geometry
    buffer_meters: float
    bbox: Tuple[float, float, float, float]


# CRS names written by GDAL/QGIS when a GeoPackage stores no EPSG authority.
KNOWN_CRS_NAMES: Mapping[str, str] = {
    "etrs89utmzone32n": "EPSG:25832",
    "etrs89utmzone33n": "EPSG:25833",
    "wgs84": "EPSG:4326",
    "wgs84geodetic": "EPSG:4326",
    "wgs84pseudomercator": "EPSG:3857",
    "dhdn3degreegausskrugerzone2": "EPSG:31466",
    "dhdn3degreegausskrugerzone3": "EPSG:31467",
    "dhdn3degreegausskrugerzone4": "EPSG:31468",
}


def _epsg_code(value: Optional[str]) -> Optional[str]:
    """Return ``EPSG:<n>`` for strings such as ``epsg:25832``, else ``None``."""
    if not value:
        return None
    match = re.fullmatch(r"\s*epsg\s*:\s*(\d+)\s*", value, flags=re.IGNORECASE)
    return f"EPSG:{match.group(1)}" if match else None


def _epsg_from_definition(definition: Optional[str]) -> Optional[str]:
    """Identify the EPSG code from a WKT CRS definition, if it is unambiguous."""
    if not definition:
        return None
    text = definition.strip()
    top_level = re.search(r'(?:AUTHORITY\["EPSG",\s*"(\d+)"\]|ID\["EPSG",\s*(\d+)\])\]\s*$', text)
    if top_level:
        return f"EPSG:{top_level.group(1) or top_level.group(2)}"
    name = re.match(r'\s*(?:PROJCS|GEOGCS|PROJCRS|GEOGCRS|GEODCRS)\["([^"]+)"', text)
    if name:
        return KNOWN_CRS_NAMES.get(_normalized(name.group(1)))
    return None


def _infer_category(table_name: str, values: Iterable[Any]) -> Optional[str]:
    text = " ".join([table_name, *(str(value) for value in values if value is not None)]).casefold()
    category_terms = {
        "Gebäude": ("gebäude", "gebaeude", "building", "buildings", "haus"),
        "Straßen": ("straße", "strasse", "street", "road", "roads"),
        "Nutzungsflächen": ("nutzung", "landuse", "land use", "fläche", "flaeche"),
        "Grünflächen": ("grün", "gruen", "green", "park", "vegetation"),
    }
    for category, terms in category_terms.items():
        if any(term in text for term in terms):
            return category
    return None


def _coerce_area(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _coerce_year(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class GeoPackageImporter:
    """Import and harmonize local GeoPackage feature layers."""

    def __init__(self, *, contract_version: str = "1.0"):
        self.contract_version = contract_version

    def import_file(
        self,
        path: str | Path,
        *,
        project_crs: str,
        study_area_wkt: str,
        buffer_meters: float = MVP_DEFAULT_BUFFER_METERS,
    ) -> PipelineResult:
        """Return a contract result for all feature tables in ``path``."""
        file_path = Path(path)
        if not project_crs.strip():
            raise ValueError("A project CRS is required")
        if not study_area_wkt.strip():
            raise ValueError("A study area polygon is required")
        if buffer_meters < 0:
            raise ValueError("The buffer must not be negative")
        if not file_path.is_file():
            raise GeoPackageImportError(f"GeoPackage does not exist: {file_path}")

        study_area, area_error = self._study_area(study_area_wkt, buffer_meters)
        issues: List[ValidationIssue] = []
        if area_error:
            issues.append(
                ValidationIssue(
                    code="invalid-study-area",
                    message=f"{area_error} Es wurden keine Objekte übernommen.",
                    severity="error",
                    rule="Untersuchungsgebiet",
                )
            )

        try:
            with sqlite3.connect(f"file:{file_path}?mode=ro", uri=True) as connection:
                layers = self._read_layers(connection, study_area, project_crs.strip(), issues)
        except sqlite3.Error as exc:
            raise GeoPackageImportError(f"Unable to read GeoPackage {file_path}: {exc}") from exc

        if not layers:
            issues.append(
                ValidationIssue(
                    code="no-feature-layers",
                    message="Das GeoPackage enthält keine unterstützten Feature-Layer.",
                    severity="error",
                )
            )

        descriptors: List[LayerDescriptor] = []
        suggestions: List[AttributeSuggestion] = []
        records: List[HarmonizedRecord] = []
        for layer in layers:
            category = _infer_category(layer.table_name, (value for row in layer.rows for value in row.values()))
            descriptors.append(
                LayerDescriptor(
                    layer_id=layer.table_name,
                    name=layer.table_name,
                    geometry_type=layer.geometry_type,
                    source_name=str(file_path),
                    category=category,
                )
            )
            for rule in self._mapping_rules(layer.fields):
                suggestions.append(
                    AttributeSuggestion(
                        source_field=rule.source_field,
                        target_field=rule.target_field,
                        confidence=rule.confidence,
                    )
                )
            records.extend(self._harmonize(layer, file_path, category, issues))

        return PipelineResult(
            contract_version=self.contract_version,
            project_crs=project_crs.strip(),
            study_area_wkt=study_area_wkt.strip(),
            buffer_meters=buffer_meters,
            layers=descriptors,
            attribute_suggestions=suggestions,
            issues=issues,
            harmonized_records=records,
        )

    @staticmethod
    def _study_area(wkt: str, buffer_meters: float) -> Tuple[Optional[StudyArea], Optional[str]]:
        try:
            geometry = parse_wkt(wkt)
        except GeometryError as exc:
            return None, f"Das Untersuchungsgebiet konnte nicht als WKT gelesen werden ({exc})."
        message = validate_study_area(geometry)
        if message:
            return None, message
        bbox = geometry.bbox()
        assert bbox is not None  # validate_study_area rejects empty geometries
        return StudyArea(geometry, buffer_meters, bbox), None

    def _read_layers(
        self,
        connection: sqlite3.Connection,
        study_area: Optional[StudyArea],
        project_crs: str,
        issues: List[ValidationIssue],
    ) -> List[GeoPackageLayer]:
        tables = self._feature_tables(connection)
        layers: List[GeoPackageLayer] = []
        for table_name, geometry_type, srs_id in tables:
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            columns = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({quoted_table})"))
            if not columns:
                continue
            geometry_column = self._geometry_column(connection, table_name)
            if geometry_column not in columns:
                geometry_column = None
            source_srs, source_epsg, is_geographic = self._srs(connection, srs_id)
            crs_usable = self._check_crs(
                table_name, source_srs, source_epsg, is_geographic, project_crs, study_area, issues
            )
            rows: List[Mapping[str, Any]] = []
            if geometry_column is None:
                issues.append(
                    ValidationIssue(
                        code="missing-geometry-column",
                        message=f"Layer {table_name} hat keine Geometriespalte und wurde nicht übernommen.",
                        severity="warning",
                    )
                )
            elif study_area is not None and crs_usable:
                rows = self._clip_rows(connection, quoted_table, table_name, geometry_column, study_area, issues)
            layers.append(
                GeoPackageLayer(table_name, geometry_type, source_srs, columns, tuple(rows), geometry_column)
            )
        return layers

    @staticmethod
    def _clip_rows(
        connection: sqlite3.Connection,
        quoted_table: str,
        table_name: str,
        geometry_column: str,
        study_area: StudyArea,
        issues: List[ValidationIssue],
    ) -> List[Mapping[str, Any]]:
        """Keep rows whose geometry lies within the buffered study area."""
        buffer = study_area.buffer_meters
        rows: List[Mapping[str, Any]] = []
        total = missing = unreadable = 0
        first_error: Optional[str] = None
        cursor = connection.execute(f"SELECT * FROM {quoted_table}")
        names = tuple(column[0] for column in cursor.description or ())
        for row in cursor:
            total += 1
            values = dict(zip(names, row))
            raw_geometry = values.get(geometry_column)
            if isinstance(raw_geometry, bytes):
                envelope = gpkg_envelope(raw_geometry)
                if envelope is not None and not bboxes_within(envelope, study_area.bbox, buffer):
                    continue
            try:
                geometry = read_geometry(raw_geometry)
            except GeometryError as exc:
                unreadable += 1
                first_error = first_error or str(exc)
                continue
            if geometry is None or geometry.is_empty:
                missing += 1
                continue
            if within_distance(geometry, study_area.geometry, buffer):
                rows.append(values)

        if missing:
            issues.append(
                ValidationIssue(
                    code="missing-geometry",
                    message=f"{missing} Objekt(e) ohne Geometrie in Layer {table_name} wurden nicht übernommen.",
                    severity="warning",
                    rule="Räumliche Begrenzung",
                )
            )
        if unreadable:
            issues.append(
                ValidationIssue(
                    code="unreadable-geometry",
                    message=(
                        f"{unreadable} Objekt(e) mit nicht lesbarer Geometrie in Layer {table_name} "
                        f"wurden nicht übernommen (z. B.: {first_error})."
                    ),
                    severity="warning",
                    rule="Räumliche Begrenzung",
                )
            )
        issues.append(
            ValidationIssue(
                code="clip-summary",
                message=(
                    f"Layer {table_name}: {len(rows)} von {total} Objekten liegen im "
                    f"Untersuchungsgebiet inklusive {buffer:g} m Puffer."
                ),
                severity="info",
                rule="Räumliche Begrenzung",
            )
        )
        return rows

    @staticmethod
    def _check_crs(
        table_name: str,
        source_srs: Optional[str],
        source_epsg: Optional[str],
        is_geographic: bool,
        project_crs: str,
        study_area: Optional[StudyArea],
        issues: List[ValidationIssue],
    ) -> bool:
        """Report CRS problems; return whether the layer can be clipped."""
        project_epsg = _epsg_code(project_crs)
        if source_epsg and project_epsg and source_epsg != project_epsg:
            issues.append(
                ValidationIssue(
                    code="crs-mismatch",
                    message=(
                        f"Layer {table_name} verwendet {source_epsg}; Projekt-CRS ist {project_epsg}. "
                        "Die Pipeline rechnet keine Koordinaten um, der Layer wurde nicht übernommen. "
                        "Bitte den Layer in QGIS ins Projekt-CRS umprojizieren."
                    ),
                    severity="error",
                    rule="Projekt-CRS",
                )
            )
            return False
        if not (source_epsg and project_epsg):
            issues.append(
                ValidationIssue(
                    code="crs-unverified",
                    message=(
                        f"Das Koordinatensystem von Layer {table_name} ({source_srs or 'unbekannt'}) "
                        f"kann nicht eindeutig mit dem Projekt-CRS {project_crs} verglichen werden. "
                        "Die räumliche Begrenzung nimmt an, dass beide übereinstimmen."
                    ),
                    severity="warning",
                    requires_confirmation=True,
                    rule="Projekt-CRS",
                )
            )
        if is_geographic and study_area is not None and study_area.buffer_meters:
            issues.append(
                ValidationIssue(
                    code="geographic-crs-buffer",
                    message=(
                        f"Layer {table_name} liegt in einem geografischen CRS (Grad). Ein Puffer in "
                        "Metern ist dort nicht anwendbar, der Layer wurde nicht übernommen. "
                        "Bitte ein metrisches Projekt-CRS wie EPSG:25832 verwenden."
                    ),
                    severity="error",
                    rule="Projekt-CRS",
                )
            )
            return False
        return True

    @staticmethod
    def _feature_tables(connection: sqlite3.Connection) -> List[Tuple[str, str, Optional[int]]]:
        try:
            rows = connection.execute(
                "SELECT table_name, geometry_type_name, srs_id "
                "FROM gpkg_geometry_columns"
            ).fetchall()
        except sqlite3.Error:
            raise GeoPackageImportError("GeoPackage-Metadaten gpkg_geometry_columns fehlen")
        return [(str(table), str(geometry), srs_id) for table, geometry, srs_id in rows]

    @staticmethod
    def _geometry_column(connection: sqlite3.Connection, table_name: str) -> Optional[str]:
        row = connection.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
            (table_name,),
        ).fetchone()
        return str(row[0]) if row else None

    @staticmethod
    def _srs(
        connection: sqlite3.Connection, srs_id: Optional[int]
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """Return (label, EPSG code if identifiable, is geographic) for ``srs_id``."""
        if srs_id is None:
            return None, None, False
        columns = {row[1] for row in connection.execute("PRAGMA table_info(gpkg_spatial_ref_sys)")}
        definition_column = "definition" if "definition" in columns else "NULL"
        name_column = "srs_name" if "srs_name" in columns else "NULL"
        row = connection.execute(
            f"SELECT organization, organization_coordsys_id, {name_column}, {definition_column} "
            "FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
            (srs_id,),
        ).fetchone()
        if not row:
            return None, None, False
        organization, code, name, definition = row
        label = f"{organization}:{code}"
        if name:
            label = f"{label} ({name})"
        if str(organization).casefold() == "epsg":
            epsg: Optional[str] = f"EPSG:{code}"
        else:
            epsg = _epsg_from_definition(definition) or (KNOWN_CRS_NAMES.get(_normalized(name)) if name else None)
        is_geographic = bool(definition) and str(definition).lstrip().upper().startswith(
            ("GEOGCS", "GEOGCRS", "GEODCRS")
        )
        return label, epsg, is_geographic

    @staticmethod
    def _mapping_rules(fields: Sequence[str]) -> Tuple[MappingRule, ...]:
        normalized_fields = {_normalized(field): field for field in fields}
        rules: List[MappingRule] = []
        for target_field, aliases in TARGET_FIELD_ALIASES.items():
            for alias in aliases:
                source_field = normalized_fields.get(_normalized(alias))
                if source_field:
                    confidence = 1.0 if _normalized(source_field) == _normalized(target_field) else 0.8
                    rules.append(MappingRule(source_field, target_field, confidence))
                    break
        return tuple(rules)

    @staticmethod
    def _harmonize(
        layer: GeoPackageLayer,
        file_path: Path,
        category: Optional[str],
        issues: List[ValidationIssue],
    ) -> List[HarmonizedRecord]:
        rules = {rule.target_field: rule.source_field for rule in GeoPackageImporter._mapping_rules(layer.fields)}
        seen: set[Tuple[Any, ...]] = set()
        records: List[HarmonizedRecord] = []
        geometry_column = layer.geometry_column or next(
            (
                field
                for field in layer.fields
                if _normalized(field) in {"geom", "geometry", "thegeom", "wktgeom"}
            ),
            None,
        )
        row_id_column = next(
            (field for field in layer.fields if _normalized(field) in {"fid", "id", "rowid"}),
            None,
        )
        duplicate_count = 0
        for index, row in enumerate(layer.rows, start=1):
            attributes: Dict[str, Any] = {
                "source_name": str(file_path),
                "object_type": row.get(rules["object_type"]) if "object_type" in rules else layer.table_name,
                "category": row.get(rules["category"]) if "category" in rules else category,
                "status": row.get(rules["status"]) if "status" in rules else None,
                "area_m2": _coerce_area(row.get(rules["area_m2"])) if "area_m2" in rules else None,
                "year": _coerce_year(row.get(rules["year"])) if "year" in rules else None,
                "source": row.get(rules["source"]) if "source" in rules else str(file_path),
            }
            geometry_value = row.get(geometry_column) if geometry_column else None
            duplicate_key = (*(attributes[field] for field in TARGET_FIELDS), geometry_value)
            if duplicate_key in seen:
                duplicate_count += 1
                continue
            seen.add(duplicate_key)
            records.append(
                HarmonizedRecord(
                    layer_id=layer.table_name,
                    source_row_id=row.get(row_id_column, index) if row_id_column else index,
                    attributes=attributes,
                    geometry=geometry_value,
                )
            )
        if duplicate_count:
            issues.append(
                ValidationIssue(
                    code="duplicate-row",
                    message=(
                        f"{duplicate_count} exakte Dublette(n) in Layer "
                        f"{layer.table_name} wurden entfernt."
                    ),
                    severity="warning",
                    rule="Exakte Attribute und Geometrie",
                )
            )
        return records
