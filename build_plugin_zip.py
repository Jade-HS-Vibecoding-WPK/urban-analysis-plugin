"""Build the plugin ZIP for installing in QGIS (W9).

    python build_plugin_zip.py              -> urban_analysis_plugin-<version>.zip
    python build_plugin_zip.py --out PATH   -> ZIP at PATH

Only the plugin itself goes in: ``__init__.py``, ``metadata.txt``,
``LICENSE`` and the folder ``urban_analysis`` (code, catalogues, icons).
Tests, plans and local data stay out.  Before writing, every file is
checked; the ZIP is not written if something should not be shared:

- file types other than code, catalogues and icons (e.g. GeoPackages),
- ``__pycache__``, ``.DS_Store``, ``__MACOSX`` and similar,
- passwords, API keys, tokens, private keys, e-mail addresses,
- local user paths (``C:\\Users\\<name>``, ``/Users/<name>``).

Standard library only, works the same on Windows and macOS.  ZIP files are
ignored by git (``.gitignore``) and are never committed.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGIN_NAME = "urban_analysis_plugin"  # folder name QGIS installs into
TOP_FILES = ("__init__.py", "metadata.txt", "LICENSE")
PACKAGE = "urban_analysis"
ALLOWED_SUFFIXES = {".py", ".json", ".svg", ".txt", ""}
SKIPPED_PARTS = {"__pycache__", ".pytest_cache"}
FORBIDDEN_NAMES = re.compile(r"(?i)(__MACOSX|\.DS_Store|Thumbs\.db|\.pyc$|\.env$)")
# Example paths in comments ('C:\Users\…\Daten', 'C:/Users/name/…') are fine.
SENSITIVE = {
    "Passwort, Schlüssel oder Token": re.compile(
        r"(?i)(passwor[dt]\s*[:=]|api[_-]?key\s*[:=]|secret\s*[:=]|ghp_[A-Za-z0-9]{20,}|github_pat_|"
        r"BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|bearer\s+[A-Za-z0-9._-]{20,})"),
    "E-Mail-Adresse": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "lokaler Benutzerpfad": re.compile(
        r"(?i)([A-Z]:[\\/]+Users[\\/]+(?!name\b|person\b|…|\.\.\.)[A-Za-z0-9._-]+|/Users/(?!name\b|person\b)[a-z][A-Za-z0-9._-]+)"),
}


def plugin_version(root=ROOT):
    """``version=`` from metadata.txt (empty if missing)."""
    for line in (root / "metadata.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip()
    return ""


def plugin_files(root=ROOT):
    """All files that belong into the ZIP, as paths relative to ``root``."""
    files = [Path(name) for name in TOP_FILES if (root / name).is_file()]
    for path in sorted((root / PACKAGE).rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not SKIPPED_PARTS.intersection(relative.parts):
            files.append(relative)
    return files


def problems(root, files):
    """Readable reasons why the ZIP must not be built (empty list = fine)."""
    found = []
    for relative in files:
        name = relative.as_posix()
        if FORBIDDEN_NAMES.search(name):
            found.append(f"{name}: Datei gehört nicht ins Plugin")
            continue
        if relative.suffix.lower() not in ALLOWED_SUFFIXES:
            found.append(f"{name}: Dateityp „{relative.suffix}“ ist nicht erlaubt (z. B. Daten-Datei)")
            continue
        text = (root / relative).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SENSITIVE.items():
                if pattern.search(line):
                    found.append(f"{name}, Zeile {number}: {label}")
    return found


def build_zip(out_path, root=ROOT):
    """Check, then write the ZIP.  Returns the list of files written."""
    files = plugin_files(root)
    missing = [name for name in ("__init__.py", "metadata.txt") if Path(name) not in files]
    if missing:
        raise SystemExit("Fehlt im Plugin-Ordner: " + ", ".join(missing))
    found = problems(root, files)
    if found:
        raise SystemExit(
            "Das ZIP wurde NICHT gebaut, weil diese Dateien etwas enthalten, das nicht "
            "weitergegeben werden soll:\n  " + "\n  ".join(found)
            + "\nWas tun: die Stellen entfernen und das Skript erneut starten.")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(root / relative, f"{PLUGIN_NAME}/{relative.as_posix()}")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plugin-ZIP für QGIS bauen (W9).")
    parser.add_argument("--out", help="Pfad der ZIP-Datei (Standard: im Repo-Ordner)")
    args = parser.parse_args(argv)
    version = plugin_version() or "dev"
    out = Path(args.out) if args.out else ROOT / f"{PLUGIN_NAME}-{version}.zip"
    files = build_zip(out)
    print(f"ZIP gebaut: {out} ({len(files)} Dateien, Prüfung ohne Befund)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
