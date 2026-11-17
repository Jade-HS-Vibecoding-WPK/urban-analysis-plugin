import sqlite3
import struct

import pytest

from urban_analysis.data_pipeline import (
    GeoPackageImportError,
    GeoPackageImporter,
    apply_data_source,
    merge_confirmed_duplicates,
)


def wkb_point(x, y):
    return struct.pack("<BIdd", 1, 1, x, y)


def wkb_polygon(ring):
    data = struct.pack("<BIII", 1, 3, 1, len(ring))
    for x, y in ring:
        data += struct.pack("<dd", x, y)
    return data


def gpkg_blob(wkb):
    return b"GP\x00\x01" + struct.pack("<i", 25832) + wkb


def gpkg_point(x, y):
    return gpkg_blob(wkb_point(x, y))


def gpkg_polygon(ring):
    return gpkg_blob(wkb_polygon(ring))


def make_geopackage(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('WGS 84 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('buildings', 'geom', 'POLYGON', 25832);
            CREATE TABLE buildings (
                fid INTEGER PRIMARY KEY, geom BLOB, type TEXT, area TEXT,
                category TEXT, year TEXT
            );
            """
        )
        house = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        connection.executemany(
            "INSERT INTO buildings VALUES (?, ?, 'house', '12,5', 'Gebäude', '2020')",
            [(1, house), (2, house)],
        )


def test_imports_geopackage_and_harmonizes_duplicate_rows(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))",
        buffer_meters=250,
    )

    assert result.buffer_meters == 250
    assert result.layers[0].geometry_type == "POLYGON"
    assert result.layers[0].category == "Gebäude"
    assert len(result.harmonized_records) == 1
    assert result.harmonized_records[0].attributes["area_m2"] == 12.5
    assert result.harmonized_records[0].attributes["year"] == 2020
    assert any(issue.code == "duplicate-row" for issue in result.issues)


def test_import_requires_valid_geopackage_and_project_setup(tmp_path):
    with pytest.raises(GeoPackageImportError):
        GeoPackageImporter().import_file(
            tmp_path / "missing.gpkg",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )

    invalid_path = tmp_path / "invalid.gpkg"
    invalid_path.write_bytes(b"not sqlite")
    with pytest.raises(GeoPackageImportError):
        GeoPackageImporter().import_file(
            invalid_path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
        )

    path = tmp_path / "valid.gpkg"
    make_geopackage(path)
    with pytest.raises(ValueError, match="must not be negative"):
        GeoPackageImporter().import_file(
            path,
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            buffer_meters=-1,
        )


def test_maps_denial_tower_fields_to_common_schema(tmp_path):
    path = tmp_path / "denial.gpkg"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('WGS 84 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('towers', 'wkt_geom', 'POINT', 25832);
            CREATE TABLE towers (
                fid INTEGER PRIMARY KEY, objid TEXT, ken TEXT, ken__bez TEXT,
                bwf TEXT, bwf__bez TEXT, untermerkmal TEXT, wkt_geom TEXT
            );
            INSERT INTO towers VALUES
                (1, 'DENIAL1100003tFJ', '51001', 'Turm', '1002',
                 'Kirchturm, Glockenturm', 'xxx', 'POINT (0 0)');
            """
        )

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
    )

    mapping = {
        suggestion.source_field: suggestion.target_field
        for suggestion in result.attribute_suggestions
    }
    assert mapping["ken__bez"] == "object_type"
    assert mapping["bwf__bez"] == "category"
    assert mapping["untermerkmal"] == "status"
    assert result.harmonized_records[0].attributes["object_type"] == "Turm"
    assert result.harmonized_records[0].attributes["category"] == "Kirchturm, Glockenturm"
    assert result.harmonized_records[0].attributes["status"] == "xxx"


def make_clipping_geopackage(path, *, srs_rows=None, srs_id=25832):
    """Points around a triangular study area plus edge cases for clipping."""
    srs_rows = srs_rows or [("ETRS89 / UTM zone 32N", 25832, "EPSG", 25832, "undefined")]
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER, definition TEXT
            );
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            CREATE TABLE places (fid INTEGER PRIMARY KEY, geom BLOB, typ TEXT);
            """
        )
        connection.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?)", srs_rows)
        connection.execute(
            "INSERT INTO gpkg_geometry_columns VALUES ('places', 'geom', 'GEOMETRY', ?)",
            (srs_id,),
        )
        connection.executemany(
            "INSERT INTO places VALUES (?, ?, ?)",
            [
                (1, gpkg_point(10, 10), "innen"),
                (2, gpkg_point(-30, 10), "im Puffer"),
                (3, gpkg_point(-80, 10), "außerhalb"),
                (4, gpkg_point(90, 90), "Rechteck-Ecke"),
                (5, gpkg_polygon([(80, -20), (120, -20), (120, 20), (80, 20), (80, -20)]), "über der Grenze"),
                (6, None, "ohne Geometrie"),
                (7, b"GP\x00\x01" + b"\x00" * 4, "kaputt"),
            ],
        )


TRIANGLE = "POLYGON ((0 0, 100 0, 0 100, 0 0))"


def import_places(path, **kwargs):
    options = {"project_crs": "EPSG:25832", "study_area_wkt": TRIANGLE, "buffer_meters": 50}
    options.update(kwargs)
    return GeoPackageImporter().import_file(path, **options)


def issue_codes(result):
    return {issue.code for issue in result.issues}


def test_clips_to_study_area_polygon_with_buffer(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]
    assert {"missing-geometry", "unreadable-geometry", "clip-summary"} <= issue_codes(result)
    assert "crs-mismatch" not in issue_codes(result)
    summary = next(issue for issue in result.issues if issue.code == "clip-summary")
    assert "3 von 7" in summary.message


def test_buffer_zero_keeps_only_touching_features(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path, buffer_meters=0)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 5]


def test_crs_mismatch_is_an_error_and_layer_is_not_clipped(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("DHDN / 3-degree Gauss-Kruger zone 3", 31467, "EPSG", 31467, "undefined")],
        srs_id=31467,
    )

    result = import_places(path)

    assert result.harmonized_records == []
    mismatch = next(issue for issue in result.issues if issue.code == "crs-mismatch")
    assert mismatch.severity == "error"
    assert [layer.layer_id for layer in result.layers] == ["places"]


def test_identifies_epsg_from_definition_when_organization_is_none(tmp_path):
    path = tmp_path / "places.gpkg"
    definition = (
        'PROJCS["ETRS89 / UTM zone 32N",GEOGCS["ETRS89",DATUM["European_Terrestrial_Reference_System_1989",'
        'SPHEROID["GRS 1980",6378137,298.257222101]]],PROJECTION["Transverse_Mercator"],UNIT["metre",1]]'
    )
    make_clipping_geopackage(
        path,
        srs_rows=[("ETRS89 / UTM zone 32N", 100000, "NONE", 100000, definition)],
        srs_id=100000,
    )

    result = import_places(path)

    assert {"crs-mismatch", "crs-unverified"}.isdisjoint(issue_codes(result))
    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]


def test_unknown_crs_is_clipped_but_requires_confirmation(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("Undefined Cartesian SRS", -1, "NONE", -1, "undefined")],
        srs_id=-1,
    )

    result = import_places(path)

    unverified = next(issue for issue in result.issues if issue.code == "crs-unverified")
    assert unverified.requires_confirmation
    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]


def test_geographic_crs_with_metre_buffer_is_rejected(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(
        path,
        srs_rows=[("WGS 84", 4326, "EPSG", 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984"]]')],
        srs_id=4326,
    )

    result = import_places(path, project_crs="EPSG:4326")

    assert result.harmonized_records == []
    assert "geographic-crs-buffer" in issue_codes(result)


def test_invalid_study_area_is_reported_and_nothing_is_imported(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)

    result = import_places(path, study_area_wkt="LINESTRING (0 0, 10 10)")

    assert result.harmonized_records == []
    issue = next(issue for issue in result.issues if issue.code == "invalid-study-area")
    assert issue.severity == "error"


def test_same_attributes_with_different_geometry_are_not_duplicates(tmp_path):
    path = tmp_path / "sample.gpkg"
    make_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO buildings VALUES (3, ?, 'house', '12,5', 'Gebäude', '2020')",
            (gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)]),),
        )

    result = GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 0))",
    )

    assert [record.source_row_id for record in result.harmonized_records] == [1, 3]
    duplicate = next(issue for issue in result.issues if issue.code == "duplicate-row")
    assert duplicate.message == "buildings: 1 Eintrag war doppelt (komplett gleich) und wurde automatisch entfernt."


def make_house_number_geopackage(path):
    """One building stored once per house number, as in ALKIS exports."""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('ETRS89 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE gebaeude (
                fid INTEGER PRIMARY KEY, geom BLOB, objid TEXT, gfk__bez TEXT, hnr TEXT
            );
            """
        )
        house = gpkg_polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        other = gpkg_polygon([(5, 1), (7, 1), (7, 3), (5, 3), (5, 1)])
        connection.executemany(
            "INSERT INTO gebaeude VALUES (?, ?, ?, 'Wohngebäude', ?)",
            [
                (1, house, "DENIAL1", "39"),
                (2, house, "DENIAL1", "41"),
                (3, house, "DENIAL1", "41"),
                (4, other, "DENIAL2", "1"),
            ],
        )


def import_houses(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
    )


def test_same_geometry_with_different_attributes_needs_confirmation(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)

    result = import_houses(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 4]
    assert [record.duplicate_group for record in result.harmonized_records] == [
        "gebaeude:1",
        "gebaeude:1",
        None,
    ]
    exact = next(issue for issue in result.issues if issue.code == "duplicate-row")
    assert exact.message == "Gebäude: 1 Eintrag war doppelt (komplett gleich) und wurde automatisch entfernt."
    uncertain = next(issue for issue in result.issues if issue.code == "uncertain-duplicate")
    assert uncertain.requires_confirmation
    assert uncertain.severity == "warning"
    assert uncertain.message.startswith(
        "Gebäude: An einer Stelle liegen mehrere Objekte genau übereinander (2 Objekte). "
        "Sie unterscheiden sich nur in Hausnummer – z. B. ein Haus mit mehreren Hausnummern."
    )
    assert uncertain.message.endswith("Sollen sie je Stelle zu einem Objekt zusammengefasst werden?")
    assert "Alle wurden behalten" in uncertain.message


def test_merge_confirmed_duplicates_keeps_first_record_per_group(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    records = import_houses(path).harmonized_records

    assert merge_confirmed_duplicates(records, []) == records
    merged = merge_confirmed_duplicates(records, ["gebaeude:1"])
    assert [record.source_row_id for record in merged] == [1, 4]


def switch_to_wal_mode(path):
    """Store the GeoPackage like QGIS does while editing (journal mode WAL)."""
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    connection.close()
    assert path.read_bytes()[18:20] == b"\x02\x02"


def test_reads_wal_mode_geopackage_without_side_files(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)
    switch_to_wal_mode(path)
    original = path.read_bytes()

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5]
    assert path.read_bytes() == original


def test_reads_wal_mode_geopackage_while_another_program_writes(tmp_path):
    path = tmp_path / "places.gpkg"
    make_clipping_geopackage(path)
    switch_to_wal_mode(path)
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO places VALUES (8, ?, 'neu gezeichnet')", (gpkg_point(20, 20),))
        writer.commit()
        assert (tmp_path / "places.gpkg-wal").exists()

        result = import_places(path)
    finally:
        writer.close()

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5, 8]


def test_reads_wal_mode_geopackage_with_unsaved_changes_and_no_shared_memory_file(tmp_path):
    source = tmp_path / "source.gpkg"
    make_clipping_geopackage(source)
    switch_to_wal_mode(source)
    writer = sqlite3.connect(source)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO places VALUES (8, ?, 'neu gezeichnet')", (gpkg_point(20, 20),))
    writer.commit()
    copy_dir = tmp_path / "copy"
    copy_dir.mkdir()
    path = copy_dir / "places.gpkg"
    path.write_bytes(source.read_bytes())
    (copy_dir / "places.gpkg-wal").write_bytes((tmp_path / "source.gpkg-wal").read_bytes())
    writer.close()
    original = path.read_bytes()

    result = import_places(path)

    assert [record.source_row_id for record in result.harmonized_records] == [1, 2, 5, 8]
    assert path.read_bytes() == original


def test_source_name_is_only_the_file_name_and_source_stays_empty(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)

    result = import_houses(path)

    assert result.layers[0].source_name == "houses.gpkg"
    assert {record.attributes["source_name"] for record in result.harmonized_records} == {"houses.gpkg"}
    assert {record.attributes["source"] for record in result.harmonized_records} == {None}
    hint = next(issue for issue in result.issues if issue.code == "missing-data-source")
    assert hint.severity == "warning"
    assert hint.message.startswith("Datenquelle fehlt: In der Datei steht nicht, woher die Daten stammen.")
    assert "z. B. „ALKIS, © LGLN 2025“" in hint.message
    assert str(tmp_path) not in hint.message


def test_source_column_in_data_is_used_and_no_hint_is_shown(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN quelle TEXT")
        connection.execute("UPDATE gebaeude SET quelle = 'ALKIS, LGLN 2025'")

    result = import_houses(path)

    assert {record.attributes["source"] for record in result.harmonized_records} == {"ALKIS, LGLN 2025"}
    assert "missing-data-source" not in {issue.code for issue in result.issues}


def test_apply_data_source_fills_only_empty_sources(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    records = import_houses(path).harmonized_records
    records[0] = records[0].__class__(
        layer_id=records[0].layer_id,
        source_row_id=records[0].source_row_id,
        attributes={**records[0].attributes, "source": "aus den Daten"},
        geometry=records[0].geometry,
        duplicate_group=records[0].duplicate_group,
    )

    filled = apply_data_source(records, "  ALKIS, LGLN 2025 ")

    assert [record.attributes["source"] for record in filled] == [
        "aus den Daten",
        "ALKIS, LGLN 2025",
        "ALKIS, LGLN 2025",
    ]
    assert records[1].attributes["source"] is None
    with pytest.raises(ValueError):
        apply_data_source(records, "   ")


NUTZUNG_ROWS = [
    ("Strassenverkehr, Begleitfläche Straßenverkehr", "Straßen", "nutzung_strassen"),
    ("Platz, Parkplatz", "Straßen", "nutzung_strassen"),
    ("Weg, Rad- und Fußweg", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Weg", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Strassenverkehr, Fußgängerzone", "Fuß- und Radwege", "nutzung_fuss_radwege"),
    ("Platz, Marktplatz", "Plätze", "nutzung_plaetze"),
    ("Sport-, Freizeit- und Erholungsfläche, Park", "Grünflächen", "nutzung_gruen"),
    ("Landwirtschaft, Grünland", "Grünflächen", "nutzung_gruen"),
    ("Unland, Vegetationslose Fläche, Sukzessionsfläche", "Grünflächen", "nutzung_gruen"),
    ("Fliessgewässer, Graben", "Wasserflächen", "nutzung_wasser"),
    ("Bahnverkehr", "Bahnflächen", "nutzung_bahn"),
    ("Schiffsverkehr, Hafenanlage (Landfläche)", "Schiffsverkehrsflächen", "nutzung_schiff"),
    ("Wohnbaufläche, Offen", "Nutzungsflächen", "nutzung_flaechen"),
    ("Sport-, Freizeit- und Erholungsfläche, Sportanlage", "Nutzungsflächen", "nutzung_flaechen"),
    ("Landwirtschaft, Ackerland", "Nutzungsflächen", "nutzung_flaechen"),
]


def make_alkis_geopackage(path, *, with_objid=True):
    """Small ALKIS-like GeoPackage: nutzung, gebaeude and an unrelated layer."""
    objid = "objid TEXT," if with_objid else ""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            f"""
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT, srs_id INTEGER PRIMARY KEY,
                organization TEXT, organization_coordsys_id INTEGER
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES
                ('ETRS89 / UTM zone 32N', 25832, 'EPSG', 25832);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT, column_name TEXT, geometry_type_name TEXT,
                srs_id INTEGER
            );
            INSERT INTO gpkg_geometry_columns VALUES
                ('nutzung', 'geom', 'MULTIPOLYGON', 25832),
                ('gebaeude', 'geom', 'MULTIPOLYGON', 25832),
                ('bodenschaetzung', 'geom', 'MULTIPOLYGON', 25832);
            CREATE TABLE nutzung (fid INTEGER PRIMARY KEY, geom BLOB, {objid} tn__bez TEXT);
            CREATE TABLE gebaeude (fid INTEGER PRIMARY KEY, geom BLOB, {objid} gfk__bez TEXT);
            CREATE TABLE bodenschaetzung (fid INTEGER PRIMARY KEY, geom BLOB, {objid} kul__bez TEXT);
            """
        )
        columns = "(fid, geom, objid, tn__bez)" if with_objid else "(fid, geom, tn__bez)"
        for index, (value, _category, _layer) in enumerate(NUTZUNG_ROWS, start=1):
            square = gpkg_polygon([(index, 1), (index + 0.5, 1), (index + 0.5, 2), (index, 2), (index, 1)])
            values = (index, square, f"N{index}", value) if with_objid else (index, square, value)
            marks = ", ".join("?" * len(values))
            connection.execute(f"INSERT INTO nutzung {columns} VALUES ({marks})", values)
        house = gpkg_polygon([(1, 5), (2, 5), (2, 6), (1, 6), (1, 5)])
        if with_objid:
            connection.execute("INSERT INTO gebaeude VALUES (1, ?, 'G1', 'Wohngebäude')", (house,))
            connection.execute("INSERT INTO bodenschaetzung VALUES (1, ?, 'B1', 'Grünland')", (house,))
        else:
            connection.execute("INSERT INTO gebaeude VALUES (1, ?, 'Wohngebäude')", (house,))
            connection.execute("INSERT INTO bodenschaetzung VALUES (1, ?, 'Grünland')", (house,))


def import_alkis(path):
    return GeoPackageImporter().import_file(
        path,
        project_crs="EPSG:25832",
        study_area_wkt="POLYGON ((0 0, 30 0, 30 10, 0 10, 0 0))",
        buffer_meters=0,
    )


def test_alkis_nutzung_is_split_into_one_result_layer_per_category(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    by_row = {
        record.source_row_id: record
        for record in result.harmonized_records
        if record.layer_id.startswith("nutzung")
    }
    for index, (value, category, layer_id) in enumerate(NUTZUNG_ROWS, start=1):
        assert by_row[index].attributes["category"] == category, value
        assert by_row[index].layer_id == layer_id, value
    nutzung_layers = {layer.layer_id: layer.category for layer in result.layers if layer.layer_id.startswith("nutzung")}
    assert nutzung_layers == {layer_id: category for _value, category, layer_id in NUTZUNG_ROWS}
    assert "nutzung" not in {layer.layer_id for layer in result.layers}


def test_alkis_values_keep_main_type_and_detail(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    def attributes_for(value):
        index = [row[0] for row in NUTZUNG_ROWS].index(value) + 1
        return next(
            record.attributes for record in result.harmonized_records
            if record.layer_id.startswith("nutzung") and record.source_row_id == index
        )

    assert attributes_for("Wohnbaufläche, Offen")["object_type"] == "Wohnbaufläche"
    assert attributes_for("Wohnbaufläche, Offen")["object_detail"] == "Offen"
    park = attributes_for("Sport-, Freizeit- und Erholungsfläche, Park")
    assert (park["object_type"], park["object_detail"]) == ("Sport-, Freizeit- und Erholungsfläche", "Park")
    unland = attributes_for("Unland, Vegetationslose Fläche, Sukzessionsfläche")
    assert (unland["object_type"], unland["object_detail"]) == ("Unland, Vegetationslose Fläche", "Sukzessionsfläche")
    assert attributes_for("Bahnverkehr")["object_detail"] is None


def test_alkis_buildings_and_unrelated_layers(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    categories = {layer.layer_id: layer.category for layer in result.layers}
    assert categories["gebaeude"] == "Gebäude"
    assert categories["bodenschaetzung"] is None
    building = next(record for record in result.harmonized_records if record.layer_id == "gebaeude")
    assert building.attributes["object_type"] == "Wohngebäude"
    assert building.attributes["category"] == "Gebäude"
    assert "missing-category" not in {issue.code for issue in result.issues}
    suggestion = next(s for s in result.attribute_suggestions if s.source_field == "gfk__bez")
    assert (suggestion.target_field, suggestion.confidence) == ("object_type", 1.0)


def test_without_alkis_profile_only_the_layer_name_decides(tmp_path):
    path = tmp_path / "other.gpkg"
    make_alkis_geopackage(path, with_objid=False)

    result = import_alkis(path)

    categories = {layer.layer_id: layer.category for layer in result.layers}
    assert categories == {"nutzung": "Nutzungsflächen", "gebaeude": "Gebäude", "bodenschaetzung": None}
    hint = next(issue for issue in result.issues if issue.code == "missing-category")
    assert hint.message.startswith("Bodenschätzung: Für diesen Layer ist unklar, was er darstellt")
    assert all(record.attributes["object_detail"] is None for record in result.harmonized_records)


def test_data_source_hint_names_only_the_layers_without_source(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN quelle TEXT")
        connection.execute("UPDATE gebaeude SET quelle = 'ALKIS, LGLN 2025'")

    result = import_alkis(path)

    hint = next(issue for issue in result.issues if issue.code == "missing-data-source")
    assert hint.message.startswith("Datenquelle fehlt für Nutzung und Bodenschätzung:")


def test_uncertain_duplicate_hint_skips_key_column_when_readable_twin_differs(tmp_path):
    path = tmp_path / "houses.gpkg"
    make_house_number_geopackage(path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE gebaeude ADD COLUMN gfk TEXT")
        connection.execute("UPDATE gebaeude SET gfk = CAST(fid AS TEXT), gfk__bez = 'Funktion ' || fid")

    result = import_houses(path)

    uncertain = next(issue for issue in result.issues if issue.code == "uncertain-duplicate")
    assert "nur in Gebäudefunktion und Hausnummer" in uncertain.message
    assert "Gebäudefunktionsschlüssel" not in uncertain.message
    assert "(" not in uncertain.message.split("(3 Objekte)")[1].split("–")[0]


def test_attribute_suggestions_name_their_layer_and_show_examples(tmp_path):
    path = tmp_path / "alkis.gpkg"
    make_alkis_geopackage(path)

    result = import_alkis(path)

    by_layer = {(s.layer_id, s.source_field): s for s in result.attribute_suggestions}
    nutzung = by_layer[("nutzung", "tn__bez")]
    assert nutzung.target_field == "object_type"
    assert nutzung.examples == ("Strassenverkehr, Begleitfläche Straßenverkehr", "Platz, Parkplatz")
    assert by_layer[("gebaeude", "gfk__bez")].examples == ("Wohngebäude",)
