# Arbeitsplan: Wer macht was, in welcher Reihenfolge – und wo treffen sich unsere Teile?

Stand: 17.11.2026. Dieser Plan ersetzt nicht `PLAN.md` (das *Was* und *Warum*),
sondern beschreibt das *Wie*: konkrete, kleine Schritte für beide Personen.

Wir coden zum ersten Mal gemeinsam. Deshalb ist jeder Schritt klein, hat eine
**Absicht** (warum machen wir das?), ein **Ziel** (woran merken wir, dass er
fertig ist?) und sagt, **welche Dateien** er berührt und **auf wen man warten
muss**.

- **Person Mac** = Datenpipeline (arbeitet auf macOS)
- **Person Windows** = Benutzerführung und Integration in QGIS (arbeitet auf Windows)
- **Gemeinsam** = beide zusammen, am besten im Call oder nebeneinander

> **Für die Claude-Code-Session der jeweiligen Person:** Lies zuerst
> `CLAUDE.md` und dann diesen Plan. Arbeite nur an den Schritten deiner Person
> und nur an den Dateien, die dort stehen. Erledige immer nur **einen**
> Schritt, zeige das Ergebnis und frage, bevor du committest, pushst oder einen
> Pull Request öffnest. Wenn ein Schritt eine Datei der anderen Person oder
> eine gemeinsame Datei braucht: anhalten und nachfragen.

---

## 1. Das große Bild

Das Plugin führt Studierende in 9 Schritten durch eine Gebietsanalyse. Unsere
beiden Teile arbeiten so zusammen:

```text
 Person Windows (QGIS-Oberfläche)              Person Mac (Datenpipeline, ohne QGIS)
 ───────────────────────────────               ─────────────────────────────────────
 1 Projekt-CRS wählen
 2 Untersuchungsgebiet + Puffer wählen
 3 GeoPackage-Datei auswählen  ── S1 ──────▶  GeoPackageImporter().import_file(...)
                                                 • Layer lesen, CRS prüfen
                                                 • auf Gebiet + Puffer zuschneiden
                                                 • Attribute vorschlagen, harmonisieren
                                                 • Dubletten finden
                               ◀── S2 ───────  PipelineResult (Layer, Vorschläge,
                                                 Prüfhinweise, harmonisierte Datensätze)
 4 Prüfhinweise anzeigen       ◀── S3
 5 Attributzuordnung bestätigen ── S5 ─────▶  Datensätze neu harmonisieren
 6 Unsichere Dubletten bestätigen ── S4 ───▶  bestätigte Gruppen zusammenführen
 7 Kartenthema wählen
 8 Ausgabe wählen
 9 Verarbeitung: Ergebnis-Layer bauen ◀ S6 ─  Geometrien in QGIS-lesbarer Form
   und in QGIS laden, GPKG/PDF speichern (S7)
```

**Merksatz:** Die Pipeline (Mac) *rechnet*, die Benutzerführung (Windows)
*zeigt an, fragt nach und lädt in QGIS*. Die Pipeline importiert nie
`qgis`, die Benutzerführung rechnet nie selbst Daten um. Die Stellen, an denen
beide sich die Hand geben, heißen **Schnittstellen S1–S7** (Abschnitt 5).

---

## 2. Grundregeln für die Zusammenarbeit

1. **Jede Person arbeitet nur in ihrem eigenen Branch.** Niemand arbeitet
   direkt auf `main`.
2. **Jede Datei hat eine Besitzerin oder einen Besitzer** (Tabelle in
   `CLAUDE.md`). Gemeinsame Dateien (`contracts.py`, `ui_contract.py`,
   `CLAUDE.md`, `PLAN.md`, `ARBEITSPLAN.md`, `metadata.txt`, `.gitignore`)
   werden nur nach Absprache und in einem eigenen kleinen Pull Request geändert.
3. **Kleine Pull Requests (PRs).** Lieber drei kleine PRs als ein großer. Die
   andere Person prüft jeden PR, bevor er in `main` kommt.
4. **Bescheid sagen.** Kurze Nachricht im Chat: „Ich arbeite jetzt an Schritt
   M3" oder „PR für W2 ist offen, kannst du schauen?".
5. **Echte ALKIS-Daten bleiben lokal** im Ordner `daten/` (von Git ignoriert),
   niemals im Repo und niemals hochladen.

### Der tägliche Ablauf (für beide gleich)

**Zu Beginn einer Arbeitssitzung** – den neuesten Stand holen:

```bash
git switch main
git pull
git switch <dein-branch>
git merge main
```

*Absicht:* Du arbeitest auf dem Stand, den die andere Person schon in `main`
gebracht hat. So entstehen weniger Konflikte.

**Am Ende einer Arbeitssitzung** – deine Arbeit teilen:

```bash
python -m pytest
git add <geänderte Dateien>
git commit -m "Kurze Beschreibung, was und warum"
git push
```

Dann auf GitHub einen Pull Request öffnen (oder den bestehenden aktualisieren)
und der anderen Person Bescheid sagen.

*Absicht:* Lokale Änderungen sieht die andere Person nicht. Erst nach `push`
sind sie auf GitHub, erst nach dem Merge in `main` bei allen.

### Wenn ein Merge-Konflikt auftritt

Nicht einfach eine Seite löschen. Die Datei gemeinsam anschauen, entscheiden,
welche Variante fachlich richtig ist, Konfliktmarkierungen (`<<<<<<<`,
`=======`, `>>>>>>>`) entfernen, Tests laufen lassen, committen. Im Zweifel:
stoppen und im Call klären.

---

## 3. Gemeinsame Schritte (beide zusammen)

### G0 – Kick-off: diesen Plan zusammen lesen (ca. 30 min)

- **Absicht:** Beide haben dasselbe Bild davon, wer was macht und wo die
  Schnittstellen sind.
- **Ziel:** Fragen zu diesem Plan sind geklärt; die offenen Entscheidungen
  unten (G2) haben eine erste Antwort oder einen Termin.
- **Dateien:** keine.

### G1 – PR-Übung mit echtem Code (zusammen mit M1 und W1)

- **Absicht:** Einmal gemeinsam den kompletten Weg erleben: Branch → Push →
  Pull Request → Review → Merge → beide holen den neuen Stand.
- **Ziel:** Der Branch `feature/pipeline-zuschnitt` ist in `main`, und
  beide haben ihn mit `git pull` geholt.
- **Wer:** Person Mac öffnet den PR (M1), Person Windows prüft und mergt (W1).

### G2 – Entscheidungen, die wir gemeinsam treffen müssen

Diese Punkte sind **fachliche** Entscheidungen. Claude kann sie nicht für uns
treffen. Ergebnis jeweils kurz unten in `CLAUDE.md` unter „Getroffene
Entscheidungen" eintragen.

| # | Frage | Vorschlag | Betrifft |
| --- | --- | --- | --- |
| E1 | Wie genau sieht das Donnerschwee-Polygon aus? | Person Mac zeichnet es in QGIS, speichert `daten/donnerschwee_gebiet.gpkg` (EPSG:25832) und schickt es per Mail/Cloud (nicht über Git). | Testen, W3 |
| E2 | Sollen Attributvorschläge pro Layer gelten? Heute ist die Liste für alle Layer gemischt; gleiche Feldnamen in zwei Layern kollidieren. | Ja: `AttributeSuggestion` bekommt ein Feld `layer_id`. | **Vertrag** `contracts.py`, M4, W5 |
| E3 | Wer setzt bei Prüfhinweisen `confirmed`? | Die Benutzerführung setzt `issue.confirmed = True/False`, wenn die Person bestätigt oder ablehnt. | S3, W5 |
| E4 | Dürfen Fehler (`severity="error"`) das Weiterklicken blockieren? | Nur wenn **gar keine** Daten übrig sind (`invalid-study-area`, `no-feature-layers`). Einzelne fehlerhafte Layer werden nur angezeigt. | W5 |
| E5 | Wie sieht das PDF aus (Format, Titel, Maßstab, Nordpfeil, Farben)? | Person Windows macht eine Skizze, beide entscheiden. | W8 |

**Wichtig:** Eine Änderung am Vertrag (`contracts.py`, z. B. für E2) macht
**eine** Person in einem eigenen kleinen PR, die andere prüft ihn. Erst nach
dem Merge bauen beide darauf auf.

### G3 – Zwischentest in QGIS (nach M3 und W4)

- **Absicht:** Früh merken, ob unsere Teile wirklich zusammenpassen – nicht
  erst ganz am Ende.
- **Ziel:** Auf **beiden** Rechnern: Plugin-ZIP installieren, Menü öffnen,
  Gebiet wählen, Donnerschwee-Ausschnitt laden, Prüfhinweise erscheinen.
- **Wenn etwas hakt:** Fehlermeldung notieren, entscheiden, wessen Teil
  betroffen ist, und dort einen kleinen Fix-Schritt einschieben.

### G4 – Abnahme des MVP (ganz am Ende)

- **Absicht:** Prüfen, ob das Plugin die 5 Abnahmekriterien aus `PLAN.md` §9
  erfüllt.
- **Ziel:** Der komplette 9-Schritte-Ablauf läuft mit dem Donnerschwee-
  Ausschnitt auf beiden Rechnern; Ergebnis-Layer erscheinen in QGIS;
  GeoPackage und PDF werden erzeugt; Warnungen stehen in der Zusammenfassung.
- **Danach:** `HANDOVER.md` aktualisieren, Version in `metadata.txt` erhöhen
  (gemeinsamer PR).

---

## 4. Schritte Person Mac – Datenpipeline

Branch-Namen: pro Schritt ein neuer Branch von `main`, z. B.
`feature/pipeline-geometrie-export`. Eigene Dateien: `urban_analysis/data_pipeline.py`,
`urban_analysis/geometry.py`, `tests/test_data_pipeline.py`, `tests/test_geometry.py`,
`STATUS_DATENPIPELINE.md`.

### M0 – Arbeitsumgebung (erledigt)

- **Absicht:** Tests lokal ausführen können.
- **Ziel:** `.venv/bin/python -m pytest` zeigt alle Tests grün.
- **Stand:** erledigt (Python 3.9 aus macOS, Ordner `.venv` ist von Git
  ignoriert).

### M1 – Pull Request für Zuschnitt und Dubletten öffnen (gehört zu G1)

- **Absicht:** Die schon fertige Arbeit (echtes Polygon statt Rechteck,
  CRS-Prüfung, unsichere Dubletten) in `main` bringen, damit Person Windows
  darauf aufbauen kann.
- **Ziel:** PR `feature/pipeline-zuschnitt → main` ist offen; Person Windows
  ist als Reviewer eingetragen.
- **Dateien:** keine neuen.
- **Warten auf:** nichts. **Andere Person wartet auf:** diesen Merge (für W4/W5).

### M2 – Status und Dateiliste aktualisieren

- **Absicht:** Dokumentation passt zum Code; beide Claude-Sessions kennen die
  neue Datei `geometry.py`.
- **Ziel:** `STATUS_DATENPIPELINE.md` beschreibt Zuschnitt, CRS-Regeln und
  Dubletten-Logik. In `CLAUDE.md` stehen `geometry.py` und `test_geometry.py`
  in der Zeile „Datenpipeline" (gemeinsame Datei → kleiner eigener PR).
- **Warten auf:** M1 gemergt.

### M3 – Geometrien für QGIS bereitstellen (Schnittstelle S6)

- **Absicht:** Person Windows muss aus den harmonisierten Datensätzen echte
  QGIS-Layer bauen. In den Datensätzen steckt die Geometrie aber noch im
  GeoPackage-Binärformat (mit „GP"-Kopf), das QGIS so nicht direkt liest.
- **Ziel:** Neue Funktion in `geometry.py`, ohne QGIS:
  `plain_geometry(value) -> bytes | str | None` – gibt reines WKB (Bytes) oder
  WKT (Text) zurück, `None` wenn keine Geometrie da ist. Mit Tests.
- **Warten auf:** M1. **Andere Person wartet auf:** M3 für W6.
- **Hinweis:** Früh machen, ist klein und schaltet W6 frei.

### M4 – Bestätigte Attributzuordnung anwenden (Schnittstelle S5)

- **Absicht:** Heute harmonisiert die Pipeline sofort mit den *automatischen*
  Vorschlägen. Wenn die Person im Assistenten eine Zuordnung ändert oder
  ablehnt, hat das noch **keine Wirkung** auf die Daten. Das widerspricht dem
  Abnahmekriterium „Nutzerkontrolle".
- **Ziel:**
  1. `HarmonizedRecord` behält zusätzlich die Original-Attribute
     (`source_attributes`).
  2. Neue Funktion `apply_attribute_decisions(result) -> list[HarmonizedRecord]`:
     harmonisiert alle Datensätze neu – mit `accepted`/`user_value` aus
     `result.attribute_suggestions`.
  3. Tests: Vorschlag abgelehnt → Zielfeld leer; Vorschlag geändert → anderes
     Quellfeld wird verwendet.
- **Warten auf:** Entscheidung **E2** und den Vertrags-PR dazu.

### M5 – Kategorien für ALKIS fachlich prüfen und Mapping auslagern

- **Absicht:** Heute landet z. B. der Layer `nutzung` in der Kategorie
  „Gebäude". `PLAN.md` §3.4 wünscht außerdem, dass Mapping-Regeln nicht nur im
  Code stehen.
- **Ziel:** `gebaeude → Gebäude`, `nutzung → Nutzungsflächen`, Straßen und
  Grünflächen werden über passende ALKIS-Werte erkannt. Die Regeln stehen in
  einer kleinen Datei `urban_analysis/mapping_rules.json` (Pipeline-Datei).
- **Warten auf:** E1 (Testgebiet), damit man an echten Daten prüfen kann.

### M6 – Pflichtfelder und fehlende Werte prüfen

- **Absicht:** `PLAN.md` Schritt 4 verlangt, Pflichtfelder und fehlende Werte
  zu prüfen.
- **Ziel:** Pro Layer ein zusammengefasster Hinweis, z. B. „312 Objekte in
  Layer gebaeude haben keine Objektart", mit Tests.
- **Warten auf:** nichts (kann parallel zu M5 laufen).

### M7 – Ende-zu-Ende-Test ohne QGIS (Vorbereitung für G4)

- **Absicht:** Automatisch prüfen, dass Pipeline und `GuidedWorkflow`
  zusammenpassen, ohne QGIS starten zu müssen.
- **Ziel:** Test in `tests/test_plugin_integration.py` (Absprache, da
  gemeinsame Testdatei): künstliches GeoPackage → `import_file` →
  `GuidedWorkflow` → Attribute bestätigen → Dubletten bestätigen → Thema
  wählen → `output_plan()`.
- **Warten auf:** M4, W5.

---

## 5. Schritte Person Windows – Benutzerführung und Integration

Branch-Namen: pro Schritt ein Branch von `main`, z. B. `feature/ui-dateiauswahl`.
Eigene Dateien: `urban_analysis/urban_analysis_plugin.py`,
`urban_analysis/guided_dialog.py`, `urban_analysis/outputs.py`,
`urban_analysis/user_guidance.py`, `tests/test_user_guidance.py`,
`tests/test_outputs.py`.

### W0 – Arbeitsumgebung einrichten

- **Absicht:** Auf Windows denselben Stand haben und Tests ausführen können.
- **Ziel:**
  1. Repo klonen bzw. `git switch main && git pull`.
  2. `CLAUDE.md` und diesen Plan lesen (oder von Claude lesen lassen).
  3. Tests laufen. Unter Windows am einfachsten in der **OSGeo4W Shell**, die
     mit QGIS installiert wird: `python -m pip install pytest`, dann im
     Repo-Ordner `python -m pytest`.
- **Warten auf:** nichts.

### W1 – Den ersten PR der anderen Person prüfen und mergen (gehört zu G1)

- **Absicht:** Lernen, wie man einen PR liest, kommentiert und freigibt – und
  die neue Pipeline in `main` holen.
- **Ziel:** Auf GitHub beim PR „Files changed" ansehen, Fragen als Kommentar
  stellen, dann „Approve" und „Merge". Danach `git switch main && git pull`.
- **Warten auf:** M1.

### W2 – Assistent direkt aus dem Menü starten

- **Absicht:** Heute startet der Assistent nur, wenn vorher in der
  Python-Konsole ein `PipelineResult` übergeben wurde. Studierende sollen
  einfach auf den Menüeintrag klicken können.
- **Ziel:** Klick auf „Urban Analysis" öffnet den Assistenten sofort. Die
  Seiten 1–3 (Projekt-CRS, Untersuchungsgebiet, Daten laden) brauchen noch
  kein `PipelineResult`. Die Seiten 4–9 werden erst gefüllt, wenn die Daten
  geladen sind (in Qt geht das mit `QWizardPage.initializePage()`).
- **Dateien:** `urban_analysis_plugin.py`, `guided_dialog.py`.
- **Warten auf:** nichts – kann sofort starten.

### W3 – Untersuchungsgebiet in QGIS auswählen statt WKT tippen

- **Absicht:** Niemand soll Koordinaten als Text eintippen müssen.
- **Ziel:** Auf Seite 2 eine Auswahlliste aller **Polygon-Layer** des Projekts
  (`QgsMapLayerComboBox` mit Polygon-Filter) und die Option „nur ausgewählte
  Objekte". Daraus wird ein WKT-Text gemacht:
  - mehrere Objekte zusammenfassen (`QgsGeometry.unaryUnion`),
  - falls der Layer ein anderes CRS hat als das Projekt-CRS: umrechnen
    (`QgsCoordinateTransform`),
  - dann `geometry.asWkt()`.
  Das Ergebnis muss ein Polygon oder MultiPolygon im Projekt-CRS sein.
- **Dateien:** `guided_dialog.py` (QGIS-Teil).
- **Warten auf:** nichts; zum Testen hilft das Polygon aus E1.

### W4 – GeoPackage auswählen und Pipeline starten (Schnittstelle S1)

- **Absicht:** Seite 3 „Daten laden" soll die Pipeline wirklich aufrufen.
- **Ziel:**
  1. Knopf „Datei wählen …" (`QFileDialog.getOpenFileName`, Filter
     `GeoPackage (*.gpkg)`).
  2. Beim Weiterklicken: `GeoPackageImporter().import_file(...)` aufrufen
     (genaue Form siehe S1), währenddessen Sanduhr-Cursor anzeigen.
  3. Fehler (`GeoPackageImportError`, `ValueError`) als Meldung zeigen und auf
     der Seite bleiben.
  4. Mit dem Ergebnis `plugin.start_workflow(result)` aufrufen.
- **Dateien:** `guided_dialog.py`, `urban_analysis_plugin.py`.
- **Warten auf:** W2. Für echte Tests: M1 gemergt.
- **Hinweis:** Mit dem kompletten ALKIS-Datensatz dauert der Import ca. 2–3
  Sekunden. Für den MVP ist das ohne `QgsTask` in Ordnung; `QgsTask` ist ein
  späterer Schritt.

### W5 – Prüfhinweise verständlich anzeigen und bestätigen (S3, S4)

- **Absicht:** Abnahmekriterien „Warnungen" und „Datenqualität": Nutzerinnen
  und Nutzer sehen alle Probleme und entscheiden selbst.
- **Ziel:** Seite 4 zeigt die Hinweise sortiert:
  - **Fehler** (rot) – z. B. falsches CRS, Layer nicht übernommen,
  - **Warnungen** (gelb) – mit Kästchen „bestätigen", wenn
    `requires_confirmation` gesetzt ist; beim Weiterklicken
    `issue.confirmed` setzen (E3),
  - **Infos** (grau) – z. B. „8236 von 107450 Objekten liegen im Gebiet".
  Seite 6 „Harmonisierung": Für den Hinweis `uncertain-duplicate` fragen
  „Gruppen zusammenführen?". Bei Ja:
  `merge_confirmed_duplicates(result.harmonized_records, gruppen)` aufrufen und
  das Ergebnis zurück in `result.harmonized_records` schreiben.
- **Dateien:** `guided_dialog.py`, ggf. `user_guidance.py` + Tests.
- **Warten auf:** M1, Entscheidungen E3/E4.

### W6 – Ergebnis-Layer in QGIS bauen (Schnittstelle S6)

- **Absicht:** Die Pipeline liefert Datensätze, QGIS braucht Layer-Objekte.
  Das ist das fehlende Stück zwischen „Daten geprüft" und „Karte sichtbar".
- **Ziel:** Für jeden ausgewählten Layer (`result.selected_layers()`) einen
  Speicher-Layer bauen:
  - `QgsVectorLayer("<Geometrietyp>?crs=<Projekt-CRS>", name, "memory")`,
  - Felder = die 7 Zielfelder (`source_name`, `object_type`, `category`,
    `status`, `area_m2`, `year`, `source`),
  - pro Datensatz ein Feature; Geometrie über `plain_geometry(...)` aus M3:
    Bytes → `QgsGeometry.fromWkb(...)`, Text → `QgsGeometry.fromWkt(...)`.
  - Daraus das Wörterbuch `layer_objects = {layer_id: QgsVectorLayer}` für S7.
  Die Eingangslayer im Projekt bleiben unverändert.
- **Dateien:** `outputs.py` (+ Tests, soweit ohne QGIS möglich).
- **Warten auf:** M3.

### W7 – Attributzuordnung wirksam machen (Schnittstelle S5)

- **Absicht:** Änderungen auf Seite 5 sollen in den Daten ankommen.
- **Ziel:** Nach dem Bestätigen auf Seite 5
  `result.harmonized_records = apply_attribute_decisions(result)` aufrufen.
  Vorschläge pro Layer gruppiert anzeigen (E2).
- **Warten auf:** M4.

### W8 – Ausgabe und Zusammenfassung (Schnittstelle S7)

- **Absicht:** Abnahmekriterium „Ausgaben".
- **Ziel:**
  1. Auf Seite 8 Dateidialoge für GeoPackage- und PDF-Pfad (nur wenn
     angehakt).
  2. Auf Seite 9 `plugin.export_outputs(layer_objects=..., geopackage_path=...,
     pdf_path=...)` aufrufen.
  3. Die Zusammenfassung lesbar formatieren statt `str(dict)`: verarbeitete
     Layer, Warnungen, Änderungen, offene Probleme.
  4. PDF nach Entscheidung E5.
- **Warten auf:** W6.

### W9 – Plugin-ZIP bauen und in QGIS (Windows) testen

- **Absicht:** Prüfen, dass das Plugin außerhalb der Entwicklungsumgebung
  funktioniert.
- **Ziel:** ZIP ohne `__pycache__`, `.venv`, `daten/`; in QGIS über
  „Erweiterungen → Aus ZIP installieren" installieren; Ablauf einmal komplett
  durchklicken. Ergebnis kurz im PR notieren.
- **Warten auf:** W4 (erster Test), danach nach jedem größeren Schritt.

---

## 6. Die Schnittstellen im Detail

Jede Schnittstelle hat **eine Seite, die liefert**, und **eine Seite, die
benutzt**. Ändert die liefernde Seite die Form, muss sie vorher Bescheid
sagen.

### S1 – Pipeline aufrufen *(vorhanden)*

- **Liefert:** Mac. **Benutzt:** Windows (W4).
- **Code:**

  ```python
  from urban_analysis.data_pipeline import GeoPackageImporter, GeoPackageImportError

  result = GeoPackageImporter().import_file(
      pfad_zur_gpkg,                 # Text oder Path
      project_crs="EPSG:25832",      # Projekt-CRS aus Seite 1
      study_area_wkt=gebiet_wkt,     # Polygon/MultiPolygon als WKT im Projekt-CRS (W3)
      buffer_meters=500,             # Puffer aus Seite 2
  )
  ```

- **Wirft Fehler:** `GeoPackageImportError` (Datei fehlt / ist kein
  GeoPackage) und `ValueError` (CRS oder Gebiet leer, Puffer negativ). Alles
  andere kommt nicht als Fehler, sondern als Prüfhinweis (S3).

### S2 – Das Ergebnis `PipelineResult` *(vorhanden, `contracts.py`)*

| Feld | Inhalt |
| --- | --- |
| `layers` | Liste `LayerDescriptor` – je Layer `layer_id`, `name`, `geometry_type`, vorgeschlagene `category` |
| `attribute_suggestions` | Liste `AttributeSuggestion` – Quellfeld → Zielfeld mit `confidence`; UI setzt `accepted`/`user_value` |
| `issues` | Liste `ValidationIssue` – siehe S3 |
| `harmonized_records` | Liste `HarmonizedRecord` – je Objekt `layer_id`, `source_row_id`, `attributes` (7 Zielfelder), `geometry`, `duplicate_group` |
| `project_crs`, `study_area_wkt`, `buffer_meters` | wie beim Aufruf übergeben |

### S3 – Prüfhinweise *(vorhanden)*

Jeder Hinweis hat `code`, `message` (deutscher Text zum Anzeigen),
`severity` (`error`/`warning`/`info`), `requires_confirmation`, `confirmed`,
`rule`.

| code | severity | Bestätigen? | Bedeutung |
| --- | --- | --- | --- |
| `invalid-study-area` | error | – | Gebiet ist kein gültiges Polygon → keine Daten |
| `no-feature-layers` | error | – | GeoPackage enthält keine Layer |
| `crs-mismatch` | error | – | Layer hat anderes CRS → nicht übernommen |
| `geographic-crs-buffer` | error | – | CRS in Grad, Puffer in Metern unmöglich |
| `crs-unverified` | warning | **ja** | CRS nicht eindeutig erkennbar, wird als Projekt-CRS angenommen |
| `missing-geometry` | warning | – | Objekte ohne Geometrie wurden weggelassen |
| `unreadable-geometry` | warning | – | Objekte mit kaputter Geometrie wurden weggelassen |
| `missing-geometry-column` | warning | – | Layer ohne Geometriespalte |
| `duplicate-row` | warning | – | Exakte Dubletten wurden automatisch entfernt |
| `uncertain-duplicate` | warning | **ja** | Gleiche Geometrie, andere Attribute → siehe S4 |
| `clip-summary` | info | – | „X von Y Objekten liegen im Gebiet" |
| `missing-topic-category` | warning | ja (von UI selbst erzeugt) | Fehlende Kartenthema-Kategorie bestätigt |

`result.visible_issues()` liefert alle Fehler und Warnungen (ohne Infos).

### S4 – Unsichere Dubletten zusammenführen *(vorhanden, auf `feature/pipeline-zuschnitt`)*

- **Liefert:** Mac. **Benutzt:** Windows (W5).
- Zusammengehörige Datensätze haben dieselbe `duplicate_group`, z. B.
  `"gebaeude:12"`; alle anderen haben `None`.
- Nach der Bestätigung:

  ```python
  from urban_analysis.data_pipeline import merge_confirmed_duplicates

  result.harmonized_records = merge_confirmed_duplicates(
      result.harmonized_records, bestaetigte_gruppen   # z. B. alle Gruppen eines Layers
  )
  ```

  Pro bestätigter Gruppe bleibt der erste Datensatz, unbestätigte bleiben
  vollständig.

### S5 – Attributzuordnung anwenden *(fehlt noch → M4 / W7)*

- **Liefert:** Mac. **Benutzt:** Windows.
- **Geplante Form:**
  `result.harmonized_records = apply_attribute_decisions(result)`
- **Voraussetzung:** Entscheidung E2 (`AttributeSuggestion.layer_id`).

### S6 – Geometrien für QGIS-Layer *(fehlt noch → M3 / W6)*

- **Liefert:** Mac. **Benutzt:** Windows.
- **Geplante Form:**

  ```python
  from urban_analysis.geometry import plain_geometry

  roh = plain_geometry(record.geometry)
  if isinstance(roh, bytes):
      geom = QgsGeometry()
      geom.fromWkb(roh)
  elif isinstance(roh, str):
      geom = QgsGeometry.fromWkt(roh)
  ```

### S7 – Ausgabe *(vorhanden, Windows-intern)*

- `workflow.output_plan()` → welche Layer, ob GeoPackage/PDF.
- `plugin.export_outputs(layer_objects=..., geopackage_path=..., pdf_path=...)`
  lädt die Layer in QGIS und schreibt die Dateien. `layer_objects` kommt aus W6.

---

## 7. Reihenfolge auf einen Blick

```text
Woche/Etappe   Person Mac                    Gemeinsam            Person Windows
────────────   ──────────────────────────    ─────────────────    ─────────────────────────
Etappe 1       M1 PR öffnen ───────────────▶ G0 Kick-off, G1 ◀─── W0 Setup, W1 Review+Merge
               M2 Doku                       E1 Polygon           W2 Assistent aus Menü
               M3 plain_geometry (S6)        E2–E4 entscheiden    W3 Gebiet aus QGIS
Etappe 2       Vertrags-PR für E2 ─────────▶ Review durch W
               M4 Attribute anwenden (S5)                         W4 Datei + Pipeline (S1)
               M6 Pflichtfelder                                   W5 Hinweise + Dubletten (S3/S4)
                                             G3 Zwischentest
Etappe 3       M5 Kategorien/Mapping                              W6 Ergebnis-Layer (S6)
               M7 Ende-zu-Ende-Test                               W7 Attribute wirksam (S5)
                                             E5 PDF-Layout        W8 Ausgabe + Zusammenfassung
                                             G4 Abnahme           W9 ZIP-Test
```

**Wer auf wen wartet:**

- W4/W5 brauchen M1 (Zuschnitt + Dubletten in `main`).
- W6 braucht M3.
- M4 und W7 brauchen den Vertrags-PR zu E2.
- M7 braucht M4 und W5.
- G4 braucht alles.

Alles andere kann parallel laufen. Wer gerade warten muss, nimmt sich den
nächsten Schritt ohne Abhängigkeit (z. B. Mac: M6; Windows: W3).

---

## 8. So startest du deine Claude-Code-Session

Kopiere diesen Text zu Beginn in deine Session (Person und Schritt anpassen):

```text
Ich bin Person Windows (Benutzerführung). Lies CLAUDE.md und ARBEITSPLAN.md.
Wir machen jetzt Schritt W2. Arbeite nur an den Dateien, die bei W2 stehen.
Erkläre mir kurz, was du vorhast, bevor du Code änderst. Lass am Ende die
Tests laufen und frag mich, bevor du committest oder pushst.
```

---

## 9. Kleines Wörterbuch

| Begriff | Bedeutung |
| --- | --- |
| Branch | Eigener Arbeitszweig; Änderungen dort stören `main` nicht |
| Commit | Gespeicherter Zwischenstand mit Beschreibung |
| Push | Commits vom eigenen Rechner zu GitHub hochladen |
| Pull | Neuen Stand von GitHub auf den eigenen Rechner holen |
| Pull Request (PR) | Bitte an die andere Person: „Prüf meinen Branch und übernimm ihn in `main`" |
| Merge | Zwei Stände zusammenführen |
| Schnittstelle | Stelle, an der ein Teil dem anderen Daten oder Funktionen übergibt |
| Vertrag (`contracts.py`) | Gemeinsam festgelegte Form der übergebenen Daten |
| WKT / WKB | Geometrie als Text bzw. als Bytes (Standardformate) |
| CRS | Koordinatensystem, bei uns EPSG:25832 (ETRS89 / UTM 32N) |
