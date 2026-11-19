"""W9: plugin ZIP – structure and the check for things that must not be shared."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_plugin_zip", ROOT / "build_plugin_zip.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def test_zip_of_the_repo_has_the_layout_qgis_expects(tmp_path):
    out = tmp_path / "plugin.zip"
    build.build_zip(out)
    names = zipfile.ZipFile(out).namelist()
    assert {name.split("/")[0] for name in names} == {"urban_analysis_plugin"}
    assert "urban_analysis_plugin/metadata.txt" in names
    assert "urban_analysis_plugin/__init__.py" in names
    assert "urban_analysis_plugin/urban_analysis/guided_dialog.py" in names
    assert not any("__pycache__" in name or "/tests/" in name or name.endswith(".md") for name in names)


def _fake_plugin(root):
    (root / "urban_analysis").mkdir()
    (root / "__init__.py").write_text("def classFactory(iface):\n    pass\n", encoding="utf-8")
    (root / "metadata.txt").write_text("[general]\nversion=1.2.3\n", encoding="utf-8")
    (root / "urban_analysis" / "code.py").write_text("x = 1\n", encoding="utf-8")


def test_clean_fake_plugin_is_built_and_named_after_the_version(tmp_path):
    _fake_plugin(tmp_path)
    (tmp_path / "urban_analysis" / "__pycache__").mkdir()
    (tmp_path / "urban_analysis" / "__pycache__" / "code.cpython-312.pyc").write_bytes(b"\0")
    assert build.plugin_version(tmp_path) == "1.2.3"
    files = build.build_zip(tmp_path / "out" / "p.zip", root=tmp_path)
    assert [f.as_posix() for f in files] == ["__init__.py", "metadata.txt", "urban_analysis/code.py"]


@pytest.mark.parametrize("name, content, reason", [
    ("daten.gpkg", "SQLite", "Dateityp"),
    ("key.py", 'API_KEY = "abc"\n', "Passwort, Schlüssel oder Token"),
    ("mail.py", "# frage an max.muster@example.org\n", "E-Mail-Adresse"),
    ("pfad.py", r'P = r"C:\Users\maxmuster\Desktop\x"' + "\n", "lokaler Benutzerpfad"),
])
def test_zip_is_not_built_if_something_must_not_be_shared(tmp_path, name, content, reason):
    _fake_plugin(tmp_path)
    (tmp_path / "urban_analysis" / name).write_text(content, encoding="utf-8")
    out = tmp_path / "p.zip"
    with pytest.raises(SystemExit) as error:
        build.build_zip(out, root=tmp_path)
    assert reason in str(error.value) and "NICHT gebaut" in str(error.value)
    assert not out.exists()


def test_example_paths_in_comments_are_allowed(tmp_path):
    _fake_plugin(tmp_path)
    (tmp_path / "urban_analysis" / "doc.py").write_text(
        "# e.g. 'C:\\\\Users\\\\…\\\\Daten' or C:/Users/name/Projekt\n", encoding="utf-8")
    assert build.problems(tmp_path, build.plugin_files(tmp_path)) == []
