"""QGIS side panel for the contract-defined eight-step user guidance.

The guidance lives in a dock widget on the right side of QGIS, so it can stay
open, be hidden via the toolbar button or be undocked while working in QGIS.

Pages 1-3 (Projekt-CRS, Untersuchungsgebiet, Daten laden) work without a
``PipelineResult``.  Pages 4-9 are rebuilt every time they are reached, so
they always reflect the data that is currently loaded.
"""

import os
import re
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from .contracts import (
    COLUMN_DROP,
    COLUMN_KEEP,
    COLUMN_TARGET,
    CORE_FIELDS,
    MVP_DEFAULT_BUFFER_METERS,
    MVP_UI_STEPS,
    ColumnDecision,
)
from .data_pipeline import (
    TARGET_FIELDS,
    GeoPackageImporter,
    GeoPackageImportError,
    apply_column_decisions,
    apply_data_source,
    default_column_decisions,
)
from .accessibility_view import (
    GUIDE_NOTE,
    AccessibilityChoice,
    RadiusError,
    add_columns_to_layer,
    build_layers as build_accessibility_layers,
    calculate as calculate_accessibility,
    choice_problem,
    distance_columns,
    guide_value,
    parse_radii,
    radii_for,
    radii_text,
    ring_colors,
)
from .map_styles import DEFAULT_MAP_STYLE, MAP_STYLES, apply_style, draw_rank
from .osm_download import (
    DownloadCanceled,
    DownloadError,
    ensure_project_crs,
    lonlat_box,
    run_download,
    unique_path,
)
from .sources import plan_osm_download
from .outputs import (
    add_result_layers,
    PAGE_SIZES_MM,
    SCALES,
    build_result_layers,
    export_map_pdf,
    format_count,
    scale_label,
    time_text,
    write_result_geopackage,
    result_group_name,
    result_layer_name,
    result_layer_names,
    result_layers_text,
)
from .study_area import (
    DRAW_INSTRUCTIONS,
    StudyAreaError,
    MAX_DOWNLOAD_TEXT,
    add_drawn_area_layer,
    area_summary_text,
    create_polygon_draw_tool,
    download_box_km2,
    download_size_text,
    format_km2,
    is_large,
    is_oversized,
    oversize_question_text,
    oversize_warning_text,
    study_area_from_layer,
)
from .theme import (
    load_fonts,
    panel_stylesheet,
    set_role,
)
from .ui_contract import UI_LABELS
from .ui.layer_icons import LAYER_ICONS, icon_key
from .user_guidance import (
    DECIDED_IN_HARMONIZATION,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    describe_group,
    issue_table_name,
)


DOCK_OBJECT_NAME = "UrbanAnalysisDock"
NO_DATA_MESSAGE = "Noch keine Daten geladen. Bitte zuerst ein GeoPackage laden."
# Step 8/9 outputs (W8b).  The PDF is still the simple one without a map;
# the real layout follows in its own step together with the sources (M10).
OUTPUT_SUFFIXES = {"geopackage": ".gpkg", "pdf": ".pdf"}
OUTPUT_KIND_LABELS = {"geopackage": "GeoPackage", "pdf": "PDF"}
OUTPUT_DIALOG_TITLES = {
    "geopackage": "Bereinigtes GeoPackage speichern unter",
    "pdf": "PDF speichern unter",
}
OUTPUT_DIALOG_FILTERS = {
    "geopackage": "GeoPackage (*.gpkg)",
    "pdf": "PDF (*.pdf)",
}
LAST_OUTPUT_FOLDER_SETTING = "urban_analysis/last_output_folder"
SAVE_AS_LABEL = "Speichern unter …"
DATA_SOURCE_PLACEHOLDER = "z. B. ALKIS, Stand 2026"
DATA_SOURCE_HINT = (
    "Pflichtfeld. Steht bei jedem Ergebnis-Objekt im Feld „Quelle“, wenn die "
    "Daten selbst keine Quelle mitbringen."
)
DATA_SOURCE_REQUIRED_MESSAGE = (
    "Bitte eine Datenquelle eintragen (z. B. „ALKIS, Stand 2026“). "
    "Sie wird bei jedem Ergebnis-Objekt im Feld „Quelle“ gespeichert."
)
MISSING_PATH_MESSAGES = {
    "geopackage": "Für das bereinigte GeoPackage fehlt der Speicherort. Bitte "
                  "„Speichern unter …“ klicken oder das Häkchen entfernen.",
    "pdf": "Für das PDF fehlt der Speicherort. Bitte „Speichern unter …“ klicken "
           "oder das Häkchen entfernen.",
}
INPUT_FILE_MESSAGE = (
    "„{name}“ ist deine Eingabedatei. Bitte wähle mit „Speichern unter …“ einen "
    "anderen Namen, damit die Originaldaten erhalten bleiben."
)
FILE_EXISTS_MESSAGE = (
    "Die Datei „{name}“ gibt es schon. Bitte „Speichern unter …“ klicken und dort "
    "bestätigen, dass sie ersetzt wird, oder einen anderen Namen wählen."
)
SIMPLE_PDF_NOTE =" (einfaches PDF ohne Karte)"
PDF_HINT = (
    "Karte mit Legende, Maßstab, Untersuchungsgebiet mit Puffer und dem Block "
    "„Datenquellen und Lizenzen“."
)
SIMPLE_PDF_HINT = (
    "Vorerst ein einfaches PDF mit den Angaben zum Lauf. Die Karte mit Legende, "
    "Maßstab und Seitengröße folgt in einem eigenen Schritt."
)
SAVE_FAILED_MESSAGE = (
    "{kind} konnte nicht gespeichert werden: {reason}\n"
    "Was tun: Ist die Datei gerade in QGIS oder einem anderen Programm geöffnet, "
    "bitte dort schließen oder unter „Speichern“ einen anderen Dateinamen wählen. "
    "Die Ergebnis-Layer in QGIS sind trotzdem angelegt."
)
CRS_HINT = (
    "Das CRS muss zu den Daten im GeoPackage passen. Layer mit einem anderen CRS "
    "werden nicht übernommen, denn die Datenpipeline rechnet keine Koordinaten um. "
    "Das CRS deines QGIS-Projekts bleibt unverändert."
)

# One guided main action per page, in the order of MVP_UI_STEPS.
PAGE_ACTIONS = (
    "CRS übernehmen",
    "Gebiet übernehmen",
    UI_LABELS["load_data"],
    "Hinweise geprüft",
    "Zuordnung bestätigen",
    "Entscheidung übernehmen",
    "Thema übernehmen",
    UI_LABELS["start_processing"],
)

# Step 3 (W10): sources OSM / ALKIS / own file.  OSM and ALKIS are
# placeholders until M10 (sources.py: suggest_state, download jobs) and W11
# (download in QGIS); only "Eigene Datei" loads data for now.
SOURCE_OSM_LABEL = "OpenStreetMap (OSM)"
SOURCE_ALKIS_LABEL = "ALKIS (amtliche Daten)"
SOURCE_OWN_LABEL = "Eigene Datei"
SOURCE_OSM_HINT = (
    "Offene Daten für ganz Deutschland: Gebäude, Straßen, Grünflächen, Nutzungen. "
    "Quellenvermerk: © OpenStreetMap-Mitwirkende (ODbL)."
)
SOURCE_ALKIS_HINT = (
    "Amtliches Liegenschaftskataster deines Bundeslands. Ob das Land ALKIS frei "
    "anbietet, prüft das Plugin, sobald der Quellen-Katalog fertig ist."
)
CHOOSE_STATE_ITEM = "Bundesland wählen …"
# Placeholder until M10 suggests the state from the study area (E11).
GERMAN_STATES = (
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg",
    "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen",
    "Rheinland-Pfalz", "Saarland", "Sachsen", "Sachsen-Anhalt",
    "Schleswig-Holstein", "Thüringen",
)
LOCAL_DATA_HINT = (
    "Eine GeoPackage-Datei (.gpkg) von deinem Rechner, z. B. eine eigene "
    "Kartierung oder ein eigener ALKIS-Export. Pro Durchlauf wird eine Datei geladen."
)
CHOOSE_SOURCE_MESSAGE = (
    "Bitte mindestens eine Quelle ankreuzen: „OpenStreetMap“, „ALKIS“ oder "
    "„Eigene Datei“."
)
CHOOSE_STATE_MESSAGE = "Für ALKIS bitte das Bundesland wählen."
DOWNLOAD_PENDING_MESSAGE = (
    "Das Herunterladen von ALKIS-Daten wird in einem späteren Schritt "
    "angeschlossen. Bitte vorerst „OpenStreetMap“ oder „Eigene Datei“ verwenden."
)
ONE_SOURCE_MESSAGE = (
    "Mehrere Quellen in einem Durchlauf kommen in einem späteren Schritt. Bitte "
    "vorerst nur eine Quelle ankreuzen: „OpenStreetMap“ oder „Eigene Datei“."
)
LAST_DOWNLOAD_FOLDER_SETTING = "urban_analysis/last_download_folder"
DOWNLOAD_FOLDER_TITLE = "Bitte Speicherort für die OSM-Daten wählen"
CHOOSE_FOLDER_ACTION = "Speicherort wählen"


def folder_chosen_text(folder):
    """Info after choosing the download folder (button now 'Daten laden')."""
    return (f"Speicherort gewählt: {short_folder(folder)}. "
            "Jetzt auf „Daten laden“ klicken, um die OSM-Daten herunterzuladen.")
DOWNLOAD_FOLDER_HINT = (
    "Zuerst unten „Speicherort wählen“: In diesem Ordner werden die OSM-Daten "
    "gespeichert (z. B. dein Projektordner). Danach „Daten laden“."
)
DOWNLOAD_NO_FOLDER_MESSAGE = "Kein Ordner gewählt – es wurde nichts heruntergeladen."
DOWNLOAD_TOO_LARGE_MESSAGE = (
    "Das Gebiet ist mit Puffer {size} km² groß. OSM- und ALKIS-Daten können nur "
    "für höchstens {limit} km² heruntergeladen werden. Bitte in Schritt 2 das "
    "Gebiet oder den Puffer verkleinern oder nur „Eigene Datei“ verwenden."
)
CHOOSE_FILE_MESSAGE = "Bitte zuerst mit „Datei wählen …“ eine GeoPackage-Datei auswählen."
MISSING_AREA_MESSAGE = (
    "Projekt-CRS und Untersuchungsgebiet fehlen. Bitte mit „Zurück“ Schritt 1 und 2 "
    "abschließen."
)
FILE_DIALOG_TITLE = "GeoPackage-Datei wählen"
FILE_DIALOG_FILTER = "GeoPackage (*.gpkg);;Alle Dateien (*)"
LAST_FOLDER_SETTING = "urban_analysis/last_geopackage_folder"
ARROW_CLOSED = "▸"
ARROW_OPEN = "▾"
PANEL_ANIMATION_MS = 180
STYLE_BUTTON_TOOLTIP = "Stil wechseln: Klassisch oder Pixel"
RESET_TOOLTIP ="Plugin auf Anfang zurücksetzen: alle Eingaben und geladenen Daten verwerfen."
RESET_QUESTION = (
    "Alles auf Anfang zurücksetzen?\n\n"
    "Alle Eingaben und die geladenen Daten im Plugin werden verworfen, du beginnst "
    "wieder bei Schritt 1. Layer in deinem QGIS-Projekt (auch ein gezeichnetes "
    "Untersuchungsgebiet) bleiben erhalten."
)
RESET_DONE_MESSAGE = "Das Plugin wurde zurückgesetzt. Du beginnst wieder bei Schritt 1."
NO_DUPLICATES_TEXT = "Keine unsicheren Dubletten gefunden – hier gibt es nichts zu entscheiden."
UNCERTAIN_DUPLICATE_EXPLANATION_STEP6 = (
    "Unsichere Dubletten: Objekte mit derselben Geometrie, aber unterschiedlichen "
    "Angaben. Bitte pro Layer entscheiden, ob jede Gruppe zu einem Objekt "
    "zusammengeführt wird oder alle Objekte bleiben. Die Originaldaten bleiben "
    "unverändert; die Entscheidung lässt sich mit „Zurück“ noch ändern."
)
DUPLICATE_EXAMPLES = 3
MAPPING_INTRO = (
    "Die Datenpipeline schlägt vor, welche Spalte deiner Daten in welches Feld der "
    "Ergebnis-Layer kommt. Prüfe die Vorschläge je Layer: Häkchen = Spalte "
    "übernehmen, rechts das Zielfeld wählen."
)
NO_SUGGESTIONS_TEXT = "Für diese Daten gibt es keine Vorschläge zur Attributzuordnung."
MAPPING_SAVED_TEXT = (
    "Zuordnung gespeichert. Auf die Daten wirkt sie, sobald die Datenpipeline das "
    "Anwenden unterstützt (ARBEITSPLAN M4)."
)
MAPPING_APPLIED_TEXT = "Zuordnung übernommen: Die Daten wurden neu zugeordnet."


SUMMARY_INTRO = (
    "Prüfe die Übersicht. Mit „Verarbeitung starten“ werden die Ergebnis-Layer in "
    "QGIS angelegt. Deine Eingangsdaten und Projekt-Layer bleiben unverändert."
)
DONE_TITLE = "Fertig ✓ – die Ergebnis-Layer sind in QGIS angelegt."
RERUN_ACTION = "Erneut verarbeiten"
REMAKE_PDF_LABEL = "PDF neu erzeugen"
REMAKE_PDF_TOOLTIP = (
    "Erzeugt das PDF mit dem aktuellen Stand in QGIS: nur sichtbare Layer der "
    "Ergebnis-Gruppe, in ihrer Reihenfolge. Titel und Format stellst du in Schritt 8 ein."
)
REMAKE_QUESTION = (
    "Das PDF wird mit den gerade sichtbaren Ergebnis-Layern neu erzeugt.\n\n"
    "Soll die bisherige PDF-Datei überschrieben oder eine neue Datei angelegt werden?"
)
REMAKE_NO_GROUP_MESSAGE = (
    "Die Ergebnis-Gruppe wurde in QGIS nicht gefunden. Bitte unter „Ausgabe“ „Layer erzeugen“ klicken."
)
REMAKE_NO_LAYERS_MESSAGE = (
    "In der Ergebnis-Gruppe ist kein Layer sichtbar. Bitte mindestens einen Layer einschalten."
)
SAME_RUN_QUESTION = (
    "Seit der letzten Verarbeitung hat sich nichts geändert – das Ergebnis wäre "
    "gleich.\n\nTrotzdem eine neue Gruppe mit denselben Ergebnis-Layern erzeugen?"
)


# Step 5 (W14, E29/E30): columns of the input layers
STEP5_GUIDE = (
    "Was siehst du? Alle Spalten deiner Daten, je Layer, mit lesbarem Namen und Beispielen.",
    "Was entscheidest du? Je Spalte: in ein Kernfeld übernehmen (z. B. Adresse), "
    "als eigene Spalte behalten oder weglassen.",
    "Was passiert dann? Die Ergebnis-Layer enthalten genau diese Spalten. Die "
    "Vorauswahl passt meistens – du musst nur ändern, was du anders willst.",
)
STEP5_SHORT_GUIDE = (
    "So sieht deine Attributtabelle am Ende aus. Klick auf ein Etikett: "
    "Kernfeld → Behalten → Ignoriert. Die Vorauswahl passt meistens."
)
MORE_COLUMNS_LABEL ="Nicht geladen (nicht lesbar)"
COLUMN_KEEP_HELP = "Die Spalte kommt unter ihrem lesbaren Namen in die Ergebnis-Layer."
COLUMN_DROP_HELP = "Die Spalte kommt nicht in die Ergebnis-Layer."
COLUMNS_SAVED_TEXT = "Spaltenauswahl übernommen. Sie gilt bei „Verarbeitung starten“."


PREVIEW_ROWS = 3
PILL_WIDTH = 92
PREVIEW_HEADING = "Vorschau Ergebnis-Tabelle"
COLUMNS_HEADING = "Spalten – Klick auf das Etikett wechselt: Kernfeld → Behalten → Ignoriert"
STATE_LEGEND = ("ⓘ Kernfeld = Pflichtfeld für Karte und Legende · Behalten = eigene "
                "Spalte · Ignoriert = wird nicht übernommen")
STATE_LABELS = {"target": "● Kernfeld", "keep": "● Behalten", "drop": "○ Ignoriert"}
# (fill, border) per state – green core field, blue kept, grey ignored
STATE_COLORS = {"target": ("#e3f2e5", "#5aa36a"), "keep": ("#e2eefa", "#4a86c5"),
                "drop": ("#f1f2f4", "#b5bcc4")}


# Step 9: one row of buttons, each opens its own area (always selectable)
STEP9_TABS = (
    ("output", "Ausgabe"),
    ("access", "Erreichbarkeit"),
    ("save", "Speichern"),
)
LAYERS_ACTION = "Layer erzeugen"
LAYERS_AGAIN_ACTION = "Layer neu erzeugen"
ACCESS_ACTION = "Analyse starten"
SAVE_ACTION = "Speichern"
LAYERS_INTRO = ("Hier entstehen die Ergebnis-Layer in QGIS (eine neue Gruppe). Deine "
                "Eingangsdaten bleiben unverändert.")
LAYERS_NEXT_HINT = ("Optional weiter mit „Erreichbarkeit“, dann „Speichern“ – die Knöpfe "
                    "oben sind jederzeit anwählbar.")
LAYERS_FIRST_HINT = ("Noch keine Ergebnis-Layer: Sie werden beim Klick unten automatisch "
                     "zuerst erzeugt (Einstellungen unter „Ausgabe“).")
SAVE_INTRO = ("Gespeichert wird der aktuelle Stand in QGIS: das GeoPackage mit allen Layern "
              "der Ergebnis-Gruppe (auch der Erreichbarkeit), das PDF mit den gerade "
              "sichtbaren Layern in ihrer Reihenfolge. Erneut speichern überschreibt die "
              "Dateien – für neue Dateien „Speichern unter …“ wählen.")
SAVE_NOTHING_MESSAGE = ("Es ist nichts zum Speichern ausgewählt. Bitte oben „GeoPackage“ "
                        "und/oder „PDF-Karte“ ankreuzen.")
ACCESS_SECTION_LABEL = "Erreichbarkeit (zusätzlich)"
ACCESS_INTRO = ("Wie weit ist es von jedem Gebäude zum nächsten Ziel (Luftlinie)? Ergebnis: "
                "Abstand je Gebäude in der Attributtabelle und Radien um die Ziele in der Karte. "
                "Die Ziele werden als eigene Punkte mit ihrer ganzen Attributtabelle kopiert.")
ACCESS_RADII_GUIDE = "Radien je Ziel in Metern (vorgeschlagen: Richtwert)"
ACCESS_TARGETS_HINT = ("Ganze Kategorien ankreuzen (z. B. „ÖPNV-Haltestellen“) oder aufklappen "
                       "und einzelne Arten wählen (z. B. nur „Supermarkt“). Mehrere Ziele sind möglich.")
ACCESS_NO_TARGETS = ("In den geladenen Daten gibt es keine Ziele wie Haltestellen, Supermärkte "
                     "oder Arztpraxen. Diese kommen aus OpenStreetMap – bitte in Schritt 3 "
                     "„OpenStreetMap“ laden.")
ACCESS_RADII_HINT = ("Mehrere Radien mit Komma trennen. Jeder Radius wird als gestrichelte "
                     "Linie um die Ziele gezeichnet; gemessen wird die Luftlinie.")
ACCESS_FILL_LABEL = "Flächen einfärben (Deckkraft 15 %)"
STEP5_QUESTION = (
    "Deine Daten haben viele Spalten. Sollen sie automatisch zugeordnet werden? "
    "Danach siehst du das Ergebnis als Tabelle und kannst bei Bedarf noch ändern."
)
AUTO_COLUMNS_HINT = ("Wichtige Spalten werden übernommen, technische und fast leere "
                     "weggelassen. Die Tabellen sind zugeklappt – meist reicht „bestätigen“.")
MANUAL_COLUMNS_HINT = ("Gleiche Vorauswahl, aber alle Tabellen sind aufgeklappt, damit du "
                       "jede Spalte prüfen kannst.")
STEP5_TABLE_GUIDE = (
    "So sieht deine Attributtabelle am Ende aus. Farbig = wird übernommen, weiß = "
    "bleibt draußen. Zum Ändern auf eine Spaltenüberschrift klicken."
)


def ordered_columns(columns, values):
    """Table order: core fields, then kept, then left-out columns."""
    rank = {"target": 0, "keep": 1, "drop": 2}
    return sorted(columns, key=lambda c: rank[state_of(values.get((c.layer_id, c.source_field)))])


def column_title(column, value):
    """Header of a column: core field name for core fields, else the readable name."""
    name = column.readable_name or column.source_field
    if state_of(value) == "target":
        return core_field_name(value.split(":", 1)[1])
    return name


def state_of(value):
    """'target:address' -> 'target'; 'keep' / 'drop' unchanged."""
    return "target" if (value or "").startswith("target:") else (value or "drop")


def next_value(value, column):
    """Click on the label: Kernfeld → Behalten → Ignoriert → Kernfeld."""
    state = state_of(value)
    if state == "target":
        return "keep"
    if state == "keep":
        return "drop"
    return f"target:{column.suggested_target or CORE_FIELDS[0]}"


def core_field_name(field_name):
    try:
        from .mapping import readable_target_field
    except ImportError:  # pragma: no cover
        return field_name
    return readable_target_field(field_name)


def preview_columns(columns, values):
    """Headers of the result table preview: (header, state, source field);
    core fields first (in their fixed order), then kept columns."""
    core, kept = [], []
    for column in columns:
        value = values.get((column.layer_id, column.source_field), "drop")
        state = state_of(value)
        if state == "target":
            field_name = value.split(":", 1)[1]
            core.append((CORE_FIELDS.index(field_name) if field_name in CORE_FIELDS else 99,
                         (core_field_name(field_name), state, column.source_field)))
        elif state == "keep":
            kept.append((column.readable_name or column.source_field, state, column.source_field))
    return [entry for _order, entry in sorted(core, key=lambda item: item[0])] + kept


def counts_text(columns, values):
    """'4 Kernfelder · 3 behalten · 8 ignoriert'."""
    counts = {"target": 0, "keep": 0, "drop": 0}
    for column in columns:
        counts[state_of(values.get((column.layer_id, column.source_field), "drop"))] += 1
    return f"{counts['target']} Kernfelder · {counts['keep']} behalten · {counts['drop']} ignoriert"


def column_choices():
    """(value, text, help) for the choice list of a column."""
    try:
        from .mapping import readable_target_field, target_field_explanation
    except ImportError:  # pragma: no cover
        readable_target_field, target_field_explanation = (lambda f: f), (lambda f: None)
    choices = [(f"target:{f}", f"→ {readable_target_field(f)}", target_field_explanation(f))
               for f in CORE_FIELDS]
    choices.append(("keep", "Als eigene Spalte behalten", COLUMN_KEEP_HELP))
    choices.append(("drop", "Weglassen", COLUMN_DROP_HELP))
    return choices


def choice_help(value):
    for choice_value, _text, help_text in column_choices():
        if choice_value == value:
            return help_text
    return None


def decision_value(decision):
    """ColumnDecision -> value of the choice list ('target:address', 'keep', 'drop')."""
    if decision is None:
        return "drop"
    if decision.action == COLUMN_TARGET:
        return f"target:{decision.target_field}"
    return decision.action


def decision_from_value(column, value):
    """Value of the choice list -> ColumnDecision for the pipeline."""
    if value and value.startswith("target:"):
        return ColumnDecision(column.layer_id, column.source_field, COLUMN_TARGET,
                              target_field=value.split(":", 1)[1])
    if value == "keep":
        return ColumnDecision(column.layer_id, column.source_field, COLUMN_KEEP,
                              name=column.readable_name or column.source_field)
    return ColumnDecision(column.layer_id, column.source_field, COLUMN_DROP)


AUTO_COLUMNS_LABEL = "Ja, automatisch zuordnen (empfohlen)"
MANUAL_COLUMNS_LABEL = "Nein, selbst wählen"
# Kept by default whenever the data have them (user wish 19.11.)
ALWAYS_KEEP = ("Geschosszahl", "Baujahr", "Name")
MIN_FILL_RATE = 0.15  # kept columns must be filled in at least 15 % of the objects
FILL_SAMPLE = 400


def fill_rates(records):
    """{(layer, source field): share of objects with a value} from a sample."""
    seen, filled = {}, {}
    for record in records:
        table = record.source_layer or record.layer_id
        if seen.get(table, 0) >= FILL_SAMPLE:
            continue
        seen[table] = seen.get(table, 0) + 1
        for field_name, value in (getattr(record, "source_attributes", None) or {}).items():
            if value not in (None, ""):
                filled[(table, field_name)] = filled.get((table, field_name), 0) + 1
    return {key: count / seen[key[0]] for key, count in filled.items()}


def always_kept(column):
    """Geschosszahl, Baujahr, Name – also 'Geschosszahl (OSM)' or 'Baujahr oder
    Entstehung' (names start with these words)."""
    name = column.readable_name or ""
    return any(name.startswith(word) for word in ALWAYS_KEEP)


def preselect(columns, decisions, rates):
    """Improve the pipeline's preselection (W14): nearly empty columns stay
    out; Geschosszahl, Baujahr and Name are kept whenever they exist.

    Core fields (above all the Objekt-ID) stay exactly as the pipeline
    suggests them: the pipeline knows which ID column a profile uses
    (e.g. OSM ``osm_way_id`` for areas, see #52)."""
    result = {}
    for column in columns:
        key = (column.layer_id, column.source_field)
        decision = decisions[key]
        if decision.action == COLUMN_KEEP and not always_kept(column) \
                and rates.get(key, 0.0) < MIN_FILL_RATE:
            decision = decision_from_value(column, "drop")  # (nearly) empty
        elif decision.action == COLUMN_DROP and always_kept(column):
            decision = decision_from_value(column, "keep")
        result[key] = decision
    return result


def column_decisions_of(flow):
    """Choices made earlier in step 5, else the improved preselection."""
    decisions = getattr(flow, "column_decisions", None)
    if decisions:
        return {(d.layer_id, d.source_field): d for d in decisions}
    defaults = {(d.layer_id, d.source_field): d
                for d in default_column_decisions(flow.result.columns)}
    return preselect(flow.result.columns, defaults, fill_rates(flow.result.harmonized_records))


def column_summary(columns, decisions):
    """{'target': [...names], 'keep': [...], 'drop': [...]} for the overview."""
    summary = {"target": [], "keep": [], "drop": []}
    for column in columns:
        decision = decisions.get((column.layer_id, column.source_field))
        action = decision.action if decision else "drop"
        if action == COLUMN_TARGET:
            try:
                from .mapping import readable_target_field
                name = readable_target_field(decision.target_field)
            except ImportError:  # pragma: no cover
                name = decision.target_field
        else:
            name = column.readable_name or column.source_field
        summary[action].append(name)
    return summary


def summary_lines(summary):
    """Overview lines of one layer in step 5 (automatic mode)."""
    lines = [
        "Kernfelder: " + (", ".join(summary["target"]) or "–"),
        "Behalten: " + (", ".join(summary["keep"]) or "–"),
    ]
    count = len(summary["drop"])
    lines.append(f"Ignoriert: {count} technische {'Spalte' if count == 1 else 'Spalten'}")
    return lines


def column_header_text(layer_name, columns, decisions):
    """'Gebäude – 4 Kernfelder, 6 behalten, 12 nicht geladen'."""
    counts = {"target": 0, "keep": 0, "drop": 0}
    for column in columns:
        decision = decisions.get((column.layer_id, column.source_field))
        counts[decision.action if decision else "drop"] += 1
    return (f"{layer_name} – {counts['target']} Kernfelder, {counts['keep']} behalten, "
            f"{counts['drop']} nicht geladen")


def crs_mismatch_text(qgis_crs, plugin_crs):
    """Warning in step 1 when QGIS and the plugin use different CRS."""
    return (
        f"Das QGIS-Projekt nutzt {qgis_crs}, im Plugin ist {plugin_crs} gewählt.\n\n"
        "Unterschiedliche Koordinatensysteme können zu Anzeigefehlern führen. Bei "
        f"„Fortfahren“ wird das QGIS-Projekt auf {plugin_crs} umgestellt, und Daten "
        f"in einem anderen CRS werden beim Laden als Kopie nach {plugin_crs} "
        "umgerechnet (die Originaldateien bleiben unverändert).\n\n"
        "Möchtest du das CRS im Plugin noch ändern?"
    )


def run_signature(flow, draft, paths):
    """Everything that changes the output of step 9; equal = nothing changed."""
    result = flow.result
    suggestions = tuple(
        (s.layer_id, s.source_field, s.user_value, s.accepted)
        for s in getattr(result, "attribute_suggestions", ()) or ()
    )
    return repr((
        tuple(d.layer_id for d in result.selected_layers()),
        result.selected_topic, result.study_area_wkt, result.buffer_meters,
        result.output, sorted((flow.duplicate_decisions or {}).items()),
        suggestions, sorted((k, str(v)) for k, v in draft.items()),
        repr(getattr(flow, "accessibility", None)), repr(getattr(flow, "column_values", None)),
        sorted((k, str(v)) for k, v in paths.items()),
    ))


def format_hectares(hectares):
    text = f"{hectares:,.1f}"
    return text.replace(",", " ").replace(".", ",")


def objects_text(count):
    """'1 Objekt', '1 571 Objekte'."""
    return f"{format_count(count)} {'Objekt' if count == 1 else 'Objekte'}"


def done_hint_text(group_name):
    return (
        f"Du findest sie im Layer-Bedienfeld in der Gruppe „{group_name}“. "
        "„Layer neu erzeugen“ legt eine neue Gruppe an; frühere Ergebnisse bleiben erhalten."
    )


def overview_rows(flow, area_ha, names):
    """Key facts of the run as (label, value) rows for step 9."""
    result = flow.result
    files = sorted({layer.source_name for layer in result.layers if layer.source_name})
    decisions = flow.duplicate_decisions
    if decisions:
        duplicates = ", ".join(
            f"{names.layer(table)} {'zusammengeführt' if merge else 'behalten'}"
            for table, merge in decisions.items()
        )
    else:
        duplicates = "keine"
    warnings = len(flow.issues_by_severity()["warning"])
    return (
        ("Projekt-CRS", result.project_crs),
        ("Untersuchungsgebiet", f"{format_hectares(area_ha)} ha" if area_ha else "–"),
        ("Puffer", f"{format_count(int(round(result.buffer_meters)))} m"),
        ("Datei", ", ".join(files) or "–"),
        ("Kartenthema", result.selected_topic or "–"),
        ("Datenquelle", result.output.data_source or "– noch nicht eingetragen (oben)"),
        ("Unsichere Dubletten", duplicates),
        ("Hinweise aus Schritt 4", f"{warnings} Warnung(en)"),
    )


def planned_layer_rows(flow, names):
    """One row per result layer that will be created, with its object count
    and its icon key as third element."""
    counts = {}
    for record in flow.result.harmonized_records:
        counts[record.layer_id] = counts.get(record.layer_id, 0) + 1
    rows = []
    selected = flow.result.selected_layers()
    unique = result_layer_names(selected, names.layer)
    for descriptor in selected:
        name = unique[descriptor.layer_id]
        rows.append((None, f"{name} – {objects_text(counts.get(descriptor.layer_id, 0))}",
                     icon_key(descriptor.layer_id, descriptor.category)))
    return tuple(rows) or ((None, "Keine Layer ausgewählt (Schritt 7)."),)


def layer_icon_key(flow, layer_id):
    """Icon key of a layer from its descriptor (category) or its id."""
    for descriptor in flow.result.layers:
        if descriptor.layer_id == layer_id:
            return icon_key(layer_id, descriptor.category)
    return icon_key(layer_id)


def issue_icon_key(flow, issue):
    """Icon key for a review hint, or None if it belongs to no single layer."""
    candidates = set(LAYER_ICONS) | {d.layer_id for d in flow.result.layers}
    table = issue_table_name(issue.message, sorted(candidates))
    return layer_icon_key(flow, table) if table else None


def source_choice_problem(*, osm, alkis, state, own, path, download_km2, has_data):
    """Check the step-3 sources.  Returns None (go on: load the file or keep
    the loaded data) or (kind, text) with kind 'error' or 'info'."""
    if not (osm or alkis or own):
        return None if has_data else ("error", CHOOSE_SOURCE_MESSAGE)
    if alkis and not state:
        return ("error", CHOOSE_STATE_MESSAGE)
    if (osm or alkis) and download_km2 is not None and is_oversized(download_km2):
        return ("error", DOWNLOAD_TOO_LARGE_MESSAGE.format(
            size=format_km2(download_km2), limit=MAX_DOWNLOAD_TEXT))
    if alkis:
        return ("info", DOWNLOAD_PENDING_MESSAGE)  # until M10b, never silent
    if osm and own:
        return ("error", ONE_SOURCE_MESSAGE)  # until M13 (several sources)
    if own and path is None and not has_data:
        return ("error", CHOOSE_FILE_MESSAGE)
    return None  # OSM: download (W11); own file: load it


def output_slug(text):
    """'Siedlungsstruktur' -> 'siedlungsstruktur'; safe for file names."""
    text = (text or "ergebnis").lower()
    for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    slug = "".join(char if char.isalnum() else "_" for char in text)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "ergebnis"


def default_output_path(folder, topic, kind, day):
    """Suggested file: <folder>/urban_analysis_<topic>_<YYYY-MM-DD>.<gpkg|pdf>."""
    return Path(folder) / f"urban_analysis_{output_slug(topic)}_{day.isoformat()}{OUTPUT_SUFFIXES[kind]}"


def with_output_suffix(path, kind):
    """Add .gpkg/.pdf if the user typed a name without it."""
    path = Path(path)
    suffix = OUTPUT_SUFFIXES[kind]
    return path if path.suffix.lower() == suffix else path.with_name(path.name + suffix)


def short_folder(folder):
    """Last two folders only ('…\\Projekt\\Ausgabe'): long paths cannot wrap
    and would make the panel wider than the window.  The full path is the
    tooltip."""
    parts = Path(folder).parts
    if len(parts) <= 3:
        return str(Path(folder))
    return "…" + os.sep + str(Path(*parts[-2:]))


def output_path_text(path):
    """Two lines below a ticked output: file name and (short) folder."""
    path = Path(path)
    return f"{path.name}\nim Ordner {short_folder(path.parent)}"


def _same_file(first, second):
    try:
        return Path(first).resolve() == Path(second).resolve()
    except OSError:
        return False


def output_choice_problem(*, geopackage, pdf, paths, data_source, confirmed=(),
                          input_paths=()):
    """First problem of the step-8 choices as user text, or None if all is set.

    The data source is always required: it goes into the field 'Quelle' of
    every result object (apply_data_source, S8).  A suggested file name that
    already exists is only replaced after the user picked it in the save
    dialog (``confirmed`` = kinds chosen there), never silently."""
    if not (data_source or "").strip():
        return DATA_SOURCE_REQUIRED_MESSAGE
    for kind, wanted in (("geopackage", geopackage), ("pdf", pdf)):
        if not wanted:
            continue
        path = paths.get(kind)
        if not path:
            return MISSING_PATH_MESSAGES[kind]
        # Raw data are never overwritten (CLAUDE.md), not even after "Ersetzen".
        if any(_same_file(path, source) for source in input_paths):
            return INPUT_FILE_MESSAGE.format(name=Path(path).name)
        if kind not in confirmed and Path(path).exists():
            return FILE_EXISTS_MESSAGE.format(name=Path(path).name)
    return None


def output_rows(output, paths=None):
    """Step-9 overview of the outputs, with the chosen file names."""
    paths = paths or {}

    def chosen(flag, kind, extra=""):
        if not flag:
            return "nein"
        path = paths.get(kind)
        return f"ja – {Path(path).name}{extra}" if path else "ja – Speicherort fehlt („Speichern unter …“)"

    return (
        ("Ergebnis-Layer in QGIS", "ja"),
        ("Bereinigtes GeoPackage", chosen(output.save_cleaned_geopackage, "geopackage")),
        ("PDF", chosen(output.create_pdf, "pdf")),
    )


def saved_rows(saved):
    """Rows for the 'Fertig' view: one per written file, ``saved`` = [(kind, path)]."""
    return tuple(
        (OUTPUT_KIND_LABELS[kind], f"{Path(path).name} – im Ordner {short_folder(Path(path).parent)}")
        for kind, path in saved
    )


def result_rows(reports, categories=None):
    """Rows for the 'Fertig' view: created layers (with icon key) and anything
    not taken over.  ``categories`` maps layer_id -> category."""
    categories = categories or {}
    rows = [
        (None, f"{report.name} – {objects_text(report.feature_count)}",
         icon_key(report.layer_id, categories.get(report.layer_id)))
        for report in reports
    ]
    for report in reports:
        for reason, count in report.skipped.items():
            rows.append((None, f"{report.name}: {format_count(count)} nicht übernommen ({reason})"))
    return tuple(rows)


class ReadableNames:
    """German names from the pipeline (mapping.py); technical names as fallback."""

    def __init__(self, layer=None, field=None, target=None):
        self._layer, self._field, self._target = layer, field, target

    @staticmethod
    def _call(function, value):
        if function is None or value is None:
            return value
        try:
            return function(value) or value
        except Exception:  # a missing name must not break the step
            return value

    def layer(self, layer_id):
        return self._call(self._layer, layer_id)

    def field(self, field):
        return self._call(self._field, field)

    def target(self, field):
        return self._call(self._target, field)


def readable_names():
    try:
        from .mapping import readable_field, readable_layer, readable_target_field
    except ImportError:
        return ReadableNames()
    return ReadableNames(readable_layer, readable_field, readable_target_field)


MORE_LABEL = "Mehr erfahren ▸"
LESS_LABEL = "Weniger ▾"
_ABBREVIATIONS = ("z. B", "d. h", "u. a", "z. T", "ca", "bzw", "Nr", "evtl", "ggf", "usw", "inkl")


def split_summary(message, details=None):
    """Short text for a hint plus the rest for 'Mehr erfahren' (W13).

    With ``details`` from the pipeline (G6) the message is the short text.
    Until then the first sentence is the summary and the rest goes below
    'Mehr erfahren'; abbreviations like 'z. B.' do not end a sentence."""
    text = (message or "").strip()
    if details:
        return text, str(details).strip()
    for match in re.finditer(r"[.!?]\s+(?=[A-ZÄÖÜ„\"(])", text):
        before = text[:match.start()]
        last_word = before.split()[-1].lstrip("(„\"'") if before.split() else ""
        # 'z.' of 'z. B.' (one letter) or a known abbreviation: no sentence end
        if len(last_word) <= 1 or before.endswith(_ABBREVIATIONS):
            continue
        return text[:match.start() + 1], text[match.end():].strip()
    return text, ""


def mapping_detail_text(source_field, examples):
    """Small line below a mapping row: examples from the data and the column."""
    shown = [f"„{example}“" for example in tuple(examples or ())[:2] if example not in (None, "")]
    prefix = f"z. B. {', '.join(shown)} · " if shown else ""
    return f"{prefix}Spalte {source_field}"


def count_text(count, singular, plural):
    """'1 Gruppe', '645 Gruppen', '1 675 Objekte'."""
    return f"{format_count(count)} {singular if count == 1 else plural}"


def duplicate_title_text(layer_name, group_count, record_count):
    """Card title in step 6, e.g. 'Gebäude: 645 Gruppen mit 1 675 Objekten'."""
    return (
        f"{layer_name}: {count_text(group_count, 'Gruppe', 'Gruppen')} mit "
        f"{count_text(record_count, 'Objekt', 'Objekten')}"
    )


def more_groups_text(count):
    """'… und 1 weitere Gruppe' / '… und 642 weitere Gruppen'."""
    return f"… und {count_text(count, 'weitere Gruppe', 'weitere Gruppen')}"


def merge_hint_text(removable):
    """What 'Zusammenführen' removes in one layer."""
    verb = "wird" if removable == 1 else "werden"
    return (
        f"Je Gruppe bleibt das erste Objekt, "
        f"{count_text(removable, 'Objekt', 'Objekte')} {verb} entfernt."
    )


def cross_layer_warning_text(count):
    """Hint for groups whose objects lie in different result layers."""
    verb = "liegt" if count == 1 else "liegen"
    return (
        f"Achtung: {count_text(count, 'Gruppe', 'Gruppen')} {verb} in verschiedenen "
        "Ergebnis-Layern (z. B. einmal als Straße, einmal als Weg). Beim "
        "Zusammenführen bleibt nur das erste Objekt – das andere fehlt dann in "
        "seiner Kategorie."
    )


def duplicates_applied_text(removed):
    """Feedback after step 6."""
    if removed == 0:
        return "Entscheidung übernommen: Alle Objekte bleiben erhalten."
    return (
        f"Entscheidung übernommen: {count_text(removed, 'Objekt', 'Objekte')} "
        "durch Zusammenführen entfernt."
    )
INDENT_PX = 22
MIN_CONTENT_WIDTH = 300
MESSAGE_MAX_HEIGHT = 140


def format_megabytes(size_bytes):
    """File size in MB with a German decimal comma, e.g. '350,2 MB'."""
    text = f"{size_bytes / (1024 * 1024):,.1f}"
    return text.replace(",", " ").replace(".", ",") + " MB"


def file_summary_text(name, folder, size_bytes):
    """Feedback after choosing a file: name, size and (shortened) folder."""
    return f"{name} – {format_megabytes(size_bytes)}\nOrdner: {shorten_middle(str(folder))}"


def shorten_middle(text, max_chars=40):
    """Shorten a long path in the middle, e.g. 'C:\\Users\\…\\Daten'."""
    if len(text) <= max_chars:
        return text
    keep = max_chars - 1
    head = keep // 2
    return text[:head] + "…" + text[len(text) - (keep - head):]


def import_error_text(file_name, error, full_path=None):
    """Readable German message when the pipeline cannot read a file.

    The full local path is replaced by the file name, so the message stays
    short and does not show the user's folder structure.
    """
    reason = error_text(error)
    if full_path:
        reason = reason.replace(str(full_path), file_name)
    return (
        f"Die Datei „{file_name}“ konnte nicht geladen werden.\n"
        f"Grund (Datenpipeline): {reason}\n"
        "Bitte prüfen, ob es eine gültige GeoPackage-Datei (.gpkg) ist, oder eine "
        "andere Datei wählen."
    )


def pipeline_reports_progress(importer):
    """True if ``import_file`` accepts a ``progress`` callback (fraction 0..1).

    The current pipeline runs in one piece; once it offers this parameter the
    busy bar shows the real progress without further UI changes.
    """
    import inspect

    try:
        return "progress" in inspect.signature(importer.import_file).parameters
    except (TypeError, ValueError):
        return False


class ImportCanceled(Exception):
    """The user stopped loading with 'Laden abbrechen'."""


CANCELED_MESSAGE = (
    "Das Laden wurde abgebrochen. Du kannst eine andere Datei wählen oder es "
    "erneut versuchen."
)
CANCELING_TEXT = "Wird abgebrochen …"


def cancel_aware_progress(is_canceled, report):
    """Progress callback for the pipeline that also stops it when canceled.

    The pipeline calls it regularly; if the user pressed 'Laden abbrechen',
    it raises ``ImportCanceled`` there, so loading stops at once without any
    change in the pipeline.
    """
    def progress(fraction):
        if is_canceled():
            raise ImportCanceled()
        report(fraction * 100)
    return progress


def busy_label_text(text, percent):
    """Text above the busy bar, with the real progress when it is known."""
    if percent is None:
        return text
    return f"{text} {int(percent)} %"


def choice_label(text, opened):
    """Text of a choice button with an arrow that shows whether it is open."""
    return f"{ARROW_OPEN if opened else ARROW_CLOSED}  {text}"


def make_texts_selectable(widget):
    """Let the user select and copy every text label inside ``widget``.

    Selectable labels also get Qt's context menu with "Kopieren" and
    "Alles auswählen".
    """
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtWidgets import QLabel

    labels = widget.findChildren(QLabel)
    if isinstance(widget, QLabel):
        labels.append(widget)
    for label in labels:
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )

LOG_TAG = "Urban Analysis"


def progress_text(index):
    """Return the overall progress label for the page at ``index``.

    A no-break space keeps the dash with the number, so a narrow panel never
    shows the dash alone on a line.
    """
    return f"{step_counter_text(index)} – {MVP_UI_STEPS[index]}"


def step_counter_text(index):
    """Small line above the step heading, e.g. 'Schritt 5 von 9'."""
    return f"Schritt {index + 1} von {len(MVP_UI_STEPS)}"


def error_text(error):
    """Return the readable message of an exception (KeyError adds quotes)."""
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)


def unexpected_error_text(context, error):
    """Describe an unexpected program error for the user."""
    return (
        f"Unerwarteter Fehler bei „{context}“: {type(error).__name__}: "
        f"{error_text(error)}\n"
        "Das ist vermutlich ein Programmfehler und nicht deine Eingabe. Die "
        "vollständige Fehlerbeschreibung steht in QGIS unter Ansicht → "
        f"Bedienfelder → Protokollmeldungen, Reiter „{LOG_TAG}“."
    )


def report_unexpected_error(plugin, context, error):
    """Log the full traceback and show a clear message in the QGIS message bar."""
    import traceback

    from qgis.core import Qgis, QgsMessageLog

    text = unexpected_error_text(context, error)
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    QgsMessageLog.logMessage(f"{text}\n\n{details}", LOG_TAG, Qgis.MessageLevel.Critical)
    plugin.iface.messageBar().pushCritical(LOG_TAG, text.replace("\n", " "))
    return text


def _clear_layout(layout):
    """Remove all widgets from a page layout before it is rebuilt."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()  # hide at once; deletion happens later in the event loop
            widget.deleteLater()


def set_dock_visible(plugin, visible):
    """Create the side panel on first use and show or hide it."""
    from qgis.PyQt.QtCore import Qt

    if plugin.dock is None:
        if not visible:
            return None
        plugin.dock = _create_dock(plugin)
        plugin.iface.addDockWidget(Qt.RightDockWidgetArea, plugin.dock)
        plugin.dock.visibilityChanged.connect(plugin._on_dock_visibility_changed)
    plugin.dock.setVisible(visible)
    if visible:
        plugin.dock.raise_()
    return plugin.dock


def _create_dock(plugin):
    """Build the side panel with progress, pages and one main action per page."""
    from qgis.core import (
        Qgis,
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsFeedback,
        QgsGeometry,
        QgsProject,
        QgsSettings,
        QgsTask,
    )
    from qgis.gui import (
        QgsColorButton,
        QgsDockWidget,
        QgsMapLayerComboBox,
        QgsProjectionSelectionWidget,
    )
    from qgis.PyQt.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, QTimer

    from .ui.widgets.pixel_button import PixelButton
    from .ui.widgets.pixel_scene import PixelScene
    from .ui.widgets.classic_header import ClassicHeader

    class _BothHeaders:
        """Sends every header message (step, loading, done …) to both looks,
        so switching the style never loses the current state."""

        def __init__(self, *views):
            self._views = views

        def __getattr__(self, name):
            def call(*args, **kwargs):
                for view in self._views:
                    getattr(view, name)(*args, **kwargs)
            return call
    from .ui.widgets.icons import (
        TITLE_ICON_PX, icon_size, layer_icon, palette_icon, title_icon, with_icon,
    )
    from qgis.PyQt.QtCore import QPoint, QSize
    from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
    from .ui import style as ui_style
    from qgis.PyQt.QtWidgets import QMenu

    try:  # Qt6: actions live in QtGui
        from qgis.PyQt.QtGui import QAction, QActionGroup
    except ImportError:  # Qt5
        from qgis.PyQt.QtWidgets import QAction, QActionGroup
    from qgis.PyQt.QtWidgets import (
        QWIDGETSIZE_MAX,
        QAbstractItemView,
        QAbstractSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTreeWidget,
        QTreeWidgetItem,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    class Page:
        """One step of the guidance: widgets, optional builder and validator."""

        def __init__(self, builder=None, validator=None, rebuild=False, on_show=None):
            self.widget = QWidget()
            self.layout = QVBoxLayout(self.widget)
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.builder = builder
            self.validator = validator
            self.rebuild = rebuild
            self.on_show = on_show
            self.widgets = {}

        def build(self):
            _clear_layout(self.layout)
            self.widgets = {}
            self.builder(self)
            guard_wheel(self.widget)

    class WheelGuard(QObject):
        """The mouse wheel never changes a choice list or number field by
        accident: it scrolls the panel instead.  Values change only after a
        click (list opens) or typing."""

        def eventFilter(self, watched, event):
            if event.type() != QEvent.Wheel:
                return False
            if isinstance(watched, QAbstractSpinBox) and watched.hasFocus():
                return False  # typing in it: wheel may change the number
            parent = watched.parentWidget()
            while parent is not None and not isinstance(parent, QScrollArea):
                parent = parent.parentWidget()
            if parent is not None:
                bar = parent.verticalScrollBar()
                steps = event.angleDelta().y() / 120
                bar.setValue(bar.value() - round(steps * bar.singleStep() * 3))
            return True  # never passed on to the list / number field

    wheel_guard = WheelGuard()

    def guard_wheel(widget):
        for child in widget.findChildren(QComboBox) + widget.findChildren(QAbstractSpinBox):
            child.setFocusPolicy(Qt.StrongFocus)  # no focus by merely hovering
            child.installEventFilter(wheel_guard)

    class GuidedDock(QgsDockWidget):
        """Side panel that walks through the eight MVP steps."""

        def __init__(self):
            super().__init__("Urban Analysis", plugin.iface.mainWindow())
            self.setObjectName(DOCK_OBJECT_NAME)
            self.pages = []
            self.current = 0
            # Values confirmed in steps 1-2; step 3 (W4) passes them to the pipeline.
            self.settings = {}
            self.draw_tool = None
            self.previous_map_tool = None
            self.import_task = None  # running background import (step 3)
            self.closing = False
            self.next_message = None  # info shown after the next page change
            self.all_done = False  # fish at the end after "Verarbeitung starten"
            self.last_reports = None  # result of the last processing run (step 9)
            self.last_saved = []  # files written by that run: [(kind, path)]
            self.output_paths = {}  # save locations chosen in step 8 (W8b)
            self.output_confirmed = set()  # kinds picked in the save dialog
            self.output_draft = {}  # step-8 input not yet confirmed
            self.input_paths = set()  # loaded input files: never an output
            self.last_run_signature = None  # what step 9 produced last time
            self.last_group_name = None
            self.step9_tab = "output"  # open area of the last step
            self.last_access_lines = []  # result of the last accessibility run
            self.download_feedback = None  # QgsFeedback of a running OSM download

            # The whole plugin shares one style (theme.py), with the bundled
            # fonts if present (otherwise the system monospace font).
            # Look chosen with the gear button (saved in the QGIS settings;
            # 'classic' = like QGIS is the default).
            fonts = load_fonts()
            self.fonts = fonts
            self.setStyleSheet(panel_stylesheet(fonts, ui_style.load()))
            # Slim title bar in sky colour: the title itself stands in the
            # scene's sky; only "Lösen" and "Schließen" remain here.
            self.setTitleBarWidget(self._title_bar())
            # The scene fills the full width at the top (no margins); all
            # other content gets normal margins below it.
            body = QWidget()
            outer = QVBoxLayout(body)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(9, 6, 9, 9)

            # Header: small "Schritt x von 9" next to "Zurücksetzen", below it
            # the step name as heading over the full width.
            self.step_counter = QLabel()
            set_role(self.step_counter, "hint")
            self.step_label = QLabel()
            self.step_label.setWordWrap(True)
            set_role(self.step_label, "heading")
            self.reset_button = PixelButton("↺ Zurücksetzen", "secondary")
            self.reset_button.setToolTip(RESET_TOOLTIP)
            self.reset_button.clicked.connect(self.ask_reset)
            header = QVBoxLayout()
            header.setSpacing(0)
            counter_row = QHBoxLayout()
            counter_row.addWidget(self.step_counter, 1)
            counter_row.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignVCenter)
            header.addLayout(counter_row)
            header.addWidget(self.step_label)

            # Header with the overall and the loading progress, in two looks:
            # pixel style = fishing scene, classic style = step points and a
            # smooth bar.  Both get every message; only one is visible.
            self.pixel_scene = PixelScene(total_steps=len(MVP_UI_STEPS), title="Urban Analysis")
            self.pixel_scene.set_title_font(fonts["heading"])
            self.classic_header = ClassicHeader(total_steps=len(MVP_UI_STEPS), title="Urban Analysis")
            self.scene = _BothHeaders(self.pixel_scene, self.classic_header)
            self.set_animations(ui_style.animations_enabled())

            # Text line for long steps ("Lade … 40 %") below the scene.
            self.busy_label = QLabel()
            self.busy_label.setWordWrap(True)
            set_role(self.busy_label, "status")
            self.busy_text = ""
            self.busy_label.hide()
            # 'Laden abbrechen': only visible while data is loading.
            self.cancel_requested = False
            self.cancel_button = PixelButton("Laden abbrechen", "secondary")
            self.cancel_button.setToolTip("Das Laden der Datei stoppen. Es wird nichts übernommen.")
            self.cancel_button.clicked.connect(self.cancel_import)
            self.cancel_button.hide()
            # text over the full width (long file names), the button below it
            busy_row = QVBoxLayout()
            busy_row.setSpacing(2)
            busy_row.addWidget(self.busy_label)
            cancel_row = QHBoxLayout()
            cancel_row.addStretch()
            cancel_row.addWidget(self.cancel_button)
            busy_row.addLayout(cancel_row)

            # Only the current page is visible. A plain box layout (instead of
            # QStackedWidget) gives wrapped texts their full height.
            self.stack = QWidget()
            self.stack_layout = QVBoxLayout(self.stack)
            self.stack_layout.setContentsMargins(8, 8, 8, 8)
            # A stretch (not AlignTop) keeps pages at the top; AlignTop would make
            # Qt ignore the height of wrapped texts and cut them off.
            self.stack_layout.addStretch(1)
            # Pages take the panel width, so long texts wrap instead of being cut.
            # Below MIN_CONTENT_WIDTH a horizontal scroll bar appears instead.
            self.stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.stack.setMinimumWidth(MIN_CONTENT_WIDTH)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setWidget(self.stack)
            self.scroll = scroll
            self.stack.installEventFilter(self)

            # Messages get their own small scroll area, so long texts (e.g. an
            # unexpected error) stay readable without pushing the buttons away.
            self.message = QLabel()
            self.message.setWordWrap(True)
            self.message.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.message_scroll = QScrollArea()
            self.message_scroll.setWidgetResizable(True)
            self.message_scroll.setWidget(self.message)
            self.message_scroll.setMaximumHeight(MESSAGE_MAX_HEIGHT)
            self.message_scroll.hide()

            # Footer buttons are drawn as pixel buttons (ui/widgets).
            self.back_button = PixelButton("Zurück", "secondary")
            self.back_button.clicked.connect(self.go_back)
            self.primary_button = PixelButton("", "primary")
            self.primary_button.setObjectName("uaPrimaryButton")
            self.primary_button.clicked.connect(self.run_primary_action)
            buttons = QHBoxLayout()
            buttons.addWidget(self.back_button)
            buttons.addStretch()
            buttons.addWidget(self.primary_button)

            outer.addWidget(self.pixel_scene)
            outer.addWidget(self.classic_header)
            self._show_header(ui_style.current())
            outer.addWidget(content, 1)
            layout.addLayout(header)
            layout.addLayout(busy_row)
            layout.addWidget(scroll, 1)
            layout.addWidget(self.message_scroll)
            layout.addLayout(buttons)
            make_texts_selectable(body)
            self.setWidget(body)

        def _title_bar(self):
            """Slim bar in the panel colour with 'Lösen' and 'Schließen'.

            Dragging the bar still moves or undocks the panel (Qt handles that
            for custom title bars)."""
            bar = QWidget()
            bar.setObjectName("uaTitleBar")
            row = QHBoxLayout(bar)
            row.setContentsMargins(6, 2, 4, 0)
            row.addStretch()
            row.addWidget(self._style_button())
            for kind, tip, action in (
                ("float", "Lösen / andocken", lambda: self.setFloating(not self.isFloating())),
                ("close", "Schließen", self.close),
            ):
                button = QToolButton()
                # own icons: same line weight as the palette next to them
                button.setIcon(title_icon(kind))
                button.setIconSize(QSize(TITLE_ICON_PX, TITLE_ICON_PX))
                button.setToolTip(tip)
                button.setAutoRaise(True)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(action)
                row.addWidget(button)
            return bar

        def _style_button(self):
            """Palette button: choose 'Klassisch (QGIS-Stil)' or 'Pixel-Stil'."""
            button = QToolButton()
            button.setIcon(palette_icon())
            button.setIconSize(QSize(TITLE_ICON_PX, TITLE_ICON_PX))
            button.setToolTip(STYLE_BUTTON_TOOLTIP)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(button)
            group = QActionGroup(menu)
            group.setExclusive(True)
            self.style_actions = {}
            for key, label in ui_style.STYLE_LABELS.items():
                action = QAction(label, menu)
                action.setCheckable(True)
                action.setChecked(key == ui_style.current())
                action.triggered.connect(lambda _checked=False, key=key: self.apply_style(key))
                group.addAction(action)
                menu.addAction(action)
                self.style_actions[key] = action
            menu.addSeparator()
            calm = QAction(ui_style.REDUCE_ANIMATIONS_LABEL, menu)
            calm.setCheckable(True)
            calm.setChecked(not ui_style.animations_enabled())
            calm.toggled.connect(lambda on: self.set_animations(not on, remember=True))
            menu.addAction(calm)
            self.calm_action = calm
            button.setMenu(menu)
            self.style_menu = menu
            return button

        def set_animations(self, enabled, remember=False):
            """'Animationen reduzieren': no ambient motion, no particles, no
            sliding panels.  Progress and press feedback stay visible."""
            if remember:
                ui_style.save_animations(enabled)
            PixelButton.animations_enabled = bool(enabled)
            self.scene.set_animations(enabled)

        def apply_style(self, style):
            """Switch the look at once and remember it for the next start."""
            try:
                style = ui_style.save(style)
                for key, action in getattr(self, "style_actions", {}).items():
                    action.setChecked(key == style)
                self.setStyleSheet(panel_stylesheet(self.fonts, style))
                self._show_header(style)
                for button in self.findChildren(PixelButton):
                    button.style_changed()
                plugin.update_toolbar_icon()
                page = self.pages[self.current] if self.pages else None
                if page is not None and page.rebuild and plugin.workflow is not None:
                    # pages with layer icons are drawn again in the new look
                    self._rebuild_current_page()
                QTimer.singleShot(0, self.fit_wrapped_labels)
            except Exception as error:  # show every program error visibly
                self.show_unexpected_error("Darstellung wechseln", error)

        def _show_header(self, style):
            self.pixel_scene.setVisible(style == "pixel")
            self.classic_header.setVisible(style == "classic")

        def _rebuild_current_page(self):
            """Build the current page again (keeps the step, messages and the
            'Fertig' view of step 9)."""
            page = self.pages[self.current]
            page.build()
            make_texts_selectable(page.widget)
            page.layout.activate()
            self.stack.updateGeometry()

        def add_page(self, builder=None, validator=None, rebuild=False, on_show=None):
            page = Page(builder, validator, rebuild, on_show)
            if builder is not None and not rebuild:
                page.build()
            self.pages.append(page)
            page.widget.hide()
            self.stack_layout.insertWidget(self.stack_layout.count() - 1, page.widget)
            return page

        def show_page(self, index):
            self.stop_drawing()
            self.last_reports = None  # the last step starts with the overview again
            self.last_saved = []
            last = index == len(self.pages) - 1
            if last:
                self.step9_tab = "output"  # 'Ausgabe' is open first
            page = self.pages[index]
            if page.rebuild:
                page.build()
            make_texts_selectable(page.widget)
            if page.on_show is not None:
                page.on_show(page)
            self.current = index
            self.all_done = False
            self.scroll.verticalScrollBar().setValue(0)
            self.scroll.horizontalScrollBar().setValue(0)
            for page_index, other in enumerate(self.pages):
                other.widget.setVisible(page_index == index)
            # Recalculate heights now that the page is visible, so wrapped
            # texts in freshly built cards get their full height.
            page.layout.activate()
            self.stack_layout.activate()
            self.stack.updateGeometry()
            QTimer.singleShot(0, self.fit_wrapped_labels)
            self.step_counter.setText(step_counter_text(index))
            self.step_label.setText(MVP_UI_STEPS[index])
            self.step_label.setToolTip(progress_text(index))
            self.scene.setToolTip(progress_text(index))
            self.update_progress()
            # a page may name its main action itself (step 3: folder first)
            action_text = page.widgets.get("action_text")
            self.primary_button.setText(action_text() if action_text else PAGE_ACTIONS[index])
            # last step: every area has its own button
            self.primary_button.setVisible(not last)
            self.back_button.setEnabled(index > 0)
            self.clear_message()
            if self.next_message:
                text, self.next_message = self.next_message, None
                self.show_message(text, kind="info")

        def run_primary_action(self):
            self.clear_message()
            try:
                page = self.pages[self.current]
                if page.validator is not None and not page.validator(page):
                    return
                if self.current + 1 < len(self.pages):
                    self.show_page(self.current + 1)
            except Exception as error:  # show every program error visibly
                self.show_unexpected_error(PAGE_ACTIONS[self.current], error)

        def go_back(self):
            try:
                if self.current > 0:
                    self.show_page(self.current - 1)
            except Exception as error:  # show every program error visibly
                self.show_unexpected_error("Zurück", error)

        def show_unexpected_error(self, context, error):
            self.show_message(report_unexpected_error(plugin, context, error))

        def show_message(self, text, kind="error"):
            set_role(self.message, kind)
            self.message.setText(text)
            self.message_scroll.show()
            # Fit the box to the text; longer texts scroll inside the box.
            width = max(self.message_scroll.viewport().width(), 200)
            height = self.message.heightForWidth(width)
            if height <= 0:
                height = self.message.sizeHint().height()
            frame = 2 * self.message_scroll.frameWidth()
            self.message_scroll.setFixedHeight(min(height + frame + 4, MESSAGE_MAX_HEIGHT))

        def clear_message(self):
            self.message.clear()
            self.message_scroll.hide()

        def update_progress(self):
            """The step fish swims to the current step (after a successful
            processing run to the last one, with all step marks lit)."""
            self.scene.set_step(len(MVP_UI_STEPS) if self.all_done else self.current)

        def mark_all_done(self):
            """Result layers created: fish to the last step, then a happy jump."""
            self.all_done = True
            self.update_progress()
            self.scene.celebrate()

        def fit_wrapped_labels(self):
            """Give every wrapped text its full height at the current width.

            Qt underestimates the height of wrapped labels inside nested cards;
            measuring them after the layout has its width avoids cut-off lines.
            """
            # The step heading wraps in narrow panels, too.
            heading_height = self.step_label.heightForWidth(self.step_label.width())
            if heading_height > 0:
                self.step_label.setMinimumHeight(heading_height)
            if not self.pages:
                return
            page = self.pages[self.current]
            changed = False
            for label in page.widget.findChildren(QLabel):
                if not label.wordWrap() or not label.isVisibleTo(page.widget):
                    continue
                height = label.heightForWidth(label.width())
                if height > 0 and label.minimumHeight() != height:
                    label.setMinimumHeight(height)
                    changed = True
            if changed:
                page.layout.activate()
                self.stack.updateGeometry()

        def eventFilter(self, watched, event):
            if watched is self.stack and event.type() == QEvent.Resize:
                QTimer.singleShot(0, self.fit_wrapped_labels)
            return super().eventFilter(watched, event)

        def set_busy(self, text):
            """The rabbit casts; lock the panel while a step runs."""
            self.busy_text = text
            self.busy_label.setText(busy_label_text(text, None))
            self.busy_label.show()
            self.cancel_requested = False
            self.cancel_button.setEnabled(True)
            self.cancel_button.show()
            self.scene.start_loading()
            self.primary_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            self.stack.setEnabled(False)

        def set_busy_progress(self, percent):
            """Real progress from the background task (0-100): the float moves."""
            if self.cancel_requested:
                return  # keep showing 'Wird abgebrochen …'
            self.scene.set_progress(percent)
            self.busy_label.setText(busy_label_text(self.busy_text, percent))

        def cancel_import(self):
            """'Laden abbrechen': ask the background task to stop."""
            if self.import_task is None:
                return
            self.cancel_requested = True
            self.cancel_button.setEnabled(False)
            self.busy_label.setText(CANCELING_TEXT)
            if self.download_feedback is not None:
                self.download_feedback.cancel()  # stops a running OSM request at once
            self.import_task.cancel()

        def clear_busy(self, outcome="cancel"):
            """Unlock the panel.  ``outcome``: 'done' (line breaks, rabbit
            casts again), 'error' (float twitches, '…' bubble) or 'cancel'."""
            {"done": self.scene.finish, "error": self.scene.fail}.get(outcome, self.scene.cancel)()
            self.busy_label.hide()
            self.cancel_button.hide()
            self.cancel_requested = False
            self.stack.setEnabled(True)
            self.primary_button.setEnabled(True)
            self.back_button.setEnabled(self.current > 0)
            self.reset_button.setEnabled(True)

        def ask_reset(self):
            """Ask, then reset the whole plugin to step 1 without data."""
            answer = QMessageBox.question(
                self,
                "Urban Analysis zurücksetzen",
                RESET_QUESTION,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self.reset()

        def reset(self):
            try:
                if self.import_task is not None:
                    self.import_task.cancel()
                    self.import_task = None
                self.clear_busy()
                self.stop_drawing()
                plugin.reset_workflow()
                self.settings = {}
                self.output_paths = {}
                self.output_confirmed = set()
                self.output_draft = {}
                self.input_paths = set()
                self.next_message = None
                self.step9_tab = "output"
                self.last_access_lines = []
                self.last_group_name = None
                for page in self.pages:
                    if page.rebuild:
                        # Pages 4-9 need loaded data; they are rebuilt when reached.
                        _clear_layout(page.layout)
                        page.widgets = {}
                    elif page.builder is not None:
                        page.build()
                self.show_page(0)
                self.show_message(RESET_DONE_MESSAGE, kind="info")
            except Exception as error:  # show every program error visibly
                self.show_unexpected_error("Zurücksetzen", error)

        def start_drawing(self, on_finished, on_canceled):
            """Activate the polygon drawing tool in the QGIS map."""
            canvas = plugin.iface.mapCanvas()
            self.stop_drawing()

            def finished(geometry):
                self.stop_drawing()
                on_finished(geometry, canvas.mapSettings().destinationCrs())

            def canceled(message):
                self.stop_drawing()
                on_canceled(message)

            self.previous_map_tool = canvas.mapTool()
            self.draw_tool = create_polygon_draw_tool(canvas, finished, canceled)
            canvas.setMapTool(self.draw_tool)
            canvas.setFocus()

        def stop_drawing(self):
            """Deactivate the drawing tool and restore the previous map tool."""
            if self.draw_tool is None:
                return
            canvas = plugin.iface.mapCanvas()
            tool, self.draw_tool = self.draw_tool, None
            if canvas.mapTool() is tool:
                if self.previous_map_tool is not None:
                    canvas.setMapTool(self.previous_map_tool)
                else:
                    canvas.unsetMapTool(tool)
            self.previous_map_tool = None

        def cleanup(self):
            """Called when the plugin is unloaded."""
            self.closing = True
            if self.import_task is not None:
                self.import_task.cancel()
                self.import_task = None
            self.scene.stop()
            self.stop_drawing()

    dock = GuidedDock()

    def workflow():
        return plugin._require_workflow()

    def indented(*widgets):
        """Group sub-options below a choice, indented to show they belong to it."""
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(INDENT_PX, 0, 0, 4)
        for widget in widgets:
            box_layout.addWidget(widget)
        return box

    def reject(text):
        dock.show_message(text)
        return False

    # Pages 1-3 start from an existing workflow (console start) or from the
    # current QGIS project; after "Zurücksetzen" there is no workflow.
    def existing():
        return plugin.workflow.result if plugin.workflow is not None else None

    # 1 Projekt-CRS
    def build_crs(page):
        crs_widget = QgsProjectionSelectionWidget()
        crs_widget.setCrs(
            QgsCoordinateReferenceSystem(existing().project_crs)
            if existing()
            else QgsProject.instance().crs()
        )
        hint = QLabel(CRS_HINT)
        hint.setWordWrap(True)
        set_role(hint, "hint")
        page.layout.addWidget(QLabel(UI_LABELS["project_crs"]))
        page.layout.addWidget(crs_widget)
        page.layout.addWidget(hint)
        page.widgets["crs"] = crs_widget

    def validate_crs(page):
        crs = page.widgets["crs"].crs()
        if not crs.isValid():
            return reject("Bitte ein gültiges CRS wählen.")
        if not crs.authid():
            return reject(
                "Dieses CRS hat keine Kennung wie EPSG:25832 und kann nicht mit "
                "den Daten verglichen werden."
            )
        if crs.isGeographic():
            return reject(
                f"{crs.authid()} rechnet in Grad. Für den Puffer in Metern bitte ein "
                "metrisches CRS wählen, z. B. EPSG:25832."
            )
        project = QgsProject.instance()
        if project.crs().isValid() and project.crs() != crs:
            # different CRS in QGIS and plugin can cause display problems
            box = QMessageBox(dock)
            box.setWindowTitle("Koordinatensystem")
            box.setIcon(QMessageBox.Warning)
            box.setText(crs_mismatch_text(project.crs().authid(), crs.authid()))
            go_on = box.addButton("Fortfahren und Projekt umstellen", QMessageBox.AcceptRole)
            box.addButton("CRS noch ändern", QMessageBox.RejectRole)
            box.exec_() if hasattr(box, "exec_") else box.exec()
            if box.clickedButton() is not go_on:
                return False
            project.setCrs(crs)
        dock.settings["project_crs"] = crs.authid()
        return True

    # 2 Untersuchungsgebiet: existing polygon layer or a polygon drawn in the map
    def build_area(page):
        use_layer = QRadioButton("Vorhandener Layer")
        use_layer.setToolTip("Vorhandenen Polygon-Layer aus dem Projekt verwenden")
        use_drawing = QRadioButton("Neu zeichnen")
        use_drawing.setToolTip("Neues Polygon in der Karte zeichnen")
        use_layer.setChecked(True)

        layer_box = QgsMapLayerComboBox()
        layer_box.setFilters(Qgis.LayerFilter.PolygonLayer)
        layer_box.setSizeAdjustPolicy(layer_box.AdjustToMinimumContentsLengthWithIcon)
        layer_box.setMinimumContentsLength(12)
        selected_only = QCheckBox("Nur ausgewählte Objekte")
        no_layer_hint = QLabel(
            "Im Projekt gibt es noch keinen Polygon-Layer. Bitte einen Layer laden "
            "oder ein neues Polygon zeichnen."
        )
        no_layer_hint.setWordWrap(True)
        set_role(no_layer_hint, "hint")

        draw_button = QPushButton("Polygon zeichnen")
        draw_button.setToolTip("Polygon in der Karte zeichnen")
        set_role(draw_button, "secondary")
        draw_button.setCursor(Qt.PointingHandCursor)
        draw_hint = QLabel(DRAW_INSTRUCTIONS)
        draw_hint.setWordWrap(True)
        set_role(draw_hint, "hint")

        status = QLabel()
        status.setWordWrap(True)
        set_role(status, "hint")
        buffer_input = QDoubleSpinBox()
        buffer_input.setRange(0, 1000000)
        buffer_input.setValue(
            existing().buffer_meters if existing() else MVP_DEFAULT_BUFFER_METERS
        )

        page.layout.addWidget(QLabel(UI_LABELS["study_area"]))
        page.layout.addWidget(use_layer)
        page.layout.addWidget(indented(layer_box, selected_only, no_layer_hint))
        page.layout.addWidget(use_drawing)
        page.layout.addWidget(indented(draw_button, draw_hint))
        size = QLabel()  # E17: size of the download rectangle
        size.setWordWrap(True)
        set_role(size, "hint")
        size.hide()

        page.layout.addWidget(status)
        page.layout.addWidget(QLabel(UI_LABELS["buffer"]))
        page.layout.addWidget(buffer_input)
        page.layout.addWidget(size)
        page.widgets.update(size=size, download_km2=None)
        page.widgets.update(
            use_layer=use_layer,
            use_drawing=use_drawing,
            layer=layer_box,
            selected_only=selected_only,
            no_layer_hint=no_layer_hint,
            draw_button=draw_button,
            draw_hint=draw_hint,
            status=status,
            buffer=buffer_input,
            drawn_layer_id=None,
            watched_layer=None,
        )

        def refresh(*_args):
            drawing = use_drawing.isChecked()
            has_layers = layer_box.count() > 0
            layer_box.setEnabled(not drawing)
            selected_only.setEnabled(not drawing)
            no_layer_hint.setVisible(not drawing and not has_layers)
            draw_button.setEnabled(drawing)
            draw_hint.setVisible(drawing)
            watch_selection()
            update_area_status(page)

        def watch_selection():
            """Update the status when objects are (de)selected in the layer."""
            layer = layer_box.currentLayer()
            previous = page.widgets["watched_layer"]
            if previous is layer:
                return
            if previous is not None:
                try:
                    previous.selectionChanged.disconnect(refresh_status)
                except (RuntimeError, TypeError):
                    pass  # layer was already removed from the project
            if layer is not None:
                layer.selectionChanged.connect(refresh_status)
            page.widgets["watched_layer"] = layer

        def refresh_status(*_args):
            update_area_status(page)

        def drawing_finished(geometry, canvas_crs):
            try:
                layer = add_drawn_area_layer(geometry, canvas_crs)
            except StudyAreaError as error:
                dock.show_message(str(error))
                return
            page.widgets["drawn_layer_id"] = layer.id()
            dock.show_message(
                f"Polygon gezeichnet und als Layer „{layer.name()}“ ins Projekt gelegt.",
                kind="info",
            )
            update_area_status(page)

        def drawing_canceled(message):
            dock.show_message(message, kind="info")

        def start_drawing():
            dock.clear_message()
            dock.show_message(DRAW_INSTRUCTIONS, kind="info")
            dock.start_drawing(drawing_finished, drawing_canceled)

        use_layer.toggled.connect(refresh)
        layer_box.layerChanged.connect(refresh)
        selected_only.toggled.connect(refresh_status)
        buffer_input.valueChanged.connect(refresh_status)
        draw_button.clicked.connect(start_drawing)
        refresh()

    def target_crs():
        return crs_page.widgets["crs"].crs()

    def chosen_area(page):
        """Return (geometry, polygon_count) or raise StudyAreaError."""
        widgets = page.widgets
        if widgets["use_drawing"].isChecked():
            layer_id = widgets["drawn_layer_id"]
            layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
            if layer is None:
                raise StudyAreaError(
                    "Es ist noch kein Polygon gezeichnet. Bitte auf „Polygon "
                    "zeichnen“ klicken."
                )
            return study_area_from_layer(layer, target_crs(), selected_only=False)
        return study_area_from_layer(
            widgets["layer"].currentLayer(),
            target_crs(),
            selected_only=widgets["selected_only"].isChecked(),
        )

    def update_area_status(page):
        status = page.widgets["status"]
        size = page.widgets["size"]
        page.widgets["download_km2"] = None
        size.hide()
        try:
            geometry, count = chosen_area(page)
        except StudyAreaError as error:
            set_role(status, "hint")
            status.setText(str(error))
            return
        set_role(status, "status")
        status.setText(area_summary_text(count, geometry.area(), target_crs().authid()))
        if target_crs().mapUnits() != Qgis.DistanceUnit.Meters:
            return  # sizes in degrees make no sense; CRS hint is in step 1
        box = geometry.boundingBox()
        km2 = download_box_km2(box.xMinimum(), box.yMinimum(), box.xMaximum(),
                               box.yMaximum(), page.widgets["buffer"].value())
        page.widgets["download_km2"] = km2
        if is_large(km2):
            set_role(size, "warning")
            size.setText(download_size_text(km2) + "\n\n" + oversize_warning_text(km2))
        else:
            set_role(size, "hint")
            size.setText(download_size_text(km2))
        size.show()
        QTimer.singleShot(0, dock.fit_wrapped_labels)

    def validate_area(page):
        try:
            geometry, _count = chosen_area(page)
        except StudyAreaError as error:
            return reject(str(error))
        update_area_status(page)
        km2 = page.widgets["download_km2"]
        if km2 is not None and is_large(km2):
            answer = QMessageBox.question(
                dock, "Großes Gebiet", oversize_question_text(km2),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return False
        project_crs = target_crs().authid()
        study_area_wkt = geometry.asWkt()
        buffer_meters = page.widgets["buffer"].value()
        if plugin.workflow is not None:
            try:
                plugin.workflow.configure_project(
                    project_crs=project_crs,
                    study_area_wkt=study_area_wkt,
                    buffer_meters=buffer_meters,
                )
            except ValueError as error:
                return reject(str(error))
        dock.settings.update(
            project_crs=project_crs,
            study_area_wkt=study_area_wkt,
            buffer_meters=buffer_meters,
            download_km2=km2,  # step 3 blocks downloads above the limit (E13)
        )
        return True

    # Choice button with a panel that opens below it (used in step 4).
    def choice_with_panel(page, key, text):
        button = QPushButton(choice_label(text, False))
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        set_role(button, "choice")
        panel = QFrame()
        set_role(panel, "panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 8, 12, 12)
        panel.setMaximumHeight(0)
        panel.hide()
        # Button and panel sit in one box without spacing, so the opened
        # panel hangs directly (flush) below its button.
        group = QWidget()
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(0)
        group_layout.addWidget(button)
        group_layout.addWidget(panel)
        page.layout.addWidget(group)
        page.widgets[f"{key}_button"] = button
        page.widgets[f"{key}_panel"] = panel

        def toggled(checked):
            button.setText(choice_label(text, checked))
            animate_panel(page, key, panel, checked)

        button.toggled.connect(toggled)
        return panel_layout

    def animate_panel(page, key, panel, opening):
        """Open or close a panel with a short height animation."""
        previous = page.widgets.get(f"{key}_animation")
        if previous is not None:
            previous.stop()
        if opening:
            panel.show()
            panel.setMaximumHeight(QWIDGETSIZE_MAX)
            panel.adjustSize()
            end = panel.sizeHint().height()
            if panel.hasHeightForWidth() and panel.width() > 0:
                end = max(end, panel.heightForWidth(panel.width()))
            start = 0
        else:
            start, end = panel.height(), 0
        animation = QPropertyAnimation(panel, b"maximumHeight", panel)
        animation.setDuration(PANEL_ANIMATION_MS if PixelButton.animations_enabled else 0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(start)
        animation.setEndValue(end)

        def done():
            if opening:
                panel.setMaximumHeight(QWIDGETSIZE_MAX)  # may grow (file info)
            else:
                panel.hide()

        animation.finished.connect(done)
        page.widgets[f"{key}_animation"] = animation
        animation.start()

    def hint_label(text):
        label = QLabel(text)
        label.setWordWrap(True)
        set_role(label, "hint")
        return label

    def source_choice(page, key, text, *details):
        """Check box for one source; its details show only while ticked."""
        box = QCheckBox(text)
        panel = indented(*details)
        panel.hide()
        page.layout.addWidget(box)
        page.layout.addWidget(panel)

        def toggled(on):
            panel.setVisible(on)
            dock.clear_message()
            QTimer.singleShot(0, dock.fit_wrapped_labels)

        box.toggled.connect(toggled)
        page.widgets[key] = box

    def build_data(page):
        question = QLabel("Woher sollen die Daten kommen? Mehrere Quellen sind möglich.")
        question.setWordWrap(True)
        page.layout.addWidget(question)

        source_choice(page, "osm", SOURCE_OSM_LABEL, hint_label(SOURCE_OSM_HINT),
                      hint_label(DOWNLOAD_FOLDER_HINT))

        state = QComboBox()
        state.addItem(CHOOSE_STATE_ITEM)
        state.addItems(GERMAN_STATES)
        source_choice(page, "alkis", SOURCE_ALKIS_LABEL, hint_label(SOURCE_ALKIS_HINT), state)

        choose_button = QPushButton("Datei wählen …")
        set_role(choose_button, "secondary")
        choose_button.setCursor(Qt.PointingHandCursor)
        file_info = hint_label("Noch keine Datei gewählt.")
        source_choice(page, "own", SOURCE_OWN_LABEL, hint_label(LOCAL_DATA_HINT),
                      choose_button, file_info)

        page.widgets.update(
            state=state, choose_button=choose_button, file_info=file_info, path=None,
            download_folder=None,
        )
        choose_button.clicked.connect(lambda: choose_file(page))

        def action_text():
            """'Speicherort wählen' first for downloads, then 'Daten laden'."""
            if page.widgets["osm"].isChecked() and page.widgets.get("download_folder") is None:
                return CHOOSE_FOLDER_ACTION
            return UI_LABELS["load_data"]

        def refresh_action(*_args):
            if dock.pages and dock.pages[dock.current] is page:
                dock.primary_button.setText(action_text())

        page.widgets["action_text"] = action_text
        page.widgets["osm"].toggled.connect(refresh_action)

    def choose_file(page):
        """Open the system file dialog and remember the chosen GeoPackage."""
        settings = QgsSettings()
        start = settings.value(LAST_FOLDER_SETTING, str(Path.home()))
        path, _filter = QFileDialog.getOpenFileName(
            dock, FILE_DIALOG_TITLE, str(start), FILE_DIALOG_FILTER
        )
        if not path:
            return  # dialog closed without a choice; keep the previous file
        chosen = Path(path)
        settings.setValue(LAST_FOLDER_SETTING, str(chosen.parent))
        page.widgets["path"] = chosen
        info = page.widgets["file_info"]
        info.setText(file_summary_text(chosen.name, chosen.parent, chosen.stat().st_size))
        info.setToolTip(str(chosen))
        set_role(info, "status")
        dock.clear_message()

    def validate_data(page):
        widgets = page.widgets
        state = widgets["state"]
        problem = source_choice_problem(
            osm=widgets["osm"].isChecked(),
            alkis=widgets["alkis"].isChecked(),
            state=state.currentText() if state.currentIndex() > 0 else None,
            own=widgets["own"].isChecked(),
            path=widgets["path"],
            download_km2=dock.settings.get("download_km2"),
            has_data=plugin.workflow is not None,
        )
        if problem is not None:
            kind, text = problem
            dock.show_message(text, kind=kind)
            return False
        if not {"project_crs", "study_area_wkt", "buffer_meters"} <= set(dock.settings):
            if widgets["osm"].isChecked() or widgets["own"].isChecked():
                return reject(MISSING_AREA_MESSAGE)
        if widgets["osm"].isChecked():
            if widgets.get("download_folder") is None:
                # first click: only choose the folder, the button then says "Daten laden"
                folder = QFileDialog.getExistingDirectory(
                    dock, DOWNLOAD_FOLDER_TITLE, str(download_folder()))
                if not folder:
                    dock.show_message(DOWNLOAD_NO_FOLDER_MESSAGE, kind="info")
                    return False
                QgsSettings().setValue(LAST_DOWNLOAD_FOLDER_SETTING, folder)
                widgets["download_folder"] = folder
                dock.primary_button.setText(UI_LABELS["load_data"])
                dock.show_message(folder_chosen_text(folder), kind="info")
                return False
            start_osm_download(widgets["download_folder"])
            return False  # the page changes when download and import are done
        if not widgets["own"].isChecked() or widgets["path"] is None:
            return True  # data already loaded (earlier run or Python console)
        start_import(widgets["path"])
        return False  # the page changes when the background import is done

    def download_folder():
        """Folder suggested in the folder dialog (E14/E18): the last one, else
        the QGIS project folder, else the home folder."""
        last = QgsSettings().value(LAST_DOWNLOAD_FOLDER_SETTING, "")
        if last and Path(str(last)).is_dir():
            return Path(str(last))
        home = QgsProject.instance().homePath()
        return Path(home) if home and Path(home).is_dir() else Path.home()

    def start_osm_download(folder):
        """W11: plan with sources.py, download into ``folder`` in the
        background, then load the GeoPackage like an own file."""
        settings = dict(dock.settings)
        project_crs = QgsCoordinateReferenceSystem(settings["project_crs"])
        context = QgsProject.instance().transformContext()
        geometry = QgsGeometry.fromWkt(settings["study_area_wkt"])
        try:
            box = lonlat_box(geometry, settings["buffer_meters"], project_crs, context)
            plan = plan_osm_download(settings["study_area_wkt"], settings["buffer_meters"], box)
        except Exception as error:  # catalog broken, CRS cannot be converted …
            dock.show_message(f"Der OSM-Download konnte nicht vorbereitet werden: {error_text(error)}")
            return
        errors = [issue.message for issue in plan.issues if issue.severity == "error"]
        if errors or not plan.requests:
            dock.show_message("\n".join(errors) or "Für dieses Gebiet gibt es keinen OSM-Auftrag.")
            return
        request = plan.requests[0]
        feedback = QgsFeedback()
        dock.download_feedback = feedback
        status = {"text": None}  # hint from the worker thread (retry countdown)
        dock.set_busy("OSM-Daten werden geladen …")

        def run(task):
            def report(text):
                status["text"] = text
                task.setProgress(task.progress() + 0.001)  # wakes the panel up

            return run_download(request, folder, project_crs, context, feedback,
                                task.isCanceled, report, task.setProgress)

        def progress_changed(percent):
            if dock.closing:
                return
            if status["text"]:
                dock.busy_text = status["text"]
            dock.set_busy_progress(percent)

        def finished(exception, result=None):
            dock.import_task = None
            dock.download_feedback = None
            if dock.closing:
                return
            try:
                if isinstance(exception, DownloadCanceled) or dock.cancel_requested:
                    dock.clear_busy("cancel")
                    dock.show_message(CANCELED_MESSAGE, kind="info")
                    return
                if exception is not None:
                    dock.clear_busy("error")
                    if isinstance(exception, (DownloadError, OSError)):
                        dock.show_message(str(exception))
                    else:
                        dock.show_unexpected_error(UI_LABELS["load_data"], exception)
                    return
                dock.clear_busy("cancel")
                # Datenquelle in step 8 pre-filled with the OSM attribution (E28)
                if not dock.output_draft.get("source"):
                    dock.output_draft["source"] = request.attribution
                start_import(Path(result))
            except Exception as error:  # show every program error visibly
                dock.show_unexpected_error(UI_LABELS["load_data"], error)

        task = QgsTask.fromFunction("Urban Analysis: OSM-Daten laden", run, on_finished=finished)
        task.progressChanged.connect(progress_changed)
        dock.import_task = task
        QgsApplication.taskManager().addTask(task)

    def start_import(path):
        """Run the pipeline (S1) as a QGIS background task with a busy bar."""
        settings = dict(dock.settings)
        dock.input_paths.add(Path(path))  # protected from being overwritten in step 8
        dock.set_busy(f"Lade „{path.name}“ … Das kann bei großen Dateien etwas dauern.")
        project_crs = QgsCoordinateReferenceSystem(settings["project_crs"])
        context = QgsProject.instance().transformContext()
        converted = {"path": None, "layers": []}  # copy in the project CRS, if needed

        def run_import(task):
            # Layers in another CRS: convert a copy first (originals stay as they are)
            used, changed = ensure_project_crs(
                path, project_crs, context, Path(tempfile.gettempdir()) / "urban_analysis")
            if changed:
                converted.update(path=used, layers=changed)
            if task.isCanceled():
                raise ImportCanceled()
            importer = GeoPackageImporter()
            options = {}
            if pipeline_reports_progress(importer):
                # fraction 0..1 from the pipeline -> task progress 0..100;
                # stops the pipeline when 'Laden abbrechen' was pressed
                options["progress"] = cancel_aware_progress(task.isCanceled, task.setProgress)
            if task.isCanceled():
                raise ImportCanceled()
            return importer.import_file(
                used,
                project_crs=settings["project_crs"],
                study_area_wkt=settings["study_area_wkt"],
                buffer_meters=settings["buffer_meters"],
                **options,
            )

        def finished(exception, result=None):
            dock.import_task = None
            if dock.closing:
                return
            try:
                if isinstance(exception, ImportCanceled) or dock.cancel_requested:
                    # stopped by the user (also if the pipeline finished anyway)
                    dock.clear_busy("cancel")
                    dock.show_message(CANCELED_MESSAGE, kind="info")
                    return
                if exception is not None:
                    dock.clear_busy("error")
                    if isinstance(exception, DownloadError):
                        dock.show_message(str(exception))
                    elif isinstance(exception, (GeoPackageImportError, ValueError, OSError)):
                        dock.show_message(import_error_text(path.name, exception, path))
                    else:
                        dock.show_unexpected_error(UI_LABELS["load_data"], exception)
                    return
                if result is None:
                    dock.clear_busy("cancel")
                    dock.show_message(CANCELED_MESSAGE, kind="info")
                    return
                dock.clear_busy("done")
                plugin.start_workflow(result)
                dock.show_page(3)
                text = (f"„{path.name}“ geladen: {len(result.layers)} Layer. "
                        "Bitte die Prüfhinweise ansehen.")
                if converted["path"] is not None:
                    dock.input_paths.add(Path(converted["path"]))
                    text += (f"\n{len(converted['layers'])} Layer lagen in einem anderen CRS und "
                             f"wurden als Kopie nach {settings['project_crs']} umgerechnet "
                             f"({Path(converted['path']).name}); die Originaldatei ist unverändert.")
                dock.show_message(text, kind="info")
            except Exception as error:  # show every program error visibly
                dock.show_unexpected_error(UI_LABELS["load_data"], error)

        task = QgsTask.fromFunction(
            f"Urban Analysis: {path.name} laden", run_import, on_finished=finished
        )
        task.progressChanged.connect(
            lambda percent: dock.set_busy_progress(percent) if not dock.closing else None
        )
        dock.import_task = task
        QgsApplication.taskManager().addTask(task)

    # 4 Layer prüfen: every hint as its own card, grouped error/warning/info
    def build_review(page):
        flow = workflow()
        summary = QLabel(flow.review_summary_text())
        summary.setWordWrap(True)
        set_role(summary, "status")
        page.layout.addWidget(summary)

        groups = flow.issues_by_severity()
        if not any(groups.values()):
            page.layout.addWidget(QLabel("Keine Prüfhinweise."))
        for severity in SEVERITY_ORDER:
            issues = groups[severity]
            if not issues:
                continue
            title = f"{SEVERITY_LABELS[severity][1]} ({len(issues)})"
            group_layout = choice_with_panel(page, f"review_{severity}", title)
            for issue in issues:
                group_layout.addWidget(issue_card(flow, severity, issue))
            page.widgets[f"review_{severity}_button"].setChecked(True)

    def issue_card(flow, severity, issue):
        card = QFrame()
        set_role(card, f"issue-{severity}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 8, 6)
        short, more = split_summary(issue.message, getattr(issue, "details", None))
        text = QLabel(short)
        text.setWordWrap(True)
        key = issue_icon_key(flow, issue)
        card_layout.addWidget(with_icon(key, text) if key else text)
        if issue.code in DECIDED_IN_HARMONIZATION:
            step6 = QLabel("Entscheidung in Schritt 6 „Harmonisierung“")
            step6.setWordWrap(True)
            set_role(step6, "hint")
            card_layout.addWidget(step6)
        extra = [more] if more else []  # rules stay internal (not shown to users)
        if extra:
            # short summary first; the explanation folds out on demand (W13)
            more_label = QLabel("\n\n".join(extra))
            more_label.setWordWrap(True)
            set_role(more_label, "hint")
            more_label.hide()
            toggle = QPushButton(MORE_LABEL)
            toggle.setFlat(True)
            toggle.setCursor(Qt.PointingHandCursor)
            toggle.setStyleSheet("text-align: left; padding: 0; border: none; background: transparent;"
                                 "text-decoration: underline;")

            def flip(_checked=False, label=more_label, button=toggle):
                label.setVisible(not label.isVisible())
                button.setText(LESS_LABEL if label.isVisible() else MORE_LABEL)
                QTimer.singleShot(0, dock.fit_wrapped_labels)

            toggle.clicked.connect(flip)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(toggle)
            row.addStretch()
            card_layout.addLayout(row)
            card_layout.addWidget(more_label)
        if flow.needs_review_confirmation(issue):
            confirm = QCheckBox("Gelesen und bestätigt")
            confirm.setChecked(issue.confirmed is True)
            confirm.setCursor(Qt.PointingHandCursor)

            def toggled(checked, issue=issue):
                flow.confirm_issue(issue, checked)
                dock.clear_message()

            confirm.toggled.connect(toggled)
            card_layout.addWidget(confirm)
        return card

    def validate_review(page):
        blocker = workflow().review_blocker()
        if blocker:
            for severity in SEVERITY_ORDER:
                button = page.widgets.get(f"review_{severity}_button")
                if button is not None and not button.isChecked():
                    button.setChecked(True)
            return reject(blocker)
        return True

    def collapsible(page, key, text, icon_key=None, opened=False):
        """Fold-out section (choice button + panel) with an optional layer icon;
        keeps long pages short.  Returns the panel's layout."""
        panel_layout = choice_with_panel(page, key, text)
        button = page.widgets[f"{key}_button"]
        if icon_key:
            button.setIcon(layer_icon(icon_key))
            button.setIconSize(icon_size())
        page.widgets.setdefault("sections", []).append(key)
        if opened:
            button.setChecked(True)
        return panel_layout

    def open_sections(page, keys=None):
        """Open fold-out sections, e.g. so a validation message can be seen."""
        for key in page.widgets.get("sections", []) if keys is None else keys:
            button = page.widgets.get(f"{key}_button")
            if button is not None and not button.isChecked():
                button.setChecked(True)

    # 5 Attributzuordnung (W14): every column of every layer, with readable
    # name, examples and one choice: core field / keep / leave out.
    def build_mapping(page):
        flow = workflow()
        if not flow.result.columns:
            return build_mapping_legacy(page)  # older pipeline result: old view
        page.widgets["columns_view"] = True
        names = readable_names()
        by_layer = {}
        for column in flow.result.columns:
            by_layer.setdefault(column.layer_id, []).append(column)
        records_by_layer = {}
        for record in flow.result.harmonized_records:
            table = record.source_layer or record.layer_id
            rows = records_by_layer.setdefault(table, [])
            if len(rows) < PREVIEW_ROWS:
                rows.append(record)

        # Part 1: one question first – automatic or own choice
        if getattr(flow, "column_phase", "ask") == "ask":
            question = QLabel(STEP5_QUESTION)
            question.setWordWrap(True)
            page.layout.addWidget(question)
            auto = QRadioButton(AUTO_COLUMNS_LABEL)
            manual = QRadioButton(MANUAL_COLUMNS_LABEL)
            (manual if getattr(flow, "column_mode", "auto") == "manual" else auto).setChecked(True)
            group = QButtonGroup(page.widget)
            group.addButton(auto)
            group.addButton(manual)
            for button, hint in ((auto, AUTO_COLUMNS_HINT), (manual, MANUAL_COLUMNS_HINT)):
                page.layout.addWidget(button)
                text = QLabel(hint)
                text.setWordWrap(True)
                set_role(text, "hint")
                page.layout.addWidget(indented(text))
            page.widgets.update(ask_auto=auto, ask_group=group,
                                action_text=lambda: "Weiter")
            return

        # Part 2: one coloured table per layer; click a column header to change
        if getattr(flow, "column_values", None) is None:  # survives rebuilds of the page
            flow.column_values = {key: decision_value(d) for key, d in column_decisions_of(flow).items()}
        values = flow.column_values
        page.widgets["values"] = values
        page.widgets["action_text"] = lambda: PAGE_ACTIONS[4]
        guide = QLabel(STEP5_TABLE_GUIDE)
        guide.setWordWrap(True)
        set_role(guide, "info")
        page.layout.addWidget(guide)
        page.layout.addWidget(state_legend())
        back = link_button("◂ Zurück zur Frage (automatisch / selbst wählen)")

        def back_to_question():
            flow.column_phase = "ask"
            dock._rebuild_current_page()

        back.clicked.connect(back_to_question)
        page.layout.addWidget(back)
        manual = getattr(flow, "column_mode", "auto") == "manual"
        for number, (layer_id, columns) in enumerate(by_layer.items()):
            panel = collapsible(page, f"cols_{number}",
                                f"{names.layer(layer_id)} ({len(columns)} Spalten)",
                                layer_icon_key(flow, layer_id),
                                opened=manual or number == 0)
            counts = QLabel(counts_text(columns, values))
            set_role(counts, "hint")
            panel.addWidget(counts)
            table = QTableWidget()
            panel.addWidget(table)
            fill_table(table, ordered_columns(columns, values), values,
                       records_by_layer.get(layer_id, []), counts)
        guard_wheel(page.widget)

    def state_legend():
        """Small colour key above the tables."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 2, 0, 2)
        for state in ("target", "keep", "drop"):
            chip = QLabel(STATE_LABELS[state])
            fill, border = STATE_COLORS[state]
            chip.setStyleSheet(f"background: {fill}; border: 1px solid {border}; "
                               "border-radius: 9px; padding: 1px 8px;")
            row.addWidget(chip)
        row.addStretch()
        return box

    def link_button(text):
        button = QPushButton(text)
        button.setFlat(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet("text-align: left; padding: 0; border: none; "
                             "background: transparent; text-decoration: underline;")
        return button

    def fill_table(table, columns, values, records, counts):
        """All columns of a layer like the QGIS attribute table: coloured =
        taken over (green core field, blue kept), white = left out.  A click on
        a column header opens a small menu to change it."""
        table.clear()
        table.setColumnCount(len(columns))
        table.setRowCount(len(records))
        for index, column in enumerate(columns):
            value = values[(column.layer_id, column.source_field)]
            state = state_of(value)
            header = QTableWidgetItem(column_title(column, value))
            header.setIcon(state_icon(state))
            header.setToolTip(f"Spalte in den Daten: {column.source_field}\n"
                              f"{choice_help(value) or ''}\nKlick: ändern")
            table.setHorizontalHeaderItem(index, header)
            fill = QColor(STATE_COLORS[state][0] if state != "drop" else "#ffffff")
            for row, record in enumerate(records):
                raw = (getattr(record, "source_attributes", None) or {}).get(column.source_field)
                cell = QTableWidgetItem("–" if raw in (None, "") else str(raw))
                cell.setBackground(fill)
                if state == "drop":
                    cell.setForeground(QColor("#9aa3ae"))
                table.setItem(row, index, cell)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.horizontalHeader().setSectionsClickable(True)
        table.horizontalHeader().setCursor(Qt.PointingHandCursor)
        table.resizeColumnsToContents()
        table.setFixedHeight(table.horizontalHeader().sizeHint().height()
                             + sum(table.rowHeight(r) for r in range(table.rowCount()))
                             + table.horizontalScrollBar().sizeHint().height() + 6)
        table.viewport().installEventFilter(wheel_guard)  # wheel scrolls the panel
        try:
            table.horizontalHeader().sectionClicked.disconnect()
        except TypeError:
            pass

        def clicked(index):
            column = columns[index]
            key = (column.layer_id, column.source_field)
            menu = QMenu(table)
            core = menu.addMenu("● Kernfeld …")
            for field_name in CORE_FIELDS:
                action = core.addAction(core_field_name(field_name))
                action.setToolTip(choice_help(f"target:{field_name}") or "")
                action.triggered.connect(lambda _c=False, f=field_name: choose(key, f"target:{f}"))
            menu.addAction("● Behalten (eigene Spalte)").triggered.connect(
                lambda _c=False: choose(key, "keep"))
            menu.addAction("○ Nicht übernehmen").triggered.connect(
                lambda _c=False: choose(key, "drop"))
            header = table.horizontalHeader()
            x = header.sectionViewportPosition(index)
            menu.exec_(header.mapToGlobal(header.rect().topLeft()) + QPoint(x, header.height()))

        def choose(key, value):
            values[key] = value
            fill_table(table, columns, values, records, counts)
            counts.setText(counts_text(columns, values))
            dock.clear_message()

        table.horizontalHeader().sectionClicked.connect(clicked)

    def state_icon(state):
        pixmap = QPixmap(10, 10)
        pixmap.fill(QColor(STATE_COLORS[state][1] if state != "drop" else "#ffffff"))
        return QIcon(pixmap)

    def validate_columns(page):
        flow = workflow()
        if "ask_auto" in page.widgets:  # part 1: remember the answer, show the tables
            flow.column_mode = "auto" if page.widgets["ask_auto"].isChecked() else "manual"
            flow.column_phase = "table"
            dock._rebuild_current_page()
            dock.primary_button.setText(PAGE_ACTIONS[4])
            return False
        values = page.widgets["values"]
        by_key = {(c.layer_id, c.source_field): c for c in flow.result.columns}
        decisions = [decision_from_value(by_key[key], value) for key, value in values.items()]
        try:
            apply_column_decisions([], flow.result.columns, decisions)  # checks doubles
        except ValueError as error:
            open_sections(page)
            return reject(error_text(error))
        flow.column_decisions = decisions
        dock.next_message = COLUMNS_SAVED_TEXT
        return True

    def build_mapping_legacy(page):
        flow = workflow()
        names = readable_names()
        intro = QLabel(MAPPING_INTRO)
        intro.setWordWrap(True)
        set_role(intro, "hint")
        page.layout.addWidget(intro)
        groups = flow.suggestions_by_layer()
        if not groups:
            page.layout.addWidget(QLabel(NO_SUGGESTIONS_TEXT))
        inputs = []
        for number, (layer_id, suggestions) in enumerate(groups.items()):
            layer_name = names.layer(layer_id) if layer_id else "Ohne Layer-Angabe"
            count = len(suggestions)
            card_layout = collapsible(
                page, f"map_{number}",
                f"{layer_name} ({count} {'Spalte' if count == 1 else 'Spalten'})",
                layer_icon_key(flow, layer_id))
            for suggestion in suggestions:
                accepted = QCheckBox(names.field(suggestion.source_field))
                accepted.setChecked(suggestion.accepted is not False)
                accepted.setToolTip(f"Spalte „{suggestion.source_field}“ übernehmen")
                accepted.setCursor(Qt.PointingHandCursor)
                arrow = QLabel("→")
                target = QComboBox()
                for field in TARGET_FIELDS:
                    target.addItem(names.target(field), field)
                current = suggestion.user_value or suggestion.target_field
                index = target.findData(current)
                if index < 0:  # value outside the target schema stays visible
                    target.addItem(current, current)
                    index = target.count() - 1
                target.setCurrentIndex(index)
                target.setEnabled(accepted.isChecked())
                accepted.toggled.connect(target.setEnabled)
                # Column name on its own line, the target field below it, so
                # long names are never cut off in a narrow panel; then a short
                # grey line with examples (G9: examples stay visible).
                detail = mapping_detail_text(suggestion.source_field, suggestion.examples)
                card_layout.addWidget(accepted)
                row = QHBoxLayout()
                row.setContentsMargins(INDENT_PX, 0, 0, 0)
                row.addWidget(arrow)
                row.addWidget(target, 1)
                card_layout.addLayout(row)
                examples = QLabel(detail)
                examples.setWordWrap(True)
                set_role(examples, "hint")
                card_layout.addWidget(indented(examples))
                inputs.append((suggestion, accepted, target))
        page.widgets["inputs"] = inputs

    def validate_mapping(page):
        if page.widgets.get("columns_view"):
            return validate_columns(page)
        flow = workflow()
        decisions = {}
        for suggestion, accepted, target in page.widgets["inputs"]:
            decisions[(suggestion.layer_id, suggestion.source_field)] = (
                target.currentData() if accepted.isChecked() else False
            )
        try:
            flow.confirm_attribute_suggestions(decisions)
        except (KeyError, ValueError) as error:
            open_sections(page)
            return reject(error_text(error))
        try:
            applied = flow.apply_attribute_decisions()
        except ValueError as error:  # e.g. a target field chosen twice
            open_sections(page)
            return reject(error_text(error))
        dock.next_message = MAPPING_APPLIED_TEXT if applied else MAPPING_SAVED_TEXT
        return True

    # 6 Harmonisierung: decide per layer whether uncertain duplicates are merged
    def build_harmonization(page):
        flow = workflow()
        layers = flow.duplicate_layers()
        if not layers:
            none = QLabel(NO_DUPLICATES_TEXT)
            none.setWordWrap(True)
            page.layout.addWidget(none)
            return
        intro = QLabel(UNCERTAIN_DUPLICATE_EXPLANATION_STEP6)
        intro.setWordWrap(True)
        set_role(intro, "hint")
        page.layout.addWidget(intro)
        names = readable_names()
        page.widgets["duplicate_sections"] = {}
        for number, layer in enumerate(layers):
            key = f"dup_{number}"
            page.widgets["duplicate_sections"][layer.table_name] = key
            # open only where a decision is still missing
            panel = collapsible(
                page, key,
                duplicate_title_text(names.layer(layer.table_name), layer.group_count,
                                     layer.record_count),
                layer_icon_key(flow, layer.table_name),
                opened=layer.table_name not in flow.duplicate_decisions)
            panel.addWidget(duplicate_card(flow, layer))

    def duplicate_card(flow, layer):
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        names = readable_names()
        descriptors = {d.layer_id: d for d in flow.result.layers}

        def result_label(layer_id):
            # same names as the result layers in step 9 (e.g. split
            # 'nutzung_flaechen' -> 'Nutzungsflächen')
            descriptor = descriptors.get(layer_id)
            if descriptor is None:
                return names.layer(layer_id)
            return result_layer_name(descriptor, names.layer)

        for group, records in layer.groups[:DUPLICATE_EXAMPLES]:
            example = QLabel(f"• {describe_group(records, result_label)}")
            example.setWordWrap(True)
            set_role(example, "hint")
            card_layout.addWidget(example)
        if layer.group_count > DUPLICATE_EXAMPLES:
            more = QLabel(more_groups_text(layer.group_count - DUPLICATE_EXAMPLES))
            set_role(more, "hint")
            card_layout.addWidget(more)
        cross = layer.cross_layer_groups()
        if cross:
            warning = QLabel(cross_layer_warning_text(len(cross)))
            warning.setWordWrap(True)
            set_role(warning, "error")
            card_layout.addWidget(warning)

        keep = QRadioButton("Behalten")
        keep.setToolTip("Alle Objekte bleiben erhalten.")
        merge = QRadioButton("Zusammenführen")
        merge.setToolTip(merge_hint_text(layer.removable_count))
        for button in (keep, merge):
            button.setCursor(Qt.PointingHandCursor)
        merge_hint = QLabel(merge_hint_text(layer.removable_count))
        merge_hint.setWordWrap(True)
        set_role(merge_hint, "hint")
        choice = QButtonGroup(card)
        choice.addButton(keep)
        choice.addButton(merge)
        decision = flow.duplicate_decisions.get(layer.table_name)
        if decision is True:
            merge.setChecked(True)
        elif decision is False:
            keep.setChecked(True)

        def chosen(merge_it, table=layer.table_name):
            flow.set_duplicate_decision(table, merge_it)
            dock.clear_message()

        keep.toggled.connect(lambda checked: checked and chosen(False))
        merge.toggled.connect(lambda checked: checked and chosen(True))
        # both choices in one row, the effect of merging below
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.addWidget(keep)
        row.addWidget(merge)
        row.addStretch()
        card_layout.addLayout(row)
        card_layout.addWidget(merge_hint)
        card._choice_group = choice  # keep the group alive with the card
        return card

    def validate_harmonization(page):
        flow = workflow()
        open_layers = flow.open_duplicate_decisions()
        if open_layers:
            sections = page.widgets.get("duplicate_sections", {})
            open_sections(page, [sections[name] for name in open_layers if name in sections])
            return reject(
                "Bitte für jeden Layer „Behalten“ oder „Zusammenführen“ wählen. "
                "Noch offen: " + ", ".join(readable_names().layer(name) for name in open_layers)
            )
        if not flow.duplicate_layers():
            return True
        removed = flow.apply_duplicate_decisions()
        dock.next_message = duplicates_applied_text(removed)
        return True

    # 7 Kartenthema
    def build_topic(page):
        topic_input = QLineEdit(workflow().result.selected_topic or "Siedlungsstruktur")
        category_list = QListWidget()
        category_list.setIconSize(icon_size())
        for category in workflow().recognized_categories():
            item = QListWidgetItem(layer_icon(icon_key(category=category)), category)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            category_list.addItem(item)
        # show all categories at once (no inner scrolling)
        rows = max(category_list.count(), 1)
        category_list.setMinimumHeight(rows * (icon_size().height() + 4) + 8)
        confirm_missing = QCheckBox(UI_LABELS["continue_incomplete"])
        page.layout.addWidget(QLabel(UI_LABELS["topic"]))
        page.layout.addWidget(topic_input)
        page.layout.addWidget(category_list)
        page.layout.addWidget(confirm_missing)
        page.widgets.update(
            topic=topic_input, categories=category_list, confirm_missing=confirm_missing
        )

    # 9 'Erreichbarkeitsanalyse' (W16): targets, radii per target, display
    def build_accessibility(page):
        flow = workflow()
        choice = getattr(flow, "accessibility", None) or AccessibilityChoice()
        try:
            from .accessibility import target_choices
            available = target_choices(flow.result.harmonized_records)
        except Exception:  # settings missing: no targets, said below
            available = {}
        intro = QLabel(ACCESS_INTRO)
        intro.setWordWrap(True)
        set_role(intro, "hint")
        page.layout.addWidget(intro)
        details_layout = page.layout

        def step_heading(text):
            label = QLabel(f"<b>{text}</b>")
            label.setWordWrap(True)
            details_layout.addWidget(label)

        # ① targets: whole categories or single kinds (subtypes)
        step_heading("① Ziele wählen")
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        if available:
            hint = QLabel(ACCESS_TARGETS_HINT)
            hint.setWordWrap(True)
            set_role(hint, "hint")
            details_layout.addWidget(hint)
            for category, kinds in available.items():
                total = sum(count for _kind, count in kinds)
                parent = QTreeWidgetItem([f"{category} ({total})"])
                parent.setData(0, Qt.UserRole, category)
                parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                chosen = choice.targets.get(category)
                parent.setCheckState(0, Qt.Unchecked)
                for kind, count in kinds:
                    child = QTreeWidgetItem([f"{kind} ({count})"])
                    child.setData(0, Qt.UserRole, kind)
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    on = chosen is not None and (not chosen or kind in chosen)
                    child.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
                    parent.addChild(child)
                tree.addTopLevelItem(parent)
            rows = sum(1 + top.childCount() for top in
                       (tree.topLevelItem(i) for i in range(tree.topLevelItemCount())))
            tree.setMinimumHeight(min(rows, 12) * 22 + 8)
            tree.setMaximumHeight(max(tree.topLevelItemCount(), 3) * 26 + 120)
            details_layout.addWidget(tree)
        else:
            none = QLabel(ACCESS_NO_TARGETS)
            none.setWordWrap(True)
            set_role(none, "warning")
            details_layout.addWidget(none)

        # ② radii per chosen target: suggested from the guide values
        step_heading("② " + ACCESS_RADII_GUIDE)
        radii_box = QWidget()
        radii_layout = QVBoxLayout(radii_box)
        radii_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addWidget(radii_box)
        radii_hint = QLabel(ACCESS_RADII_HINT + " " + GUIDE_NOTE)
        radii_hint.setWordWrap(True)
        set_role(radii_hint, "hint")
        details_layout.addWidget(radii_hint)
        page.widgets["access_radii"] = {}  # category -> line edit
        own_radii = dict(choice.radii)  # typed values survive a rebuild of the rows

        def chosen_targets():
            return tree_targets(tree)

        def remember_radii():
            for category, line in page.widgets["access_radii"].items():
                own_radii[category] = line.text()

        def refresh_radii(*_args):
            remember_radii()
            _clear_layout(radii_layout)
            lines = {}
            targets = chosen_targets()
            if not targets:
                none = QLabel("Erst oben ein Ziel ankreuzen.")
                set_role(none, "hint")
                radii_layout.addWidget(none)
            for category, subtypes in targets.items():
                guide_radii, guide_text = guide_value(category, subtypes)
                label = QLabel(f"{', '.join(subtypes) if subtypes else category}:")
                label.setWordWrap(True)
                radii_layout.addWidget(label)
                typed = own_radii.get(category)
                text = typed if isinstance(typed, str) else radii_text(typed or guide_radii)
                line = QLineEdit(text)
                line.setPlaceholderText(radii_text(guide_radii))
                line.editingFinished.connect(refresh_colors)
                radii_layout.addWidget(line)
                guide = QLabel(f"Richtwert {radii_text(guide_radii)} m – {guide_text}")
                guide.setWordWrap(True)
                set_role(guide, "hint")
                radii_layout.addWidget(guide)
                lines[category] = line
            page.widgets["access_radii"] = lines
            refresh_colors()
            QTimer.singleShot(0, dock.fit_wrapped_labels)

        # ③ display: fill between the rings (15 %), colours per ring
        step_heading("③ Darstellung")
        fill = QCheckBox(ACCESS_FILL_LABEL)
        fill.setChecked(choice.fill)
        details_layout.addWidget(fill)
        colors_box = QWidget()
        colors_layout = QHBoxLayout(colors_box)
        colors_layout.setContentsMargins(INDENT_PX, 0, 0, 0)
        details_layout.addWidget(colors_box)
        page.widgets["access_colors"] = []

        def refresh_colors(*_args):
            # as many colours as the target with the most radii
            values = ()
            for line in page.widgets["access_radii"].values():
                try:
                    found = parse_radii(line.text())
                except RadiusError:
                    continue
                if len(found) > len(values):
                    values = found
            values = values or (300, 500)
            current = [b.color().name() for b in page.widgets["access_colors"]] or list(choice.colors)
            _clear_layout(colors_layout)
            buttons = []
            for number, color in enumerate(ring_colors(values, current), start=1):
                box = QWidget()
                box_layout = QVBoxLayout(box)
                box_layout.setContentsMargins(0, 0, 4, 0)
                button = QgsColorButton()
                button.setColor(QColor(color))
                button.setFixedWidth(46)
                button.setToolTip(f"Farbe für den {number}. Ring von innen")
                box_layout.addWidget(button)
                caption = QLabel(f"{number}. Ring")
                set_role(caption, "hint")
                box_layout.addWidget(caption)
                colors_layout.addWidget(box)
                buttons.append(button)
            colors_layout.addStretch()
            page.widgets["access_colors"] = buttons
            colors_box.setVisible(fill.isChecked())

        fill.toggled.connect(lambda on: colors_box.setVisible(on))
        if available:
            tree.itemChanged.connect(lambda *_args: QTimer.singleShot(0, refresh_radii))
        refresh_radii()
        page.widgets.update(access_tree=tree, access_fill=fill, access_available=bool(available))

    def tree_targets(tree):
        """{category: subtypes} of the ticked targets (empty = whole category)."""
        targets = {}
        for index in range(tree.topLevelItemCount()):
            parent = tree.topLevelItem(index)
            state = parent.checkState(0)
            if state == Qt.Checked:
                targets[parent.data(0, Qt.UserRole)] = ()  # whole category
            elif state == Qt.PartiallyChecked:
                targets[parent.data(0, Qt.UserRole)] = tuple(
                    parent.child(i).data(0, Qt.UserRole) for i in range(parent.childCount())
                    if parent.child(i).checkState(0) == Qt.Checked)
        return targets

    def accessibility_from(page):
        """Read the accessibility settings of step 9 (raises RadiusError)."""
        widgets = page.widgets
        radii = {}
        for category, line in widgets["access_radii"].items():
            try:
                radii[category] = parse_radii(line.text())
            except RadiusError as error:
                raise RadiusError(f"{category}: {error}")
        return AccessibilityChoice(
            targets=tree_targets(widgets["access_tree"]),
            radii=radii,
            fill=widgets["access_fill"].isChecked(),
            colors=tuple(button.color().name() for button in widgets["access_colors"]),
        )

    def validate_topic(page):
        category_list = page.widgets["categories"]
        selected = tuple(
            category_list.item(index).text()
            for index in range(category_list.count())
            if category_list.item(index).checkState() == Qt.Checked
        )
        try:
            workflow().select_topic(
                page.widgets["topic"].text(),
                selected,
                confirm_missing=page.widgets["confirm_missing"].isChecked(),
            )
        except ValueError as error:
            return reject(str(error))
        return True

    # 8 Ausgabe: QGIS layers always; GeoPackage/PDF with a save location each
    def output_folder():
        """Folder for the save dialog: the last one, else the project folder."""
        last = QgsSettings().value(LAST_OUTPUT_FOLDER_SETTING, "")
        if last and Path(str(last)).is_dir():
            return Path(str(last))
        home = QgsProject.instance().homePath()
        return Path(home) if home and Path(home).is_dir() else Path.home()

    def show_output_path(page, kind):
        path = dock.output_paths.get(kind)
        label = page.widgets[f"{kind}_path"]
        if path:
            label.setText(output_path_text(path))
            label.setToolTip(str(path))
        else:
            label.setText("Noch kein Speicherort gewählt.")
            label.setToolTip("")

    def choose_output_path(page, kind):
        """System save dialog; remembers the folder for the next time."""
        current = dock.output_paths.get(kind) or default_output_path(
            output_folder(), workflow().result.selected_topic, kind, date.today())
        path, _filter = QFileDialog.getSaveFileName(
            dock, OUTPUT_DIALOG_TITLES[kind], str(current), OUTPUT_DIALOG_FILTERS[kind])
        if not path:
            return  # dialog closed: keep the previous choice
        chosen = with_output_suffix(path, kind)
        QgsSettings().setValue(LAST_OUTPUT_FOLDER_SETTING, str(chosen.parent))
        dock.output_paths[kind] = chosen
        dock.output_confirmed.add(kind)  # the dialog asked about replacing
        show_output_path(page, kind)
        dock.clear_message()

    def output_choice(page, kind, text, checked, hint=None, extra=()):
        box = QCheckBox(text)
        box.setChecked(checked)
        path_label = QLabel()
        path_label.setWordWrap(True)
        set_role(path_label, "hint")
        button = QPushButton(SAVE_AS_LABEL)
        set_role(button, "secondary")
        button.setCursor(Qt.PointingHandCursor)
        parts = [path_label, button, *extra]
        if hint:
            note = QLabel(hint)
            note.setWordWrap(True)
            set_role(note, "hint")
            parts.insert(0, note)
        details = indented(*parts)
        page.layout.addWidget(box)
        page.layout.addWidget(details)
        page.widgets.update({kind: box, f"{kind}_path": path_label})

        def toggled(on):
            if on and not dock.output_paths.get(kind):
                # visible suggestion; "Speichern unter …" changes it
                dock.output_paths[kind] = default_output_path(
                    output_folder(), workflow().result.selected_topic, kind, date.today())
            show_output_path(page, kind)
            details.setVisible(on)
            QTimer.singleShot(0, dock.fit_wrapped_labels)

        box.toggled.connect(toggled)
        box.toggled.connect(lambda on: dock.output_draft.__setitem__(kind, on))
        button.clicked.connect(lambda: choose_output_path(page, kind))
        toggled(checked)

    def output_draft():
        """Settings of the last step; unconfirmed input survives a rebuild."""
        output = workflow().result.output
        draft = dock.output_draft
        draft.setdefault("geopackage", output.save_cleaned_geopackage)
        draft.setdefault("pdf", output.create_pdf)
        draft.setdefault("source", output.data_source)
        return draft

    def labelled_combo(label, items, key, default):
        """Small 'Label + choice list' block; the choice is kept in the draft."""
        draft = output_draft()
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 4, 0, 0)
        box_layout.addWidget(QLabel(label))
        combo = QComboBox()
        for value, text in items:
            combo.addItem(text, value)
        index = combo.findData(draft.setdefault(key, default))
        combo.setCurrentIndex(max(index, 0))
        combo.currentIndexChanged.connect(
            lambda _i, c=combo: draft.__setitem__(key, c.currentData()))
        box_layout.addWidget(combo)
        return box

    def labelled_line(label, key, placeholder):
        draft = output_draft()
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 4, 0, 0)
        box_layout.addWidget(QLabel(label))
        line = QLineEdit(draft.setdefault(key, ""))
        line.setPlaceholderText(placeholder)
        line.textChanged.connect(lambda text: draft.__setitem__(key, text))
        box_layout.addWidget(line)
        return box

    # 8 Verarbeitung starten: three areas with their own button each
    def summary_card(title, rows):
        card = QFrame()
        set_role(card, "issue-info")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 8, 8)
        heading = QLabel(title)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        card_layout.addWidget(heading)
        for row in rows:
            label, value = row[0], row[1]
            line = QLabel(f"{label}: {value}" if label else value)
            line.setWordWrap(True)
            # optional third element: icon key of a layer
            card_layout.addWidget(with_icon(row[2], line) if len(row) > 2 and row[2] else line)
        return card

    def study_area_hectares(result):
        geometry = QgsGeometry.fromWkt(result.study_area_wkt or "")
        if geometry is None or geometry.isNull():
            return None
        return geometry.area() / 10000

    class Area:
        """One area of the last step: own layout, shares the widgets of the page."""

        def __init__(self, layout, widgets):
            self.layout = layout
            self.widgets = widgets

    def result_group():
        """The layer group of the last 'Layer erzeugen', or None (also when
        the user removed it in QGIS)."""
        if not dock.last_group_name:
            return None
        return QgsProject.instance().layerTreeRoot().findGroup(dock.last_group_name)

    def build_summary(page):
        """Last step: a row of buttons (always selectable), below the chosen area."""
        tab = dock.step9_tab
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for key, text in STEP9_TABS:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(key == tab)
            button.setCursor(Qt.PointingHandCursor)
            set_role(button, "choice")
            button.clicked.connect(lambda _checked=False, k=key: switch_step9_tab(page, k))
            row.addWidget(button)
        page.layout.addLayout(row)
        panel = QFrame()
        set_role(panel, "panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 12)
        page.layout.addWidget(panel)
        area = Area(panel_layout, page.widgets)
        {"output": build_layers_area, "access": build_access_area,
         "save": build_save_area}[tab](area)

    def switch_step9_tab(page, key):
        try:
            remember_accessibility(page)
            dock.step9_tab = key
            dock.clear_message()
            rebuild_last_step(page)
        except Exception as error:  # show every program error visibly
            dock.show_unexpected_error("Bereich wechseln", error)

    def rebuild_last_step(page):
        page.build()
        make_texts_selectable(page.widget)
        QTimer.singleShot(0, dock.fit_wrapped_labels)

    def remember_accessibility(page):
        """Keep the accessibility settings, even without starting the analysis."""
        if dock.step9_tab == "access" and "access_tree" in page.widgets:
            try:
                workflow().accessibility = accessibility_from(page)
            except RadiusError:
                pass  # said again on 'Analyse starten'

    def area_hint(area, text, role="hint"):
        label = QLabel(text)
        label.setWordWrap(True)
        set_role(label, role)
        area.layout.addWidget(label)

    def area_button(area, page, text, action, context):
        """The own main button of an area (at its end)."""
        button = PixelButton(text, "primary")
        button.setCursor(Qt.PointingHandCursor)

        def clicked():
            dock.clear_message()
            try:
                action(page)
            except Exception as error:  # show every program error visibly
                dock.show_unexpected_error(context, error)

        button.clicked.connect(clicked)
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 0)
        row.addStretch()
        row.addWidget(button)
        area.layout.addLayout(row)
        return button

    # Ausgabe: map style, data source, 'Layer erzeugen'
    def build_layers_area(area):
        flow = workflow()
        names = readable_names()
        draft = output_draft()
        group = result_group()
        area_hint(area, LAYERS_INTRO)
        area.layout.addWidget(labelled_combo(
            "Kartenstil (Ergebnis-Layer und PDF)", list(MAP_STYLES.items()),
            "map_style", DEFAULT_MAP_STYLE))
        area.layout.addWidget(QLabel(UI_LABELS["data_source"]))
        source = QLineEdit(draft["source"])
        source.textChanged.connect(lambda text: draft.__setitem__("source", text))
        source.setPlaceholderText(DATA_SOURCE_PLACEHOLDER)
        area.layout.addWidget(source)
        area_hint(area, DATA_SOURCE_HINT)
        if dock.last_reports is not None and group is not None:
            area_hint(area, DONE_TITLE, "status")
            area.layout.addWidget(summary_card(
                "Angelegte Ergebnis-Layer",
                result_rows(dock.last_reports,
                            {d.layer_id: d.category for d in flow.result.layers})))
            area_hint(area, done_hint_text(group.name()))
        else:
            area.layout.addWidget(summary_card(
                "Grundlagen", overview_rows(flow, study_area_hectares(flow.result), names)))
            area.layout.addWidget(summary_card(
                "Diese Ergebnis-Layer werden angelegt", planned_layer_rows(flow, names)))
        area_button(area, area_page(area), LAYERS_AGAIN_ACTION if group is not None else LAYERS_ACTION,
                    create_layers_clicked, LAYERS_ACTION)

    def area_page(area):
        return dock.pages[dock.current]

    def create_layers_clicked(page):
        if make_layers(ask_same=True) is None:
            return
        rebuild_last_step(page)
        dock.show_message(result_layers_text(dock.last_reports) + "\n" + LAYERS_NEXT_HINT, kind="info")

    def ensure_layers():
        """The result group; created first if there is none yet, so every
        area works on its own.  None if that failed (message shown)."""
        group = result_group()
        if group is not None:
            return group
        return make_layers(ask_same=False)

    def make_layers(ask_same):
        """Build the result layers and add them to QGIS as a new group."""
        flow = workflow()
        selected = flow.result.selected_layers()
        if not selected:
            reject("Für das Kartenthema ist kein Layer ausgewählt. Bitte in Schritt 7 "
                   "mindestens eine Kategorie ankreuzen.")
            return None
        draft = output_draft()
        source = draft.get("source", "")
        problem = output_choice_problem(geopackage=False, pdf=False, paths={}, data_source=source)
        if problem:
            reject(problem + " (Bereich „Ausgabe“)")
            return None
        signature = run_signature(flow, draft, dock.output_paths)
        if ask_same and signature == dock.last_run_signature and result_group() is not None:
            answer = QMessageBox.question(
                dock, LAYERS_AGAIN_ACTION, SAME_RUN_QUESTION,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return None
        try:
            flow.choose_output(
                save_cleaned_geopackage=bool(draft.get("geopackage")),
                create_pdf=bool(draft.get("pdf")),
                data_source=source,
            )
            # Current decisions of step 5 (and step 6) on the data (S5),
            # then the data source into empty 'source' fields (S8).
            flow.apply_attribute_decisions()
            if flow.result.columns:  # W14: the column choices of step 5
                flow.result.harmonized_records = apply_column_decisions(
                    flow.result.harmonized_records, flow.result.columns,
                    getattr(flow, "column_decisions", None))
            flow.result.harmonized_records = apply_data_source(
                flow.result.harmonized_records, source)
        except ValueError as error:
            reject(error_text(error))
            return None
        try:
            from .mapping import readable_layer
        except ImportError:
            readable_layer = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layer_objects, reports = build_result_layers(flow.result, selected, readable_layer)
            # E33: map colours per category; buildings and lines on top of areas
            categories = {d.layer_id: d.category for d in selected}
            style = draft.get("map_style", DEFAULT_MAP_STYLE)
            for layer_id, layer in layer_objects.items():
                apply_style(layer, categories.get(layer_id), style)
            layer_objects = dict(sorted(
                layer_objects.items(),
                key=lambda item: -draw_rank(categories.get(item[0]))))
            group = add_result_layers(layer_objects, result_group_name(flow.result.selected_topic))
        finally:
            QApplication.restoreOverrideCursor()
        dock.last_group_name = group.name()
        dock.last_run_signature = signature
        plugin.result_layers = layer_objects
        dock.last_reports = reports
        dock.last_saved = []
        dock.last_access_lines = []  # a new group has no analysis yet
        dock.mark_all_done()
        return group

    # Erreichbarkeit
    def build_access_area(area):
        build_accessibility(area)
        if dock.last_access_lines:
            area.layout.addWidget(summary_card("Ergebnis der letzten Analyse",
                                               [(None, line) for line in dock.last_access_lines]))
        if result_group() is None:
            area_hint(area, LAYERS_FIRST_HINT)
        area_button(area, area_page(area), ACCESS_ACTION, run_accessibility, ACCESS_ACTION)

    def run_accessibility(page):
        """'Analyse starten': distances into the buildings of the map, targets
        (copies with attribute table) and dashed radii as sub-groups."""
        flow = workflow()
        if not page.widgets.get("access_available"):
            return reject(ACCESS_NO_TARGETS)
        try:
            choice = accessibility_from(page)
        except RadiusError as error:
            return reject(str(error))
        problem = choice_problem(choice)
        if problem:
            return reject(problem)
        flow.accessibility = choice
        group = ensure_layers()
        if group is None:
            return False
        try:
            from .mapping import readable_layer
        except ImportError:
            readable_layer = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            records, issues, targets = calculate_accessibility(flow.result.harmonized_records, choice)
            flow.result.harmonized_records = records
            # distance columns into the buildings that are already in the map
            values = distance_columns(records, list(targets))
            filled = missing = 0
            origin_ids = {d.layer_id for d in flow.result.layers if d.category == "Gebäude"}
            for layer_id, layer in (plugin.result_layers or {}).items():
                if layer_id not in origin_ids:
                    continue
                try:
                    if QgsProject.instance().mapLayer(layer.id()) is None:
                        continue  # removed in QGIS
                except RuntimeError:
                    continue
                done, not_found = add_columns_to_layer(layer, values)
                filled += done
                missing += not_found
            descriptors = {d.layer_id: d for d in flow.result.layers}
            for label, layers in build_accessibility_layers(
                    targets, choice, flow.result.project_crs, descriptors, readable_layer):
                old = group.findGroup(label)
                if old is not None:  # same target again: replace its layers
                    QgsProject.instance().removeMapLayers([n.layerId() for n in old.findLayers()])
                    group.removeChildNode(old)
                sub = group.insertGroup(0, label)
                for layer in layers:
                    QgsProject.instance().addMapLayer(layer, False)
                    sub.addLayer(layer)
        finally:
            QApplication.restoreOverrideCursor()
        lines = [issue.message for issue in issues]
        if filled:
            lines.append(f"Abstände in {format_count(filled)} Gebäude eingetragen "
                         "(Attributtabelle: Spalten „Abstand … (m)“ und „… bis … m“).")
        if missing:
            lines.append(f"{format_count(missing)} Gebäude ohne passende Objekt-ID – dort "
                         "fehlen die Abstände.")
        dock.last_access_lines = lines
        rebuild_last_step(page)
        severe = any(issue.severity in ("error", "warning") for issue in issues) or missing
        dock.show_message("\n".join(lines), kind="warning" if severe else "info")
        return False

    # Speichern: GeoPackage and PDF with its settings
    def build_save_area(area):
        draft = output_draft()
        area_hint(area, SAVE_INTRO)
        output_choice(area, "geopackage", "Bereinigtes GeoPackage speichern", draft["geopackage"])
        topic = workflow().result.selected_topic or "Siedlungsstruktur"
        north = QCheckBox("Nordpfeil anzeigen")
        north.setChecked(draft.setdefault("pdf_north", True))
        north.toggled.connect(lambda on: draft.__setitem__("pdf_north", on))
        # a PDF setting only: shown inside the PDF options
        grey = QCheckBox("Umgebung außerhalb des Gebiets in Graustufen")
        grey.setChecked(draft.setdefault("grey_outside", True))
        grey.toggled.connect(lambda on: draft.__setitem__("grey_outside", on))
        pdf_extra = (
            labelled_line("Titel", "pdf_title", f"z. B. {topic} Donnerschwee"),
            labelled_line("Name / Kurs (Untertitel)", "pdf_subtitle", "z. B. Urban Design, WS 2026/27"),
            labelled_combo("Papierformat", [(p, p) for p in PAGE_SIZES_MM], "pdf_page", "A3"),
            labelled_combo("Ausrichtung", [("auto", "Automatisch (passend zum Gebiet)"),
                                           ("quer", "Querformat"), ("hoch", "Hochformat")],
                           "pdf_orientation", "auto"),
            labelled_combo("Maßstab", [(s or 0, scale_label(s)) for s in SCALES], "pdf_scale", 0),
            north,
            grey,
        )
        output_choice(area, "pdf", "PDF-Karte erzeugen", draft["pdf"], PDF_HINT, pdf_extra)
        if dock.last_saved:
            area.layout.addWidget(summary_card("Gespeicherte Dateien", saved_rows(dock.last_saved)))
        if result_group() is None:
            area_hint(area, LAYERS_FIRST_HINT)
        area_button(area, area_page(area), SAVE_ACTION, save_files, SAVE_ACTION)

    def write_map_pdf(flow, path, layers):
        """PDF map with the settings of 'Speichern'."""
        draft = dock.output_draft
        return export_map_pdf(
            path, layers=layers,
            grey_outside=draft.get("grey_outside", True),
            study_area_wkt=flow.result.study_area_wkt,
            buffer_meters=flow.result.buffer_meters,
            crs_authid=flow.result.project_crs,
            title=draft.get("pdf_title") or flow.result.selected_topic or "Siedlungsstruktur",
            subtitle=draft.get("pdf_subtitle", ""),
            data_source=flow.result.output.data_source,
            page=draft.get("pdf_page", "A3"),
            orientation=draft.get("pdf_orientation", "auto"),
            scale=draft.get("pdf_scale") or None,
            north_arrow=draft.get("pdf_north", True))

    def save_files(page):
        """'Speichern': GeoPackage (all layers of the group) and PDF (visible
        layers in their order) from the current state in QGIS."""
        flow = workflow()
        draft = output_draft()
        geopackage, pdf = bool(draft.get("geopackage")), bool(draft.get("pdf"))
        if not (geopackage or pdf):
            return reject(SAVE_NOTHING_MESSAGE)
        source = draft.get("source", "")
        problem = output_choice_problem(
            geopackage=geopackage, pdf=pdf, paths=dock.output_paths, data_source=source,
            confirmed=dock.output_confirmed, input_paths=dock.input_paths)
        if problem:
            return reject(problem)
        group = ensure_layers()
        if group is None:
            return False
        try:
            flow.choose_output(save_cleaned_geopackage=geopackage, create_pdf=pdf, data_source=source)
        except ValueError as error:
            return reject(str(error))
        nodes = [node for node in group.findLayers() if node.layer() is not None]
        all_layers = [node.layer() for node in nodes]
        visible = [node.layer() for node in nodes if node.isVisible()]
        jobs = []
        if geopackage:
            jobs.append(("geopackage", lambda path: write_result_geopackage(path, all_layers)))
        if pdf:
            if not visible:
                return reject(REMAKE_NO_LAYERS_MESSAGE)
            jobs.append(("pdf", lambda path: write_map_pdf(flow, path, visible)))
        saved, failures = [], []
        for kind, write in jobs:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                saved.append((kind, Path(write(dock.output_paths[kind]))))
                dock.output_confirmed.add(kind)  # saving again may replace our own file
            except (OSError, RuntimeError, ValueError) as error:
                failures.append(SAVE_FAILED_MESSAGE.format(
                    kind=OUTPUT_KIND_LABELS[kind], reason=error_text(error)))
            finally:
                QApplication.restoreOverrideCursor()
        dock.last_saved = saved
        rebuild_last_step(page)
        text = ("Gespeichert: " + ", ".join(path.name for _kind, path in saved) + ".") if saved else ""
        if failures:
            dock.show_message("\n\n".join([t for t in [text] if t] + failures), kind="error")
        else:
            dock.show_message(text, kind="info")
        return False

    def validate_summary(page):
        """The areas have their own buttons; the panel button is hidden here."""
        return False

    crs_page = dock.add_page(build_crs, validate_crs)
    dock.add_page(build_area, validate_area, on_show=update_area_status)
    dock.add_page(build_data, validate_data)
    dock.add_page(build_review, validate_review, rebuild=True)
    dock.add_page(build_mapping, validate_mapping, rebuild=True)
    dock.add_page(build_harmonization, validate_harmonization, rebuild=True)
    dock.add_page(build_topic, validate_topic, rebuild=True)
    dock.add_page(build_summary, validate_summary, rebuild=True)
    dock.show_page(0)
    return dock
