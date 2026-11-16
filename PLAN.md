# Plan für das QGIS-Plugin zur Stadtgebietsanalyse

## 1. Produktziel

Das Plugin soll Urban-Design-Studierende bei der Analyse von Projektgebieten unterstützen. Es soll einen nachvollziehbaren Workflow anbieten, in dem Daten aus mehreren Quellen verarbeitet und anschließend für städtebauliche Fragestellungen ausgewertet werden.

Der Pilot bezieht sich auf den Stadtteil **Donnerschwee in Oldenburg**. Der fachliche Schwerpunkt liegt auf **Mobilität und ÖPNV-Erreichbarkeit**.

Der vorgesehene Gesamtworkflow lautet:

**Daten laden → prüfen → bereinigen → harmonisieren → analysieren → visualisieren**

Dabei sollen Rohdaten unverändert bleiben. Bereinigte Daten und Analyseergebnisse werden als neue Layer beziehungsweise Ergebnisse erzeugt. Probleme, Änderungen und Unsicherheiten sollen sichtbar und in einem Prüfprotokoll dokumentiert werden.

## 2. MVP

Die erste Version soll bewusst klein und belastbar bleiben:

- Nutzerinnen und Nutzer laden die Daten selbst in QGIS.
- Das Plugin kann vorhandene Layer auswählen und verarbeiten.
- Koordinatensysteme werden erkannt und vereinheitlicht.
- Geometriefehler, Duplikate, fehlende Werte und widersprüchliche Attribute werden erkannt und markiert.
- Attribute werden in ein vorher festgelegtes Zielschema überführt.
- Rohdaten werden nicht überschrieben; bereinigte Kopien werden erzeugt.
- Die Verarbeitung erzeugt einen Ergebnisordner oder eine Ergebnisgruppe im QGIS-Projekt.
- Es gibt einen Prüfbericht mit Warnungen, behobenen Problemen und dokumentierten Änderungen.
- Die erste Analyse betrachtet die ÖPNV-Erreichbarkeit anhand von Haltestellen und Einzugsbereichen.
- Im MVP werden dafür einfache **300-m-Luftlinienpuffer** um Haltestellen erzeugt.
- Ergebnisse bestehen zunächst aus einer Karte und den dazugehörigen Kennwerten.

Nicht Teil des ersten MVP sind die automatische Datensuche, eine umfangreiche automatische Fehlerkorrektur, die Erreichbarkeit entlang des tatsächlichen Fußwegenetzes und frei konfigurierbare Gestaltung. Die Nutzung des Fußwegenetzes ist eine spätere Erweiterung. Zunächst werden ausschließlich frei verfügbare Daten von **OpenStreetMap** verwendet.

## 3. Fachlicher und technischer Workflow

### 3.1 Daten laden

In der ersten Version werden vorhandene Layer manuell in **QGIS 3.44** geladen und im Plugin ausgewählt. Die erste Datenquelle ist **OpenStreetMap**. Für jede Datenquelle wird dokumentiert:

| Punkt | Zu dokumentieren |
| --- | --- |
| Geometrietyp | Punkt, Linie oder Polygon |
| Koordinatensystem | zum Beispiel EPSG:25832, sofern für die Quelle zutreffend |
| wichtige Attribute | Feldnamen und fachliche Bedeutung |
| erwartete Fehler | zum Beispiel Duplikate oder fehlende Werte |
| Zielschema | standardisierte Feldnamen und Datentypen |
| Quelle und Lizenz | Herkunft der Daten und Nutzungsbedingungen |

Automatische Datenabfragen aus weiteren vorher festgelegten Quellen werden erst ergänzt, wenn der manuelle Ablauf zuverlässig funktioniert. Quellen sollen dann versioniert, nachvollziehbar und ausfalltolerant sein.

### 3.2 Daten prüfen

Das Plugin prüft unter anderem:

- Koordinatensysteme,
- gültige Geometrien,
- Duplikate,
- fehlende Werte,
- unterschiedliche Einheiten,
- widersprüchliche Kategorien und Attribute.

Jede Prüfung soll ihre Warnungen und Ergebnisse im Prüfprotokoll festhalten. Das Plugin soll keine unsicheren Korrekturen stillschweigend durchführen.

### 3.3 Daten bereinigen

Automatisch sicher behebbare Fehler können korrigiert werden. Unsichere Fälle werden markiert, damit sie geprüft werden können. Änderungen sollen in einer Liste mit Warnungen und behobenen Problemen nachvollziehbar bleiben.

Die Rohdaten bleiben erhalten. Bereinigte Daten werden als neue Layer erzeugt, damit der Ausgangszustand jederzeit wiederhergestellt und verglichen werden kann.

### 3.4 Daten harmonisieren

Für jede unterstützte Datenart wird ein gemeinsames Zielschema definiert. Dazu gehören:

- standardisierte Feldnamen,
- Datentypen,
- Kategorien,
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

### 3.5 Analysieren

Jede Analyse soll möglichst als eigener QGIS-Processing-Algorithmus umgesetzt werden. Sie definiert:

- Eingabedaten,
- Parameter,
- Berechnung,
- Ergebnislayer,
- Kennwerte,
- Diagramme,
- eine sinnvolle Standarddarstellung,
- eine kurze Interpretation.

Die erste Analyse im Pilot ist die **ÖPNV-Erreichbarkeit in Donnerschwee**:

- Haltestellen aus OpenStreetMap werden als Eingabedaten verwendet.
- Für jede Haltestelle wird ein 300-m-Luftlinienpuffer erzeugt.
- Die Überlagerung der Puffer mit den verfügbaren Daten wird als Karte visualisiert und mit Kennwerten beschrieben.

Eine Erreichbarkeitsberechnung entlang des tatsächlichen Fußwegenetzes gehört nicht zum MVP und wird erst später geprüft.

#### Spätere Erweiterungen

- **Fußwegenetz:** Eine spätere Erweiterung kann die Erreichbarkeit entlang des tatsächlichen Fußwegenetzes prüfen.
- **ÖV-Erschließungsqualität:** Eine spätere Erweiterung kann bewerten, wie gut das Untersuchungsgebiet durch den öffentlichen Verkehr erschlossen ist. Dafür könnten beispielsweise Haltestellen, Linienangebot, Bedienhäufigkeit und/oder Einzugsbereiche berücksichtigt werden. Die genaue Methodik ist eine noch gemeinsam festzulegende fachliche Entscheidung.

### 3.6 Visualisieren

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

Die erste technische Version soll:

1. das Plugin öffnen,
2. vorhandene Layer auswählen lassen,
3. eine Verarbeitung starten,
4. einen Ergebnisordner oder eine Ergebnisgruppe im QGIS-Projekt erzeugen,
5. einen Prüfbericht ausgeben.

Die Architektur soll Rohdaten, bereinigte Daten und Analyseergebnisse strikt trennen. Verarbeitungsschritte werden protokolliert und Analysebausteine modular aufgebaut, damit später weitere Themen ergänzt werden können.

## 5. Entwicklungsphasen

### Phase 0 – Scope und Beispieldaten

- Das bestätigte Testgebiet ist der Stadtteil Donnerschwee in Oldenburg.
- OpenStreetMap als erste frei verfügbare Datenquelle festlegen.
- Den Pilotumfang auf Mobilität und ÖPNV-Erreichbarkeit begrenzen.
- Drei konkrete Analysefragen für den Piloten formulieren; diese sind noch offen.

### Phase 1 – Fachlichen Fokus und Datenkonzept festlegen

- Die erste Analyse als ÖPNV-Erreichbarkeit über Haltestellen und 300-m-Luftlinienpuffer festlegen.
- Benötigte Datensätze festlegen.
- Datenquellen, Geometrietypen, CRS, Attribute, erwartete Fehler sowie Lizenzen dokumentieren.
- Zielschema und erste Mapping-Regeln definieren.
- Festlegen, welche Entscheidungen das Plugin automatisiert und welche es nur vorschlägt.

### Phase 2 – Technischer Prototyp

- Plugin-Menü und einfachen Dialog erstellen.
- Layer-Auswahl und Parameterübergabe umsetzen.
- Processing-Anbindung herstellen.
- Ergebnisordner oder Ergebnisgruppe im QGIS-Projekt erzeugen.
- Ersten Prüfbericht ausgeben.

### Phase 3 – Datenprüfung und Bereinigung

- CRS erkennen und vereinheitlichen.
- Geometriefehler prüfen.
- Duplikate erkennen.
- Fehlende und widersprüchliche Attribute markieren.
- Bereinigte Kopien statt Überschreiben der Rohdaten erzeugen.
- Prüfprotokoll mit Warnungen und behobenen Problemen erstellen.

### Phase 4 – Attribut- und Datenharmonisierung

- Zielschema je Datenart umsetzen.
- Mapping-Regeln anwenden und dokumentieren.
- Unterschiedliche Kategorien, Datentypen und Einheiten vereinheitlichen.
- Konfigurierbare Mapping-Tabelle oder Konfigurationsdatei vorbereiten.

### Phase 5 – Erste Analysebausteine

- Mit einem Thema und einem vollständigen End-to-End-Workflow beginnen.
- Danach weitere Analysebausteine ergänzen.
- Jede Analyse als möglichst eigenständigen Processing-Algorithmus umsetzen.
- Karten, Kennwerte und einfache Diagramme erzeugen.

### Phase 6 – Gestaltung und Ausgabe

- Standardstile verbessern.
- Farbpaletten und Darstellungsregeln auswählbar machen.
- Karten-, Tabellen- und Diagrammexport ergänzen.

### Phase 7 – Automatische Datenquellen

- Festgelegte Datenquellen anbinden.
- Quellen- und Lizenzverwaltung ergänzen.
- Datenquellen versionieren und Ausfälle berücksichtigen.
- Die automatische Suche nicht als Ersatz für die manuelle Datenprüfung behandeln.

## 6. Offene Entscheidungen

Die folgenden Punkte sind ausdrücklich noch nicht entschieden und dürfen im Plan nicht vorweggenommen werden:

- **Drei Analysefragen:** Welche drei konkreten städtebaulichen Fragen soll die ÖPNV-Erreichbarkeitsanalyse in Donnerschwee beantworten?

Bestätigt sind das Testgebiet Donnerschwee in Oldenburg, der Pilot-Schwerpunkt Mobilität und ÖPNV sowie die erste Analyse mit 300-m-Luftlinienpuffern um OpenStreetMap-Haltestellen. Die Erreichbarkeit entlang des tatsächlichen Fußwegenetzes bleibt eine spätere Erweiterung. Bei Unsicherheiten wird vor einer Entscheidung zuerst nachgefragt; offene Punkte werden nicht stillschweigend festgelegt.

## 7. Rollen im Zweierteam

Die Rollen werden unabhängig vom Betriebssystem verteilt. Eine Person arbeitet mit Microsoft Windows, die andere mit macOS; beide arbeiten am gleichen fachlichen Ablauf und prüfen gegenseitig die Ergebnisse.

### Person A – Plugin und Nutzeroberfläche

- Dialoge und Nutzerführung,
- Layer- und Parameterauswahl,
- Ergebnisdarstellung,
- Processing-Anbindung,
- Kartenstile und Exporte.

### Person B – Daten und Analysen

- Datenmodell,
- CRS- und Geometrieprüfung,
- Duplikat- und Fehlererkennung,
- Attribut-Mapping,
- Analysealgorithmen,
- Testdatensätze.

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

### Empfohlener Ablauf

1. Beide verwenden QGIS 3.44 und holen vor einer neuen Aufgabe den aktuellen Stand:

   ```bash
   git switch main
   git pull origin main
   ```

2. Einen eigenen Branch für die Aufgabe erstellen:

   ```bash
   git switch -c feature/data-cleaning
   ```

3. Kleine, klar abgegrenzte Änderungen umsetzen und regelmäßig committen:

   ```bash
   git add .
   git commit -m "Add duplicate feature detection"
   ```

4. Den Branch zu GitHub hochladen:

   ```bash
   git push -u origin feature/data-cleaning
   ```

5. Einen Pull Request erstellen. Die andere Person prüft den Code, schreibt bei Bedarf Kommentare und übernimmt den Branch nach der Zustimmung in `main`.

Der Windows-/macOS-Ablauf bleibt fachlich gleich: Beide verwenden dieselben Branch- und Commit-Regeln, dieselben relativen Projektpfade und dieselben Testdaten. Lokale Pfade werden nicht in den Code geschrieben. Wenn sich ein Schritt unter Windows und macOS unterschiedlich verhält, wird das Problem dokumentiert und zuerst gemeinsam geklärt, bevor eine technische Entscheidung getroffen wird.

Zu Beginn ist eine kleine gemeinsame Übung sinnvoll: Beide laden das Repository herunter, ändern jeweils eine kleine Datei, erstellen Commits und führen einen Branch über einen Pull Request zusammen. Danach kann derselbe Ablauf für den Plugin-Code verwendet werden.

Um Merge-Konflikte zu vermeiden, sollten beide nicht dauerhaft dieselben Dateien ändern, vor neuen Aufgaben den aktuellen Stand von `main` holen, kleine Änderungen machen und absprechen, wer welchen Bereich bearbeitet. Wenn Git einen Konflikt nicht automatisch lösen kann, besprecht ihr die betroffene Stelle, entscheidet euch gemeinsam für die richtige Variante, bereinigt die Datei und bestätigt die Lösung.

Für den Einstieg können GitHub Desktop unter Windows oder die Git-Funktionen in Visual Studio Code auf beiden Systemen genutzt werden. Benötigt werden GitHub-Konten, Git, ein Editor, QGIS 3.44 und die jeweilige Python-Umgebung. QGIS-Version, verwendete Plugins und Testdaten werden vor gemeinsamen Tests abgeglichen.

## 9. Tests und Qualitätssicherung

Tests begleiten jede Phase und werden von beiden gemeinsam durchgeführt:

- Testfälle für CRS-Erkennung und -Vereinheitlichung,
- Tests für gültige und ungültige Geometrien,
- Tests für Duplikate,
- Tests für fehlende Werte,
- Tests für widersprüchliche Kategorien,
- Tests für Mapping-Regeln und Zielschema,
- Prüfung, dass Rohdaten nicht überschrieben werden,
- Prüfung des Prüfprotokolls mit Warnungen und behobenen Problemen,
- Prüfung, dass Processing-Algorithmen die erwarteten Layer, Kennwerte und Diagramme erzeugen,
- Tests mit realistischen Fehlerfällen in einem kleinen realen Testgebiet.

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

1. **Drei Analysefragen formulieren** – konkrete Fragen festlegen, die die ÖPNV-Erreichbarkeitsanalyse in Donnerschwee beantworten soll.
2. Die dafür notwendigen OpenStreetMap-Datensätze sammeln.
3. Eine Tabelle mit Datenquellen, Attributen, CRS, erwarteten Fehlern, Zielschema und Lizenz erstellen.
4. Die kleinste durchgängige Funktion festlegen und umsetzen:

   **Layer laden → prüfen → bereinigen → harmonisieren → eine Karte erzeugen**

5. Die Aufgaben im Zweierteam zwischen Windows und macOS aufteilen und einen gemeinsamen ersten Git- und GitHub-Übungsablauf durchführen.
6. Erst danach die Plugin-Struktur und den Processing-Algorithmus für die 300-m-Luftlinienpuffer weiter ausbauen.
