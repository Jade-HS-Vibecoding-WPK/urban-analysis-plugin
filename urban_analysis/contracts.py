"""Shared data contract between the data pipeline and user-facing output."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


MVP_DEFAULT_BUFFER_METERS = 500
MVP_TOPIC_NAME = "Siedlungsstruktur"
MVP_UI_STEPS = (
    "Projekt-CRS",
    "Untersuchungsgebiet",
    "Daten laden",
    "Layer prüfen",
    "Attributzuordnung",
    "Harmonisierung",
    "Kartenthema",
    "Verarbeitung starten",
)

# E29 (G11): the few fields every result layer has, because map and legend
# need them.  All other columns are source columns with a readable name.
CORE_FIELDS = (
    "object_id",
    "address",
    "object_type",
    "category",
    "source",
    "source_name",
)

# S11: where the data of a layer came from.
SOURCE_KINDS = ("OSM", "ALKIS", "Eigene Datei")

# G11: what the user decided for one column in step 5.
COLUMN_TARGET = "target"  # becomes a core field (target_field says which)
COLUMN_KEEP = "keep"  # stays as its own column (name = shown column name)
COLUMN_DROP = "drop"  # not written into the result layer
COLUMN_ACTIONS = (COLUMN_TARGET, COLUMN_KEEP, COLUMN_DROP)


@dataclass
class LayerDescriptor:
    """A normalized layer available to the user-facing branch.

    ``source_kind`` (S11) is one of ``SOURCE_KINDS`` or empty if unknown.
    """

    layer_id: str
    name: str
    geometry_type: str
    source_name: str
    category: Optional[str] = None
    selected_for_topic: bool = False
    source_kind: str = ""


@dataclass
class AttributeSuggestion:
    """A visible, user-editable proposal for mapping a source attribute.

    ``layer_id`` names the input layer the source field belongs to, so equal
    field names in different layers can be shown and confirmed separately.
    ``examples`` holds up to two sample values from the data for display.
    """

    source_field: str
    target_field: str
    confidence: float
    accepted: Optional[bool] = None
    user_value: Optional[str] = None
    layer_id: Optional[str] = None
    examples: Tuple[str, ...] = ()


@dataclass
class ColumnInfo:
    """One column of one input layer, as shown in step 5 (G11, E29, E30).

    ``readable_name`` is the proposed column name from the name list in
    ``mapping_rules.json``.  ``known`` is True if the column is in that list:
    it is ticked by default; unknown columns are shown folded under
    "Nicht geladen (nicht lesbar)" and can be ticked by the user.
    ``examples`` holds up to three different, non-empty values from the data.
    ``suggested_target`` is a core field (``CORE_FIELDS``) or empty.
    """

    layer_id: str
    source_field: str
    readable_name: str = ""
    known: bool = False
    examples: Tuple[str, ...] = ()
    suggested_target: str = ""
    confidence: float = 0.0


@dataclass
class ColumnDecision:
    """The user's choice for one column in step 5 (back from the UI).

    ``action`` is one of ``COLUMN_ACTIONS``.  ``target_field`` is set only for
    ``"target"``; ``name`` is the column name the user chose for ``"keep"``.
    """

    layer_id: str
    source_field: str
    action: str
    target_field: str = ""
    name: str = ""

    def __post_init__(self) -> None:
        if self.action not in COLUMN_ACTIONS:
            raise ValueError(f"Unbekannte Spaltenentscheidung: {self.action}")
        if self.action == COLUMN_TARGET and self.target_field not in CORE_FIELDS:
            raise ValueError(f"Kein Kernfeld: {self.target_field}")


@dataclass
class ValueDifference:
    """One column in which the objects of a duplicate group differ (E31)."""

    source_field: str
    readable_name: str
    values: Tuple[str, ...] = ()


@dataclass
class DuplicateGroupInfo:
    """Readable explanation of one uncertain-duplicate group (G11, E31).

    ``group_id`` matches ``duplicate_group`` of the harmonized records.
    ``reason`` says why the objects count as one place, e.g. "gleiche Form".
    ``example_text`` is one sentence in everyday language for step 6.
    """

    group_id: str
    layer_id: str
    record_count: int
    reason: str = ""
    example_text: str = ""
    differences: Tuple[ValueDifference, ...] = ()


@dataclass
class ValidationIssue:
    """A warning or review item that must remain visible in the result.

    ``message`` is the short text ("was ist los").  ``action`` is one short
    sentence "was tun"; empty means nothing to do.  ``details`` is the longer
    explanation behind "Mehr erfahren".  ``layer_id`` names the input layer
    the issue belongs to, if any.
    """

    code: str
    message: str
    severity: str = "warning"
    requires_confirmation: bool = False
    confirmed: Optional[bool] = None
    rule: Optional[str] = None
    details: str = ""
    action: str = ""
    layer_id: Optional[str] = None


@dataclass
class OutputSelection:
    """User-controlled output choices for the integrated workflow."""

    load_qgis_layers: bool = True
    save_cleaned_geopackage: bool = False
    create_pdf: bool = False
    data_source: str = ""


@dataclass
class PipelineResult:
    """Versioned hand-off from the data pipeline to the user-facing branch."""

    contract_version: str
    project_crs: str
    study_area_wkt: str
    buffer_meters: float = MVP_DEFAULT_BUFFER_METERS
    layers: List[LayerDescriptor] = field(default_factory=list)
    attribute_suggestions: List[AttributeSuggestion] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    selected_topic: Optional[str] = None
    output: OutputSelection = field(default_factory=OutputSelection)
    harmonized_records: List[object] = field(default_factory=list)
    columns: List[ColumnInfo] = field(default_factory=list)
    duplicate_groups: List[DuplicateGroupInfo] = field(default_factory=list)

    def columns_of(self, layer_id: str) -> List[ColumnInfo]:
        """All columns of one input layer, in the order of the source."""
        return [column for column in self.columns if column.layer_id == layer_id]

    def visible_issues(self) -> List[ValidationIssue]:
        """Return issues that must be shown before processing continues."""
        return [
            issue
            for issue in self.issues
            if issue.severity in ("warning", "error") or issue.requires_confirmation
        ]

    def selected_layers(self) -> List[LayerDescriptor]:
        """Return only result layers selected after topic confirmation."""
        return [layer for layer in self.layers if layer.selected_for_topic]

    def as_summary(self) -> Dict[str, object]:
        """Expose a stable summary shape for QGIS and optional PDF output."""
        return {
            "contract_version": self.contract_version,
            "project_crs": self.project_crs,
            "study_area_wkt": self.study_area_wkt,
            "buffer_meters": self.buffer_meters,
            "selected_topic": self.selected_topic,
            "input_layer_count": len(self.layers),
            "selected_layer_count": len(self.selected_layers()),
            "issue_count": len(self.visible_issues()),
            "data_source": self.output.data_source,
        }
