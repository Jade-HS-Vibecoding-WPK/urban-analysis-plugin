"""QGIS side panel for the contract-defined nine-step user guidance.

The guidance lives in a dock widget on the right side of QGIS, so it can stay
open, be hidden via the toolbar button or be undocked while working in QGIS.

Pages 1-3 (Projekt-CRS, Untersuchungsgebiet, Daten laden) work without a
``PipelineResult``.  Pages 4-9 are rebuilt every time they are reached, so
they always reflect the data that is currently loaded.
"""

from pathlib import Path

from .contracts import MVP_DEFAULT_BUFFER_METERS, MVP_UI_STEPS
from .data_pipeline import GeoPackageImporter, GeoPackageImportError
from .outputs import (
    add_result_layers,
    build_result_layers,
    result_group_name,
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
    LAMP_FILES,
    LAMP_SIZE_PX,
    busy_chunk_stylesheet,
    icon_path,
    panel_stylesheet,
    set_role,
)
from .ui_contract import UI_LABELS
from .user_guidance import (
    DECIDED_IN_HARMONIZATION,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    describe_group,
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
BUSY_TICK_MS = 120
BUSY_SHINE_STEP = 0.06
PROGRESS_MARGIN_PX = 10
RESET_TOOLTIP = "Plugin auf Anfang zurücksetzen: alle Eingaben und geladenen Daten verwerfen."
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


def cross_layer_warning_text(count):
    """Hint for groups whose objects lie in different result layers."""
    return (
        f"Achtung: {count} Gruppe(n) liegen in verschiedenen Ergebnis-Layern "
        "(z. B. einmal als Straße, einmal als Weg). Beim Zusammenführen bleibt nur "
        "das erste Objekt – das andere fehlt dann in seiner Kategorie."
    )


def duplicates_applied_text(removed):
    """Feedback after step 6."""
    if removed == 0:
        return "Entscheidung übernommen: Alle Objekte bleiben erhalten."
    noun = "Objekt" if removed == 1 else "Objekte"
    return f"Entscheidung übernommen: {removed} {noun} durch Zusammenführen entfernt."
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


def lamp_state(step_index, current_index, pulse_on=False):
    """Lamp of a step: 'on' when done, 'dim' for the current step, else 'off'.

    While a long step runs without known progress, the current lamp pulses
    (``pulse_on``) between 'dim' and 'on'.
    """
    if step_index < current_index:
        return "on"
    if step_index == current_index:
        return "on" if pulse_on else "dim"
    return "off"


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
    """Return the overall progress label for the page at ``index``."""
    return f"Schritt {index + 1} von {len(MVP_UI_STEPS)} – {MVP_UI_STEPS[index]}"


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
        QgsProject,
        QgsSettings,
        QgsTask,
    )
    from qgis.gui import QgsDockWidget, QgsMapLayerComboBox, QgsProjectionSelectionWidget
    from qgis.PyQt.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
    from qgis.PyQt.QtGui import QIcon
    from qgis.PyQt.QtWidgets import (
        QWIDGETSIZE_MAX,
        QApplication,
        QButtonGroup,
        QCheckBox,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSizePolicy,
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
            self.all_done = False  # all lamps on after "Verarbeitung starten"

            # The whole plugin shares one style (theme.py).
            self.setStyleSheet(panel_stylesheet())
            body = QWidget()
            layout = QVBoxLayout(body)

            self.step_label = QLabel()
            self.step_label.setWordWrap(True)
            set_role(self.step_label, "heading")
            self.reset_button = QPushButton("↺ Zurücksetzen")
            set_role(self.reset_button, "secondary")
            self.reset_button.setCursor(Qt.PointingHandCursor)
            self.reset_button.setToolTip(RESET_TOOLTIP)
            self.reset_button.clicked.connect(self.ask_reset)
            header = QHBoxLayout()
            header.addWidget(self.step_label, 1)
            header.addWidget(self.reset_button, 0, Qt.AlignTop)

            # Overall progress: one lamp per step up to the map
            # (off = open, dim = current step, on = done).
            self.lamp_pixmaps = {
                state: QIcon(icon_path(name)).pixmap(LAMP_SIZE_PX, LAMP_SIZE_PX)
                for state, name in LAMP_FILES.items()
            }
            self.step_lamps = []
            progress_row = QHBoxLayout()
            progress_row.setContentsMargins(0, PROGRESS_MARGIN_PX, 0, PROGRESS_MARGIN_PX)
            progress_row.setSpacing(6)
            for index, step in enumerate(MVP_UI_STEPS):
                lamp = QLabel()
                lamp.setFixedSize(LAMP_SIZE_PX, LAMP_SIZE_PX)
                lamp.setToolTip(f"{index + 1}. {step}")
                lamp.setPixmap(self.lamp_pixmaps["off"])
                progress_row.addWidget(lamp)
                self.step_lamps.append(lamp)
            progress_row.addStretch()
            self.pulse_on = False

            # Busy bar for long steps: fills once with the real progress (if the
            # pipeline reports it); only the loaded part shimmers. While no
            # progress is known, the current lamp pulses so QGIS looks alive.
            self.busy_label = QLabel()
            self.busy_label.setWordWrap(True)
            set_role(self.busy_label, "status")
            self.busy_bar = QProgressBar()
            self.busy_bar.setRange(0, 100)
            self.busy_bar.setTextVisible(False)
            self.busy_text = ""
            self.busy_progress_known = False
            self.busy_phase = 0.0
            self.busy_timer = QTimer(self)
            self.busy_timer.setInterval(BUSY_TICK_MS)
            self.busy_timer.timeout.connect(self._advance_busy)
            self.busy_label.hide()
            self.busy_bar.hide()

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

            self.back_button = QPushButton("Zurück")
            set_role(self.back_button, "secondary")
            self.back_button.setCursor(Qt.PointingHandCursor)
            self.back_button.clicked.connect(self.go_back)
            self.primary_button = QPushButton()
            self.primary_button.setObjectName("uaPrimaryButton")
            set_role(self.primary_button, "primary")
            self.primary_button.setCursor(Qt.PointingHandCursor)
            self.primary_button.clicked.connect(self.run_primary_action)
            buttons = QHBoxLayout()
            buttons.addWidget(self.back_button)
            buttons.addStretch()
            buttons.addWidget(self.primary_button)

            layout.addLayout(header)
            layout.addLayout(progress_row)
            layout.addWidget(self.busy_label)
            layout.addWidget(self.busy_bar)
            layout.addWidget(scroll, 1)
            layout.addWidget(self.message_scroll)
            layout.addLayout(buttons)
            make_texts_selectable(body)
            self.setWidget(body)

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
            self.step_label.setText(progress_text(index))
            self.update_lamps()
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

        def update_lamps(self):
            """Lamps before the current step are on, the current one glows.

            After a successful processing run all lamps are on.
            """
            current = len(self.step_lamps) if self.all_done else self.current
            for index, lamp in enumerate(self.step_lamps):
                lamp.setPixmap(self.lamp_pixmaps[lamp_state(index, current, self.pulse_on)])

        def mark_all_done(self):
            self.all_done = True
            self.update_lamps()

        def set_busy(self, text):
            """Show the busy bar and lock the panel while a step runs."""
            self.busy_text = text
            self.busy_progress_known = False
            self.busy_phase = 0.0
            self.busy_bar.setValue(0)
            self.busy_label.setText(busy_label_text(text, None))
            self.busy_label.show()
            self.busy_bar.show()
            self.busy_timer.start()
            self.primary_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            self.stack.setEnabled(False)

        def set_busy_progress(self, percent):
            """Real progress from the background task (0-100)."""
            self.busy_progress_known = True
            self.busy_bar.setValue(int(percent))
            self.busy_label.setText(busy_label_text(self.busy_text, percent))

        def clear_busy(self):
            self.busy_timer.stop()
            self.pulse_on = False
            self.update_lamps()
            self.busy_label.hide()
            self.busy_bar.hide()
            self.stack.setEnabled(True)
            self.primary_button.setEnabled(True)
            self.back_button.setEnabled(self.current > 0)
            self.reset_button.setEnabled(True)

        def _advance_busy(self):
            # Shine moves across the loaded part of the bar only.
            self.busy_phase = (self.busy_phase + BUSY_SHINE_STEP) % 1.0
            self.busy_bar.setStyleSheet(busy_chunk_stylesheet(self.busy_phase))
            if not self.busy_progress_known:
                # Unknown progress: the current lamp pulses between dim and on.
                self.pulse_on = not self.pulse_on
                self.update_lamps()

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
            self.busy_timer.stop()
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
                # fraction 0..1 from the pipeline -> task progress 0..100
                options["progress"] = lambda fraction: task.setProgress(fraction * 100)
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
                dock.clear_busy()
                if exception is not None:
                    if isinstance(exception, (GeoPackageImportError, ValueError, OSError)):
                        dock.show_message(import_error_text(path.name, exception, path))
                    else:
                        dock.show_unexpected_error(UI_LABELS["load_data"], exception)
                    return
                if result is None:
                    dock.show_message("Das Laden wurde abgebrochen.", kind="info")
                    return
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
        card_layout.addWidget(text)
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

    # 5 Attributzuordnung
    def build_mapping(page):
        inputs = []
        for suggestion in workflow().attribute_suggestions():
            accepted = QCheckBox(suggestion.source_field)
            accepted.setChecked(suggestion.accepted is not False)
            target = QLineEdit(suggestion.user_value or suggestion.target_field)
            page.layout.addWidget(accepted)
            page.layout.addWidget(target)
            inputs.append((suggestion, accepted, target))
        page.widgets["inputs"] = inputs

    def validate_mapping(page):
        decisions = {}
        for suggestion, accepted, target in page.widgets["inputs"]:
            decisions[suggestion.source_field] = (
                target.text() if accepted.isChecked() else False
            )
        try:
            workflow().confirm_attribute_suggestions(decisions)
        except (KeyError, ValueError) as error:
            return reject(error_text(error))
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
        title = QLabel(
            f"{layer.table_name}: {layer.group_count} Gruppe(n) mit "
            f"{layer.record_count} Objekten"
        )
        title.setWordWrap(True)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        card_layout.addWidget(title)
        for group, records in layer.groups[:DUPLICATE_EXAMPLES]:
            example = QLabel(f"• {describe_group(records)}")
            example.setWordWrap(True)
            set_role(example, "hint")
            card_layout.addWidget(example)
        if layer.group_count > DUPLICATE_EXAMPLES:
            more = QLabel(f"… und {layer.group_count - DUPLICATE_EXAMPLES} weitere Gruppe(n)")
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
        merge_hint = QLabel(
            f"Je Gruppe bleibt das erste Objekt, {layer.removable_count} Objekte "
            "werden entfernt."
        )
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
                "Noch offen: " + ", ".join(open_layers)
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
        for category in workflow().recognized_categories():
            item = QListWidgetItem(category)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            category_list.addItem(item)
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

    # 9 Verarbeitung starten
    def build_summary(page):
        summary = QLabel(str(workflow().summary()))
        summary.setWordWrap(True)
        page.layout.addWidget(summary)

    def validate_summary(_page):
        """'Verarbeitung starten': build the result layers and add them to QGIS."""
        flow = workflow()
        selected = flow.result.selected_layers()
        if not selected:
            return reject(
                "Für das Kartenthema ist kein Layer ausgewählt. Bitte in Schritt 7 "
                "mindestens eine Kategorie ankreuzen."
            )
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
