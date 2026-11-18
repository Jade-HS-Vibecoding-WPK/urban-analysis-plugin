"""W13 (UI part): short summary of a hint, the rest below 'Mehr erfahren'."""

from urban_analysis.guided_dialog import split_summary


def test_first_sentence_is_the_summary():
    short, more = split_summary(
        "Gebäude: 312 Objekte ohne Gebäudeart. Die Spalte ist leer; bitte in Schritt 5 prüfen."
    )
    assert short == "Gebäude: 312 Objekte ohne Gebäudeart."
    assert more == "Die Spalte ist leer; bitte in Schritt 5 prüfen."


def test_abbreviations_do_not_end_the_summary():
    short, more = split_summary("Fehlende Werte, z. B. Baujahr. Mehr dazu im Protokoll.")
    assert short == "Fehlende Werte, z. B. Baujahr."
    assert more == "Mehr dazu im Protokoll."


def test_one_sentence_has_nothing_more():
    assert split_summary("Alles in Ordnung.") == ("Alles in Ordnung.", "")


def test_details_from_the_pipeline_win():
    assert split_summary("Kurz. Und noch mehr.", details="Lange Erklärung") == (
        "Kurz. Und noch mehr.", "Lange Erklärung")
