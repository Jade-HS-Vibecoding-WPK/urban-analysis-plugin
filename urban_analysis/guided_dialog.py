"""QGIS wizard for the contract-defined nine-step user guidance."""

from .contracts import MVP_UI_STEPS
from .ui_contract import UI_LABELS


def show_guided_dialog(plugin):
    """Show and apply a guided wizard for the active workflow."""
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtWidgets import (
        QCheckBox,
        QDoubleSpinBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPlainTextEdit,
        QVBoxLayout,
        QWizard,
        QWizardPage,
    )

    class WorkflowPage(QWizardPage):
        def __init__(self):
            super().__init__()
            self.validator = None

        def validatePage(self):
            return self.validator() if self.validator is not None else True

    workflow = plugin._require_workflow()
    wizard = QWizard(plugin.iface.mainWindow())
    wizard.setWindowTitle("Urban Analysis - Benutzerführung")

    def page(title):
        result = WorkflowPage()
        result.setTitle(title)
        result._layout = QVBoxLayout(result)
        wizard.addPage(result)
        return result

    project_page = page(MVP_UI_STEPS[0])
    crs_input = QLineEdit(workflow.result.project_crs)
    project_page._layout.addWidget(QLabel("Projekt-CRS"))
    project_page._layout.addWidget(crs_input)

    area_page = page(MVP_UI_STEPS[1])
    area_input = QPlainTextEdit(workflow.result.study_area_wkt)
    buffer_input = QDoubleSpinBox()
    buffer_input.setRange(0, 1000000)
    buffer_input.setValue(workflow.result.buffer_meters)
    area_page._layout.addWidget(QLabel("Untersuchungsgebiet (WKT-Polygon)"))
    area_page._layout.addWidget(area_input)
    area_page._layout.addWidget(QLabel(UI_LABELS["buffer"]))
    area_page._layout.addWidget(buffer_input)

    data_page = page(MVP_UI_STEPS[2])
    data_page._layout.addWidget(
        QLabel("Die Daten werden von der Datenpipeline bereitgestellt.")
    )

    review_page = page(MVP_UI_STEPS[3])
    review_page._layout.addWidget(QLabel("Prüfhinweise aus der Datenpipeline:"))
    review_page._layout.addWidget(
        QLabel(
            "\n".join(issue.message for issue in workflow.result.visible_issues())
            or "Keine Prüfhinweise."
        )
    )

    mapping_page = page(MVP_UI_STEPS[4])
    mapping_inputs = []
    for suggestion in workflow.attribute_suggestions():
        accepted = QCheckBox(suggestion.source_field)
        accepted.setChecked(suggestion.accepted is not False)
        target = QLineEdit(suggestion.user_value or suggestion.target_field)
        mapping_page._layout.addWidget(accepted)
        mapping_page._layout.addWidget(target)
        mapping_inputs.append((suggestion, accepted, target))

    harmonization_page = page(MVP_UI_STEPS[5])
    harmonization_page._layout.addWidget(
        QLabel("Unsichere Dopplungen und Harmonisierung bleiben vor der Verarbeitung sichtbar.")
    )

    topic_page = page(MVP_UI_STEPS[6])
    topic_input = QLineEdit(workflow.result.selected_topic or "Siedlungsstruktur")
    category_list = QListWidget()
    categories = workflow.recognized_categories()
    for category in categories:
        item = QListWidgetItem(category)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        category_list.addItem(item)
    confirm_missing = QCheckBox(UI_LABELS["continue_incomplete"])
    topic_page._layout.addWidget(QLabel("Kartenthema"))
    topic_page._layout.addWidget(topic_input)
    topic_page._layout.addWidget(category_list)
    topic_page._layout.addWidget(confirm_missing)

    output_page = page(MVP_UI_STEPS[7])
    geopackage = QCheckBox("Bereinigtes GeoPackage speichern")
    pdf = QCheckBox("PDF erzeugen")
    source = QLineEdit(workflow.result.output.data_source)
    output_page._layout.addWidget(geopackage)
    output_page._layout.addWidget(pdf)
    output_page._layout.addWidget(QLabel(UI_LABELS["data_source"]))
    output_page._layout.addWidget(source)

    summary_page = page(MVP_UI_STEPS[8])
    summary = QLabel()
    summary.setWordWrap(True)
    summary_page._layout.addWidget(summary)

    def reject(message):
        QMessageBox.warning(wizard, "Eingabe prüfen", message)
        return False

    def validate_project(_page):
        try:
            workflow.configure_project(
                project_crs=crs_input.text(),
                study_area_wkt=area_input.toPlainText(),
                buffer_meters=buffer_input.value(),
            )
        except ValueError as error:
            return reject(str(error))
        return True

    def validate_mapping(_page):
        decisions = {}
        for suggestion, accepted, target in mapping_inputs:
            decisions[suggestion.source_field] = (
                target.text() if accepted.isChecked() else False
            )
        try:
            workflow.confirm_attribute_suggestions(decisions)
        except (KeyError, ValueError) as error:
            return reject(str(error))
        return True

    def validate_topic(_page):
        selected = tuple(
            category_list.item(index).text()
            for index in range(category_list.count())
            if category_list.item(index).checkState()
        )
        try:
            workflow.select_topic(
                topic_input.text(),
                selected,
                confirm_missing=confirm_missing.isChecked(),
            )
        except ValueError as error:
            return reject(str(error))
        return True

    def validate_output(_page):
        try:
            workflow.choose_output(
                save_cleaned_geopackage=geopackage.isChecked(),
                create_pdf=pdf.isChecked(),
                data_source=source.text(),
            )
        except ValueError as error:
            return reject(str(error))
        summary.setText(str(workflow.summary()))
        return True

    project_page.validator = lambda: validate_project(project_page)
    mapping_page.validator = lambda: validate_mapping(mapping_page)
    topic_page.validator = lambda: validate_topic(topic_page)
    output_page.validator = lambda: validate_output(output_page)
    return wizard.exec_()
