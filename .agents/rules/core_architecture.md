# Kern-Architektur (py-worms-claude)

1. **Trennung von Logik und Darstellung**:
   - `src/core/` importiert niemals `pygame` oder `src.settings`. Darstellung (`src/render`, `src/scenes`) liest den Zustand und konsumiert Ereignisse über `world.bus`.
   - Der Test `test_core_has_no_pygame_and_no_settings_imports` erzwingt diese Regel.

2. **Konfiguration**:
   - Alles, was Spieler einstellen können, steht in `GameScheme` (`src/core/scheme.py`) mit Feld-Metadaten (Beschriftung, Bereich). Feste Physikwerte stehen in `src/core/constants.py`.
   - Neue Schema-Felder brauchen einen Default. Inkompatible Formatänderungen erhöhen `SCHEME_VERSION` und registrieren eine Migration (`persistence.register_migration`).

3. **Determinismus**:
   - Jeder Zufall der Simulation läuft über `match.rng.stream("<name>")`. Kosmetischer Zufall (Partikel) darf frei sein.
   - Spielbefehle laufen über die `Match`-Methoden in `COMMANDS`, damit sie im Eingabeprotokoll landen. Die KI rechnet mit festen Schritten statt mit Zeitbudgets.

4. **Inhalte statt Umbauten**:
   - Neue Waffen sind ein `WeaponDef` in `src/core/weapons/catalog.py`. Neues Verhalten ist eine Klasse mit `@register_behavior`, nicht ein Sonderfall in `World` oder `Match`.
   - Jede neue Waffe bekommt mindestens einen Logiktest mit messbarem Effekt.

5. **Rust-Kernel (ADR-0008)**:
   - Die heißen Schleifen gibt es doppelt: in Python (Referenz und Fallback) und in `native/src/lib.rs`. Jede Änderung an Terrain-Abfragen, Geschossschritt, Laufen, Flug oder Körper-Kollision muss in beiden gleich umgesetzt werden.
   - Keine `math.hypot` oder `**` in diesen Pfaden, gleiche Rechenreihenfolge. `tests/test_native.py` muss grün bleiben, nach `uv run build-native`.

