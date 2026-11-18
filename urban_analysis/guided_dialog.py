"""QGIS side panel for the contract-defined nine-step user guidance.

The guidance lives in a dock widget on the right side of QGIS, so it can stay
open, be hidden via the toolbar button or be undocked while working in QGIS.

Pages 1-3 (Projekt-CRS, Untersuchungsgebiet, Daten laden) work without a
``PipelineResult``.  Pages 4-9 are rebuilt every time they are reached, so
they always reflect the data that is currently loaded.
"""

from pathlib import Path

from .contracts import MVP_DEFAULT_BUFFER_METERS, MVP_UI_STEPS
from .data_pipeline import TARGET_FIELDS, GeoPackageImporter, GeoPackageImportError
from .outputs import (
    add_result_layers,
    build_result_layers,
    format_count,
    result_group_name,
    result_layer_name,
    result_layers_text,
)
from .study_area import (
    DRAW_INSTRUCTIONS,
    StudyAreaError,
    add_drawn_area_layer,
    area_summary_text,
    create_polygon_draw_tool,
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
EXPORT_PENDING_MESSAGE = (
    "GeoPackage- und PDF-Ausgabe werden in einem späteren Schritt angeschlossen "
    "(ARBEITSPLAN W8)."
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
    "Ausgabe übernehmen",
    UI_LABELS["start_processing"],
)

SOURCE_LOCAL_LABEL = "Lokale Daten"
SOURCE_ONLINE_LABEL = "Online-Suche"
ONLINE_PENDING_MESSAGE = (
    "Die Online-Suche nach offenen Daten wird in einem späteren Schritt gebaut. "
    "Bitte vorerst „Lokale Daten“ verwenden."
)
LOCAL_DATA_HINT = (
    "Eine GeoPackage-Datei (.gpkg) von deinem Rechner, z. B. ALKIS-Daten. "
    "Pro Durchlauf wird eine Datei geladen."
)
CHOOSE_SOURCE_MESSAGE = "Bitte zuerst wählen, woher die Daten kommen: „Lokale Daten“ oder „Online-Suche“."
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


def format_hectares(hectares):
    text = f"{hectares:,.1f}"
    return text.replace(",", " ").replace(".", ",")


def objects_text(count):
    """'1 Objekt', '1 571 Objekte'."""
    return f"{format_count(count)} {'Objekt' if count == 1 else 'Objekte'}"


def done_hint_text(group_name):
    return (
        f"Du findest sie im Layer-Bedienfeld in der Gruppe „{group_name}“. "
        "„Erneut verarbeiten“ ersetzt diese Gruppe; andere Layer bleiben unberührt."
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
        ("Datenquelle", result.output.data_source or "– noch nicht eingetragen (Schritt 8)"),
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
    for descriptor in flow.result.selected_layers():
        name = result_layer_name(descriptor, names.layer)
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


def output_rows(output):
    def yes_no(flag, pending=False):
        if not flag:
            return "nein"
        return "ja (wird mit W8 angeschlossen)" if pending else "ja"

    return (
        ("Ergebnis-Layer in QGIS", "ja"),
        ("Bereinigtes GeoPackage", yes_no(output.save_cleaned_geopackage, pending=True)),
        ("PDF", yes_no(output.create_pdf, pending=True)),
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
        QgsGeometry,
        QgsProject,
        QgsSettings,
        QgsTask,
    )
    from qgis.gui import QgsDockWidget, QgsMapLayerComboBox, QgsProjectionSelectionWidget
    from qgis.PyQt.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer

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
    from qgis.PyQt.QtCore import QSize
    from .ui import style as ui_style
    from qgis.PyQt.QtWidgets import QMenu

    try:  # Qt6: actions live in QtGui
        from qgis.PyQt.QtGui import QAction, QActionGroup
    except ImportError:  # Qt5
        from qgis.PyQt.QtWidgets import QAction, QActionGroup
    from qgis.PyQt.QtWidgets import (
        QWIDGETSIZE_MAX,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
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

    class GuidedDock(QgsDockWidget):
        """Side panel that walks through the nine MVP steps."""

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
            button.setMenu(menu)
            self.style_menu = menu
            return button

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
            self.last_reports = None  # step 9 starts with the overview again
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
            self.primary_button.setText(PAGE_ACTIONS[index])
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
                self.next_message = None
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
        page.layout.addWidget(status)
        page.layout.addWidget(QLabel(UI_LABELS["buffer"]))
        page.layout.addWidget(buffer_input)
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
        try:
            geometry, count = chosen_area(page)
        except StudyAreaError as error:
            set_role(status, "hint")
            status.setText(str(error))
            return
        set_role(status, "status")
        status.setText(area_summary_text(count, geometry.area(), target_crs().authid()))

    def validate_area(page):
        try:
            geometry, _count = chosen_area(page)
        except StudyAreaError as error:
            return reject(str(error))
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
        )
        return True

    # 3 Daten laden: two choice buttons on top of each other; the chosen one
    # opens a panel below it (local: file chooser, online: later extension).
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
        page.layout.addWidget(button)
        page.layout.addWidget(panel)
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
        animation.setDuration(PANEL_ANIMATION_MS)
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

    def build_data(page):
        question = QLabel("Woher sollen die Daten kommen?")
        question.setWordWrap(True)
        page.layout.addWidget(question)

        local = choice_with_panel(page, "local", SOURCE_LOCAL_LABEL)
        local_hint = QLabel(LOCAL_DATA_HINT)
        local_hint.setWordWrap(True)
        set_role(local_hint, "hint")
        choose_button = QPushButton("Datei wählen …")
        set_role(choose_button, "secondary")
        choose_button.setCursor(Qt.PointingHandCursor)
        file_info = QLabel("Noch keine Datei gewählt.")
        file_info.setWordWrap(True)
        set_role(file_info, "hint")
        local.addWidget(local_hint)
        local.addWidget(choose_button)
        local.addWidget(file_info)

        online = choice_with_panel(page, "online", SOURCE_ONLINE_LABEL)
        online_hint = QLabel(ONLINE_PENDING_MESSAGE)
        online_hint.setWordWrap(True)
        set_role(online_hint, "hint")
        online.addWidget(online_hint)

        group = QButtonGroup(page.widget)
        group.setExclusive(True)
        group.addButton(page.widgets["local_button"])
        group.addButton(page.widgets["online_button"])
        page.widgets.update(
            group=group, choose_button=choose_button, file_info=file_info, path=None
        )
        choose_button.clicked.connect(lambda: choose_file(page))

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
        if widgets["online_button"].isChecked():
            dock.show_message(ONLINE_PENDING_MESSAGE, kind="info")
            return False
        if not widgets["local_button"].isChecked():
            if plugin.workflow is not None:
                return True  # data already passed in via the Python console
            return reject(CHOOSE_SOURCE_MESSAGE)
        if widgets["path"] is None:
            if plugin.workflow is not None:
                return True
            return reject(CHOOSE_FILE_MESSAGE)
        if not {"project_crs", "study_area_wkt", "buffer_meters"} <= set(dock.settings):
            return reject(MISSING_AREA_MESSAGE)
        start_import(widgets["path"])
        return False  # the page changes when the background import is done

    def start_import(path):
        """Run the pipeline (S1) as a QGIS background task with a busy bar."""
        settings = dict(dock.settings)
        dock.set_busy(f"Lade „{path.name}“ … Das kann bei großen Dateien etwas dauern.")

        def run_import(task):
            importer = GeoPackageImporter()
            options = {}
            if pipeline_reports_progress(importer):
                # fraction 0..1 from the pipeline -> task progress 0..100;
                # stops the pipeline when 'Laden abbrechen' was pressed
                options["progress"] = cancel_aware_progress(task.isCanceled, task.setProgress)
            if task.isCanceled():
                raise ImportCanceled()
            return importer.import_file(
                path,
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
                    if isinstance(exception, (GeoPackageImportError, ValueError, OSError)):
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
                dock.show_message(
                    f"„{path.name}“ geladen: {len(result.layers)} Layer. "
                    "Bitte die Prüfhinweise ansehen.",
                    kind="info",
                )
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
        text = QLabel(issue.message)
        text.setWordWrap(True)
        key = issue_icon_key(flow, issue)
        card_layout.addWidget(with_icon(key, text) if key else text)
        details = []
        if issue.rule:
            details.append(f"Regel: {issue.rule}")
        if issue.code in DECIDED_IN_HARMONIZATION:
            details.append("Entscheidung in Schritt 6 „Harmonisierung“")
        if details:
            meta = QLabel(" · ".join(details))
            meta.setWordWrap(True)
            set_role(meta, "hint")
            card_layout.addWidget(meta)
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

    # 5 Attributzuordnung: per layer "column -> target field" with examples
    def build_mapping(page):
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
        for layer_id, suggestions in groups.items():
            card = QFrame()
            set_role(card, "issue-info")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 8, 8)
            title = QLabel(names.layer(layer_id) if layer_id else "Ohne Layer-Angabe")
            font = title.font()
            font.setBold(True)
            title.setFont(font)
            card_layout.addWidget(with_icon(layer_icon_key(flow, layer_id), title))
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
                # long names are never cut off in a narrow panel.
                card_layout.addWidget(accepted)
                row = QHBoxLayout()
                row.setContentsMargins(INDENT_PX, 0, 0, 0)
                row.addWidget(arrow)
                row.addWidget(target, 1)
                card_layout.addLayout(row)
                detail = QLabel(mapping_detail_text(suggestion.source_field, suggestion.examples))
                detail.setWordWrap(True)
                set_role(detail, "hint")
                card_layout.addWidget(indented(detail))
                inputs.append((suggestion, accepted, target))
            page.layout.addWidget(card)
        page.widgets["inputs"] = inputs

    def validate_mapping(page):
        flow = workflow()
        decisions = {}
        for suggestion, accepted, target in page.widgets["inputs"]:
            decisions[(suggestion.layer_id, suggestion.source_field)] = (
                target.currentData() if accepted.isChecked() else False
            )
        try:
            flow.confirm_attribute_suggestions(decisions)
        except (KeyError, ValueError) as error:
            return reject(error_text(error))
        try:
            applied = flow.apply_attribute_decisions()
        except ValueError as error:  # e.g. a target field chosen twice
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
        for layer in layers:
            page.layout.addWidget(duplicate_card(flow, layer))

    def duplicate_card(flow, layer):
        card = QFrame()
        set_role(card, "issue-warning")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 8, 8)
        names = readable_names()
        descriptors = {d.layer_id: d for d in flow.result.layers}

        def result_label(layer_id):
            # same names as the result layers in step 9 (e.g. split
            # 'nutzung_flaechen' -> 'Nutzungsflächen')
            descriptor = descriptors.get(layer_id)
            if descriptor is None:
                return names.layer(layer_id)
            return result_layer_name(descriptor, names.layer)

        title = QLabel(
            duplicate_title_text(
                names.layer(layer.table_name), layer.group_count, layer.record_count
            )
        )
        title.setWordWrap(True)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        card_layout.addWidget(with_icon(layer_icon_key(flow, layer.table_name), title))
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
        keep_hint = QLabel("Alle Objekte bleiben erhalten.")
        merge = QRadioButton("Zusammenführen")
        merge_hint = QLabel(merge_hint_text(layer.removable_count))
        for button in (keep, merge):
            button.setCursor(Qt.PointingHandCursor)
        for hint in (keep_hint, merge_hint):
            hint.setWordWrap(True)
            set_role(hint, "hint")
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
        card_layout.addWidget(keep)
        card_layout.addWidget(indented(keep_hint))
        card_layout.addWidget(merge)
        card_layout.addWidget(indented(merge_hint))
        card._choice_group = choice  # keep the group alive with the card
        return card

    def validate_harmonization(_page):
        flow = workflow()
        open_layers = flow.open_duplicate_decisions()
        if open_layers:
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

    # 8 Ausgabe
    def build_output(page):
        geopackage = QCheckBox("Bereinigtes GeoPackage speichern")
        pdf = QCheckBox("PDF erzeugen")
        source = QLineEdit(workflow().result.output.data_source)
        page.layout.addWidget(geopackage)
        page.layout.addWidget(pdf)
        page.layout.addWidget(QLabel(UI_LABELS["data_source"]))
        page.layout.addWidget(source)
        page.widgets.update(geopackage=geopackage, pdf=pdf, source=source)

    def validate_output(page):
        try:
            workflow().choose_output(
                save_cleaned_geopackage=page.widgets["geopackage"].isChecked(),
                create_pdf=page.widgets["pdf"].isChecked(),
                data_source=page.widgets["source"].text(),
            )
        except ValueError as error:
            return reject(str(error))
        return True

    # 9 Verarbeitung starten: readable overview before, result list after
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

    def build_summary(page):
        flow = workflow()
        names = readable_names()
        if dock.last_reports is not None:
            done = QLabel(DONE_TITLE)
            done.setWordWrap(True)
            set_role(done, "status")
            page.layout.addWidget(done)
            page.layout.addWidget(summary_card(
                "Angelegte Ergebnis-Layer",
                result_rows(dock.last_reports,
                            {d.layer_id: d.category for d in flow.result.layers})))
            hint = QLabel(done_hint_text(result_group_name(flow.result.selected_topic)))
            hint.setWordWrap(True)
            set_role(hint, "hint")
            page.layout.addWidget(hint)
            return
        intro = QLabel(SUMMARY_INTRO)
        intro.setWordWrap(True)
        set_role(intro, "hint")
        page.layout.addWidget(intro)
        page.layout.addWidget(summary_card(
            "Grundlagen", overview_rows(flow, study_area_hectares(flow.result), names)))
        page.layout.addWidget(summary_card(
            "Diese Ergebnis-Layer werden angelegt", planned_layer_rows(flow, names)))
        page.layout.addWidget(summary_card("Ausgabe", output_rows(flow.result.output)))

    def validate_summary(page):
        """'Verarbeitung starten': build the result layers and add them to QGIS."""
        flow = workflow()
        selected = flow.result.selected_layers()
        if not selected:
            return reject(
                "Für das Kartenthema ist kein Layer ausgewählt. Bitte in Schritt 7 "
                "mindestens eine Kategorie ankreuzen."
            )
        try:
            # Current decisions of step 5 (and step 6) on the data (S5).
            flow.apply_attribute_decisions()
        except ValueError as error:
            return reject(error_text(error))
        try:
            from .mapping import readable_layer
        except ImportError:
            readable_layer = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layer_objects, reports = build_result_layers(flow.result, selected, readable_layer)
            add_result_layers(layer_objects, result_group_name(flow.result.selected_topic))
        finally:
            QApplication.restoreOverrideCursor()
        plugin.result_layers = layer_objects
        # Switch the page to "Fertig" with the list of created layers.
        dock.last_reports = reports
        page.build()
        make_texts_selectable(page.widget)
        QTimer.singleShot(0, dock.fit_wrapped_labels)
        dock.primary_button.setText(RERUN_ACTION)
        text = result_layers_text(reports)
        if flow.result.output.save_cleaned_geopackage or flow.result.output.create_pdf:
            text += "\n" + EXPORT_PENDING_MESSAGE
        dock.show_message(text, kind="info")
        dock.mark_all_done()
        return False  # last step: stay here

    crs_page = dock.add_page(build_crs, validate_crs)
    dock.add_page(build_area, validate_area, on_show=update_area_status)
    dock.add_page(build_data, validate_data)
    dock.add_page(build_review, validate_review, rebuild=True)
    dock.add_page(build_mapping, validate_mapping, rebuild=True)
    dock.add_page(build_harmonization, validate_harmonization, rebuild=True)
    dock.add_page(build_topic, validate_topic, rebuild=True)
    dock.add_page(build_output, validate_output, rebuild=True)
    dock.add_page(build_summary, validate_summary, rebuild=True)
    dock.show_page(0)
    return dock
