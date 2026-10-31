# ADR-0003: Gemeinsame Körper-Physik und Wurm-Wurm-Kollision

- **Status:** Angenommen · **Datum:** 2026-10-31 · **Phase:** 0 (Basis), 1 (Kollision)

## Kontext

Würmer sollen sich gegenseitig blockieren oder überkrochen werden. Dazu kommen Minen, Fässer,
Kisten, Schafe und weitere Objekte. Heute haben Wurm und Geschoss getrennte Bewegungslogik, und
Objekte untereinander kollidieren nicht.

## Optionen

1. Eine fertige Physik-Engine (pymunk). Starrkörper sind präzise, aber pixelgenaues zerstörbares
   Terrain passt schlecht dazu, und es entsteht eine Abhängigkeit mit nativer Komponente.
2. **Eigene, einfache Kreis-Körper** über dem vorhandenen Pixel-Terrain: Terrain-Kollision wie heute,
   Körper-Körper als Kreis-Kreis-Test mit Raster-Vorfilter, Schlafzustand für ruhende Objekte.

## Entscheidung

Option 2. `Body` ist die Basis aller Objekte, und `PhysicsWorld.body_collides()` prüft Terrain und
andere Körper mit `collides_with_bodies`. Die Wurm-Kollision kennt drei Schema-Modi (`aus`,
`blockieren`, `ueberkriechen`). Überkriechen ist eine Laufregel mit größerer Steighöhe gegenüber
Wurm-Körpern, keine Physik.

## Konsequenzen

- Deterministisch und vollständig ohne pygame testbar.
- Kein echtes Stapeln oder Rollen von Objekten. Gewollt: Landungen auf Würmern rutschen seitlich ab.
- Die Leistung muss mit dem Budget-Test (Plan C.0) überwacht werden.
