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
    "Ausgabe",
    "Verarbeitung starten",
)


@dataclass
class LayerDescriptor:
    """A normalized layer available to the user-facing branch."""

    layer_id: str
    name: str
    geometry_type: str
    source_name: str
    category: Optional[str] = None
    selected_for_topic: bool = False


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
class ValidationIssue:
    """A warning or review item that must remain visible in the result."""

    code: str
    message: str
    severity: str = "warning"
    requires_confirmation: bool = False
    confirmed: Optional[bool] = None
    rule: Optional[str] = None


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
