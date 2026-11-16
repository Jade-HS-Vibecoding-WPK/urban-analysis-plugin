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


TARGET_FIELDS = ("source_name", "object_type", "category", "status", "area_m2", "year", "source")
TARGET_FIELD_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "object_type": ("object_type", "objecttype", "type", "typ", "haltestellenart"),
    "category": ("category", "categorie", "kategorie", "art", "klasse", "nutzung"),
    "status": ("status", "zustand", "state"),
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


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _parse_wkt_bbox(wkt: str) -> Optional[Tuple[float, float, float, float]]:
    values = [float(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", wkt)]
    if len(values) < 4 or len(values) % 2:
        return None
    points = list(zip(values[::2], values[1::2]))
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _geometry_bbox(blob: Any) -> Optional[Tuple[float, float, float, float]]:
    """Read the GeoPackage envelope when the geometry is stored as a blob."""
    if not isinstance(blob, bytes) or len(blob) < 8 or blob[:2] != b"GP":
        return None
    flags = blob[3]
    envelope_indicator = (flags >> 1) & 0b111
    envelope_sizes = {1: 32, 2: 48, 3: 48, 4: 64}
    envelope_size = envelope_sizes.get(envelope_indicator)
    if envelope_size is None or len(blob) < 8 + envelope_size:
        return None
    byte_order = "little" if flags & 1 else "big"
    import struct

    doubles = struct.unpack(
        ("<" if byte_order == "little" else ">") + ("d" * (envelope_size // 8)),
        blob[8 : 8 + envelope_size],
    )
    return doubles[0], doubles[2], doubles[1], doubles[3]


def _intersects(
    geometry_bbox: Optional[Tuple[float, float, float, float]],
    area_bbox: Optional[Tuple[float, float, float, float]],
) -> bool:
    if geometry_bbox is None or area_bbox is None:
        return True
    min_x, min_y, max_x, max_y = geometry_bbox
    area_min_x, area_min_y, area_max_x, area_max_y = area_bbox
    return not (
        max_x < area_min_x
        or min_x > area_max_x
        or max_y < area_min_y
        or min_y > area_max_y
    )


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

        area_bbox = _parse_wkt_bbox(study_area_wkt)
        issues: List[ValidationIssue] = []
        if area_bbox is None:
            issues.append(
                ValidationIssue(
                    code="invalid-study-area",
                    message="Das Untersuchungsgebiet konnte nicht als WKT-Polygon gelesen werden.",
                    severity="error",
                )
            )
        elif buffer_meters:
            area_bbox = (
                area_bbox[0] - buffer_meters,
                area_bbox[1] - buffer_meters,
                area_bbox[2] + buffer_meters,
                area_bbox[3] + buffer_meters,
            )

        try:
            with sqlite3.connect(f"file:{file_path}?mode=ro", uri=True) as connection:
                layers = self._read_layers(connection, area_bbox, issues)
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

            if layer.source_srs and _normalized(layer.source_srs) != _normalized(project_crs):
                issues.append(
                    ValidationIssue(
                        code="crs-mismatch",
                        message=f"Layer {layer.table_name} verwendet {layer.source_srs}; Projekt-CRS ist {project_crs}.",
                        severity="warning",
                        requires_confirmation=True,
                        rule="Projekt-CRS",
                    )
                )

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

    def _read_layers(
        self,
        connection: sqlite3.Connection,
        area_bbox: Optional[Tuple[float, float, float, float]],
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
            rows: List[Mapping[str, Any]] = []
            cursor = connection.execute(f"SELECT * FROM {quoted_table}")
            names = tuple(column[0] for column in cursor.description or ())
            for row in cursor:
                values = dict(zip(names, row))
                geometry = values.get(geometry_column) if geometry_column else None
                if _intersects(_geometry_bbox(geometry), area_bbox):
                    rows.append(values)
            source_srs = self._srs_name(connection, srs_id)
            layers.append(GeoPackageLayer(table_name, geometry_type, source_srs, columns, tuple(rows)))
            if geometry_column is None:
                issues.append(
                    ValidationIssue(
                        code="missing-geometry-column",
                        message=f"Layer {table_name} hat keine Geometriespalte.",
                        severity="warning",
                    )
                )
        return layers

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
    def _srs_name(connection: sqlite3.Connection, srs_id: Optional[int]) -> Optional[str]:
        if srs_id is None:
            return None
        row = connection.execute(
            "SELECT organization, organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
            (srs_id,),
        ).fetchone()
        if not row:
            return None
        return f"{row[0]}:{row[1]}"

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
        geometry_column = next(
            (field for field in layer.fields if _normalized(field) in {"geom", "geometry", "thegeom"}),
            None,
        )
        row_id_column = next(
            (field for field in layer.fields if _normalized(field) in {"fid", "id", "rowid"}),
            None,
        )
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
            duplicate_key = tuple(attributes[field] for field in TARGET_FIELDS)
            if duplicate_key in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate-row",
                        message=f"Exakte Dublette in Layer {layer.table_name} wurde entfernt.",
                        severity="warning",
                        rule="Exakte Attribute",
                    )
                )
                continue
            seen.add(duplicate_key)
            records.append(
                HarmonizedRecord(
                    layer_id=layer.table_name,
                    source_row_id=row.get(row_id_column, index) if row_id_column else index,
                    attributes=attributes,
                    geometry=row.get(geometry_column) if geometry_column else None,
                )
            )
        return records
