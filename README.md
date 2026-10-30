# py-worms-claude

A python adaptation of the classic worms game.

## Framework
Entwickelt mit **Pygame-ce (Community Edition)**.

## Steuerung & Features
- **F11:** Vollbildmodus umschalten (Toggle zwischen Fenster- und Vollbild)
- **ESC:** Spiel beenden
- **Game-Loop:** Saubere Trennung von Event-Handling, Zustands-Update (`dt`) und Rendering

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
│   ├── audio/        # Sound-Effekte und Musik
│   └── sprites/      # Texturen, Sprites und Grafiken
├── src/
│   ├── __init__.py
│   ├── main.py       # Game-Loop & Einstiegspunkt
│   ├── settings.py   # Auflösung, FPS, Konstanten
│   ├── tools.py      # Format & Lint Helfer
│   └── build.py      # PyInstaller Build-Skript
└── tests/
    └── test_game.py  # Tests für Spiellogik
```