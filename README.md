# py-worms-claude

Ein Worms-Klon in Python: rundenbasierte Artillerie-Schlachten auf zerstörbarem Pixel-Terrain.

## Framework

Entwickelt mit **Pygame-ce (Community Edition)**. Die komplette Spiellogik (`src/core/`) ist reines
Python ohne pygame und dadurch headless testbar.

## Features

- 2–4 Teams mit je 1–6 Würmern, jedes Team wahlweise **Mensch** (Hotseat) oder **KI**
- Zerstörbares Terrain: **zufällig generierte Inseln** (mit Höhlen und schwebenden Plattformen) oder
  **PNG-Karten** aus `assets/maps/`
- Waffen: **Bazooka** (windabhängig), **Granate** (3-s-Zünder, prallt ab), **Schrotflinte**
  (Sofortschuss), **Luftschlag** (5 Raketen, 1x pro Team)
- Wind, Fallschaden, Tod im Wasser, Rückstoß durch Explosionen, Rundentimer (45 s) und Rückzugszeit (3 s)
- KI simuliert Flugbahnen mit derselben Physik wie das Spiel und wählt den Schuss mit dem besten
  Schaden-Nutzen-Verhältnis (inkl. Wind, Abprallen und Eigenschaden)
- Kamera folgt Würmern und Geschossen, virtuelle Auflösung 1280×720 mit Letterboxing
- **Drei Sprungarten**: Vorwärtssprung, Hochsprung und Rückwärtssalto
- **Lebendige Würmer**: prozedurale Kriech-Animation aus Körpersegmenten, Blinzeln, Atmen,
  Gesichtsausdrücke (ängstlich bei naher Gefahr, verletzt, jubelnd), Waffe in der Hand beim Zielen
- **Wurm-Kollision** (im Schema): Würmer gehen durcheinander hindurch, blockieren sich oder werden
  überkrochen (Standard). Wer auf einem Wurm landet, rutscht ab
- KI läuft und springt zu besseren Schusspositionen
- **Hauptmenü** mit „Schnelles Spiel“ (Mensch gegen KI) und „Battle einrichten“ (Teams, Karte, Schema)
- **Spielschemata** (JSON): Zugzeit, Rückzug, Würmer, Gesundheit, Fallschaden, Wasserspiegel, Wind,
  Schwerkraft, Sprungkraft, Wurm-Kollision sowie Munition, Verzögerung und Stärke pro Waffe. Mitgeliefert: „Standard“, „Schnell“
- Deterministische Simulation mit festen Zeitschritten und Eingabeprotokoll (Grundlage für Replays)

## Steuerung

| Taste | Aktion |
| --- | --- |
| ← / → (A / D) | Laufen |
| ↑ / ↓ (W / S) | Zielen |
| Enter | Vorwärtssprung |
| Rücktaste | Hochsprung |
| Enter oder Rücktaste 2× schnell | Rückwärtssalto |
| 1–4 | Waffe wählen |
| Leertaste | Bazooka/Granate: halten zum Laden, loslassen zum Werfen · Schrotflinte: schießen |
| Linksklick | Luftschlag-Ziel wählen |
| Rechte Maustaste ziehen | Kamera verschieben |
| P | Pause |
| ESC | Zurück zum Menü (im Menü: Beenden) |
| F11 | Vollbild umschalten |

## Eigene Spielschemata

Schemata liegen als JSON-Dateien in `assets/schemes/` (mitgeliefert) und im Nutzerdatenordner
(`%APPDATA%\py-worms-claude\schemes\` unter Windows, sonst `~/.local/share/py-worms-claude/schemes/`).
Am einfachsten kopierst du `assets/schemes/standard.json` dorthin, änderst `name` und die Werte.
Das Schema erscheint dann unter „Battle einrichten“. Fehlende Felder bekommen Standardwerte.

Die Tastenbelegung lässt sich in `settings.json` im selben Ordner anpassen
(`{"version": 1, "controls": {"jump": ["return"], ...}}`, Tastennamen wie in pygame).

## Eigene Karten

Lege eine PNG-Datei in `assets/maps/`. Nicht-transparente Pixel sind fester Boden, transparente Pixel
sind Luft. Die Karte wird auf 2000×1000 Pixel skaliert, das Wasser beginnt bei y = 930. Die Farben
des Bildes werden als Terrain-Textur verwendet. Die Karte erscheint automatisch im Menü.

## Schnellstart

Voraussetzung: [uv](https://docs.astral.sh/uv/)

```bash
# Abhängigkeiten synchronisieren
uv sync

# Spiel starten
uv run main

# Tests ausführen
uv run test

# Code formatieren & prüfen
uv run format
uv run lint

# Standalone-Executable bauen (PyInstaller)
uv run build
```

## Projektstruktur

```text
py-worms-claude/
├── assets/
│   ├── audio/          # Sound-Effekte und Musik (derzeit ungenutzt)
│   ├── maps/           # PNG-Karten (Doppelinsel, Canyon)
│   ├── schemes/        # Spielschemata (Standard, Schnell)
│   └── sprites/        # Texturen, Sprites und Grafiken
├── docs/               # Implementierungsplan und Architekturentscheidungen (ADRs)
├── src/
│   ├── core/           # Reine Spiellogik ohne pygame
│   │   ├── constants.py   # Feste Simulationskonstanten
│   │   ├── scheme.py      # Spielschema (alle einstellbaren Regeln)
│   │   ├── rng.py         # Benannte, deterministische Zufallsströme
│   │   ├── events.py      # Typisierte Ereignisse + Ereignisbus
│   │   ├── persistence.py # Datenordner, versioniertes JSON, Migrationen
│   │   ├── physics.py     # Körper-Basis, Raster-Abfragen
│   │   ├── terrain.py     # Zerstörbares Pixel-Terrain
│   │   ├── mapgen.py      # Prozeduraler Insel-Generator
│   │   ├── entities.py    # Würmer und Geschosse
│   │   ├── weapons/       # Waffen-Register, Verhaltensbausteine, Katalog
│   │   ├── world.py       # Bewegung, Explosionen, Schaden
│   │   ├── match.py       # Rundenablauf, Teams, Sieg, Eingabeprotokoll, Replay
│   │   └── ai.py          # KI-Gegner
│   ├── render/         # pygame-Darstellung (Terrain, Welt, Wurm-Animation, Waffen-Icons, HUD, Effekte, Kamera)
│   ├── scenes/         # Hauptmenü, Battle-Setup und Spielszene
│   ├── maps.py         # Karten laden (Zufall oder PNG)
│   ├── controls.py     # Aktions-Mapping und Tastenbelegung
│   ├── jump_input.py   # Doppeltipp-Erkennung für den Rückwärtssalto
│   ├── main.py         # Game-Loop, Fenster, Letterboxing
│   ├── settings.py     # Darstellung: Auflösung, Farben, Team-Vorgaben
│   ├── tools.py        # Format & Lint Helfer
│   └── build.py        # PyInstaller Build-Skript
└── tests/
    ├── test_core.py        # Logik-Tests (Terrain, Physik, Waffen, Runden, KI)
    ├── test_foundation.py  # Schema, Ereignisse, Register, Persistenz, Determinismus
    ├── test_performance.py # Leistungsbudget der Simulation
    ├── test_movement.py    # Sprünge, Wurm-Zustände, Kollisionsmodi, KI-Bewegung
    ├── test_smoke.py   # Headless-Tests der kompletten pygame-Anwendung
    └── test_game.py    # Einstellungen
```
