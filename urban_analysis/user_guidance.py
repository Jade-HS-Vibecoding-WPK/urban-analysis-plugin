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
from .data_pipeline import merge_confirmed_duplicates
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

EXAMPLE_FIELDS = ("object_type", "object_detail", "category", "status")


@dataclass(frozen=True)
class DuplicateLayer:
    """Uncertain-duplicate groups of one input layer (step 6)."""

    table_name: str
    groups: Tuple[Tuple[str, Tuple[object, ...]], ...]  # (group id, records)

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def record_count(self) -> int:
        return sum(len(records) for _group, records in self.groups)

    @property
    def removable_count(self) -> int:
        """Objects removed if all groups are merged (one is kept per group)."""
        return self.record_count - self.group_count

    def cross_layer_groups(self) -> Tuple[str, ...]:
        """Groups whose objects ended up in different result layers."""
        return tuple(
            group for group, records in self.groups
            if len({record.layer_id for record in records}) > 1
        )


def group_table_name(group_id: str) -> str:
    """'gebaeude:12' -> 'gebaeude'."""
    return group_id.rsplit(":", 1)[0]


def _layer_names(table_name: str) -> Tuple[str, ...]:
    """Table name plus its readable name from the pipeline, if available.

    The pipeline's hint texts may use readable names such as „Gebäude“ for the
    table ``gebaeude`` (``mapping.readable_layer``, PR #13).
    """
    names = [table_name]
    try:
        from .mapping import readable_layer  # provided by the pipeline
    except ImportError:
        return tuple(names)
    try:
        readable = readable_layer(table_name)
    except Exception:  # an unknown table must not break the assignment
        readable = None
    if readable and readable not in names:
        names.append(str(readable))
    return tuple(names)


def issue_table_name(message: str, table_names: Iterable[str]) -> Optional[str]:
    """The one layer mentioned in a hint text, else ``None``.

    Hints have no layer field in the contract, so the table name or its
    readable name is looked up as a whole word in the text; ambiguous texts
    are not assigned.
    """
    import re

    found = [
        name for name in table_names
        if any(
            re.search(rf"(?<![\w]){re.escape(candidate)}(?![\w])", message, re.IGNORECASE)
            for candidate in _layer_names(name)
        )
    ]
    return found[0] if len(found) == 1 else None


def describe_group(records) -> str:
    """Short example of one group: count and the shown attribute values."""
    parts = []
    for field in EXAMPLE_FIELDS:
        values = []
        for record in records:
            value = record.attributes.get(field)
            text = "–" if value in (None, "") else str(value)
            if text not in values:
                values.append(text)
        if values != ["–"]:
            parts.append(" / ".join(values))
    layers = sorted({record.layer_id for record in records})
    detail = "; ".join(parts) if parts else "gleiche Angaben im Zielschema"
    return f"{len(records)} Objekte ({detail}) in {', '.join(layers)}"


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
        # Step 6: decisions per input layer (True = merge, False = keep) and
        # the records as delivered by the pipeline, so a decision can be
        # changed later without losing data.
        self.duplicate_decisions: Dict[str, bool] = {}
        self._records_before_merge: Optional[List[object]] = None

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

    def suggestions_by_layer(self) -> Dict[Optional[str], Tuple[AttributeSuggestion, ...]]:
        """Attribute proposals grouped by their input layer (E2), in data order."""
        groups: Dict[Optional[str], List[AttributeSuggestion]] = {}
        for suggestion in self.result.attribute_suggestions:
            groups.setdefault(suggestion.layer_id, []).append(suggestion)
        return {layer: tuple(items) for layer, items in groups.items()}

    def confirm_attribute_suggestions(
        self, decisions: Mapping[object, object]
    ) -> Tuple[AttributeSuggestion, ...]:
        """Apply confirmation or replacement values to the proposals.

        Keys are ``(layer_id, source_field)`` pairs, so equal column names in
        different layers are decided separately. A plain ``source_field`` key
        still works and applies to every layer with that column.
        A boolean confirms or rejects a proposal. A string replaces the target
        field and confirms it, keeping the decision visible in the contract.
        """
        suggestions = list(self.result.attribute_suggestions)
        targets: Dict[object, List[AttributeSuggestion]] = {}
        for key in decisions:
            if isinstance(key, tuple):
                layer_id, source_field = key
                matches = [
                    s for s in suggestions
                    if s.layer_id == layer_id and s.source_field == source_field
                ]
            else:
                matches = [s for s in suggestions if s.source_field == key]
            targets[key] = matches
        unknown = [key for key, matches in targets.items() if not matches]
        if unknown:
            raise KeyError(
                "Diese Quellfelder gibt es in den Attributvorschlägen nicht: "
                + ", ".join(sorted(
                    f"{key[1]} ({key[0]})" if isinstance(key, tuple) else str(key)
                    for key in unknown
                ))
            )

        for key, decision in decisions.items():
            source_field = key[1] if isinstance(key, tuple) else key
            if not isinstance(decision, bool) and not (
                isinstance(decision, str) and decision.strip()
            ):
                raise ValueError(
                    f"Für das Quellfeld „{source_field}“ ist kein Zielfeld eingetragen. "
                    "Bitte ein Zielfeld eintragen oder das Häkchen entfernen, um den "
                    "Vorschlag abzulehnen."
                )
            for suggestion in targets[key]:
                if isinstance(decision, bool):
                    suggestion.accepted = decision
                else:
                    suggestion.user_value = decision.strip()
                    suggestion.accepted = True
        return self.attribute_suggestions()

    def apply_attribute_decisions(self) -> bool:
        """Re-harmonize the records with the confirmed mapping (S5, M4).

        Uses the pipeline's ``apply_attribute_decisions`` once it exists and
        returns ``True``; returns ``False`` while the pipeline cannot do it yet,
        so the step can say so instead of pretending the data changed.
        """
        from . import data_pipeline

        apply = getattr(data_pipeline, "apply_attribute_decisions", None)
        if apply is None:
            return False
        if self._records_before_merge is None:
            self.result.harmonized_records = apply(self.result)
            return True
        # Step 6 already merged duplicates: re-map the original records and
        # apply the duplicate decisions again, so nothing is lost when the
        # user goes back to step 5 after step 6.
        self.result.harmonized_records = list(self._records_before_merge)
        self._records_before_merge = list(apply(self.result))
        self.result.harmonized_records = list(self._records_before_merge)
        if self.duplicate_decisions and not self.open_duplicate_decisions():
            self.apply_duplicate_decisions()
        return True

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

    # --- Step 6 "Harmonisierung" (W5 part 2): uncertain duplicates (S4) ---

    def _source_records(self) -> List[object]:
        if self._records_before_merge is not None:
            return self._records_before_merge
        return list(self.result.harmonized_records)

    def duplicate_layers(self) -> Tuple[DuplicateLayer, ...]:
        """Uncertain-duplicate groups per input layer, in data order."""
        groups: Dict[str, List[object]] = {}
        for record in self._source_records():
            group = getattr(record, "duplicate_group", None)
            if group:
                groups.setdefault(group, []).append(record)
        layers: Dict[str, List[Tuple[str, Tuple[object, ...]]]] = {}
        for group, records in groups.items():
            layers.setdefault(group_table_name(group), []).append((group, tuple(records)))
        return tuple(DuplicateLayer(name, tuple(items)) for name, items in layers.items())

    def set_duplicate_decision(self, table_name: str, merge: bool) -> None:
        known = {layer.table_name for layer in self.duplicate_layers()}
        if table_name not in known:
            raise KeyError(f"Für den Layer „{table_name}“ gibt es keine unsicheren Dubletten.")
        self.duplicate_decisions[table_name] = bool(merge)

    def open_duplicate_decisions(self) -> Tuple[str, ...]:
        """Layers whose duplicate groups still need a decision."""
        return tuple(
            layer.table_name
            for layer in self.duplicate_layers()
            if layer.table_name not in self.duplicate_decisions
        )

    def apply_duplicate_decisions(self) -> int:
        """Apply all decisions to the original records; return removed objects.

        Every call starts again from the records the pipeline delivered, so
        changing a decision never loses data. The decision is also stored on
        the matching hint (confirmed True = merged, False = kept).
        """
        open_layers = self.open_duplicate_decisions()
        if open_layers:
            raise ValueError(
                "Bitte für jeden Layer „Behalten“ oder „Zusammenführen“ wählen: "
                + ", ".join(open_layers)
            )
        original = self._source_records()
        self._records_before_merge = original
        confirmed_groups = [
            group
            for layer in self.duplicate_layers()
            if self.duplicate_decisions.get(layer.table_name)
            for group, _records in layer.groups
        ]
        merged = merge_confirmed_duplicates(original, confirmed_groups)
        self.result.harmonized_records = merged
        for issue in self.result.issues:
            if issue.code in DECIDED_IN_HARMONIZATION:
                table = issue_table_name(issue.message, self.duplicate_decisions)
                if table is not None:
                    issue.confirmed = self.duplicate_decisions[table]
        return len(original) - len(merged)

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
