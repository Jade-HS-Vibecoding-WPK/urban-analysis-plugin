"""QGIS side panel for the contract-defined nine-step user guidance.

The guidance lives in a dock widget on the right side of QGIS, so it can stay
open, be hidden via the toolbar button or be undocked while working in QGIS.

Pages 1-3 (Projekt-CRS, Untersuchungsgebiet, Daten laden) work without a
``PipelineResult``.  Pages 4-9 are rebuilt every time they are reached, so
they always reflect the data that is currently loaded.
"""

from .contracts import MVP_DEFAULT_BUFFER_METERS, MVP_UI_STEPS
from .study_area import (
    DRAW_INSTRUCTIONS,
    StudyAreaError,
    add_drawn_area_layer,
    area_summary_text,
    create_polygon_draw_tool,
    study_area_from_layer,
)
from .theme import panel_stylesheet, set_role
from .ui_contract import UI_LABELS


DOCK_OBJECT_NAME = "UrbanAnalysisDock"
NO_DATA_MESSAGE = "Noch keine Daten geladen. Bitte zuerst ein GeoPackage laden."
OUTPUT_PENDING_MESSAGE = (
    "Die Ausgabe in QGIS (Ergebnis-Layer, GeoPackage, PDF) wird in einem "
    "späteren Schritt angeschlossen (ARBEITSPLAN W6/W8)."
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
    "Weiter",
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
    "Eigene GeoPackage-Datei (.gpkg) von deinem Rechner. Dateiauswahl und Start "
    "der Datenpipeline folgen im nächsten Schritt (ARBEITSPLAN W4)."
)
BUSY_TICK_MS = 120
INDENT_PX = 22
MIN_CONTENT_WIDTH = 300
MESSAGE_MAX_HEIGHT = 140


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
    from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsProject
    from qgis.gui import QgsDockWidget, QgsMapLayerComboBox, QgsProjectionSelectionWidget
    from qgis.PyQt.QtCore import Qt, QTimer
    from qgis.PyQt.QtWidgets import (
        QButtonGroup,
        QCheckBox,
        QDoubleSpinBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
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

            # The whole plugin shares one style (theme.py).
            self.setStyleSheet(panel_stylesheet())
            body = QWidget()
            layout = QVBoxLayout(body)

            self.step_label = QLabel()
            self.step_label.setWordWrap(True)
            set_role(self.step_label, "heading")

            # Overall progress: one block per step up to the map.
            self.step_blocks = []
            progress_row = QHBoxLayout()
            progress_row.setSpacing(3)
            for index, step in enumerate(MVP_UI_STEPS):
                block = QFrame()
                block.setFixedSize(26, 8)
                block.setToolTip(f"{index + 1}. {step}")
                set_role(block, "step-todo")
                progress_row.addWidget(block)
                self.step_blocks.append(block)
            progress_row.addStretch()

            # Busy indicator for long steps (used from W4 on). A timer moves
            # the blocks, so it is visible that QGIS is still working.
            self.busy_label = QLabel()
            set_role(self.busy_label, "status")
            self.busy_bar = QProgressBar()
            self.busy_bar.setRange(0, 12)
            self.busy_bar.setTextVisible(False)
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

            layout.addWidget(self.step_label)
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
            self.scroll.verticalScrollBar().setValue(0)
            self.scroll.horizontalScrollBar().setValue(0)
            for page_index, other in enumerate(self.pages):
                other.widget.setVisible(page_index == index)
            self.step_label.setText(progress_text(index))
            for block_index, block in enumerate(self.step_blocks):
                if block_index < index:
                    set_role(block, "step-done")
                elif block_index == index:
                    set_role(block, "step-current")
                else:
                    set_role(block, "step-todo")
            self.primary_button.setText(PAGE_ACTIONS[index])
            self.back_button.setEnabled(index > 0)
            self.clear_message()

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

        def clear_message(self):
            self.message.clear()
            self.message_scroll.hide()

        def set_busy(self, text):
            """Show the moving busy bar and block navigation."""
            self.busy_label.setText(text)
            self.busy_bar.setValue(0)
            self.busy_label.show()
            self.busy_bar.show()
            self.busy_timer.start()
            self.primary_button.setEnabled(False)
            self.back_button.setEnabled(False)

        def clear_busy(self):
            self.busy_timer.stop()
            self.busy_label.hide()
            self.busy_bar.hide()
            self.primary_button.setEnabled(True)
            self.back_button.setEnabled(self.current > 0)

        def _advance_busy(self):
            value = self.busy_bar.value() + 1
            self.busy_bar.setValue(0 if value > self.busy_bar.maximum() else value)

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
    # current QGIS project.
    existing = plugin.workflow.result if plugin.workflow is not None else None

    # 1 Projekt-CRS
    def build_crs(page):
        crs_widget = QgsProjectionSelectionWidget()
        crs_widget.setCrs(
            QgsCoordinateReferenceSystem(existing.project_crs)
            if existing
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
            existing.buffer_meters if existing else MVP_DEFAULT_BUFFER_METERS
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

    # 3 Daten laden: local GeoPackage (W4) or online search (later extension)
    def build_data(page):
        use_local = QRadioButton(SOURCE_LOCAL_LABEL)
        use_online = QRadioButton(SOURCE_ONLINE_LABEL)
        use_local.setChecked(True)
        group = QButtonGroup(page.widget)
        group.addButton(use_local)
        group.addButton(use_online)
        local_hint = QLabel(LOCAL_DATA_HINT)
        local_hint.setWordWrap(True)
        set_role(local_hint, "hint")
        online_hint = QLabel(ONLINE_PENDING_MESSAGE)
        online_hint.setWordWrap(True)
        set_role(online_hint, "hint")

        question = QLabel("Woher sollen die Daten kommen?")
        question.setWordWrap(True)
        page.layout.addWidget(question)
        page.layout.addWidget(use_local)
        page.layout.addWidget(indented(local_hint))
        page.layout.addWidget(use_online)
        page.layout.addWidget(indented(online_hint))
        page.widgets.update(
            use_local=use_local,
            use_online=use_online,
            group=group,
            local_hint=local_hint,
            online_hint=online_hint,
        )

        def refresh(*_args):
            local_hint.setVisible(use_local.isChecked())
            online_hint.setVisible(use_online.isChecked())

        use_local.toggled.connect(refresh)
        refresh()

    def validate_data(page):
        if page.widgets["use_online"].isChecked():
            return reject(ONLINE_PENDING_MESSAGE)
        if plugin.workflow is None:
            return reject(NO_DATA_MESSAGE)
        return True

    # 4 Layer prüfen
    def build_review(page):
        page.layout.addWidget(QLabel("Prüfhinweise aus der Datenpipeline:"))
        messages = QLabel(
            "\n".join(issue.message for issue in workflow().result.visible_issues())
            or "Keine Prüfhinweise."
        )
        messages.setWordWrap(True)
        page.layout.addWidget(messages)

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

    # 6 Harmonisierung
    def build_harmonization(page):
        label = QLabel(
            "Unsichere Dopplungen und Harmonisierung bleiben vor der "
            "Verarbeitung sichtbar."
        )
        label.setWordWrap(True)
        page.layout.addWidget(label)

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
        dock.show_message(OUTPUT_PENDING_MESSAGE, kind="info")
        return False

    crs_page = dock.add_page(build_crs, validate_crs)
    dock.add_page(build_area, validate_area, on_show=update_area_status)
    dock.add_page(build_data, validate_data)
    dock.add_page(build_review, rebuild=True)
    dock.add_page(build_mapping, validate_mapping, rebuild=True)
    dock.add_page(build_harmonization, rebuild=True)
    dock.add_page(build_topic, validate_topic, rebuild=True)
    dock.add_page(build_output, validate_output, rebuild=True)
    dock.add_page(build_summary, validate_summary, rebuild=True)
    dock.show_page(0)
    return dock
