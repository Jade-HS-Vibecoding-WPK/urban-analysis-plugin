import sys
import types

from urban_analysis.contracts import LayerDescriptor, PipelineResult


def load_plugin(monkeypatch):
    class FakeAction:
        def __init__(self, *args):
            self.triggered = types.SimpleNamespace(connect=lambda callback: None)

        def setObjectName(self, name):
            self.object_name = name

        def deleteLater(self):
            pass

    qtwidgets = types.SimpleNamespace(QAction=FakeAction)
    monkeypatch.setitem(sys.modules, "qgis", types.ModuleType("qgis"))
    monkeypatch.setitem(sys.modules, "qgis.PyQt", types.ModuleType("qgis.PyQt"))
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtWidgets", qtwidgets)
    from urban_analysis.urban_analysis_plugin import UrbanAnalysisPlugin

    return UrbanAnalysisPlugin


def test_plugin_connects_pipeline_result_to_guided_workflow_and_output_plan(monkeypatch):
    UrbanAnalysisPlugin = load_plugin(monkeypatch)
    plugin = UrbanAnalysisPlugin(iface=None)
    result = PipelineResult(
        contract_version="1.0",
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON EMPTY",
        layers=[
            LayerDescriptor("buildings", "Gebäude", "Polygon", "input.gpkg", category="Gebäude")
        ],
    )

    workflow = plugin.start_workflow(result)
    assert workflow.current_step == "Projekt-CRS"
    assert plugin.advance_workflow() == "Untersuchungsgebiet"
    selected = plugin.select_topic(
        "Siedlungsstruktur", categories=("Gebäude",), confirm_missing=True
    )
    plugin.choose_output(save_cleaned_geopackage=True)

    assert workflow.result is result
    assert [layer.layer_id for layer in selected] == ["buildings"]
    assert plugin.output_plan().qgis_layer_ids == ("buildings",)
    assert plugin.output_plan().geopackage_requested is True
