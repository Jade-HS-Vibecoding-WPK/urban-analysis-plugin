"""Testable user guidance and output planning for the MVP workflow."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .contracts import (
    AttributeSuggestion,
    LayerDescriptor,
    OutputSelection,
    PipelineResult,
    ValidationIssue,
)
from .ui_contract import MVP_REQUIRED_TOPIC_SUGGESTIONS


SEVERITY_ORDER = ("error", "warning", "info")
# (singular, plural) per severity
SEVERITY_LABELS = {
    "error": ("Fehler", "Fehler"),
    "warning": ("Warnung", "Warnungen"),
    "info": ("Info", "Infos"),
}


def severity_label(severity: str, count: int) -> str:
    """'1 Warnung', '6 Warnungen', '0 Fehler' ..."""
    singular, plural = SEVERITY_LABELS[severity]
    return f"{count} {singular if count == 1 else plural}"
# Hints confirmed in a later step instead of step 4 ("Layer prüfen").
DECIDED_IN_HARMONIZATION = ("uncertain-duplicate",)
# Errors that leave no usable data (decision E4): only these block step 4.
BLOCKING_ERROR_CODES = ("invalid-study-area", "no-feature-layers")
UNCERTAIN_DUPLICATE_EXPLANATION = (
    "Unsichere Dubletten sind Objekte mit derselben Geometrie, aber "
    "unterschiedlichen Angaben – etwa wenn dasselbe Objekt mehrfach mit "
    "unterschiedlichen Angaben gespeichert ist. Alle wurden behalten. Ob sie "
    "zusammengeführt werden, entscheidest du in Schritt 6 „Harmonisierung“."
)

PDF_DATA_SOURCE_MESSAGE = (
    "Für das PDF ist eine Datenquelle nötig. Bitte das Feld „Datenquelle“ ausfüllen."
)


@dataclass(frozen=True)
class OutputPlan:
    """Concrete output choices derived from the user's selection."""

    qgis_layer_ids: Tuple[str, ...]
    geopackage_requested: bool
    pdf_requested: bool
    pdf_metadata: Optional[Dict[str, object]] = None


class GuidedWorkflow:
    """Apply user decisions to a pipeline result without reimplementing the pipeline."""

    def __init__(self, result: PipelineResult):
        self.result = result
        self._step_index = 0

    @property
    def current_step(self) -> str:
        """Return the label of the step currently shown to the user."""
        from .contracts import MVP_UI_STEPS

        return MVP_UI_STEPS[self._step_index]

    def advance(self) -> str:
        """Move to the next contract-defined step and return its label."""
        from .contracts import MVP_UI_STEPS

        self._step_index = min(self._step_index + 1, len(MVP_UI_STEPS) - 1)
        return MVP_UI_STEPS[self._step_index]

    def configure_project(
        self, *, project_crs: str, study_area_wkt: str, buffer_meters: float
    ) -> PipelineResult:
        """Validate and store the CRS, study area, and user-selected buffer."""
        if not project_crs.strip():
            raise ValueError(
                "Es ist kein Projekt-CRS gewählt. Bitte in Schritt 1 ein CRS auswählen."
            )
        if not study_area_wkt.strip():
            raise ValueError(
                "Es ist kein Untersuchungsgebiet angegeben. Bitte in Schritt 2 ein "
                "Polygon wählen."
            )
        if buffer_meters < 0:
            raise ValueError(
                "Der Puffer darf nicht negativ sein. Bitte einen Wert ab 0 m eingeben."
            )
        self.result.project_crs = project_crs.strip()
        self.result.study_area_wkt = study_area_wkt.strip()
        self.result.buffer_meters = buffer_meters
        return self.result

    def attribute_suggestions(self) -> Tuple[AttributeSuggestion, ...]:
        """Expose visible, editable attribute proposals from the pipeline."""
        return tuple(self.result.attribute_suggestions)

    def confirm_attribute_suggestions(
        self, decisions: Mapping[str, object]
    ) -> Tuple[AttributeSuggestion, ...]:
        """Apply confirmation or replacement values keyed by source field.

        A boolean confirms or rejects a proposal. A string replaces the target
        field and confirms it, keeping the decision visible in the contract.
        """
        known = {suggestion.source_field: suggestion for suggestion in self.result.attribute_suggestions}
        unknown = set(decisions) - set(known)
        if unknown:
            raise KeyError(
                "Diese Quellfelder gibt es in den Attributvorschlägen nicht: "
                + ", ".join(sorted(unknown))
            )

        for source_field, decision in decisions.items():
            suggestion = known[source_field]
            if isinstance(decision, bool):
                suggestion.accepted = decision
            elif isinstance(decision, str) and decision.strip():
                suggestion.user_value = decision.strip()
                suggestion.accepted = True
            else:
                raise ValueError(
                    f"Für das Quellfeld „{source_field}“ ist kein Zielfeld eingetragen. "
                    "Bitte ein Zielfeld eintragen oder das Häkchen entfernen, um den "
                    "Vorschlag abzulehnen."
                )
        return self.attribute_suggestions()

    # --- Step 4 "Layer prüfen" (W5): all hints, grouped and confirmable ---

    def issues_by_severity(self) -> Dict[str, List[ValidationIssue]]:
        """All hints of the result (incl. infos), grouped error/warning/info.

        Unknown severities are shown as warnings so nothing disappears.
        """
        groups: Dict[str, List[ValidationIssue]] = {key: [] for key in SEVERITY_ORDER}
        for issue in self.result.issues:
            key = issue.severity if issue.severity in groups else "warning"
            groups[key].append(issue)
        return groups

    @staticmethod
    def needs_review_confirmation(issue: ValidationIssue) -> bool:
        """True if the hint gets a check box in step 4."""
        return issue.requires_confirmation and issue.code not in DECIDED_IN_HARMONIZATION

    def open_review_confirmations(self) -> Tuple[ValidationIssue, ...]:
        """Hints in step 4 that still have to be confirmed."""
        return tuple(
            issue
            for issue in self.result.issues
            if self.needs_review_confirmation(issue) and issue.confirmed is not True
        )

    @staticmethod
    def confirm_issue(issue: ValidationIssue, confirmed: bool) -> ValidationIssue:
        """Store the user's confirmation on the hint itself (decision E3)."""
        issue.confirmed = bool(confirmed)
        return issue

    def has_uncertain_duplicates(self) -> bool:
        return any(issue.code in DECIDED_IN_HARMONIZATION for issue in self.result.issues)

    def review_blocker(self) -> Optional[str]:
        """Why step 4 cannot be left yet, or ``None`` if it can."""
        blocking = [issue for issue in self.result.issues if issue.code in BLOCKING_ERROR_CODES]
        if blocking or not self.result.layers:
            return (
                "Es sind keine verwendbaren Daten übrig. Bitte mit „Zurück“ das "
                "Untersuchungsgebiet (Schritt 2) oder die Datei (Schritt 3) prüfen."
            )
        open_items = self.open_review_confirmations()
        if open_items:
            count = len(open_items)
            noun = "Hinweis" if count == 1 else "Hinweise"
            return (
                f"Noch {count} {noun} bestätigen: Bitte bei allen markierten Hinweisen "
                "„Gelesen und bestätigt“ ankreuzen."
            )
        return None

    def review_summary_text(self) -> str:
        """One line above the list, e.g. '9 Layer geladen · 0 Fehler · ...'."""
        groups = self.issues_by_severity()
        return " · ".join(
            [f"{len(self.result.layers)} Layer geladen"]
            + [severity_label(key, len(groups[key])) for key in SEVERITY_ORDER]
        )

    def recognized_categories(self) -> Tuple[str, ...]:
        """Return categories supplied by the pipeline in stable input order."""
        categories: List[str] = []
        for layer in self.result.layers:
            if layer.category and layer.category not in categories:
                categories.append(layer.category)
        return tuple(categories)

    def category_suggestions(self) -> Dict[str, Tuple[LayerDescriptor, ...]]:
        """Group recognized categories and their candidate layers."""
        return {
            category: tuple(layer for layer in self.result.layers if layer.category == category)
            for category in self.recognized_categories()
        }

    def select_topic(
        self,
        topic: str,
        categories: Optional[Iterable[str]] = None,
        *,
        confirm_missing: bool = False,
    ) -> Tuple[LayerDescriptor, ...]:
        """Select the topic categories and mark only their layers for output."""
        selected_categories = tuple(categories) if categories is not None else self.recognized_categories()
        unknown = set(selected_categories) - set(self.recognized_categories())
        if unknown:
            raise ValueError(
                "Diese Kategorien wurden in den Daten nicht erkannt: "
                + ", ".join(sorted(unknown))
            )

        missing = [category for category in MVP_REQUIRED_TOPIC_SUGGESTIONS if category not in selected_categories]
        if missing and not confirm_missing:
            raise ValueError(
                "Für das Kartenthema fehlen diese Kategorien: "
                + ", ".join(missing)
                + ". Bitte „Unvollständig fortfahren“ ankreuzen, um bewusst ohne sie "
                "weiterzumachen. Das Ergebnis wird dann als unvollständig markiert."
            )
        self.result.selected_topic = topic
        for layer in self.result.layers:
            layer.selected_for_topic = bool(layer.category in selected_categories)

        self.result.issues = [
            issue for issue in self.result.issues if issue.code != "missing-topic-category"
        ]
        if missing:
            self.result.issues.append(
                ValidationIssue(
                    code="missing-topic-category",
                    message="Fehlende Kategorien bestätigt: " + ", ".join(missing),
                    severity="warning",
                    requires_confirmation=True,
                    confirmed=True,
                    rule="MVP-Zielkategorien",
                )
            )
        return tuple(self.result.selected_layers())

    def choose_output(
        self,
        *,
        save_cleaned_geopackage: bool = False,
        create_pdf: bool = False,
        data_source: Optional[str] = None,
    ) -> OutputSelection:
        """Store output choices; QGIS layers remain mandatory."""
        if data_source is not None:
            self.result.output.data_source = data_source.strip()
        if create_pdf and not self.result.output.data_source:
            raise ValueError(PDF_DATA_SOURCE_MESSAGE)
        self.result.output = OutputSelection(
            load_qgis_layers=True,
            save_cleaned_geopackage=save_cleaned_geopackage,
            create_pdf=create_pdf,
            data_source=self.result.output.data_source,
        )
        return self.result.output

    def output_plan(self) -> OutputPlan:
        """Describe the selected QGIS layers and optional export metadata."""
        output = self.result.output
        metadata = None
        if output.create_pdf:
            if not output.data_source:
                raise ValueError(PDF_DATA_SOURCE_MESSAGE)
            metadata = {
                "study_area_wkt": self.result.study_area_wkt,
                "buffer_meters": self.result.buffer_meters,
                "legend": [layer.name for layer in self.result.selected_layers()],
                "data_source": output.data_source,
            }
        return OutputPlan(
            qgis_layer_ids=tuple(layer.layer_id for layer in self.result.selected_layers()),
            geopackage_requested=output.save_cleaned_geopackage,
            pdf_requested=output.create_pdf,
            pdf_metadata=metadata,
        )

    def summary(self) -> Dict[str, object]:
        """Return the stable result summary plus user-facing output details."""
        summary = self.result.as_summary()
        summary.update(
            {
                "recognized_categories": self.recognized_categories(),
                "qgis_layer_ids": self.output_plan().qgis_layer_ids,
                "geopackage_requested": self.result.output.save_cleaned_geopackage,
                "pdf_requested": self.result.output.create_pdf,
            }
        )
        return summary
