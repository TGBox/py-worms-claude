# Game Development & 2D-Engine Richtlinien

1. **Game-Loop & Entkopplung**:
   - Trenne Event-Handling, Zustands-Update (`dt`) und Rendering strikt voneinander.
   - Führe physikalische Berechnungen und Objektbewegungen immer zeitbasiert (`velocity * dt`) und niemals frameraten-abhängig aus.

2. **Fenster- und Vollbildmodus**:
   - Spiele müssen sowohl im Fenstermodus (resizable) als auch im Vollbildmodus (z. B. via F11) nahtlos funktionieren.
   - Bei Auflösungs- und Vollbildwechseln darf das Seitenverhältnis (Aspect Ratio) nicht verzerrt werden (Virtual Resolution / Letterboxing oder flexibles Scaling).

3. **Asset-Management & Ressourcen**:
   - Lade Sprites, Sounds und Schriften gebündelt während des Setups oder in Ladezuständen, niemals dynamisch innerhalb des Render-Loops.
   - Stelle sicher, dass bei fehlenden Bild-/Audio-Dateien ein Graceful Fallback (z. B. Platzhalter-Farbrechteck oder Stummschaltung) greift.

4. **Headless- & CI-Fähigkeit**:
   - Spiellogik (Kollisionen, Punktestand, Entitätsverwaltung) muss modular und unabhängig vom Grafiktreiber testbar sein (`SDL_VIDEODRIVER=dummy` bzw. `ARCADE_HEADLESS=True`).
