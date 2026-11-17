"""GeoPackage import and normalization for the urban-analysis MVP.

The module deliberately keeps the data pipeline independent from the guided
workflow.  It uses the GeoPackage SQLite metadata directly, so import tests
can run without a QGIS installation.  A QGIS project can consume the returned
``PipelineResult`` through the existing contract.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

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
from .mapping import LayerProfile, MappingRules, default_mapping_rules


TARGET_FIELDS = (
    "source_name",
    "object_type",
    "object_detail",
    "category",
    "status",
    "area_m2",
    "year",
    "source",
)
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
    duplicate_group: Optional[str] = None


@dataclass(frozen=True)
class GeoPackageLayer:
    """Metadata and rows imported from one GeoPackage feature table."""

    table_name: str
    geometry_type: str
    source_srs: Optional[str]
    fields: Tuple[str, ...]
    rows: Tuple[Mapping[str, Any], ...]
    geometry_column: Optional[str] = None
    primary_key: Optional[str] = None


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


@contextmanager
def _open_read_only(file_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a GeoPackage without writing to it or creating files next to it.

    QGIS saves GeoPackages in SQLite's WAL journal mode.  Such a file cannot be
    opened with ``mode=ro`` when its ``-shm`` side file is missing, e.g. after
    copying it.  If there is no ``-wal`` file either, no unsaved changes are
    pending and the file can safely be read as immutable.
    """
    base_uri = file_path.resolve().as_uri()
    connection = sqlite3.connect(f"{base_uri}?mode=ro", uri=True)
    try:
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.OperationalError:
        connection.close()
        if file_path.with_name(file_path.name + "-wal").exists():
            raise
        connection = sqlite3.connect(f"{base_uri}?immutable=1", uri=True)
    except sqlite3.Error:
        connection.close()
        raise
    try:
        yield connection
    finally:
        connection.close()


def _count(number: int) -> str:
    """German-style number with a non-breaking space as thousands separator."""
    return f"{number:,}".replace(",", "\u00a0")


def _names(names: Sequence[str]) -> str:
    """Join names as "A", "A und B" or "A, B und C"."""
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " und " + names[-1]


def _examples(rows: Sequence[Mapping[str, Any]], field: str, limit: int = 2) -> Tuple[str, ...]:
    """Up to ``limit`` different, non-empty sample values of ``field``."""
    found: List[str] = []
    for row in rows:
        value = row.get(field)
        if value in (None, "") or isinstance(value, (bytes, bytearray, memoryview)):
            continue
        text = str(value).strip()
        if len(text) > 60:
            text = text[:59] + "…"
        if text and text not in found:
            found.append(text)
            if len(found) == limit:
                break
    return tuple(found)


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


#: Share of the progress bar used for reading and clipping; the rest is
#: harmonisation, which is much faster.
READ_SHARE = 0.9
#: Report clipping progress after this many rows.
PROGRESS_EVERY_ROWS = 1000


class _Progress:
    """Forward a 0..1 fraction to an optional callback, rising and throttled."""

    def __init__(self, callback: Optional[Callable[[float], None]]):
        self.callback = callback
        self.last = -1.0

    def report(self, fraction: float) -> None:
        if self.callback is None:
            return
        fraction = min(1.0, max(self.last, fraction, 0.0))
        if fraction - self.last >= 0.01 or (fraction == 1.0 and self.last < 1.0):
            self.last = fraction
            self.callback(fraction)


class GeoPackageImporter:
    """Import and harmonize local GeoPackage feature layers."""

    def __init__(self, *, contract_version: str = "1.0", mapping_rules: Optional[MappingRules] = None):
        self.contract_version = contract_version
        self.mapping_rules = mapping_rules or default_mapping_rules()

    def import_file(
        self,
        path: str | Path,
        *,
        project_crs: str,
        study_area_wkt: str,
        buffer_meters: float = MVP_DEFAULT_BUFFER_METERS,
        progress: Optional[Callable[[float], None]] = None,
    ) -> PipelineResult:
        """Return a contract result for all feature tables in ``path``.

        ``progress`` is called with a rising fraction from 0.0 to 1.0, e.g.
        to drive a progress bar.  It is called from the thread that runs the
        import, at most about a hundred times.
        """
        tracker = _Progress(progress)
        file_path = Path(path)
        if not project_crs.strip():
            raise ValueError("A project CRS is required")
        if not study_area_wkt.strip():
            raise ValueError("A study area polygon is required")
        if buffer_meters < 0:
            raise ValueError("The buffer must not be negative")
        if not file_path.is_file():
            raise GeoPackageImportError(f"GeoPackage does not exist: {file_path}")

        tracker.report(0.0)
        study_area, area_error = self._study_area(study_area_wkt, buffer_meters)
        issues: List[ValidationIssue] = []
        if area_error:
            issues.append(
                ValidationIssue(
                    code="invalid-study-area",
                    message=(
                        f"Das Untersuchungsgebiet kann nicht verwendet werden: {area_error} "
                        "Deshalb wurden keine Daten geladen. So behebst du es: Im Schritt "
                        "„Untersuchungsgebiet“ eine Polygonfläche wählen."
                    ),
                    severity="error",
                    rule="Untersuchungsgebiet",
                )
            )

        try:
            with _open_read_only(file_path) as connection:
                layers = self._read_layers(connection, study_area, project_crs.strip(), issues, tracker)
        except sqlite3.Error as exc:
            raise GeoPackageImportError(f"Unable to read GeoPackage {file_path}: {exc}") from exc

        if not layers:
            issues.append(
                ValidationIssue(
                    code="no-feature-layers",
                    message=(
                        "In der Datei wurden keine Geodaten-Layer gefunden. Bitte prüfe, ob du "
                        "die richtige GeoPackage-Datei gewählt hast."
                    ),
                    severity="error",
                )
            )

        descriptors: List[LayerDescriptor] = []
        suggestions: List[AttributeSuggestion] = []
        records: List[HarmonizedRecord] = []
        layers_without_source: List[str] = []
        layers_without_category: List[str] = []
        for layer_index, layer in enumerate(layers, start=1):
            tracker.report(READ_SHARE + (1 - READ_SHARE) * (layer_index - 1) / len(layers))
            profile = self.mapping_rules.profile_for(layer.table_name, layer.fields)
            category = (
                profile.category if profile is not None
                else self.mapping_rules.category_from_name(layer.table_name)
            )
            field_rules = self._layer_field_rules(layer.fields, profile)
            if layer.rows and not any(rule.target_field == "source" for rule in field_rules):
                layers_without_source.append(layer.table_name)
            if layer.rows and profile is None and category is None:
                layers_without_category.append(layer.table_name)
            for rule in field_rules:
                suggestions.append(
                    AttributeSuggestion(
                        source_field=rule.source_field,
                        target_field=rule.target_field,
                        confidence=rule.confidence,
                        layer_id=layer.table_name,
                        examples=_examples(layer.rows, rule.source_field),
                    )
                )
            layer_records = self._harmonize(layer, file_path, category, issues, profile, field_rules, self.mapping_rules)
            records.extend(layer_records)
            descriptors.extend(self._layer_descriptors(layer, file_path, category, profile, layer_records))

        if layers_without_category:
            issues.append(
                ValidationIssue(
                    code="missing-category",
                    message=(
                        f"{_names([self.mapping_rules.layer_name(name) for name in layers_without_category])}: "
                        + (
                            "Für diesen Layer ist unklar, was er darstellt (z. B. Gebäude oder "
                            "Grünflächen). Er wird geladen, steht beim Kartenthema aber nicht zur Auswahl."
                            if len(layers_without_category) == 1
                            else "Für diese Layer ist unklar, was sie darstellen (z. B. Gebäude oder "
                            "Grünflächen). Sie werden geladen, stehen beim Kartenthema aber nicht zur Auswahl."
                        )
                    ),
                    severity="warning",
                    rule="Kategorie aus Layername",
                )
            )

        if layers_without_source:
            layers_with_rows = [layer.table_name for layer in layers if layer.rows]
            if layers_without_source == layers_with_rows:
                missing_text = "Datenquelle fehlt: In der Datei steht nicht, woher die Daten stammen."
            else:
                missing_text = (
                    "Datenquelle fehlt für "
                    f"{_names([self.mapping_rules.layer_name(name) for name in layers_without_source])}: "
                    "Dort steht nicht, woher die Daten stammen."
                )
            issues.append(
                ValidationIssue(
                    code="missing-data-source",
                    message=(
                        f"{missing_text} Bitte trage die Quelle im Schritt „Ausgabe“ ein, "
                        "z. B. „ALKIS, © LGLN 2025“."
                    ),
                    severity="warning",
                    rule="Datenquelle",
                )
            )

        tracker.report(1.0)
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
        tracker: Optional[_Progress] = None,
    ) -> List[GeoPackageLayer]:
        tracker = tracker or _Progress(None)
        tables = self._feature_tables(connection)
        row_counts = self._row_counts(connection, tables) if tracker.callback else {}
        total_rows = sum(row_counts.values()) or 1
        rows_before = 0
        layers: List[GeoPackageLayer] = []
        for table_name, geometry_type, srs_id in tables:
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            table_info = connection.execute(f"PRAGMA table_info({quoted_table})").fetchall()
            columns = tuple(row[1] for row in table_info)
            if not columns:
                continue
            primary_keys = [row[1] for row in table_info if row[5]]
            primary_key = primary_keys[0] if len(primary_keys) == 1 else None
            geometry_column = self._geometry_column(connection, table_name)
            if geometry_column not in columns:
                geometry_column = None
            display_name = self.mapping_rules.layer_name(table_name)
            source_srs, source_epsg, is_geographic = self._srs(connection, srs_id)
            crs_usable = self._check_crs(
                display_name, source_srs, source_epsg, is_geographic, project_crs, study_area, issues
            )
            rows: List[Mapping[str, Any]] = []
            if geometry_column is None:
                issues.append(
                    ValidationIssue(
                        code="missing-geometry-column",
                        message=(
                            f"{display_name} wurde nicht geladen: Der Layer enthält keine Geometrien, "
                            "also keine Lage auf der Karte."
                        ),
                        severity="warning",
                    )
                )
            elif study_area is not None and crs_usable:
                start = rows_before

                def on_rows(done: int, start: int = start) -> None:
                    tracker.report(READ_SHARE * (start + done) / total_rows)

                rows = self._clip_rows(
                    connection, quoted_table, display_name, geometry_column, study_area, issues, on_rows
                )
            rows_before += row_counts.get(table_name, 0)
            tracker.report(READ_SHARE * rows_before / total_rows)
            layers.append(
                GeoPackageLayer(
                    table_name, geometry_type, source_srs, columns, tuple(rows), geometry_column, primary_key
                )
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
        on_rows: Optional[Callable[[int], None]] = None,
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
            if on_rows is not None and total % PROGRESS_EVERY_ROWS == 0:
                on_rows(total)
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
                    message=(
                        f"{table_name}: {_count(missing)} "
                        + ("Objekt hat" if missing == 1 else "Objekte haben")
                        + " keine Lage auf der Karte (keine Geometrie) und "
                        + ("wurde" if missing == 1 else "wurden")
                        + " weggelassen."
                    ),
                    severity="warning",
                    rule="Räumliche Begrenzung",
                )
            )
        if unreadable:
            issues.append(
                ValidationIssue(
                    code="unreadable-geometry",
                    message=(
                        f"{table_name}: {_count(unreadable)} "
                        + ("Objekt hat eine fehlerhafte Geometrie und wurde" if unreadable == 1
                           else "Objekte haben eine fehlerhafte Geometrie und wurden")
                        + f" weggelassen. (Technischer Grund: {first_error})"
                    ),
                    severity="warning",
                    rule="Räumliche Begrenzung",
                )
            )
        issues.append(
            ValidationIssue(
                code="clip-summary",
                message=(
                    f"{table_name}: {_count(len(rows))} von {_count(total)} Objekten liegen im Gebiet "
                    + (f"(mit {buffer:g} m Puffer)." if buffer else "(ohne Puffer).")
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
                        f"{table_name} wurde nicht geladen: Der Layer nutzt ein anderes "
                        f"Koordinatensystem ({source_epsg}) als das Projekt ({project_epsg}). "
                        "So behebst du es: Den Layer in QGIS mit „Exportieren → Objekte speichern "
                        f"als …“ im Koordinatensystem {project_epsg} speichern und diese Datei laden."
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
                        f"{table_name}: Das Koordinatensystem des Layers ist nicht eindeutig "
                        f"angegeben ({source_srs or 'unbekannt'}). Es wird angenommen, dass es zum "
                        f"Projekt ({project_crs}) passt. Bitte prüfe in QGIS, ob der Layer an der "
                        "richtigen Stelle liegt, und bestätige."
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
                        f"{table_name} wurde nicht geladen: Sein Koordinatensystem rechnet in Grad, "
                        "der Puffer aber in Metern. So behebst du es: Im Schritt „Projekt-CRS“ ein "
                        "System in Metern wählen, z. B. EPSG:25832, und die Daten darin speichern."
                    ),
                    severity="error",
                    rule="Projekt-CRS",
                )
            )
            return False
        return True

    @staticmethod
    def _row_counts(
        connection: sqlite3.Connection, tables: Sequence[Tuple[str, str, Optional[int]]]
    ) -> Dict[str, int]:
        """Number of rows per feature table, to weight the progress."""
        counts: Dict[str, int] = {}
        for table_name, _geometry_type, _srs_id in tables:
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            try:
                counts[table_name] = connection.execute(f"SELECT count(*) FROM {quoted_table}").fetchone()[0]
            except sqlite3.Error:
                counts[table_name] = 0
        return counts

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

    @classmethod
    def _layer_field_rules(
        cls, fields: Sequence[str], profile: Optional[LayerProfile]
    ) -> Tuple[MappingRule, ...]:
        """Alias rules, with object type and category taken over by a profile."""
        rules = cls._mapping_rules(fields)
        if profile is None:
            return rules
        kept = [rule for rule in rules if rule.target_field not in ("object_type", "category")]
        if profile.uses_field(fields):
            kept.insert(0, MappingRule(str(profile.object_type_field), "object_type", 1.0))
        return tuple(kept)

    @staticmethod
    def _layer_descriptors(
        layer: GeoPackageLayer,
        file_path: Path,
        category: Optional[str],
        profile: Optional[LayerProfile],
        records: Sequence[HarmonizedRecord],
    ) -> List[LayerDescriptor]:
        """One descriptor per layer, or per category for layers a profile splits."""
        if profile is None or not profile.splits_layer or not records:
            return [
                LayerDescriptor(
                    layer_id=layer.table_name,
                    name=layer.table_name,
                    geometry_type=layer.geometry_type,
                    source_name=file_path.name,
                    category=category,
                )
            ]
        rule_order = [*profile.category_rules, *([profile.default_rule] if profile.default_rule else [])]
        suffix_order: Dict[str, str] = {}
        for rule in rule_order:
            suffix_order.setdefault(rule.layer_suffix, rule.category)
        present = {record.layer_id for record in records}
        descriptors = []
        for suffix, rule_category in suffix_order.items():
            layer_id = f"{layer.table_name}_{suffix}"
            if layer_id in present:
                descriptors.append(
                    LayerDescriptor(
                        layer_id=layer_id,
                        name=f"{layer.table_name} – {rule_category}",
                        geometry_type=layer.geometry_type,
                        source_name=file_path.name,
                        category=rule_category,
                    )
                )
        return descriptors

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
        profile: Optional[LayerProfile] = None,
        field_rules: Optional[Sequence[MappingRule]] = None,
        mapping_rules: Optional[MappingRules] = None,
    ) -> List[HarmonizedRecord]:
        if field_rules is None:
            field_rules = GeoPackageImporter._mapping_rules(layer.fields)
        if mapping_rules is None:
            mapping_rules = default_mapping_rules()
        display_name = mapping_rules.layer_name(layer.table_name)
        rules = {rule.target_field: rule.source_field for rule in field_rules}
        geometry_column = layer.geometry_column or next(
            (
                field
                for field in layer.fields
                if _normalized(field) in {"geom", "geometry", "thegeom", "wktgeom"}
            ),
            None,
        )
        row_id_column = layer.primary_key or next(
            (field for field in layer.fields if _normalized(field) in {"fid", "id", "rowid"}),
            None,
        )
        # Exact duplicates: every source column except the primary key is equal,
        # including the geometry.  Only these are removed automatically.
        compared_fields = tuple(field for field in layer.fields if field != layer.primary_key)
        seen: set = set()
        duplicate_count = 0
        records: List[HarmonizedRecord] = []
        kept_rows: List[Mapping[str, Any]] = []
        for index, row in enumerate(layer.rows, start=1):
            duplicate_key = tuple(row.get(field) for field in compared_fields)
            if duplicate_key in seen:
                duplicate_count += 1
                continue
            seen.add(duplicate_key)
            layer_id = layer.table_name
            attributes: Dict[str, Any] = {
                "source_name": file_path.name,
                "object_type": row.get(rules["object_type"]) if "object_type" in rules else layer.table_name,
                "object_detail": None,
                "category": row.get(rules["category"]) if "category" in rules else category,
                "status": row.get(rules["status"]) if "status" in rules else None,
                "area_m2": _coerce_area(row.get(rules["area_m2"])) if "area_m2" in rules else None,
                "year": _coerce_year(row.get(rules["year"])) if "year" in rules else None,
                "source": row.get(rules["source"]) if "source" in rules else None,
            }
            if profile is not None:
                classification = profile.classify(row, layer.fields)
                if profile.uses_field(layer.fields):
                    attributes["object_type"] = classification.object_type
                    attributes["object_detail"] = classification.object_detail
                attributes["category"] = classification.category
                if classification.layer_suffix:
                    layer_id = f"{layer.table_name}_{classification.layer_suffix}"
            records.append(
                HarmonizedRecord(
                    layer_id=layer_id,
                    source_row_id=row.get(row_id_column, index) if row_id_column else index,
                    attributes=attributes,
                    geometry=row.get(geometry_column) if geometry_column else None,
                )
            )
            kept_rows.append(row)
        if duplicate_count:
            issues.append(
                ValidationIssue(
                    code="duplicate-row",
                    message=(
                        f"{display_name}: "
                        + (
                            "1 Eintrag war doppelt (komplett gleich) und wurde"
                            if duplicate_count == 1
                            else f"{_count(duplicate_count)} Einträge waren doppelt (komplett gleich) und wurden"
                        )
                        + " automatisch entfernt."
                    ),
                    severity="warning",
                    rule="Alle Attribute und Geometrie identisch",
                )
            )
        if geometry_column:
            records = GeoPackageImporter._mark_uncertain_duplicates(
                layer.table_name, records, kept_rows, compared_fields, geometry_column, issues,
                mapping_rules.field_name, display_name,
            )
        return records

    @staticmethod
    def _mark_uncertain_duplicates(
        table_name: str,
        records: List[HarmonizedRecord],
        rows: List[Mapping[str, Any]],
        compared_fields: Sequence[str],
        geometry_column: str,
        issues: List[ValidationIssue],
        label: Any = str,
        display_name: Optional[str] = None,
    ) -> List[HarmonizedRecord]:
        """Group records that share a geometry but differ in other attributes.

        They are kept and reported for confirmation, never removed here.
        """
        positions_by_geometry: Dict[Any, List[int]] = {}
        for position, row in enumerate(rows):
            geometry = row.get(geometry_column)
            if geometry is not None:
                positions_by_geometry.setdefault(geometry, []).append(position)
        # Only records that ended up in the same result layer (same category)
        # can be duplicates.  Equal geometries in different categories are two
        # different uses at the same place and are reported separately.
        groups: List[List[int]] = []
        cross_category_places = 0
        for positions in positions_by_geometry.values():
            if len(positions) < 2:
                continue
            by_layer: Dict[str, List[int]] = {}
            for position in positions:
                by_layer.setdefault(records[position].layer_id, []).append(position)
            if len(by_layer) > 1:
                cross_category_places += 1
            groups.extend(group for group in by_layer.values() if len(group) > 1)

        if cross_category_places:
            issues.append(
                ValidationIssue(
                    code="overlap-different-category",
                    message=(
                        f"{display_name or table_name}: "
                        + (
                            "An einer Stelle liegen"
                            if cross_category_places == 1
                            else f"An {_count(cross_category_places)} Stellen liegen"
                        )
                        + " Flächen mit unterschiedlicher Kategorie genau übereinander. "
                        "Sie sind keine Dubletten und bleiben in ihrer jeweiligen Kategorie erhalten."
                    ),
                    severity="info",
                    rule="Gleiche Geometrie, unterschiedliche Kategorie",
                )
            )
        if not groups:
            return records

        differing_fields: Dict[str, int] = {}
        marked = list(records)
        for number, positions in enumerate(groups, start=1):
            group_id = f"{table_name}:{number}"
            for position in positions:
                marked[position] = replace(marked[position], duplicate_group=group_id)
            for field in compared_fields:
                if len({rows[position].get(field) for position in positions}) > 1:
                    differing_fields[field] = differing_fields.get(field, 0) + 1

        row_count = sum(len(positions) for positions in groups)
        # A key column such as "tn" and its readable twin "tn__bez" carry the
        # same information; only the readable one is shown.
        shown_fields = {
            field: count for field, count in differing_fields.items()
            if field + "__bez" not in differing_fields
        }
        top_fields = sorted(shown_fields, key=lambda field: (-shown_fields[field], field))[:3]
        issues.append(
            ValidationIssue(
                code="uncertain-duplicate",
                message=(
                    f"{display_name or table_name}: "
                    + (
                        "An einer Stelle liegen"
                        if len(groups) == 1
                        else f"An {_count(len(groups))} Stellen liegen"
                    )
                    + f" mehrere Objekte genau übereinander ({_count(row_count)} Objekte). "
                    + "Sie unterscheiden sich nur in "
                    + (_names([label(field) for field in top_fields]) or "einzelnen Angaben")
                    + (
                        " – z. B. ein Haus mit mehreren Hausnummern."
                        if "hnr" in shown_fields
                        else " – z. B. dasselbe Objekt mit zwei Einträgen."
                    )
                    + " Alle wurden behalten. Sollen sie je Stelle zu einem Objekt zusammengefasst werden?"
                ),
                severity="warning",
                requires_confirmation=True,
                rule="Gleiche Geometrie, abweichende Attribute",
            )
        )
        return marked


def merge_confirmed_duplicates(
    records: Sequence[HarmonizedRecord], confirmed_groups: Iterable[str]
) -> List[HarmonizedRecord]:
    """Keep only the first record of each confirmed uncertain-duplicate group.

    Records of unconfirmed groups stay unchanged, so the user's decision is
    applied explicitly and the raw data is never modified.
    """
    confirmed = set(confirmed_groups)
    merged: List[HarmonizedRecord] = []
    seen_groups: set = set()
    for record in records:
        group = record.duplicate_group
        if group in confirmed:
            if group in seen_groups:
                continue
            seen_groups.add(group)
        merged.append(record)
    return merged


def apply_data_source(records: Sequence[HarmonizedRecord], data_source: str) -> List[HarmonizedRecord]:
    """Fill empty ``source`` attributes with the data source the user entered.

    Interface S8 for the user-guidance branch: call it in the step "Ausgabe"
    with ``result.output.data_source``.  Values that came from the input data
    stay unchanged.  An empty data source is rejected instead of ignored.
    """
    text = (data_source or "").strip()
    if not text:
        raise ValueError("Eine Datenquelle ist erforderlich")
    updated: List[HarmonizedRecord] = []
    for record in records:
        if record.attributes.get("source") in (None, ""):
            attributes = dict(record.attributes)
            attributes["source"] = text
            record = replace(record, attributes=attributes)
        updated.append(record)
    return updated
