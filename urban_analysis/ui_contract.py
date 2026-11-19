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

# G13 (E36): the seven general map topics, topic_id -> name in the UI.  The
# catalog (topics_catalog.json) uses the same ids; names are only set here.
TOPIC_NAMES = {
    "bebauung": "Bebauung & Stadtstruktur",
    "nutzungen": "Nutzungen",
    "versorgung": "Versorgung & soziale Infrastruktur",
    "freiraum": "Freiraum & öffentlicher Raum",
    "mobilitaet": "Mobilität & Erschließung",
    "gruen_wasser_klima": "Grün, Wasser & Klima",
    "geschichte_stadtbild": "Geschichte & Stadtbild",
}

TOPIC_LABELS = {
    "classes": "Klassen",
    "scales": "Stufen",
    "limits": "Was die Daten nicht zeigen",
    "source_tips": "Bessere Daten",
    "overlay": "Themen überlagern",
    "uncertain": "vermutlich",
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
