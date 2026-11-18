"""W10: area size in step 2 (E13/E17) and source choice in step 3 (placeholders)."""

from urban_analysis.guided_dialog import (
    CHOOSE_FILE_MESSAGE,
    CHOOSE_SOURCE_MESSAGE,
    CHOOSE_STATE_MESSAGE,
    DOWNLOAD_PENDING_MESSAGE,
    GERMAN_STATES,
    source_choice_problem,
)
from urban_analysis.study_area import (
    download_box_km2,
    download_size_text,
    is_large,
    is_oversized,
    oversize_question_text,
    oversize_warning_text,
)


def test_download_box_includes_the_buffer_on_all_sides():
    # Donnerschwee: 2041 m x 2582 m, buffer 500 m -> 3041 m x 3582 m
    km2 = download_box_km2(446950, 5888700, 448991, 5891282, 500)
    assert round(km2, 1) == 10.9
    assert download_size_text(km2) == (
        "Gebiet mit Puffer: 10,9 km² von höchstens 50 km² (Rechteck für den Download)"
    )
    assert not is_large(km2) and not is_oversized(km2)


def test_large_area_warns_but_downloads_stay_possible():
    km2 = download_box_km2(0, 0, 5000, 5000, 500)  # 6 km x 6 km = 36 km²
    assert is_large(km2) and not is_oversized(km2)
    assert "36,0 km²" in oversize_warning_text(km2)
    assert "lange dauern" in oversize_warning_text(km2)
    assert "nicht heruntergeladen" not in oversize_warning_text(km2)
    assert oversize_question_text(km2).endswith("Trotzdem fortfahren?")
    assert not is_large(25.0)  # exactly the limit is no warning


def test_above_50_km2_no_download_but_continuing_is_possible():
    km2 = 60.0
    assert is_oversized(km2)
    assert "nicht heruntergeladen" in oversize_warning_text(km2)
    assert "trotzdem weitermachen" in oversize_warning_text(km2)
    assert not is_oversized(50.0)


def choice(**kwargs):
    values = dict(osm=False, alkis=False, state=None, own=False, path=None,
                  download_km2=10.0, has_data=False)
    values.update(kwargs)
    return source_choice_problem(**values)


def test_a_source_must_be_ticked_unless_data_is_loaded():
    assert choice() == ("error", CHOOSE_SOURCE_MESSAGE)
    assert choice(has_data=True) is None


def test_own_file_needs_a_file_and_then_loads():
    assert choice(own=True) == ("error", CHOOSE_FILE_MESSAGE)
    assert choice(own=True, path="daten.gpkg") is None


def test_alkis_needs_a_state():
    assert choice(alkis=True) == ("error", CHOOSE_STATE_MESSAGE)


def test_downloads_are_blocked_only_above_50_km2():
    kind, text = choice(osm=True, download_km2=60.0)
    assert kind == "error" and "60,0 km²" in text and "50 km²" in text
    assert choice(osm=True, download_km2=36.0) == ("info", DOWNLOAD_PENDING_MESSAGE)
    # an own file is still possible for a large area
    assert choice(own=True, path="daten.gpkg", download_km2=60.0) is None


def test_downloads_say_clearly_that_they_come_later():
    assert choice(osm=True) == ("info", DOWNLOAD_PENDING_MESSAGE)
    assert choice(alkis=True, state="Niedersachsen", own=True, path="x.gpkg") == (
        "info", DOWNLOAD_PENDING_MESSAGE)


def test_all_16_states_are_listed():
    assert len(GERMAN_STATES) == 16 and "Niedersachsen" in GERMAN_STATES
