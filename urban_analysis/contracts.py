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


# --- G13: general map topics (E36, S16) ----------------------------------------

# Geometry of a topic class, as in the catalog.
TOPIC_GEOMETRIES = ("Fläche", "Linie", "Punkt")

# Hint codes of the topic step (ValidationIssue.code).
TOPIC_LIMIT = "topic-limit"  # info: what a topic cannot show (one per topic)
TOPIC_CLASS_EMPTY = "topic-class-empty"  # info: a chosen class has no object in the area


@dataclass(frozen=True)
class TopicClass:
    """One class of a topic, e.g. „Wohnen“ in „Nutzungen“ (read only for the UI).

    ``colour`` is a suggestion from the catalog (``#rrggbb``) or empty; the
    map styles (E33) may replace it, e.g. for Schwarzplan or Graustufen.
    ``uncertain`` marks classes that are only a guess („vermutlich“, e.g.
    Erdgeschossnutzung) and must be confirmed before they count.
    """

    class_id: str
    name: str
    geometry: str
    colour: str = ""
    description: str = ""
    uncertain: bool = False

    def __post_init__(self) -> None:
        if self.geometry not in TOPIC_GEOMETRIES:
            raise ValueError(f"Unbekannte Geometrie einer Themenklasse: {self.geometry}")


@dataclass(frozen=True)
class TopicStep:
    """One step of a scale: ``lower`` <= value < ``upper`` (None = open)."""

    name: str
    lower: Optional[float] = None
    upper: Optional[float] = None
    colour: str = ""


@dataclass(frozen=True)
class TopicScale:
    """A graded map instead of classes, e.g. buildings by number of floors.

    ``field`` names the column of the result layer that holds the value,
    e.g. a core field or an accessibility column „Abstand Nahversorgung (m)“.
    """

    scale_id: str
    name: str
    field: str
    steps: Tuple[TopicStep, ...] = ()


@dataclass(frozen=True)
class TopicInfo:
    """One topic from the catalog (``topics_catalog.json``), read only for the UI.

    ``limits`` are the sentences of the hint ``topic-limit`` (what the data
    cannot show), ``source_tips`` say where better data could come from.
    """

    topic_id: str
    name: str
    description: str = ""
    classes: Tuple[TopicClass, ...] = ()
    scales: Tuple[TopicScale, ...] = ()
    limits: Tuple[str, ...] = ()
    source_tips: Tuple[str, ...] = ()

    def class_by_id(self, class_id: str) -> Optional[TopicClass]:
        return next((item for item in self.classes if item.class_id == class_id), None)


@dataclass
class TopicSelection:
    """What the user ticked in step 7 for one topic (back from the UI).

    Several selections may be chosen; together they are overlaid.  Each
    harmonized record gets at most one class per selected topic in
    ``topic_classes`` (topic_id -> class_id), next to its ``category``.
    """

    topic_id: str
    class_ids: Tuple[str, ...] = ()
    scale_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.class_ids = tuple(self.class_ids)
        self.scale_ids = tuple(self.scale_ids)
        if not self.topic_id:
            raise ValueError("Ein Thema braucht eine topic_id")
        if not self.class_ids and not self.scale_ids:
            raise ValueError(f"Thema {self.topic_id}: mindestens eine Klasse oder Stufe wählen")


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
    # G13: the topics chosen in step 7 (empty = old single topic via
    # selected_topic, which stays until W19 is done).
    selected_topics: List[TopicSelection] = field(default_factory=list)

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
            "selected_topics": [selection.topic_id for selection in self.selected_topics],
            "input_layer_count": len(self.layers),
            "selected_layer_count": len(self.selected_layers()),
            "issue_count": len(self.visible_issues()),
            "data_source": self.output.data_source,
        }
