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

## Steuerung

| Taste | Aktion |
|---|---|
| ← / → (A / D) | Laufen |
| ↑ / ↓ (W / S) | Zielen |
| Enter | Springen |
| 1–4 | Waffe wählen |
| Leertaste | Bazooka/Granate: halten zum Laden, loslassen zum Werfen · Schrotflinte: schießen |
| Linksklick | Luftschlag-Ziel wählen |
| Rechte Maustaste ziehen | Kamera verschieben |
| P | Pause |
| ESC | Zurück zum Menü (im Menü: Beenden) |
| F11 | Vollbild umschalten |

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
```
py-worms-claude/
├── assets/
│   ├── audio/          # Sound-Effekte und Musik (derzeit ungenutzt)
│   ├── maps/           # PNG-Karten (Doppelinsel, Canyon)
│   └── sprites/        # Texturen, Sprites und Grafiken
├── src/
│   ├── core/           # Reine Spiellogik ohne pygame
│   │   ├── terrain.py  # Zerstörbares Pixel-Terrain
│   │   ├── mapgen.py   # Prozeduraler Insel-Generator
│   │   ├── entities.py # Würmer und Geschosse
│   │   ├── weapons.py  # Waffendefinitionen
│   │   ├── world.py    # Physik, Explosionen, Schaden
│   │   ├── match.py    # Rundenablauf, Teams, Sieg
│   │   └── ai.py       # KI-Gegner
│   ├── render/         # pygame-Darstellung (Terrain, Welt, HUD, Effekte, Kamera)
│   ├── scenes/         # Menü und Spielszene
│   ├── maps.py         # Karten laden (Zufall oder PNG)
│   ├── main.py         # Game-Loop, Fenster, Letterboxing
│   ├── settings.py     # Auflösung, Physik-Konstanten, Farben
│   ├── tools.py        # Format & Lint Helfer
│   └── build.py        # PyInstaller Build-Skript
└── tests/
    ├── test_core.py    # Logik-Tests (Terrain, Physik, Waffen, Runden, KI)
    ├── test_smoke.py   # Headless-Tests der kompletten pygame-Anwendung
    └── test_game.py    # Einstellungen
```
