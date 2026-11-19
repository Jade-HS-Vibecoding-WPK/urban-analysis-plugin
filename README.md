# Urban Analysis – QGIS-Plugin für städtebauliche Bestandsanalysen

Ein QGIS-Plugin, das Studierende Schritt für Schritt von der leeren Karte zu einer
sauberen Datengrundlage führt: Es lädt Daten für ein selbst gewähltes Gebiet
(OpenStreetMap, amtliches ALKIS oder eigene Dateien), führt sie zusammen, bereinigt
sie, prüft auf Dopplungen und erzeugt daraus geordnete Karten-Layer, eine
Erreichbarkeitsanalyse und ein PDF.

Entstanden im Wahlpflichtkurs „KI / Vibecoding“ an der Jade Hochschule, Fachbereich
Architektur, Studiengang Urban Design (Wintersemester 2026/27).

> **Stand:** experimentell (Version 0.1). Das Plugin funktioniert für ganz Deutschland,
> getestet wurde vor allem in Oldenburg (Niedersachsen).

---

## Unser Anspruch: nah an den Daten, fachlich sauber

Das Plugin soll nichts „schöner rechnen“, als die Daten sind:

- **Rohdaten bleiben unverändert** – Ergebnisse entstehen als neue Layer und Dateien.
- **Nichts passiert still** – Fehler, Lücken und unsichere Fälle erscheinen als Hinweis,
  Vorschläge des Plugins gelten erst, wenn du sie bestätigst.
- **Dopplungen mit Augenmaß** – exakt gleiche Objekte werden entfernt, ähnliche nur
  angezeigt; du entscheidest.
- **Herkunft bleibt sichtbar** – jedes Objekt behält Quelle und Dateiname, kein Wert geht
  verloren.
- **Grenzen werden genannt** – was die Daten nicht zeigen, steht dabei; Unsicheres ist als
  „vermutlich“ markiert.

---

## Was das Plugin kann

### Der Ablauf in 8 Schritten

1. **Projekt-KBS** – Koordinatensystem in Metern wählen (z. B. EPSG:25832).
2. **Untersuchungsgebiet** – Fläche in QGIS wählen oder zeichnen, Puffer festlegen.
   Die Größe wird gleich angezeigt (Warnung ab 25 km², kein Download über 50 km²).
3. **Daten laden** – OpenStreetMap, ALKIS deines Bundeslands und/oder eigene Dateien,
   auch mehrere zugleich.
4. **Layer prüfen** – Was ist angekommen, was fehlt? Hinweise mit Erklärung.
5. **Attributzuordnung** – Vorschau der späteren Attributtabelle mit lesbaren
   Spaltennamen; je Spalte „Kernfeld“, „Behalten“ oder „Ignorieren“.
6. **Harmonisierung** – Dopplungen und gleiche Objekte aus verschiedenen Quellen;
   je Kategorie wählst du die Quelle (das Plugin schlägt eine vor).
7. **Kartenthema** – Auswahl der Kategorien für die Karte.
8. **Verarbeitung** – Ergebnis-Layer erzeugen, Erreichbarkeit berechnen, speichern.

### Ergebnisse

- **Geordnete Ergebnis-Layer** in QGIS, je Kategorie ein Layer (z. B. ein Layer
  „Gebäude“ aus ALKIS und OSM zusammen), in Gruppen wie Bebauung, Verkehr,
  Grün & Wasser. Kleinkram wie Zäune liegt ausgeblendet unter „Sonstiges“.
- **Kartenstile:** Nutzungskarte (farbig), Schwarzplan, Graustufen (für Druck).
- **Erreichbarkeit:** Abstand jedes Gebäudes zum nächsten Ziel (z. B. Nahversorgung,
  Bildung, Haltestellen oder eigene Ziele), mit Ringen um die Ziele (Standard 300 m
  und 500 m).
- **PDF-Karte** mit Legende, Nordpfeil, Maßstab und Quellen.
- **GeoPackage** mit allen Ergebnis-Layern.

### Zwei Oberflächen-Stile

Über das Paletten-Symbol im Plugin-Fenster lässt sich jederzeit wechseln:

- **Klassisch** – hell und neutral wie QGIS selbst, mit blauem Akzent, QGIS-Schrift und
  gewohnten Bedienelementen. Oben zeigen Schrittpunkte und ein Ladebalken, wo du stehst.
- **Pixel** – verspielt, mit Einflüssen aus Spielen (Gamification): pastellige
  Pixel-Landschaft, ein angelnder Hase zieht beim Laden den Fortschritt heran, ein Fisch
  schwimmt zum aktuellen Schritt und beißt an, wenn etwas fertig ist. Alle Figuren sind
  selbst gezeichnet.

Beide Stile bieten dieselben Funktionen; der Kartenstil der Ergebnisse ist davon
unabhängig.

### In Arbeit

- **Kartenthemen:** sieben allgemeine Themen für Bestandsanalysen – Bebauung &
  Stadtstruktur, Nutzungen, Versorgung & soziale Infrastruktur, Freiraum & öffentlicher
  Raum, Mobilität & Erschließung, Grün, Wasser & Klima, Geschichte & Stadtbild – mit an-
  und abwählbaren Klassen. Katalog und Einordnung sind fertig, die Auswahl in Schritt 7
  folgt.

---

## Installation

Voraussetzung: **QGIS 3.44 oder neuer** (Windows oder macOS).

1. Plugin-ZIP besorgen – fertig herunterladen (sobald es unter „Releases“ eines gibt)
   oder im heruntergeladenen Repository selbst bauen:
   ```bash
   python build_plugin_zip.py
   ```
   Das Skript packt nur den Plugin-Code und bricht ab, falls versehentlich Daten,
   Passwörter oder persönliche Pfade enthalten wären.
2. In QGIS: **Erweiterungen → Erweiterungen verwalten und installieren → Aus ZIP
   installieren** und die ZIP-Datei wählen.
3. Weil das Plugin experimentell ist: unter **Einstellungen** „Auch experimentelle
   Erweiterungen anzeigen“ anhaken.
4. Das Plugin erscheint im Menü und in der Werkzeugleiste als **Urban Analysis**.

---

## Daten und Lizenzen

Das Plugin enthält **keine Geodaten**. Es lädt sie beim Benutzen für dein Gebiet herunter
oder liest deine eigenen Dateien. Heruntergeladene Daten landen in einem Ordner, den du
wählst.

### Was welcher Lizenz unterliegt

| Bestandteil | Lizenz |
| --- | --- |
| Plugin: Code, Kataloge (Quellen, Kategorien, Kartenthemen), Icons | [Apache License 2.0](LICENSE) |
| OpenStreetMap-Daten (über Overpass oder den Niedersachsen-Zwischenspeicher) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) – Vermerk „© OpenStreetMap-Mitwirkende, ODbL“ |
| ALKIS-Daten | Lizenz des jeweiligen Bundeslands (Tabelle unten) |
| Eigene Dateien | die Lizenz deiner Daten – bitte im Feld „Datenquelle“ angeben |
| Deine Ergebnisse (Layer, GeoPackage, PDF) | die Lizenzen der darin enthaltenen Daten; aus OSM abgeleitete Daten bleiben unter der ODbL |

### ALKIS je Bundesland

| Land | Im Plugin | Lizenz | Quellenvermerk |
| --- | --- | --- | --- |
| Brandenburg | verfügbar | dl-de/by-2-0 | © GeoBasis-DE/LGB, dl-de/by-2-0 |
| Hamburg | verfügbar | dl-de/by-2-0 | © FHH, LGV, dl-de/by-2-0 |
| Hessen | verfügbar | dl-de/zero-2-0 | © HVBG |
| Mecklenburg-Vorpommern | verfügbar | CC BY 4.0 | © GeoBasis-DE/M-V ‹Jahr›, CC BY 4.0 |
| Niedersachsen | verfügbar | CC BY 4.0 | © GeoBasis-DE/LGLN ‹Jahr›, CC BY 4.0 |
| Nordrhein-Westfalen | verfügbar | dl-de/zero-2-0 | © GeoBasis NRW |
| Rheinland-Pfalz | verfügbar | dl-de/by-2-0 | © GeoBasis-DE / LVermGeoRP ‹Jahr›, dl-de/by-2-0 |
| Sachsen | verfügbar | dl-de/by-2-0 | © GeoSN, dl-de/by-2-0 |
| Schleswig-Holstein | verfügbar | CC BY 4.0 | © GeoBasis-DE/LVermGeo SH, CC BY 4.0 |
| Thüringen | verfügbar | CC BY 4.0 | © GDI-Th |
| Baden-Württemberg, Bayern, Berlin, Bremen, Saarland | kommt später | – | – |
| Sachsen-Anhalt | nicht frei abrufbar | – | – |

Lizenztexte: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de),
[dl-de/by-2-0](https://www.govdata.de/dl-de/by-2-0),
[dl-de/zero-2-0](https://www.govdata.de/dl-de/zero-2-0).

Die Quellenvermerke trägt das Plugin automatisch in die Attributtabelle (Spalte
„Datenquelle“) und ins PDF ein. **Bitte keine lizenzpflichtigen Daten weitergeben oder
veröffentlichen.**

---

## Grenzen und Hinweise

- **Erreichbarkeit ist Luftlinie.** Echte Fußwege sind meist 20–30 % länger; Ziele
  außerhalb des geladenen Gebiets fehlen, am Rand sind Abstände deshalb eher zu groß.
- **OSM ist unterschiedlich vollständig.** Geschosszahlen, Bänke oder Bäume fehlen oft;
  ALKIS ist bei Gebäuden meist vollständiger.
- **Deutung bleibt bei dir.** Raumkanten, Typologien, Aufenthaltsqualität, Sichtachsen
  oder Leerstand zeigen die Daten nicht.
- **Dienste können ausfallen.** Overpass ist zeitweise überlastet, ALKIS-Dienste haben
  Wartungszeiten. Das Plugin meldet das; eine eigene Datei ist dann der Ausweg.
- **Keine Umprojektion im Hintergrund.** Passt das Koordinatensystem einer Quelle nicht,
  wird das angezeigt statt still umgerechnet.

---

## Hinweis zur KI-Nutzung

Das Plugin ist in einem Kurs zum Programmieren mit KI entstanden. Code, Tests und Texte
wurden zu großen Teilen mit KI-Programmierassistenten (Claude Code, GitHub Copilot)
geschrieben – nach den Vorgaben des Teams. Fachliche Entscheidungen (was das Plugin
können soll, welche Daten wie behandelt werden) hat das Team getroffen; jede Änderung
wurde mit automatischen Tests und von Hand in QGIS geprüft.

Das Plugin selbst nutzt **keine KI** und sendet keine Daten an KI-Dienste. Es fragt nur
die genannten Datendienste ab (OpenStreetMap, ALKIS der Länder).

---

## Lizenz

Das Plugin steht unter der [Apache License 2.0](LICENSE). Für die Daten gelten die
Lizenzen der jeweiligen Quellen (siehe „Daten und Lizenzen“). Diese README ist keine
Rechtsberatung.
