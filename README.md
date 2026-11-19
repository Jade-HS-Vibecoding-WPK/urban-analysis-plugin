# Urban Analysis – QGIS-Plugin für städtebauliche Bestandsanalysen

Ein QGIS-Plugin, das Studierende Schritt für Schritt von der leeren Karte zu einer
sauberen Datengrundlage führt: Es lädt Daten für ein selbst gewähltes Gebiet
(OpenStreetMap, amtliches ALKIS oder eigene Dateien), führt sie zusammen, bereinigt
sie, prüft auf Dopplungen und erzeugt daraus geordnete Karten-Layer, eine
Erreichbarkeitsanalyse und ein PDF.

Entstanden im Wahlpflichtkurs „KI / Vibecoding“ im Studiengang Urban Design an der
Jade Hochschule (Wintersemester 2026/27).

> **Stand:** experimentell (Version 0.1). Das Plugin funktioniert für ganz Deutschland,
> getestet wurde vor allem in Oldenburg (Niedersachsen).

---

## Unser Anspruch: nah an den Daten, fachlich sauber

Das Plugin soll nichts „schöner rechnen“, als die Daten sind. Deshalb gilt überall:

- **Rohdaten bleiben unverändert.** Bereinigte Daten und Ergebnisse entstehen immer als
  neue Layer bzw. neue Dateien.
- **Keine stillen Korrekturen.** Fehler, Lücken und unsichere Fälle werden als Hinweis
  angezeigt – mit einem Satz, was los ist, und einem Satz, was zu tun ist.
- **Vorschläge sind nur Vorschläge.** Spaltenzuordnungen, Kategorien und die Wahl der
  Quelle schlägt das Plugin vor; endgültig werden sie erst, wenn du sie bestätigst.
- **Dopplungen mit Augenmaß.** Exakt gleiche Objekte werden automatisch entfernt. Ähnliche
  Objekte (z. B. dasselbe Haus aus ALKIS und aus OSM) werden nur angezeigt und mit einem
  Beispiel erklärt – du entscheidest.
- **Herkunft bleibt sichtbar.** Jedes Objekt behält seine Quelle und den Dateinamen; die
  Lizenzvermerke kommen automatisch in Attributtabelle und PDF.
- **Kein Wert geht verloren.** Spalten werden lesbar benannt und geordnet; weggelassen wird
  eine Spalte nur, wenn sie im ganzen Layer leer ist oder du sie bewusst abwählst.
- **Genau zugeschnitten.** Ein Objekt gehört dazu, wenn sein Abstand zum
  Untersuchungsgebiet höchstens dem Puffer entspricht – nicht nur das umgebende Rechteck.
- **Grenzen werden genannt.** Was die Daten nicht hergeben (z. B. Leerstand,
  Aufenthaltsqualität, echte Wegelängen), steht als Hinweis dabei. Unsichere Zuordnungen
  sind als „vermutlich“ markiert.

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

| Quelle | Woher | Lizenz | Hinweis |
| --- | --- | --- | --- |
| OpenStreetMap | Overpass-API (ganz Deutschland) | ODbL 1.0 – „© OpenStreetMap-Mitwirkende“ | Ist der Server überlastet, springt für Niedersachsen ein vorberechneter Zwischenspeicher ein (mit Hinweis). |
| ALKIS (amtliches Liegenschaftskataster) | Dienste der Bundesländer | je Land, z. B. CC BY 4.0 oder dl-de | Frei abrufbar derzeit in BB, HH, HE, MV, NI, NW, RP, SN, SH, TH. Weitere Länder folgen; Sachsen-Anhalt bietet ALKIS nicht frei an. |
| Eigene Datei | z. B. GeoPackage, auch eigener ALKIS-Export | deine Verantwortung | Bitte die Lizenz deiner Daten im Feld „Datenquelle“ angeben. |

Die Quellenvermerke werden automatisch in die Attributtabelle (Spalte „Datenquelle“)
und ins PDF übernommen. **Bitte keine lizenzpflichtigen Daten weitergeben oder
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
- **Experimentell:** Fehler sind möglich. Rückmeldungen gern als Issue im Repository.

---

## Lizenz

Der Code steht unter der [Apache License 2.0](LICENSE). Für die Daten gelten die
Lizenzen der jeweiligen Quellen (siehe oben).
