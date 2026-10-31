# ADR-0001: Datengetriebene Waffen aus Verhaltensbausteinen

- **Status:** Angenommen · **Datum:** 2026-10-31 · **Phase:** 0

## Kontext

Bis 1.0 sollen rund 45 Waffen und Werkzeuge entstehen. Heute steckt jede Feuerart als eigener Zweig
in `World` (`fire_projectile`, `fire_hitscan`, `launch_airstrike`) und als `FireMode` in `Match`.
Jede neue Waffe würde mehrere Kernklassen berühren.

## Optionen

1. **Eine Unterklasse pro Waffe.** Maximal flexibel, aber viel duplizierter Code und keine
   Konfigurierbarkeit über das Spielschema.
2. **Reine Daten (JSON) ohne Code-Erweiterung.** Einfach, scheitert aber an Sonderfällen
   (Seil, lenkbares Schaf).
3. **Hybrid:** `WeaponDef` (Daten) verweist auf einen Baustein im Register. Bausteine sind
   parametrisierte Python-Klassen (`ballistic`, `cluster`, `hitscan`, `melee`, `placed`, `walker`,
   `homing`, `airstrike`, …). Sonderfälle sind eigene Klassen im selben Register.

## Entscheidung

Option 3. Der Katalog liegt in `src/core/weapons/catalog.py` als Python-Daten (typgeprüft, von Ruff
erfasst). Schema-Werte pro Waffe (Munition, Verzögerung, Kistengewicht, Stärke) liegen im
`GameScheme`, nicht in der Definition.

## Konsequenzen

- **Positiv:** Die meisten neuen Waffen sind ein Katalogeintrag plus Test. Die KI bekommt über
  `AIHint` eine einheitliche Schnittstelle.
- **Negativ:** Einmaliger Umbau in Phase 0. Bausteine brauchen eine saubere `FireContext`-API, die
  stabil bleiben muss.
