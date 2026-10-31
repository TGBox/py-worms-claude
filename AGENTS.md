# Agent Workspace Configuration

Dieses Projekt ('py-worms-claude') enthält projektspezifische Richtlinien und Skills für Coding-Agenten im Verzeichnis `.agents/`.

## Aktive Regeln (`.agents/rules/`)

- **Allgemeine Architektur & Code-Standards**: Grundregeln: Saubere Modularisierung, lesbarer Code, englische Variablennamen/Kommentare, deutsche Nutzeroberflächentexte.
- **Python & uv Best Practices**: Moderne Python-Standards: Paketmanagement mit uv, Typ-Annotationen, Ruff Linter/Formatter und Pytest.
- **Game Development & 2D-Engine Richtlinien**: Best Practices für 2D-Spiele: Saubere Game-Loop (Event/Update/Draw), Delta-Time-Bewegung, Fenster- und Vollbildmodus, Entkopplung von Spiellogik und Rendering.
- **Kern-Architektur (py-worms-claude)**: `src/core` ohne pygame, alle Spielwerte aus `GameScheme`, Simulationszufall nur über `RngStreams`, neue Waffen als Katalogeintrag. Plan: `docs/IMPLEMENTATION_PLAN.md`, Entscheidungen: `docs/adr/`.

## Aktive Skills (`.agents/skills/`)

- **Code-Review Skill**: Strukturierte Überprüfung von Code-Änderungen hinsichtlich Korrektheit, Lesbarkeit, Sicherheit und Performance.
- **Test-Runner & Diagnose Skill**: Automatisiertes Ausführen und Analysieren von Tests mit den passenden Werkzeugen des Projekts (pytest, cargo test, vitest, unity).

## Richtlinien für KI-Agenten

1. Lies vor größeren Änderungen die anwendbaren Regeln in `.agents/rules/`.
2. Verwende die Skills in `.agents/skills/` für automatisierte Workflows wie Reviews und Tests.
3. Behalte die Projektstruktur sauber und folge den etablierten Konventionen.
