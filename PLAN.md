# Plan für das QGIS-Plugin zur Stadtgebietsanalyse

## 1. Produktziel

Das Plugin soll Urban-Design-Studierende bei der Analyse von Projektgebieten unterstützen. Es soll einen nachvollziehbaren Workflow anbieten, in dem Daten aus mehreren Quellen verarbeitet und anschließend für städtebauliche Fragestellungen ausgewertet werden.

Der Pilot bezieht sich auf den Stadtteil **Donnerschwee in Oldenburg**. Das
Kartenthema des MVP ist zunächst die **Siedlungsstruktur**.

Der vorgesehene Gesamtworkflow lautet:

**Daten laden → prüfen → bereinigen → harmonisieren → analysieren → visualisieren**

Dabei sollen Rohdaten unverändert bleiben. Bereinigte Daten und Analyseergebnisse werden als neue Layer beziehungsweise Ergebnisse erzeugt. Probleme, Änderungen und Unsicherheiten sollen sichtbar und in einem Prüfprotokoll dokumentiert werden.

## 2. MVP

Die erste Version soll bewusst klein und belastbar bleiben. Der verbindliche
MVP-Ablauf besteht aus diesen neun Schritten:

1. **CRS festlegen:** Das Projekt-CRS ist vorausgewählt und kann manuell
   geändert werden.
2. **Untersuchungsgebiet festlegen:** Ein Polygon wird im Projekt ausgewählt
   oder gezeichnet.
3. **Lokale Daten laden:** GeoPackage-Dateien werden geladen und mit einem
   Standardpuffer von **500 m** räumlich auf das Untersuchungsgebiet begrenzt.
   Der Nutzer kann diesen Wert ändern.
4. **Layer prüfen:** Alle geladenen Layer werden auf CRS, Geometrien,
   Pflichtfelder, fehlende Werte und grundlegende Konsistenz geprüft.
5. **Attribute zuordnen:** Das Plugin schlägt Zuordnungen automatisch vor;
   Nutzerinnen und Nutzer können diese Zuordnungen bestätigen oder ändern.
6. **Dopplungen und Harmonisierung prüfen:** Exakte Dopplungen werden
   automatisch entfernt. Unsichere Fälle bei IDs sowie Geometrien und
   Attributen werden angezeigt und müssen bestätigt werden.
7. **Kartenthema wählen:** Das Plugin schlägt **Siedlungsstruktur** und
   passende Layer wie Gebäude, Straßen, Nutzungsflächen und Grünflächen aus
   Layernamen, Attributen, Geometrietypen und Werten vor. Die Vorschläge sind
   nicht fest vorgegeben: Fehlende oder anders benannte Layer können bestätigt
   oder geändert werden und werden nachvollziehbar gewarnt.
8. **Ausgabe wählen:** QGIS-Layer sind verpflichtend. Eine bereinigte
   GeoPackage-Datei und ein PDF sind optionale Ausgaben.
9. **Verarbeitung starten:** Die Verarbeitung erzeugt die gewählten Ausgaben
   und eine Zusammenfassung mit Warnungen, Änderungen und offenen Problemen.

Externe Open-Source-Datenquellen, automatische Datenabfragen, weitere
Dateiformate und zusätzliche Kartenthemen sind ausdrücklich spätere
Erweiterungen. Rohdaten werden nicht überschrieben; bereinigte Kopien und
Ergebnislayer werden getrennt erzeugt.

## 3. Fachlicher und technischer Workflow

### 3.1 CRS und Untersuchungsgebiet

Beim Start ist das Projekt-CRS vorausgewählt. Die Nutzerin oder der Nutzer kann
es manuell ändern. Danach wird das Untersuchungsgebiet als Polygon ausgewählt
oder festgelegt. CRS und Polygon werden als Teil des Verarbeitungslaufs
protokolliert.

### 3.2 Lokale Daten laden und räumlich begrenzen

Im MVP werden lokale **GeoPackage-Dateien** geladen. Ein Standardpuffer von
**500 m** begrenzt die Daten räumlich um das Untersuchungsgebiet; der Nutzer
kann ihn ändern. Externe
Open-Source-Datenquellen und weitere Dateiformate werden erst später ergänzt.
Für jede Datenquelle wird dokumentiert:

| Punkt | Zu dokumentieren |
| --- | --- |
| Geometrietyp | Punkt, Linie oder Polygon |
| Koordinatensystem | zum Beispiel EPSG:25832, sofern für die Quelle zutreffend |
| wichtige Attribute | Feldnamen und fachliche Bedeutung |
| erwartete Fehler | zum Beispiel Duplikate oder fehlende Werte |
| Zielschema | standardisierte Feldnamen und Datentypen |
| Quelle und Lizenz | Herkunft der Daten und Nutzungsbedingungen |

Automatische Datenabfragen aus weiteren vorher festgelegten Quellen werden erst ergänzt, wenn der manuelle Ablauf zuverlässig funktioniert. Quellen sollen dann versioniert, nachvollziehbar und ausfalltolerant sein.

### 3.3 Daten und Layer prüfen

Das Plugin prüft unter anderem:

- Koordinatensysteme,
- gültige Geometrien,
- Duplikate,
- fehlende Werte,
- unterschiedliche Einheiten,
- widersprüchliche Kategorien und Attribute.

Jede Prüfung soll ihre Warnungen und Ergebnisse im Prüfprotokoll festhalten. Das Plugin soll keine unsicheren Korrekturen stillschweigend durchführen.

### 3.4 Attribute zuordnen und harmonisieren

Das Plugin schlägt Attributzuordnungen automatisch vor. Die Nutzerin oder der
Nutzer bestätigt diese Vorschläge oder ändert sie vor dem Start. Für jede
unterstützte Datenart wird ein gemeinsames Zielschema definiert. Dazu gehören:

- standardisierte Feldnamen,
- Datentypen,
- vorgeschlagene Kategorien und ihre nutzerbestätigten Zuordnungen,
- Einheiten.

Ein mögliches Zielschema aus dem fachlichen Konzept ist:

```text
source_name
object_type
category
status
area_m2
year
source
```

Die Überführung der Quellattribute wird über Mapping-Regeln dokumentiert, zum Beispiel:

```text
"Haltestellenart", "type", "category" → object_type
"Fläche", "area", "Shape_Area" → area_m2
```

Die Mapping-Regeln sollen später möglichst in Konfigurationsdateien oder einer einfachen Mapping-Tabelle verwaltet werden und nicht ausschließlich im Code stehen.
Kategorien werden nicht vorausgesetzt, sondern aus Layernamen, Attributen,
Geometrietypen und Werten vorgeschlagen. Die Datenquelle bleibt als
editierbares Feld unter Nutzerkontrolle.

### 3.5 Dopplungen und Konsistenz prüfen

IDs sowie Geometrien und Attribute werden auf Dopplungen, Widersprüche und
inkonsistente Inhalte geprüft. Exakte Dopplungen werden automatisch entfernt.
Unsichere Fälle werden angezeigt und erst nach Bestätigung bereinigt. Die
Rohdaten bleiben erhalten; jede Änderung wird in der Zusammenfassung
ausgewiesen.

### 3.6 Kartenthema und Ausgabe

Im MVP schlägt das Plugin das Kartenthema **Siedlungsstruktur** sowie passende
Layer aus Layernamen, Attributen, Geometrietypen und Werten vor. Gebäude,
Straßen, Nutzungsflächen und Grünflächen sind fachliche Zielkategorien, aber
keine starren Pflichtlayer. Nutzerinnen und Nutzer bestätigen oder ändern die
Vorschläge. Fehlende Kategorien können bewusst bestätigt werden, erzeugen aber
eine sichtbare Warnung.

QGIS-Layer sind die verpflichtende Ausgabe. Optional können eine bereinigte
GeoPackage-Datei und ein PDF erzeugt werden. Das PDF enthält mindestens eine
Karte des Untersuchungsgebiets mit dem gewählten Puffer und einer Legende.
Die Datenquelle ist ein editierbares, vom Nutzer kontrollierbares Feld und
wird im PDF sowie in den Ergebnismetadaten ausgegeben. Der Lauf endet mit
einer Zusammenfassung der verarbeiteten Layer, Warnungen, Änderungen und
offenen Probleme.

### 3.7 Analysieren und visualisieren

Jede Analyse soll möglichst als eigener QGIS-Processing-Algorithmus umgesetzt werden. Sie definiert:

- Eingabedaten,
- Parameter,
- Berechnung,
- Ergebnislayer,
- Kennwerte,
- Diagramme,
- eine sinnvolle Standarddarstellung,
- eine kurze Interpretation.

Die erste Darstellung im Pilot ist die **Siedlungsstruktur in Donnerschwee**.
Weitere Analysen, darunter ÖPNV-Erreichbarkeit, können auf dem stabilen
Datenvertrag aufbauen und werden erst danach ergänzt.

#### Spätere Erweiterungen

- **Externe Open-Source-Datenquellen:** Automatische Abfragen und
  Quellenverwaltung werden erst nach dem lokalen GeoPackage-MVP geprüft.
- **Weitere Formate:** Zusätzliche Eingabe- und Ausgabeformate werden später
  ergänzt.
- **ÖPNV und Fußwegenetz:** Erreichbarkeitsanalysen und Netzberechnungen sind
  spätere fachliche Erweiterungen.

### 3.8 Visualisieren

Zuerst werden verständliche Standardstile verwendet. Später können folgende Erweiterungen hinzukommen:

- Auswahl von Farbpaletten,
- eigene Klassifizierungsregeln,
- Kartenlayouts,
- Export von Karten, Tabellen und Diagrammen,
- eventuell ein zusammenfassender Analysebericht.

## 4. QGIS, Python, PyQGIS und Processing

Die technische Basis ist:

- **QGIS 3.44** als gemeinsame Zielumgebung,
- **Python** als Programmiersprache,
- **PyQGIS** für die Arbeit mit QGIS-Projekten, Layern und Geometrien,
- das **QGIS Processing Framework** für wiederverwendbare Verarbeitungsschritte und eigene Algorithmen.

Eine Person arbeitet mit Microsoft Windows, die andere mit macOS. Beide verwenden QGIS 3.44 und stimmen Erweiterungen, Projektstruktur und Testdaten ab. Datei- und Ordnerpfade werden im Plan und in der Implementierung plattformneutral behandelt; hardcodierte Windows- oder macOS-Pfade werden vermieden.

Die erste technische Version soll den vollständigen MVP-Ablauf von der
CRS-Auswahl bis zur Zusammenfassung abbilden. Die UI verwendet dafür
einheitliche, fachlich verständliche Begriffe: **Projekt-CRS**,
**Untersuchungsgebiet**, **Daten laden**, **Layer prüfen**,
**Attributzuordnung**, **Harmonisierung**, **Kartenthema**, **Ausgabe** und
**Verarbeitung starten**.

Die Architektur soll Rohdaten, bereinigte Daten und Analyseergebnisse strikt trennen. Verarbeitungsschritte werden protokolliert und Analysebausteine modular aufgebaut, damit später weitere Themen ergänzt werden können.

Die gemeinsame Basis liegt in diesen Dateien:

- `metadata.txt` und `urban_analysis/__init__.py` bilden die minimale
  installierbare QGIS-Plugin-Struktur.
- `urban_analysis/urban_analysis_plugin.py` registriert zunächst nur den
  gemeinsamen Menüeintrag und einen sichtbaren Hinweis, dass die MVP-Features
  noch nicht implementiert sind.
- `urban_analysis/contracts.py` definiert den gemeinsamen Datenvertrag:
  Projekt-CRS, Untersuchungsgebiet, 500-m-Standardpuffer, Layerbeschreibungen,
  sichtbare Attributvorschläge, Prüfhinweise, ausgewähltes Kartenthema,
  kontrollierte Datenquelle und Ausgaben.
- `urban_analysis/ui_contract.py` definiert die gemeinsame Reihenfolge der
  UI-Schritte, Beschriftungen und dynamischen Themenvorschläge.
- `tests/test_contracts.py` prüft die unveränderliche Basis des Vertrags.

Die Datenpipeline liefert später ein `PipelineResult` mit `layers`,
`attribute_suggestions`, `issues`, `selected_topic` und `output` an die
Benutzerführung. Die Benutzerführung zeigt Vorschläge und Prüfhinweise vor
der Verarbeitung und verwendet danach ausschließlich die bestätigten
Ergebnis-Layer. Diese gemeinsame Basis enthält noch keine vollständige
Datenpipeline, Kartenansicht oder PDF-Erzeugung.

## 5. Entwicklungsphasen

### Phase 0 – Gemeinsame Vorbereitung

- Minimale QGIS-Plugin-Struktur mit Menü, Dialog und testbarem Einstiegspunkt
  anlegen.
- Datenvertrag festlegen: CRS, Untersuchungsgebiet, Puffer, Layernamen,
  Pflichtfelder, IDs, Zielschema, Warnungen und Ausgabeobjekte.
- UI-Namenskonventionen aus Abschnitt 4 verbindlich übernehmen.
- Eine kleine lokale GeoPackage-Testdatei und einen reproduzierbaren
  End-to-End-Test bereitstellen.

### Phase 1 – Arbeitsstränge parallel umsetzen

**Arbeitsstrang A – Datenpipeline und Import**

- GeoPackage-Dateien laden und räumlich mit dem änderbaren Standardpuffer von
  500 m begrenzen.
- CRS und Untersuchungsgebiet verarbeiten.
- Layer-, Geometrie- und Konsistenzprüfungen umsetzen.
- Attributzuordnung vorschlagen und bestätigte Änderungen übernehmen.
- Kategorien aus Layernamen, Attributen, Geometrietypen und Werten vorschlagen.
- Exakte Dopplungen automatisch entfernen und unsichere Fälle zur Bestätigung
  anzeigen.

**Arbeitsstrang B – Benutzerführung und Ausgabe**

- Dialogschritte und verständliche Status-/Warnmeldungen umsetzen.
- Kartenthema Siedlungsstruktur mit dynamischen Vorschlägen und bewusster
  Bestätigung fehlender Kategorien abbilden.
- QGIS-Layer, optionales GeoPackage und optionales PDF mit Karte, Puffer und
  Legende ausgeben.
- Editierbare Datenquelle in Formular, Ergebnismetadaten und PDF anbieten.
- Zusammenfassung und Ergebnisdarstellung integrieren.

### Phase 2 – Integration und MVP-Test

- Beide Arbeitsstränge über den Datenvertrag verbinden.
- Zuerst A integrieren, anschließend B auf den echten Pipeline-Ergebnissen
  testen.
- Den vollständigen Ablauf mit der gemeinsamen GeoPackage-Testdatei prüfen.
- Erst nach erfolgreichem End-to-End-Test weitere Kartenthemen, externe
  Open-Source-Datenquellen oder zusätzliche Formate planen.

## 6. Offene Entscheidungen

Vor dem Start müssen noch festgelegt werden:

- konkretes Untersuchungsgebiet-Polygon und Beispiel-GeoPackage,
- genaue Testdaten und die zulässige Einheit für den änderbaren 500-m-Puffer,
- Details des Zielschemas je vorgeschlagener Kategorie,
- Schwelle, ab der ein Fall als unsichere Dopplung angezeigt wird,
- Details des PDF-Layouts über Karte, Puffer, Legende und Datenquelle,
- gemeinsamer Integrationspunkt und Abnahmekriterien.

Externe Open-Source-Datenquellen, weitere Formate und zusätzliche
Kartenthemen bleiben spätere Erweiterungen.

## 7. Rollen im Zweierteam

Die Rollen werden unabhängig vom Betriebssystem verteilt. Eine Person arbeitet mit Microsoft Windows, die andere mit macOS; beide arbeiten am gleichen fachlichen Ablauf und prüfen gegenseitig die Ergebnisse.

### Gemeinsame Vorbereitung

Beide Personen legen zuerst die minimale Plugin-Struktur, den Datenvertrag,
die UI-Namenskonventionen, Testdaten und die Abnahmekriterien gemeinsam fest.
Danach arbeitet jede Person in einer eigenen Copilot-Session, einem eigenen
Arbeitsordner und einem eigenen Branch.

### Arbeitsstrang A – Datenpipeline und Import

Branch: `feature/datenpipeline`

Verantwortlich sind CRS, Untersuchungsgebiet, GeoPackage-Import, räumliche
Pufferung, Layer- und Geometrieprüfung, Attributmapping, Duplikaterkennung und
Harmonisierung. Änderungen erfolgen möglichst in Daten-/Processing-Modulen,
Datenvertragsdefinitionen und zugehörigen Tests.

### Arbeitsstrang B – Benutzerführung und Ausgabe

Branch: `feature/benutzerfuehrung`

Verantwortlich sind Dialogschritte, Karten- und Warnmeldungen, das Kartenthema
Siedlungsstruktur, QGIS-Ausgabe sowie optionale GeoPackage- und PDF-Ausgabe.
Änderungen erfolgen möglichst in UI-, Darstellungs- und Exportmodulen sowie
zugehörigen Tests.

### Gemeinsame Schnittstelle

Arbeitsstrang A liefert an B ein versioniertes Verarbeitungsergebnis mit:

- Projekt-CRS und Untersuchungsgebiet,
- verarbeiteten Layern und ihren standardisierten Namen,
- Pflichtfeld-/Attributmapping,
- Warnungen und Prüfstatus,
- Duplikat- und Harmonisierungsergebnissen,
- der vom Nutzer bestätigten oder geänderten Datenquelle,
- auswählbaren QGIS-Layern und optionalen Exportdaten.

B darf diese Daten nur über den vereinbarten Vertrag verwenden. Änderungen am
Datenvertrag werden von beiden abgestimmt und zuerst in einem gemeinsamen
Integrations-Commit dokumentiert.

Gemeinsam entscheidet ihr über:

- fachliche Regeln,
- Zielschema,
- Testfälle,
- Prioritäten,
- die städtebauliche Sinnhaftigkeit der Analyseergebnisse.

Die Aufteilung ist eine Arbeitsaufteilung, keine vollständige Trennung. Beide sollten die wichtigsten Teile verstehen und sich gegenseitig prüfen.

## 8. Git- und GitHub-Anfängerworkflow

GitHub ist das gemeinsame Repository. Jede Person arbeitet zunächst in einer eigenen lokalen Kopie. `main` enthält möglichst den funktionierenden Stand; neue Funktionen werden in eigenen Branches entwickelt.

### Wichtige Begriffe

- **Repository:** Gemeinsamer Projektordner mit dem gesamten Code und Änderungsverlauf.
- **Commit:** Beschrifteter gespeicherter Zwischenstand einer überschaubaren Änderung.
- **Branch:** Separater Arbeitszweig für eine neue Funktion.
- **Pull Request:** Vorschlag, einen Branch zu prüfen und anschließend in `main` zu übernehmen.
- **Merge:** Zusammenführen des geprüften Branches mit `main`.

### Empfohlener Ablauf für zwei parallele Copilot-Sessions

Jede Person arbeitet in einem **eigenen lokalen Arbeitsordner** und in einem
**eigenen Branch**. Die beiden Copilot-Sessions dürfen nicht denselben
Arbeitsordner gleichzeitig verändern. Eine Datei, die gerade von einer Person
bearbeitet wird, wird nicht gleichzeitig von der anderen Person geändert.

1. Vor dem Start den eigenen Arbeitsordner öffnen und den aktuellen Stand holen:

   ```bash
   git switch main
   git pull origin main
   ```

2. Einen eigenen Aufgaben-Branch erstellen oder auswählen:

   ```bash
   git switch -c feature/datenpipeline
   ```

   Für die Benutzerführung wird entsprechend `feature/benutzerfuehrung`
   verwendet.

3. Kleine, klar abgegrenzte Änderungen umsetzen und regelmäßig committen:

   ```bash
   git add .
   git commit -m "Implement data pipeline step"
   ```

4. Den Branch zu GitHub hochladen:

   ```bash
   git push -u origin feature/datenpipeline
   ```

   Für die Benutzerführung wird der eigene Branch-Name eingesetzt.

5. Einen Pull Request erstellen. Die andere Person prüft den Code, schreibt bei
   Bedarf Kommentare und übernimmt den Branch nach der Zustimmung in `main`.

6. Vor dem Weiterarbeiten `main` aktualisieren und den eigenen Branch
   gegebenenfalls mit dem neuen Stand abgleichen:

   ```bash
   git switch main
   git pull origin main
   git switch feature/datenpipeline
   git merge main
   ```

   Ein `git pull` aktualisiert immer nur den **aktuell ausgewählten Branch**
   und nicht automatisch alle anderen Branches. Die Auswahl des
   Aufgabenbereichs erfolgt daher über den Branch und die dazugehörige
   Copilot-Session, nicht über `git pull`.

Der Windows-/macOS-Ablauf bleibt fachlich gleich: Beide verwenden dieselben Branch- und Commit-Regeln, dieselben relativen Projektpfade und dieselben Testdaten. Lokale Pfade werden nicht in den Code geschrieben. Wenn sich ein Schritt unter Windows und macOS unterschiedlich verhält, wird das Problem dokumentiert und zuerst gemeinsam geklärt, bevor eine technische Entscheidung getroffen wird.

Zu Beginn ist eine kleine gemeinsame Übung sinnvoll: Beide laden das Repository herunter, ändern jeweils eine kleine Datei, erstellen Commits und führen einen Branch über einen Pull Request zusammen. Danach kann derselbe Ablauf für den Plugin-Code verwendet werden.

### Zusammenarbeit zweier realer Personen mit getrennten Copilot-Sessions

Beide Personen starten vom selben **GitHub-Ausgangsbranch** (in der Regel
`main`). Jede Person arbeitet anschließend in einem eigenen Branch und einem
eigenen lokalen Arbeitsordner. Die Aufgaben werden vorher klar aufgeteilt:
Zum Beispiel bearbeitet eine Person die Datenpipeline und die andere die
Benutzerführung und Ausgabe. Beide stimmen außerdem ab, welche Dateien und
Schnittstellen jeweils in ihrem Aufgabenbereich liegen. Dieselbe Datei darf
nicht gleichzeitig in beiden Arbeitsordnern bearbeitet werden.

Lokale Änderungen in einer Copilot-Session sind für die andere Person
unsichtbar. Erst nach `git commit` und `git push` sind sie im gemeinsamen
GitHub-Repository verfügbar. Vor dem Teilen müssen die Änderungen daher
geprüft, committed und auf den eigenen Remote-Branch gepusht werden. Der
Pull Request ist die formale Übergabe: Die andere Person prüft diesen Branch,
gibt Rückmeldung und übernimmt ihn erst nach der Zustimmung.

`git pull` lädt ausschließlich bereits gepushte Änderungen des aktuell
ausgewählten Remote-Branches. Ungespeicherte oder nur lokal committed
Änderungen in der anderen Copilot-Session werden dadurch nicht übertragen.
Niemand arbeitet direkt auf `main`; Änderungen gelangen ausschließlich über
geprüfte Pull Requests in den gemeinsamen Ausgangsbranch.

Der aktuelle gemeinsame Stand ist **bereit für Commit und Push**. Ein Push
wird an dieser Stelle ausdrücklich noch nicht ausgeführt und erst nach
Bestätigung vorgenommen.

### Konfliktvermeidung und Vorgehen bei Konflikten

- Vor dem Bearbeiten absprechen, welche Person welche Dateien und
  Schnittstellen besitzt.
- Gemeinsame Dateien wie `PLAN.md`, zentrale Plugin-Einstiegspunkte und
  Konfigurationsdateien nicht gleichzeitig bearbeiten.
- Kleine Commits erstellen und Pull Requests möglichst früh öffnen.
- Vor einem Pull Request den eigenen Branch mit dem aktuellen `main` abgleichen.
- Bei einem Konflikt nicht einfach eine Seite überschreiben: Die betroffene
  Datei gemeinsam prüfen, die fachlich richtige Variante auswählen, die
  Konfliktmarkierungen entfernen, testen und anschließend committen.
- Wenn die richtige Lösung unklar ist, den Konflikt stoppen und zuerst im
  Team entscheiden. Ein Konflikt darf nicht durch stillschweigendes Weglassen
  von Änderungen „gelöst“ werden.

### Integration und Reihenfolge

- Die gemeinsame Vorbereitung wird zuerst abgeschlossen, damit beide auf
  derselben Plugin-Struktur und demselben Datenvertrag arbeiten.
- Arbeitsstrang A wird zuerst integriert, weil B dessen standardisierte Layer,
  Warnungen und Ausgabeobjekte benötigt.
- Danach wird Arbeitsstrang B integriert und mit den echten Ergebnissen aus A
  getestet.
- Änderungen am Datenvertrag, an zentralen Einstiegspunkten oder an gemeinsam
  genutzten Konfigurationsdateien werden nicht parallel vorgenommen.
- Jede Person bearbeitet nur die vereinbarten Dateien ihres Arbeitsstrangs.
  Gemeinsame Dateien werden in einem kurzen Integrationsschritt gemeinsam
  geändert.

### Vor dem Start gemeinsam festlegen

- genaue Anforderungen und ein kleines überprüfbares Ziel je Aufgabenbereich,
- welche Dateien und Ordner zu Datenpipeline beziehungsweise Benutzerführung
  gehören,
- gemeinsame Schnittstellen zwischen beiden Bereichen, zum Beispiel die
  erwarteten Layer und Parameter,
- gemeinsame Testdaten und ein reproduzierbarer Testablauf,
- der Integrationspunkt, an dem zuerst `feature/datenpipeline` und danach
  `feature/benutzerfuehrung` zusammengeführt und gemeinsam getestet werden,
- wer den Pull Request prüft und wer die Integration nach der Freigabe
  durchführt.

Für den Einstieg können GitHub Desktop unter Windows oder die Git-Funktionen in Visual Studio Code auf beiden Systemen genutzt werden. Benötigt werden GitHub-Konten, Git, ein Editor, QGIS 3.44 und die jeweilige Python-Umgebung. QGIS-Version, verwendete Plugins und Testdaten werden vor gemeinsamen Tests abgeglichen.

## 9. Tests und Qualitätssicherung

Tests begleiten jede Phase und werden von beiden gemeinsam durchgeführt:

- **Arbeitsstrang A:** Tests für CRS, Polygon und Puffer, GeoPackage-Import,
  gültige/ungültige Geometrien, Pflichtfelder, Attributmapping, IDs,
  Duplikate, Harmonisierung und unveränderte Rohdaten.
- **Arbeitsstrang B:** Tests für Dialogreihenfolge, Status- und Warnmeldungen,
  dynamische Kategorien, bewusst bestätigte fehlende Kategorien, QGIS-Layer
  sowie optionale GeoPackage- und PDF-Ausgabe mit Karte, Puffer, Legende und
  editierbarer Datenquelle.
- **Integration:** Ein End-to-End-Test mit der gemeinsamen GeoPackage-Datei
  prüft alle neun MVP-Schritte und die Zusammenfassung.

### Bestätigtes MVP-Abnahmekriterium

Der MVP ist fachlich abnahmefähig, wenn dieser Ablauf in genau dieser
Reihenfolge funktioniert:

1. Eine lokale GeoPackage-Datei laden.
2. Das CRS wählen; das Projekt-CRS ist vorausgewählt und kann manuell geändert
   werden.
3. Das Untersuchungsgebiet als Polygon und den Standardpuffer von 500 m
   festlegen; der Puffer ist änderbar.
4. Die Daten und Kategorien analysieren.
5. Attribute zuordnen sowie Dopplungen und Harmonisierung prüfen.
6. Das Kartenthema aus den erkannten Kategorien auswählen.
7. Nur die zum gewählten Thema passenden Ergebnis-Layer in QGIS anzeigen.

Alle Eingangslayer bleiben zunächst verfügbar und werden nicht ausgeblendet
oder gelöscht. Erst nach der Themenwahl zeigt das Plugin die passenden
Ergebnis-Layer an; nicht ausgewählte oder nicht passende Layer bleiben als
Eingangsdaten erhalten und werden bei Bedarf durch Warnungen erläutert.

### Zweites bestätigtes MVP-Abnahmekriterium: Nutzerkontrolle

Automatische Kategorie- und Attributvorschläge werden immer vor der
Verarbeitung angezeigt. Die Nutzerin oder der Nutzer kann jeden Vorschlag
bestätigen, ändern oder ergänzen. Keine automatische Zuordnung gilt ohne
sichtbare Nutzerkontrolle als endgültig.

### Drittes bestätigtes MVP-Abnahmekriterium: Datenqualität

Exakte Dopplungen werden automatisch entfernt. Unsichere Dopplungen erscheinen
in einer nachvollziehbaren Prüfliste und müssen von der Nutzerin oder dem
Nutzer bestätigt werden. Die getroffene Entscheidung und die verwendete
Prüfregel werden im Ergebnis dokumentiert und bleiben nachvollziehbar.

### Viertes bestätigtes MVP-Abnahmekriterium: Ausgaben

Die bestätigten thematischen Ergebnis-Layer werden in QGIS geladen. Optional
kann eine bereinigte GeoPackage-Datei gespeichert werden. Optional kann ein
PDF mit einer Karte des Untersuchungsgebiets, dem gewählten Puffer, einer
Legende und der vom Nutzer kontrollierbaren und änderbaren Datenquelle
erzeugt werden.

### Fünftes bestätigtes MVP-Abnahmekriterium: Warnungen

Fehlende oder nicht eindeutig zuordenbare Kategorien werden deutlich
angezeigt. Die Nutzerin oder der Nutzer kann bewusst fortfahren. Das Ergebnis
wird dann sichtbar als unvollständig markiert, und die Warnung bleibt in der
Zusammenfassung nachvollziehbar.

Vor einem Merge sollte die jeweils andere Person die Änderung prüfen. Die fachliche Prüfung ist genauso wichtig wie die technische Prüfung: Die Ergebnisse müssen für die gewählten städtebaulichen Fragen sinnvoll sein.

## 10. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
| --- | --- |
| Der Umfang wird zu groß, weil Datenimport, automatische Suche, vollständige Bereinigung, mehrere Themen und freie Gestaltung gleichzeitig umgesetzt werden sollen. | Mit einem kleinen MVP und einem durchgängigen Pilotworkflow beginnen. |
| Unsichere Fehler werden automatisch und falsch korrigiert. | Sichere Korrekturen automatisieren, unsichere Fälle markieren und alle Änderungen protokollieren. |
| Rohdaten gehen durch Verarbeitungsschritte verloren. | Rohdaten niemals überschreiben; bereinigte Kopien und getrennte Ergebnislayer erzeugen. |
| Zusammengeführte Tabellen bleiben unübersichtlich oder fachlich uneinheitlich. | Zielschema, Kategorien, Einheiten und Mapping-Regeln früh definieren und dokumentieren. |
| Automatische Datenquellen sind nicht verfügbar oder ändern sich. | Automatische Quellen erst nach dem stabilen manuellen Workflow ergänzen, versionieren und ausfalltolerant anbinden. |
| Die Ergebnisse sind technisch korrekt, aber städtebaulich nicht sinnvoll. | Fachliche Regeln und Analyseergebnisse gemeinsam bewerten. |
| Beide ändern dieselbe Datei und erzeugen Merge-Konflikte. | Aufgaben und Dateien absprechen, kleine Branches und Pull Requests verwenden. |
| Quellen, Lizenzen oder Datenschutz werden zu spät berücksichtigt. | Datenquellen, Lizenzen und Datenschutz von Anfang an dokumentieren. |

## 11. Nächste Schritte

1. Gemeinsame Vorbereitung mit minimaler Plugin-Struktur, Datenvertrag,
   UI-Namenskonventionen, Test-GeoPackage und Abnahmekriterien abschließen.
2. `feature/datenpipeline` für Import, CRS, Puffer, Prüfungen, Mapping und
   Harmonisierung umsetzen und separat testen.
3. `feature/benutzerfuehrung` für Dialog, Kartenthema und Ausgaben auf dem
   vereinbarten Vertrag umsetzen und separat testen.
4. Zuerst die Datenpipeline, danach die Benutzerführung integrieren und den
   vollständigen Neun-Schritte-MVP gemeinsam abnehmen.
5. Erst nach dieser Abnahme externe Open-Source-Datenquellen, weitere Formate
   oder zusätzliche Kartenthemen planen.
