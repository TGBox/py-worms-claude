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
