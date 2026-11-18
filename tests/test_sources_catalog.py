"""The sources catalog (M9) stays complete and consistent.

The catalog only holds addresses, licences and rules – no data. These tests
make sure every Bundesland is listed with what the download (S9/S10) needs.
"""

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "urban_analysis" / "sources_catalog.json"
ALL_STATES = {"BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"}
LICENCES = {"CC-BY-4.0", "dl-de/by-2-0", "dl-de/zero-2-0"}


def load():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_every_state_has_a_source_with_licence_and_attribution():
    alkis = load()["alkis"]
    assert set(alkis) == ALL_STATES
    for code, entry in alkis.items():
        assert entry["dienst"] in {"wfs", "download"}, code
        assert entry["url"].startswith("https://"), code
        assert entry["crs"].startswith("EPSG:"), code
        assert entry["lizenz"] in LICENCES, code
        assert entry["quellenvermerk"], code
        assert entry["inhalt"], code


def test_every_state_uses_a_described_format():
    catalog = load()
    formats = catalog["alkis_formate"]
    for code, entry in catalog["alkis"].items():
        assert entry["format"] in formats, code
        for content in entry["inhalt"]:
            kind = "gebaeude" if content == "gebaeude_umringe" else content
            assert kind in formats[entry["format"]]["layer"], (code, content)


def test_states_without_land_use_say_so():
    """No silent gaps: a missing part is explained for the user (E6)."""
    for code, entry in load()["alkis"].items():
        if "nutzung" not in entry["inhalt"] or "flurstuecke" not in entry["inhalt"]:
            assert entry.get("einschraenkung"), code


def test_osm_and_state_borders_are_listed():
    catalog = load()
    assert catalog["osm"]["quellenvermerk"] == "© OpenStreetMap-Mitwirkende, ODbL"
    assert catalog["osm"]["regeln"]["max_abfragen_pro_tag"] > 0
    assert catalog["laendergrenzen"]["lizenz"] in LICENCES
