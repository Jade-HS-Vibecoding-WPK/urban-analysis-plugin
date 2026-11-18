"""W8b: step 8 save locations and data source, step 9 saving (QGIS-free parts)."""

import os
from datetime import date
from pathlib import Path

from urban_analysis.contracts import OutputSelection
from urban_analysis.guided_dialog import (
    DATA_SOURCE_REQUIRED_MESSAGE,
    MISSING_PATH_MESSAGES,
    default_output_path,
    output_choice_problem,
    output_path_text,
    output_rows,
    output_slug,
    saved_rows,
    short_folder,
    with_output_suffix,
)
from urban_analysis.outputs import unique_layer_names, write_minimal_pdf


def test_slug_is_safe_for_file_names():
    assert output_slug("Siedlungsstruktur") == "siedlungsstruktur"
    assert output_slug("Grün- und Freiflächen") == "gruen_und_freiflaechen"
    assert output_slug(None) == "ergebnis"
    assert output_slug("???") == "ergebnis"


def test_default_path_has_topic_date_and_suffix(tmp_path):
    day = date(2026, 11, 18)
    assert default_output_path(tmp_path, "Siedlungsstruktur", "geopackage", day) == (
        tmp_path / "urban_analysis_siedlungsstruktur_2026-11-18.gpkg"
    )
    assert default_output_path(tmp_path, None, "pdf", day).name == "urban_analysis_ergebnis_2026-11-18.pdf"


def test_suffix_is_added_only_when_missing():
    assert with_output_suffix("C:/x/karte", "pdf") == Path("C:/x/karte.pdf")
    assert with_output_suffix("C:/x/karte.PDF", "pdf") == Path("C:/x/karte.PDF")
    assert with_output_suffix("C:/x/daten.v2", "geopackage") == Path("C:/x/daten.v2.gpkg")


def test_data_source_is_always_required():
    problem = output_choice_problem(geopackage=False, pdf=False, paths={}, data_source="  ")
    assert problem == DATA_SOURCE_REQUIRED_MESSAGE


def test_each_chosen_output_needs_a_save_location():
    common = dict(data_source="ALKIS")
    assert output_choice_problem(geopackage=True, pdf=False, paths={}, **common) == (
        MISSING_PATH_MESSAGES["geopackage"]
    )
    assert output_choice_problem(geopackage=False, pdf=True, paths={"geopackage": "a.gpkg"}, **common) == (
        MISSING_PATH_MESSAGES["pdf"]
    )
    assert output_choice_problem(
        geopackage=True, pdf=True, paths={"geopackage": "a.gpkg", "pdf": "a.pdf"}, **common
    ) is None
    # an unticked output does not need a path
    assert output_choice_problem(geopackage=False, pdf=False, paths={}, **common) is None


def test_existing_file_is_only_replaced_after_the_save_dialog(tmp_path):
    existing = tmp_path / "ergebnis.gpkg"
    existing.write_bytes(b"alt")
    choice = dict(geopackage=True, pdf=False, paths={"geopackage": existing}, data_source="ALKIS")
    problem = output_choice_problem(**choice)
    assert "ergebnis.gpkg" in problem and "gibt es schon" in problem
    assert output_choice_problem(confirmed={"geopackage"}, **choice) is None


def test_overview_shows_chosen_file_names():
    output = OutputSelection(save_cleaned_geopackage=True, create_pdf=True, data_source="ALKIS")
    rows = dict(output_rows(output, {"geopackage": Path("C:/daten/ergebnis.gpkg")}))
    assert rows["Ergebnis-Layer in QGIS"] == "ja"
    assert rows["Bereinigtes GeoPackage"] == "ja – ergebnis.gpkg"
    assert rows["PDF"] == "ja – Speicherort fehlt (Schritt 8)"
    rows = dict(output_rows(OutputSelection()))
    assert rows["Bereinigtes GeoPackage"] == "nein"
    assert rows["PDF"] == "nein"


def test_saved_rows_name_file_and_folder():
    rows = saved_rows([("geopackage", Path("C:/daten/ergebnis.gpkg"))])
    assert rows[0][0] == "GeoPackage"
    assert rows[0][1].startswith("ergebnis.gpkg – im Ordner ")


def test_long_folders_are_shortened_to_the_last_two():
    long = Path("C:/Users/name/Documents/Studium/Projekt/Ausgabe")
    assert short_folder(long) == "…" + os.sep + str(Path("Projekt/Ausgabe"))
    assert short_folder(Path("C:/daten")) == str(Path("C:/daten"))
    text = output_path_text(long / "karte.pdf")
    assert text.startswith("karte.pdf\nim Ordner …")


def test_geopackage_layer_names_are_unique():
    assert unique_layer_names(["Gebäude", "Straßen", "gebäude", ""]) == [
        "Gebäude", "Straßen", "gebäude (2)", "Ergebnis",
    ]


def test_simple_pdf_keeps_umlauts_and_shortens_long_areas(tmp_path):
    target = tmp_path / "karte.pdf"
    write_minimal_pdf(
        target,
        title="Urban Analysis - Siedlungsstruktur",
        study_area_wkt="POLYGON ((" + ", ".join(f"{i} {i}" for i in range(500)) + "))",
        buffer_meters=500,
        legend=("Gebäude", "Grünflächen"),
        data_source="ALKIS Stadt Oldenburg",
    )
    content = target.read_bytes()
    assert "Gebäude, Grünflächen".encode("cp1252") in content
    assert b"WinAnsiEncoding" in content
    assert b"499 499" not in content  # long polygon shortened
