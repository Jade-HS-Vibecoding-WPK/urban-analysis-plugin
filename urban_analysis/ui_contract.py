"""Shared UI labels and interaction rules for both feature branches."""

from .contracts import MVP_UI_STEPS


UI_LABELS = {
    "project_crs": "Projekt-CRS",
    "study_area": "Untersuchungsgebiet",
    "buffer": "Puffer (m)",
    "load_data": "Daten laden",
    "review_layers": "Layer prüfen",
    "attribute_mapping": "Attributzuordnung",
    "harmonization": "Harmonisierung",
    "topic": "Kartenthema",
    "output": "Ausgabe",
    "data_source": "Datenquelle",
    "start_processing": "Verarbeitung starten",
    "confirm": "Bestätigen",
    "change": "Ändern",
    "add": "Ergänzen",
    "continue_incomplete": "Unvollständig fortfahren",
}

MVP_REQUIRED_TOPIC_SUGGESTIONS = (
    "Gebäude",
    "Straßen",
    "Nutzungsflächen",
    "Grünflächen",
)


def validate_ui_step_order(step_labels):
    """Validate that a UI implements the shared MVP step order."""
    return tuple(step_labels) == MVP_UI_STEPS
