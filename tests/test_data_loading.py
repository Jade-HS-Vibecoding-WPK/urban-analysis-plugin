"""Texts of step 3 'Daten laden' (ARBEITSPLAN W4); the QGIS part is tested live."""

import pytest

from urban_analysis.data_pipeline import GeoPackageImporter, GeoPackageImportError
from urban_analysis.guided_dialog import (
    ARROW_CLOSED,
    ARROW_OPEN,
    CANCELED_MESSAGE,
    FILE_DIALOG_FILTER,
    ImportCanceled,
    cancel_aware_progress,
    choice_label,
    file_summary_text,
    format_megabytes,
    import_error_text,
)


def test_progress_is_passed_on_while_not_canceled():
    shown = []
    progress = cancel_aware_progress(lambda: False, shown.append)
    progress(0.0)
    progress(0.5)
    assert shown == [0.0, 50.0]


def test_cancel_stops_the_pipeline_at_its_next_progress_report(tmp_path):
    from test_data_pipeline import make_many_points_geopackage

    path = tmp_path / "points.gpkg"
    make_many_points_geopackage(path, 5000)
    calls = []

    def canceled():
        calls.append(1)
        return len(calls) > 3  # the user presses 'Laden abbrechen' meanwhile

    with pytest.raises(ImportCanceled):
        GeoPackageImporter().import_file(
            path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))",
            buffer_meters=0,
            progress=cancel_aware_progress(canceled, lambda percent: None),
        )
    assert len(calls) == 4  # stopped right away, not at the end


def test_cancel_message_says_what_to_do_next():
    assert "abgebrochen" in CANCELED_MESSAGE and "andere Datei" in CANCELED_MESSAGE


def test_file_size_is_shown_in_megabytes_with_german_comma():
    assert format_megabytes(367_001_600) == "350,0 MB"
    assert format_megabytes(1_572_864) == "1,5 MB"


def test_file_summary_names_file_size_and_folder():
    text = file_summary_text("lkr_03403_Stadt_Oldenburg_kon.gpkg", "C:/Daten", 1_572_864)
    assert text == "lkr_03403_Stadt_Oldenburg_kon.gpkg – 1,5 MB\nOrdner: C:/Daten"
    # file_summary_text is shown in a selectable label, so it must be plain text


def test_import_errors_name_the_file_the_reason_and_what_to_do():
    text = import_error_text("kaputt.gpkg", GeoPackageImportError("file is not a database"))
    assert "„kaputt.gpkg“ konnte nicht geladen werden" in text
    assert "file is not a database" in text
    assert "andere Datei wählen" in text


def test_error_message_shows_the_file_name_instead_of_the_full_path():
    path = r"C:\Users\person\Privat\Daten\kaputt.gpkg"
    error = GeoPackageImportError(f"Unable to read GeoPackage {path}: file is not a database")
    text = import_error_text("kaputt.gpkg", error, path)
    assert path not in text
    assert "Unable to read GeoPackage kaputt.gpkg: file is not a database" in text


def test_long_folders_are_shortened_in_the_middle():
    folder = r"C:\Users\person\OneDrive\Desktop\Projekte\Oldenburg\ALKIS\Daten"
    text = file_summary_text("a.gpkg", folder, 0)
    shown = text.split("Ordner: ")[1]
    assert len(shown) == 40 and "…" in shown
    assert shown.startswith("C:\\Users") and shown.endswith("ALKIS\\Daten")


def test_choice_buttons_show_whether_their_panel_is_open():
    assert choice_label("Lokale Daten", False) == f"{ARROW_CLOSED}  Lokale Daten"
    assert choice_label("Lokale Daten", True) == f"{ARROW_OPEN}  Lokale Daten"


def test_file_dialog_offers_geopackages_first():
    assert FILE_DIALOG_FILTER.startswith("GeoPackage (*.gpkg)")
