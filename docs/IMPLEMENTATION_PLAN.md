# Implementierungsplan: py-worms-claude 0.2 → 1.0

Stand: 2026-10-31 · Ausgangsbasis: v0.2.0 (Commit `3245615`, „feat: add first draft“)

Dieses Dokument hat drei Teile:

- **Teil A – Ideen (Ideate):** Was das Spiel zusätzlich spaßig machen kann, bewertet und gefiltert.
- **Teil B – Spezifikation (Spec):** Zielarchitektur, Datenformate und Verträge zwischen den Modulen.
- **Teil C – Umsetzungsreihenfolge:** Phasen mit Aufgaben, Abnahmekriterien und Tests.

Architekturentscheidungen stehen als ADRs in [`docs/adr/`](adr/).

---

## Teil A – Ideen

### A.1 Problemstellung (How Might We)

> Wie machen wir aus dem spielbaren Prototyp ein Spiel, das man stundenlang mit Freunden oder
> allein spielt? Ziel: viel Abwechslung bei Waffen, Einstellungen, Teams und Inhalten, aber eine
> Codebasis, in der jede neue Waffe, Option oder Mission Konfiguration ist und kein Umbau.

**Der wichtigste Hebel:** Fast alle Wünsche (viele Waffen, feine Einstellungen, eigene Teams,
Editor, Kampagne, Tutorials) sind **Inhalte auf einem gemeinsamen Fundament**. Wenn das Fundament
datengetrieben ist (Waffen-Baukasten, Spielschema, Objektsystem, Speichern/Laden), wird jede
weitere Funktion billig. Fehlt es, kostet jede weitere Waffe einen Eingriff in `world.py`.

### A.2 Gewünschte Punkte (aus deiner Anfrage)

| # | Wunsch | Kern |
| --- | --- | --- |
| W1 | Zwei weitere Sprungarten | Hochsprung, Rückwärtssalto |
| W2 | Kriech-Animationen | Prozedurale Wurm-Animation mit Zuständen |
| W3 | Kollision zwischen Würmern | Blockieren oder Überkriechen, im Schema einstellbar |
| W4 | Welt-Editor | Terrain malen, Objekte und Startpunkte setzen, speichern |
| W5 | Viel mehr Waffen, auch verrückte | Waffen-Baukasten + Katalog mit ca. 45 Waffen/Werkzeugen |
| W6 | KI-Schwierigkeitsgrade | 5 Stufen über ein KI-Profil |
| W7 | Feingranulare Battle-Einstellungen | Spielschema (JSON) + Editor + Vorlagen |
| W8 | Teams erstellen, speichern, personalisieren | Team-Editor, Grabsteine, Superwaffe, Statistiken |
| W9 | Kampagne | Missionssystem + Missionskette mit Fortschritt |
| W10 | Tutorial-Level | Missionen mit Hinweis- und Trigger-System |

### A.3 Zusätzliche Spaß-Ideen

Gesammelt aus mehreren Blickwinkeln: Was passiert, wenn Grenzen wegfallen? Was ist das Gegenteil?
Was steckt im Kleinen? Was skaliert?

| Idee | Warum es Spaß macht | Aufwand | Empfehlung |
| --- | --- | --- | --- |
| **Kettenreaktionen**: Ölfässer, Minen, Kisten mit Sprengstoff | Ein Schuss, fünf Explosionen: die Momente, über die man lacht | M | ✅ Phase 3 |
| **Zeitlupe und Kill-Kamera** bei Volltreffern, Ertrinken, Ketten | Macht große Momente sichtbar | S | ✅ Phase 9 |
| **Kommentator-Sprüche und Sprechblasen** („Selbsttor!“, „Bis später, Fischfutter!“) | Persönlichkeit ohne Audio-Assets | S | ✅ Phase 5 (Team-Sprachpaket) |
| **Gesichtsausdrücke**: Würmer schauen ängstlich zur tickenden Granate | Sehr viel Charme für wenig Code | S | ✅ Phase 1 |
| **Terrain-Themen** mit Physik: Eis (rutschig), Mond (wenig Gravitation), Lava statt Wasser, Süßigkeiten | Jede Karte spielt sich anders | M | ✅ Phase 4 |
| **Wetter**: Böen, Gewitter mit Blitzeinschlägen, Meteoritenschauer | Umweltgefahren, die du dir gewünscht hast | M | ✅ Phase 4 |
| **Spielmodi**: Festung (Burgen + Bauzeit), König des Hügels, Kopfgeld, Schatzsuche | Langzeitmotivation ohne neue Engine | M | ✅ Phase 9 (Festung früher, da nur Schema + Karte) |
| **Prozeduraler Sound-Synth** (Explosion, Platschen, Wurm-Quietschen aus Rauschen/Oszillatoren) | Keine Assets nötig, große Wirkung | M | ✅ Phase 9 |
| **Replays** über deterministische Simulation + Eingabeprotokoll | Wiederholung, Teilen, Bug-Reproduktion | M | ✅ Grundlage in Phase 0, UI in Phase 9 |
| **Tägliche Herausforderung** (fester Seed + festes Schema, Bestenliste lokal) | Grund, morgen wiederzukommen | S | ✅ Phase 9 |
| **Hüte und Accessoires** pro Wurm | Teil der Team-Personalisierung | S | ✅ Phase 5 |
| **Erfolge und Statistiken** („10 Würmer mit dem Baseballschläger ertränkt“) | Fortschritt außerhalb der Kampagne | S | ✅ Phase 5 |
| **Waffen-Basteln** (Teile aus Kisten zu Spezialwaffen kombinieren, wie in neueren Teilen) | Taktische Tiefe | L | ⏸ nach 1.0 |
| **Fahrzeuge und Geschütze** (Panzer, Hubschrauber, Geschützturm) | Spektakulär | L | ⏸ nach 1.0 |
| **Online/LAN-Mehrspieler** (Lockstep auf der deterministischen Simulation) | Freunde ohne Hotseat | XL | ⏸ nach 1.0, Determinismus ab Phase 0 vorhalten |
| **Gamepad-Steuerung** | Couch-Spiel | S | ✅ Phase 9 (Aktions-Mapping ab Phase 0) |

### A.4 Stresstest und versteckte Annahmen

**Worauf wir wetten:**

1. **Pure-Python-Physik bleibt schnell genug.** Mit Seil, Schafen, Clustern, 30 Minen und 8 Teams
   steigt die Last. Gegenmaßnahmen: Ruhende Objekte schlafen lassen, Kollisionen über ein Raster
   vorfiltern, ein Leistungsbudget-Test pro Phase (siehe C.0). Fällt die Wette, verschieben wir
   Hotspots in `numpy` oder Cython. Das ist wegen der Kapselung in `src/core/` lokal begrenzt.
2. **Prozedurale Grafik reicht für Charme.** Dazu gehören Animation, Gesichter und Hüte. Ohne Sprites
   hängt viel an Bewegung und Effekten, deshalb kommen Animationen früh (Phase 1).
3. **Daten statt Code.** Eine Waffe muss sich aus wenigen Verhaltensbausteinen zusammensetzen lassen.
   Für die ca. 10 % Sonderfälle (gesteuertes Raketen-Schaf, Seil) gibt es Python-Klassen im selben
   Register.

**Was das Projekt gefährden kann:**

- **Feature-Breite vor Fundament:** Ohne Phase 0 wird jede Waffe teurer. Deshalb gilt: **erst das
  Fundament, dann Inhalte.**
- **Das Seil (Enterseil)** ist physikalisch das schwierigste Werkzeug. Es bekommt einen eigenen
  Prototyp mit Abbruchkriterium.
- **Markenrechte:** Originalnamen und -figuren (z. B. „Holy Hand Grenade“, „Super Sheep“, „Concrete
  Donkey“) übernehmen wir nicht. Alle Waffen bekommen eigene Namen und eigene Optik.

### A.5 Empfohlene Richtung

**„Systemische Sandbox“:** Ein kleines Set an Systemen (Körper/Physik, Waffenbausteine, Schema,
Ereignisbus, Missionstrigger) trägt alle Inhalte. Die Reihenfolge folgt drei Regeln:

1. Was du am direktesten spürst und was wenig Abhängigkeiten hat, kommt zuerst (Sprünge, Animation,
   Kollision).
2. Systeme vor Inhalten.
3. Kampagne und Tutorials ganz am Ende, weil sie fast alles andere benutzen.

### A.6 Nicht im Umfang bis 1.0 (bewusste Abgrenzung)

- Online/LAN-Mehrspieler, Fahrzeuge, Waffen-Basteln
- Bild-Sprites und Sprachaufnahmen von außen (alles bleibt prozedural; eigene PNGs sind optional möglich)
- 3D, Mod-Skriptsprache, Steam-/Store-Integration
- Mehr als 8 Teams oder mehr als 8 Würmer pro Team

---

## Teil B – Spezifikation

### B.1 Zielarchitektur

```text
src/
├── core/                      # weiterhin ohne pygame, vollständig headless testbar
│   ├── scheme.py              # GameScheme: alle Spieloptionen, JSON, Vorlagen
│   ├── rng.py                 # benannte, deterministische Zufallsströme
│   ├── events.py              # typisierte Ereignisse + Bus (Effekte, Statistik, Missionen)
│   ├── physics.py             # Body, Integration, Terrain- und Körper-Kollision, Schlafzustand
│   ├── terrain.py             # + unzerstörbare Ebene, Materialien (Eis, Beton)
│   ├── mapgen.py              # + Generator-Parameter, Themen
│   ├── objects/               # Wurm, Geschoss, Mine, Fass, Kiste, Läufer (Schaf, …)
│   ├── weapons/
│   │   ├── registry.py        # WeaponDef-Register, Laden aus Katalog
│   │   ├── behaviors.py       # Bausteine: ballistic, cluster, hitscan, melee, placed, …
│   │   ├── specials/          # Sonderklassen: rope.py, steerable.py, jetpack.py, …
│   │   └── catalog.py         # alle Waffen als Daten
│   ├── match.py               # Rundenmaschine (+ Sudden Death, Kisten, Gefahren, Siegbedingungen)
│   ├── hazards.py             # Wasseranstieg, Blitz, Meteore, Gas
│   ├── teams.py               # TeamProfile (persistentes Team) ↔ Team (im Match)
│   ├── persistence.py         # Pfade, versionierte JSON-Dateien, Migration
│   ├── ai/
│   │   ├── profiles.py        # 5 Schwierigkeitsgrade
│   │   ├── planner.py         # Schuss-Suche über Waffen-KI-Hinweise
│   │   └── movement.py        # erreichbare Standpunkte, Sprünge, Werkzeuge
│   └── missions/
│       ├── model.py           # Mission, Ziel, Trigger, Aktion
│       ├── objectives.py      # Ziel-Register
│       └── runner.py          # wertet Trigger über Ereignisse aus
├── render/                    # + worm_animator.py, weapon_icons.py, themes.py, hats.py
├── ui/                        # pygame_gui-Thema + kleine Helfer (ADR-0004)
└── scenes/                    # Hauptmenü, Battle-Setup, Schema-Editor, Team-Editor,
                               # Karten-Editor, Kampagnenkarte, Briefing, Match, Ergebnis
assets/
├── schemes/  teams/  maps/<name>/{terrain.png,map.json}  campaign/  tutorials/  themes/
```

**Grundregeln (Erweiterung von `.agents/rules/`):**

- `src/core` importiert nie pygame. Die Darstellung liest den Zustand und konsumiert Ereignisse.
- Spiellogik schreibt keine Konstanten fest: Alles Einstellbare kommt aus `GameScheme`.
- Jede Zufallsentscheidung der Simulation läuft über `rng.py`, damit Replays und Tests
  deterministisch sind. Kosmetischer Zufall (Partikel) darf frei sein.
- Neue Inhalte (Waffe, Mission, Vorlage) sollen in der Regel ohne Änderung an `match.py`/`world.py`
  auskommen.

### B.2 Verträge (Kern-Schnittstellen)

**Körper und Physik** (ADR-0003):

```python
class Body:                       # Basis für Wurm, Geschoss, Mine, Fass, Kiste, Schaf
    x: float; y: float; vx: float; vy: float
    radius: float
    mass: float                   # Rückstoß-Skalierung
    collides_with_bodies: bool    # Würmer/Fässer/Kisten ja, Partikel-Geschosse nein
    asleep: bool                  # ruhende Körper werden nicht integriert

class PhysicsWorld:
    def step(self, dt: float) -> None
    def body_collides(self, body: Body, x: float, y: float) -> bool   # Terrain + andere Körper
    def bodies_in_radius(self, x: float, y: float, r: float) -> list[Body]
```

**Waffen** (ADR-0001):

```python
@dataclass(frozen=True)
class WeaponDef:
    key: str  # "bazooka"
    name: str  # "Bazooka" (UI, deutsch)
    category: Category  # ARTILLERIE, GEWEHR, NAHKAMPF, GELEGT, LUFT, TIER, VERRÜCKT, WERKZEUG
    aim: AimMode  # CHARGED, ANGLE_ONLY, TARGET_POINT, NONE
    behavior: str  # Baustein- oder Sonderklassen-Key im Register
    params: Mapping[str, Any]  # z. B. {"radius": 40, "damage": 50, "wind": 1.0, "fuse": 3}
    shots_per_turn: int = 1
    ends_turn: bool = True  # Werkzeuge wie Fallschirm/Seil: False
    ai: AIHint | None = (
        None  # wie die KI die Waffe simulieren/bewerten kann; None = KI nutzt sie nicht
    )
    icon: str = ""  # Schlüssel für prozedurales Icon
```

Ein Baustein implementiert `fire(ctx: FireContext) -> list[Body]` und bei Bedarf `update(body, dt)`.
Die Schema-Werte pro Waffe (Munition, Verzögerung, Kistenhäufigkeit, Stärke ±) liegen in
`GameScheme.weapons[key]`, nicht in der Definition.

**Spielschema** (ADR-0002), gekürzt:

```jsonc
{
  "version": 1,
  "name": "Standard",
  "turn":   { "turn_time": 45, "retreat_time": 3, "hotseat_time": 5, "worm_select": "reihum",
              "round_time_min": 15, "sudden_death": { "mode": "wasser", "water_rise": 20, "hp_to_one": false } },
  "worms":  { "count": 4, "hp": 100, "fall_damage": true, "fall_damage_factor": 1.0,
              "collision": "ueberkriechen", "start_placement": "zufaellig" },
  "terrain":{ "source": "generator", "map": null, "theme": "erde", "indestructible": false,
              "generator": { "islands": 1, "caves": 0.5, "floating": 0.4, "roughness": 0.5 },
              "water_level": 930 },
  "objects":{ "mines": 8, "mine_fuse": [0, 5], "mine_dud_chance": 0.1, "barrels": 5 },
  "crates": { "chance": 0.4, "max_on_map": 5, "weights": { "waffe": 60, "gesundheit": 25, "werkzeug": 15 },
              "health_amount": 25, "trap_chance": 0.05 },
  "environment": { "wind_max": 1.0, "wind_changes": "pro_runde", "gravity": 1.0,
                   "hazards": { "lightning": 0, "meteors": 0, "rising_water_per_turn": 0 } },
  "weapons": { "bazooka": { "ammo": -1, "delay": 0, "crate_weight": 0, "power": 1.0 },
               "luftschlag": { "ammo": 1, "delay": 2, "crate_weight": 10, "power": 1.0 } },
  "rules":  { "win": "letztes_team", "allow_superweapons": true, "stockpile": "nein" }
}
```

**Team-Profil** (persistent, ADR-0006):

```jsonc
{
  "version": 1, "id": "c3a2…", "name": "Die Regenwürmer", "color": [244, 63, 94],
  "controller": { "type": "ki", "difficulty": "schwer" },     // oder {"type":"mensch"}
  "worms": [ { "name": "Kurt", "hat": "zylinder" }, { "name": "Lotte", "hat": null } ],
  "gravestone": "kreuz", "flag": "streifen", "superweapon": "gummiente",
  "voice": "frech",          // Sprachpaket für Sprechblasen
  "victory_dance": "salto",
  "stats": { "games": 12, "wins": 5, "kills": 31, "deaths": 27, "best_shot": 87 }
}
```

**Karte** (ADR-0005): `assets/maps/<name>/terrain.png` (Alpha = fest) + optional `indestructible.png`

- `map.json`:

```jsonc
{ "version": 1, "name": "Doppelinsel", "theme": "erde", "water_level": 930,
  "spawns": [[210, 400], [1720, 380]], "objects": [{ "type": "fass", "x": 990, "y": 250 }],
  "author": "", "recommended_teams": [2, 4] }
```

Die bisherigen einzelnen PNG-Dateien in `assets/maps/` werden weiter geladen (Abwärtskompatibilität).

**Mission** (ADR-0007):

```jsonc
{ "version": 1, "id": "kampagne-03", "title": "Brücke über den Abgrund",
  "briefing": "Erreiche die Kiste auf der anderen Seite, bevor die Flut kommt.",
  "map": "brueckenland", "scheme": "kampagne-standard", "scheme_overrides": { "turn": { "turn_time": 30 } },
  "teams": [ { "ref": "spieler" }, { "profile": "kampagne/piraten", "difficulty": "leicht" } ],
  "inventory": { "spieler": { "teleporter": 1, "brueckenteil": 3 } },
  "objectives": [ { "type": "kiste_einsammeln", "crate": "ziel" },
                  { "type": "ueberleben", "turns": 10, "optional": true, "reward": "medaille" } ],
  "triggers": [ { "when": { "event": "runde_beginnt", "turn": 5 },
                  "do": [ { "action": "nachricht", "text": "Das Wasser steigt!" },
                          { "action": "wasser_steigen", "amount": 60 } ] } ],
  "unlocks": ["waffe:raketen-schaf"] }
```

### B.3 Waffen-Katalog (Ziel 1.0)

Eigene Namen, Verhalten in Klammern. **Fett** = Teil von Welle 1.

| Kategorie | Waffen |
| --- | --- |
| Artillerie | Bazooka ✔, **Lenkrakete** (homing auf Zielpunkt), **Mörser** (Cluster beim Aufprall), Granate ✔, **Splittergranate** (Cluster nach Zünder), **Fruchtbombe** (springende Riesen-Cluster), Molotow-Cocktail (Feuer), Gasgranate (Gift über Zeit) |
| Gewehre | Schrotflinte ✔ (2 Schüsse), **Uzi** (Streufeuer), Minigun, Präzisionsgewehr (Zoom, Durchschlag), Bogen (Pfeil bleibt stecken, kann als Stufe dienen) |
| Nahkampf | **Feuerfaust** (Aufwärtshaken), **Baseballschläger** (Weitschlag), Schubser, Kamikaze (Flug + Explosion), Kettenhieb |
| Gelegt | **Dynamit**, **Mine**, Haftmine, Ölfass platzieren |
| Luft | Luftschlag ✔, Napalmschlag, Minenabwurf, Kühlschrank-Regen (springende Kühlschränke) |
| Tiere/Läufer | **Sprengschaf** (läuft, springt, Zündung auf Taste), Raketen-Schaf (fliegt, lenkbar), Maulwurfbombe (gräbt), Hüpf-Häschen (Riesensprünge), Bienenschwarm (verfolgen Würmer) |
| Verrückt | Gummiente (riesige Explosion, quietscht), Schwarzes Loch (zieht alles für 3 s an), Tauschgranate (vertauscht zwei Würmer), Diskokugel (Gegner tanzen eine Runde lang statt zu handeln), Klavier (fällt, springt, explodiert mehrfach), Gravitationsumkehr (eine Runde), Wanderkuchen (läuft auf Gegner zu), Ballonbombe (steigt mit dem Wind), Magnet (zieht Geschosse/Minen), Verwandlungsstab (Wurm wird eine Runde lang zum Schaf), Konfetti-Bombe (Sudden-Death-Superwaffe: alle Würmer −50 %, Wasser steigt) |
| Werkzeuge | **Teleporter**, **Brückenteil**, **Fallschirm**, Enterseil, Bungee, Jetpack, Lötlampe, Presslufthammer, Bohrer, Zug aussetzen, Kapitulieren, Wurm wählen, Wenig Gravitation, Doppelschaden, Schnelles Laufen, Lasersicht |

Superwaffen (Kategorie „Verrückt“) können pro Schema abgeschaltet werden. Jedes Team-Profil hat eine
**Lieblings-Superwaffe**, die mit erhöhter Chance in Kisten dieses Teams auftaucht und mit
`superweapon_bonus` einmal pro Spiel im Inventar liegen kann.

### B.4 Wurm-Bewegung, Animation und Kollision (W1–W3)

**Sprünge** (Belegung wie im Klassiker):

| Eingabe | Sprung | Startgeschwindigkeit (Basis) |
| --- | --- | --- |
| Enter | Vorwärtssprung | (130·Blickrichtung, −230) wie bisher |
| Rücktaste | Hochsprung | (25·Blickrichtung, −330) |
| Enter, Enter oder Rücktaste, Rücktaste (innerhalb 0,25 s) | Rückwärtssalto | (−90·Blickrichtung, −380) + Salto-Animation |

Ein Eingabepuffer wartet bis zu 0,25 s auf den zweiten Tastendruck. Die KI nutzt die Sprünge über
`movement.py`.

**Zustandsmaschine** im Kern (`WormState`: IDLE, WALK, JUMP, BACKFLIP, FALL, SLIDE, AIM, HURT,
DROWN, DEAD, ROPE, PARACHUTE, JETPACK, VICTORY). Die Darstellung leitet daraus die Animation ab,
der Kern kennt keine Animationsdaten.

**Kriech-Animation** (`render/worm_animator.py`): Der Wurmkörper ist eine Kette aus 6 Segmenten
entlang einer Wirbelsäule. Beim Laufen wandert eine Stauchwelle von hinten nach vorn
(Raupenbewegung, Phase an zurückgelegte Strecke gekoppelt, damit sie beim Stehen stoppt). Dazu kommen
Blinzeln und Atmen im Leerlauf, gestreckter Körper im Sprung, Rotation beim Salto, Zappeln im Fall,
Kopf folgt dem Zielwinkel, Waffen-Icon in der „Hand“, Gesichtsausdruck (normal, ängstlich bei naher
Gefahr, verletzt, jubelnd), Hut.

**Wurm-Wurm-Kollision** (Schema `worms.collision`):

- `aus`: wie bisher, Würmer gehen durcheinander hindurch.
- `blockieren`: Andere Würmer sind feste Kreise. Wer vorbeiwill, muss springen.
- `ueberkriechen` (Standard): Läuft ein Wurm gegen einen stehenden Wurm, klettert er langsam über
  ihn. Erlaubte Steighöhe ist dann Wurmhöhe + 2 px bei halber Geschwindigkeit. Steht der andere Wurm
  an einer Wand, die höher als die normale Steighöhe ist, blockiert er.

Landende Würmer rutschen von einem anderen Wurm seitlich ab, damit sich keine Türme bilden.
Explosionen übertragen Impuls zwischen sich berührenden Würmern nicht doppelt.

### B.5 KI-Schwierigkeitsgrade (W6)

| Parameter | Anfänger | Leicht | Mittel | Schwer | Experte |
| --- | --- | --- | --- | --- | --- |
| Zielstreuung Winkel σ (rad) | 0,15 | 0,09 | 0,05 | 0,025 | 0,01 |
| Kraftstreuung σ | 0,15 | 0,09 | 0,05 | 0,025 | 0,01 |
| Berücksichtigt Wind | 30 % | 60 % | 100 % | 100 % | 100 % |
| Suchauflösung (Winkel × Kraft) | 8×4 | 14×6 | 26×8 | 36×10 | 48×12 |
| Waffenwissen | Bazooka, Granate | + Gewehre | + Gelegt, Luft | + Tiere, Nahkampf | alles inkl. Verrückt |
| Bewegung vor dem Schuss | nein | nein | kurz laufen | laufen + springen | laufen, springen, Teleport/Seil |
| Eigenschaden-Vermeidung | schwach | mittel | stark | stark | stark |
| Zielwahl | nächster | nächster | bester Schaden | Kill-Chance + Wasser | Kill-Chance + Kombos + Kistenwert |
| Denkzeit-Budget pro Zug | 0,2 s | 0,3 s | 0,5 s | 1,0 s | 1,5 s |

Umsetzung über `AIProfile` (Datenklasse) und `AIHint` in der Waffendefinition (`simulate`,
`direct`, `target_point`, `placement`, `melee`, `utility`). Der Planer wird generisch: Er fragt pro
Waffe nach Kandidaten und bewertet sie mit derselben Schadensfunktion wie bisher, erweitert um
Wasser-Kills (Rückstoß ins Wasser) und Kettenreaktionen.

### B.6 Persistenz

- Nutzerdaten: Windows `%APPDATA%\py-worms-claude\`, sonst `~/.local/share/py-worms-claude/`. Darin
  `teams/`, `schemes/`, `maps/`, `progress.json` (Kampagne, Tutorials, Erfolge), `settings.json`
  (Tastenbelegung, Vollbild, Lautstärke).
- Mitgelieferte Inhalte unter `assets/` sind schreibgeschützt. Nutzerdateien mit gleichem Namen
  überschreiben sie in der Auswahl.
- Jede Datei hat `"version"`. `persistence.load()` migriert Schritt für Schritt und lehnt unbekannte
  Felder nicht ab (Vorwärtskompatibilität).
- Schreiben atomar (temporäre Datei + Umbenennen), damit ein Absturz nichts beschädigt.

---

## Teil C – Umsetzungsreihenfolge

### C.0 Arbeitsweise für alle Phasen

- **Pro Phase eine Minor-Version** (0.3, 0.4, …), CHANGELOG-Eintrag, atomare Commits.
- **Definition of Done jeder Phase:** `uv run pytest` grün, `uv run lint` und
  `ruff format --check` sauber, Smoke-Test der neuen Szenen headless, kurzer manueller Spieltest,
  README aktualisiert.
- **Leistungsbudget-Test** (`tests/test_performance.py`, ab Phase 0): Ein Referenz-Szenario mit
  8 Würmern, 10 Minen, 5 Fässern und einem Cluster-Wurf muss für 600 Simulationsschritte unter
  einer festen Zeit bleiben. Der Grenzwert wird in Phase 0 gemessen, dann gilt +20 % als Obergrenze.
- **Determinismus-Test:** Gleicher Seed + gleiches Eingabeprotokoll ⇒ identischer Endzustand (Hash).
- Größen: **S** ≈ 1 Arbeitssitzung, **M** ≈ 2–3, **L** ≈ 4–6.

### C.1 Abhängigkeiten auf einen Blick

```text
Phase 0 Fundament ──┬─► Phase 1 Bewegung/Animation/Kollision
                    ├─► Phase 2 Waffen-Welle 1 ──► Phase 3 Objekte & Kisten ──► Phase 6 Werkzeuge ──► Phase 7 Verrückte Waffen
                    ├─► Phase 4 Battle-Optionen & Umwelt (braucht Schema-UI aus 0, Objekte aus 3)
                    └─► Phase 5 Teams & KI-Stufen (braucht Waffen-KI-Hinweise aus 2)
Phase 3 + 4 ──► Phase 8 Karten-Editor
Phase 1–8 ──► Phase 9 Missionssystem ► Tutorials ► Kampagne ──► Phase 10 Spaß & Politur ──► 1.0
```

---

### Phase 0 – Fundament (v0.3) · L

**Ziel:** Alle späteren Funktionen werden zu Daten statt Umbauten. Für Spieler ändert sich fast nichts.

| # | Aufgabe | Ergebnis |
| --- | --- | --- |
| 0.1 | `GameScheme` mit Untergruppen (B.2), Laden/Speichern, Vorlage „Standard“ = heutiges Verhalten | `core/scheme.py`, `assets/schemes/standard.json` |
| 0.2 | `Match`, `World`, KI lesen alle Werte aus dem Schema statt aus `settings.py` | `settings.py` enthält nur noch Darstellung |
| 0.3 | `rng.py` mit benannten Strömen (`wind`, `crates`, `ai`, `spawn`), Eingabeprotokoll in `Match` | Grundlage für Replays/Determinismus |
| 0.4 | `events.py`: typisierte Ereignisse (`Explosion`, `Damage`, `WormDied`, `TurnStarted`, `CratePicked`, …) + Abonnements | ersetzt die lose `Event`-Liste |
| 0.5 | `physics.py`: `Body`-Basis, `PhysicsWorld` mit Schlafzustand und Raster-Vorfilter. Wurm und Geschoss werden Bodies (Verhalten unverändert) | ADR-0003 |
| 0.6 | Waffen-Register + Bausteine `ballistic`, `hitscan`, `airstrike`. Die vier bestehenden Waffen als Katalogeinträge. `FireMode`-Sonderwege in `World` entfallen | ADR-0001 |
| 0.7 | `persistence.py` (Pfade, versioniertes JSON, atomares Schreiben, Migration) | ADR-0006 |
| 0.8 | UI-Grundlage: `pygame_gui` einbinden, Thema im bisherigen Farbschema, Aktions-Mapping für Tastatur (später Gamepad) | ADR-0004 |
| 0.9 | Hauptmenü-Struktur: „Schnelles Spiel“, „Battle einrichten“ (vorerst nur Schema-Auswahl), „Teams“, „Editor“, „Kampagne“, „Tutorial“, „Optionen“ (noch leere Einträge ausgegraut) | Navigationsrahmen steht |

**Abnahme:**

- Alle bestehenden 35 Tests grün, ohne Verhaltensänderung (KI-gegen-KI-Partie mit festem Seed endet identisch wie vor dem Umbau oder die Abweichung ist begründet).
- `grep pygame src/core` leer. Kein Zugriff aus `src/core` auf Spielwerte in `settings.py`.
- Neue Waffe als reiner Katalogeintrag möglich (Test: Bazooka-Klon mit Radius 60 ohne Codeänderung außerhalb des Katalogs).
- Determinismus- und Leistungsbudget-Test vorhanden und grün.

**Status: umgesetzt (2026-10-31).** Entscheidungslog:

- **Verhaltensänderung, begründet:** Wind, Startpositionen und Namen ziehen jetzt aus eigenen
  Zufallsströmen (`rng.py`). Gleicher Seed ergibt deshalb andere Partien als vor dem Umbau. Physik,
  Waffenwerte und Regeln sind unverändert, alle 35 Alt-Tests laufen weiter.
- **KI-Denkbudget in Schritten statt Sekunden:** Pro Frame werden 40 Kandidaten geprüft
  (`AIController.think_steps`). Ein Zeitbudget hängt von der Rechnergeschwindigkeit ab und hätte
  die Determinismus-Tests gebrochen.
- **Feste Simulationsschritte:** Die Spielszene simuliert mit 1/60 s (Akkumulator, maximal 5
  Schritte pro Frame). Eingabeprotokoll und Replays (`match.replay`) setzen das voraus.
- **Schema enthält nur, was schon wirkt:** Zugzeit, Rückzug, Wurmanzahl, HP, Fallschaden,
  Wasserspiegel, Wind, Schwerkraft sowie Munition, Verzögerung und Stärke pro Waffe. Weitere Gruppen
  aus B.2 kommen mit den Phasen, die sie nutzen. Alte Dateien bleiben über Defaults ladbar.
- **0.8 `pygame_gui` verschoben:** In der Build-Umgebung ist PyPI nicht erreichbar, die Bibliothek
  wäre also ungetestet eingebunden worden. Umgesetzt ist das Aktions-Mapping (`src/controls.py`,
  Tasten in `settings.json`). Der Spike aus ADR-0004 läuft vor Phase 4, wo die ersten Formulare
  entstehen.
- **Körper-Kollision ist vorbereitet, aber aus:** `Body.collides_with_bodies` wirkt bereits in
  `PhysicsWorld.body_collides`. Die Schema-Option und das Überkriechen kommen in Phase 1.
- **Leistungsbudget:** Szenario/Kalibrierung ≈ 1,4 (CPython 3.13), Grenze 1,4 × 1,2. Auf einer
  anderen Python-Version kann der Wert abweichen. Dann wird `BASELINE_RATIO` dort einmalig neu
  gemessen.

---

### Phase 1 – Bewegung, Animation, Wurm-Kollision (v0.4) · M · *W1, W2, W3*

| # | Aufgabe |
| --- | --- |
| 1.1 | `WormState`-Zustandsmaschine im Kern, Übergänge getestet |
| 1.2 | Hochsprung und Rückwärtssalto inkl. Doppeltipp-Puffer (B.4), Werte im Schema (`worms.jump_*`) |
| 1.3 | Wurm-Wurm-Kollision mit den Modi `aus`/`blockieren`/`ueberkriechen`, Abrutschen beim Landen |
| 1.4 | `worm_animator.py`: Segmentkörper, Kriechwelle, Leerlauf, Sprung/Salto/Fall, Zielen, Treffer, Ertrinken, Sieg; Gesichtsausdrücke |
| 1.5 | Gefahren-Wahrnehmung für Gesichter (Ereignis „Gefahr nahe“: tickende Granate/Mine im Umkreis) |
| 1.6 | KI nutzt Laufen + Vorwärts-/Hochsprung, um eine bessere Schussposition zu erreichen (nur ab Stufe „Mittel“ aktiv, Stufen kommen in Phase 5) |

**Abnahme:**

- Tests: Hochsprung erreicht ≥ 1,4× die Höhe des Vorwärtssprungs. Ein Salto landet hinter dem Startpunkt. Im Modus `blockieren` kommt ein laufender Wurm nicht an einem stehenden Wurm vorbei, mit Sprung schon. Im Modus `ueberkriechen` gelingt das Überqueren auf flachem Boden in < 2 s. Würmer stapeln sich nach 10 zufälligen Landungen nicht.
- Animation reagiert auf Zustände (Smoke-Test prüft, dass jeder Zustand einmal gezeichnet wurde).
- Manuell: Laufen sieht nach Kriechen aus, nicht nach Gleiten.

**Status: umgesetzt (2026-10-31).** Entscheidungslog:

- **Belegung:** Enter = Vorwärtssprung, Rücktaste = Hochsprung, zweimal innerhalb 0,25 s =
  Rückwärtssalto (`src/jump_input.py`). Ein einzelner Sprung startet deshalb erst nach diesem
  Fenster, wie im Klassiker.
- **Schema:** statt einzelner `jump_*`-Vektoren ein Faktor `worms.jump_strength`. Die drei
  Sprungprofile stehen in `constants.py`. Neu ist auch `worms.collision` (Standard: `ueberkriechen`).
- **Stufenhöhe:** Eine Stufe gilt nur durch Terrain als Treppe. Ein anderer Wurm ist im Modus
  `blockieren` immer eine Wand und wird im Modus `ueberkriechen` mit halber Geschwindigkeit bis zu
  Wurmhöhe + 2 px überklettert. Voraussetzung ist, dass der Boden dahinter begehbar ist.
- **Berührende Körper:** Bewegungen, die den Abstand nicht verringern, sind immer erlaubt, damit
  sich verhakte Würmer trennen können. Seitlicher Kontakt in der Luft gleitet tangential statt
  abzuprallen. Wer auf einem Wurm landet, rutscht ab (höchstens 3 Versuche, dann bleibt er stehen).
- **Zustände:** Der Kern kennt Bewegungszustände (IDLE, WALK, JUMP, HIGH_JUMP, BACKFLIP, FALL,
  DROWNED, DEAD). Zielen, Treffer und Sieg sind reine Posen, die der Animator aus dem Match ableitet.
- **„Gefahr nahe“ als Abfrage statt Ereignis:** `World.danger_near()` wird pro Frame vom Animator
  gefragt. Ein Ereignis hätte bei jeder Geschossbewegung gefeuert.
- **KI-Bewegung:** Die KI erkundet erreichbare Positionen mit der echten Bewegungs-Physik
  (`World.look_ahead`, ohne Seiteneffekte). Mit Anlauf springt sie auch über Hindernisse. Jede
  Position bewertet sie mit einer groben Schusssuche und läuft nur bei klarem Gewinn los. Abschaltbar
  über `AIController(use_movement=..., use_jumps=...)`, die Schwierigkeitsstufen folgen in Phase 5.
- **Leistung:** Wurm-Kollision kostet Zeit. Die Engpässe `is_solid`, `circle_collides` und
  `step_projectile` (Broad-Phase für Treffer) wurden optimiert, das Budget hält (≈ 1,35–1,6 bei
  Grenze 1,68).

---

### Phase 2 – Waffen-Welle 1 (v0.5) · M · *W5 Teil 1*

| # | Aufgabe |
| --- | --- |
| 2.1 | Neue Bausteine: `cluster` (Kinder-Geschosse), `homing` (Zielpunkt per Klick, Steuerphase nach 0,5 s), `melee` (Kegel vor dem Wurm, Impuls), `placed` (mit Zünder oder Näherungszünder), `multi_shot` (Uzi/Schrotflinte 2 Schüsse) |
| 2.2 | Waffen: Lenkrakete, Mörser, Splittergranate, Fruchtbombe, Uzi, Feuerfaust, Baseballschläger, Dynamit, Mine, Teleporter, Brückenteil (drehbar, setzt unzerstörbares Material), Fallschirm (Werkzeug, beendet Zug nicht) |
| 2.3 | Waffenmenü: Raster nach Kategorien mit prozeduralen Icons, Maus und Tasten (F1–F12 je Kategorie wie im Klassiker), Munition und Verzögerung sichtbar |
| 2.4 | Granaten-Zünder 1–5 s und Abprall-Stärke wählbar (Tasten 1–5, `+`/`-`) |
| 2.5 | `AIHint` für alle Welle-1-Waffen außer Teleporter, Brückenteil und Fallschirm |

**Abnahme:**

- Für jede Waffe mindestens ein Logiktest mit messbarem Effekt (Schaden/Kratergröße/Impuls/Position).
- Die KI setzt in 20 Seed-Partien mindestens 6 verschiedene Waffen ein.
- Waffenmenü vollständig per Tastatur und per Maus bedienbar.

---

### Phase 3 – Objekte, Kettenreaktionen, Kisten (v0.6) · M

| # | Aufgabe |
| --- | --- |
| 3.1 | Objekte als Bodies: Mine (Zünder, Blindgänger-Chance), Ölfass (explodiert, hinterlässt Feuer), Kiste (Fallschirm, Treffer-Explosion) |
| 3.2 | Feuer-System (brennende Flächen, Schaden pro Tick, erlischt), wird von Molotow/Napalm später wiederverwendet |
| 3.3 | Kisten-System: Spawn-Chance pro Runde, Gewichte, Inhalte (Waffe, Gesundheit, Werkzeug, Falle), Einsammeln durch Berührung, Anzeige „+1 Mörser“ |
| 3.4 | Kartenstart: Minen/Fässer laut Schema platzieren (nicht in Startnähe) |
| 3.5 | Statistik-Ereignisse für Ketten („3er-Kette!“) |

**Abnahme:** Kettenreaktion Fass → Mine → Fass im Test deterministisch. Kisten-Gewichte statistisch
korrekt (10 000 Ziehungen, ±2 %). Minen spawnen nie im 40-px-Umkreis eines Wurms.

---

### Phase 4 – Battle-Einstellungen, Sudden Death, Umwelt (v0.7) · L · *W7*

| # | Aufgabe |
| --- | --- |
| 4.1 | Szene **Battle einrichten**: Teams wählen (vorerst Ad-hoc-Teams), Karte/Generator, Schema wählen |
| 4.2 | **Schema-Editor** mit Reitern: Runden · Würmer · Waffen (Tabelle: Munition, Verzögerung, Kiste, Stärke) · Kisten · Terrain · Umwelt · Sudden Death · Regeln. Speichern, Laden, Duplizieren, Zurücksetzen |
| 4.3 | Vorlagen: Standard, Schnell (20 s), Profi (wenig Waffen, kein Wind-Zufall), Chaos (alles verrückt, viele Kisten), Festung (Burgkarten, Bauphase), Nur Werkzeuge (Seil-Rennen) |
| 4.4 | Sudden Death: Auslöser nach Runden-Minuten, Modi Wasser steigt / HP auf 1 / beides / Unentschieden |
| 4.5 | Umweltgefahren: Wasseranstieg pro Runde, Blitz (zufälliger Einschlag pro Runde), Meteoritenschauer, Windböen; Gravitation global |
| 4.6 | Terrain-Optionen: Themen (Erde, Eis rutschig, Mond, Lava, Süßigkeiten), unzerstörbares Terrain, Generator-Regler (Inseln, Höhlen, Plattformen, Rauheit), Wasserspiegel |
| 4.7 | Wechseltimer (Hotseat-Übergabe-Zeit mit „Bereit?“-Bildschirm), Wurmauswahl reihum/frei |

**Abnahme:** Jede Schema-Option hat einen Test, der ihren Effekt nachweist (parametrisiert).
Gespeichertes Schema lädt identisch (Rundlauf-Test). Ein Schema der Version 1 lädt auch nach einer
Feldergänzung (Migrationstest).

---

### Phase 5 – Teams und KI-Schwierigkeitsgrade (v0.8) · M · *W6, W8*

| # | Aufgabe |
| --- | --- |
| 5.1 | `TeamProfile` + Speicherung (B.2), mitgelieferte Beispielteams |
| 5.2 | **Team-Editor**: Name, Farbe, Fahne, bis zu 8 Wurmnamen (Zufallsnamen-Würfel), Hut pro Wurm, Grabstein (8 prozedurale Formen), Lieblings-Superwaffe, Sprachpaket für Sprechblasen, Siegestanz, Steuerung Mensch/KI + Stufe |
| 5.3 | Team-Statistik: Spiele, Siege, Kills, Tode, bester Schuss, Lieblingswaffe (automatisch) |
| 5.4 | KI-Profile (B.5) + generischer Planer über `AIHint`; Stufe pro Team im Battle-Setup überschreibbar |
| 5.5 | Sprechblasen + Kommentator-Zeilen nach Ereignissen (Sprachpakete als JSON-Textlisten) |
| 5.6 | Erfolge (lokal, `progress.json`) |

**Abnahme:** KI-Turnier-Test (headless, 30 Seeds): Jede höhere Stufe gewinnt gegen die
niedrigere in ≥ 65 % der Partien; Experte trifft auf flachem Gelände bei Windstille ≥ 80 %.
Teams überleben Speichern/Laden und Umbenennen.

---

### Phase 6 – Werkzeuge mit eigener Physik (v0.9) · L · *W5 Teil 2*

| # | Aufgabe |
| --- | --- |
| 6.1 | **Prototyp Enterseil** (zeitbox: 2 Sitzungen): Seil haftet an Terrain, Pendelphysik, Ein-/Ausholen, Loslassen, mehrfaches Anheften, Waffe am Seil abfeuern. *Abbruchkriterium:* Wenn das Seil im Prototyp nicht stabil ist, wird die vereinfachte Variante „Kletterhaken“ (gerade Zugbewegung) gebaut |
| 6.2 | Bungee, Jetpack (Treibstoff), Lötlampe, Presslufthammer, Bohrer |
| 6.3 | Zug-Modifikatoren: Wenig Gravitation, Doppelschaden, Schnelles Laufen, Lasersicht, Zug aussetzen, Kapitulieren, Wurm wählen |
| 6.4 | KI (Stufe Experte) nutzt Teleporter und Jetpack, um Kills/Kisten zu erreichen |

**Abnahme:** Seil-Tests (Länge bleibt beim Pendeln konstant ±2 px; Ankerpunkt verschwindet bei Explosion → Wurm fällt). „Nur Werkzeuge“-Vorlage spielbar.

---

### Phase 7 – Verrückte Waffen und Tiere (v0.10) · L · *W5 Teil 3*

| # | Aufgabe |
| --- | --- |
| 7.1 | Läufer-Baustein (läuft, springt über Hindernisse, Zündung per Taste/Zeit): Sprengschaf, Wanderkuchen, Hüpf-Häschen |
| 7.2 | Lenkbare Flieger: Raketen-Schaf (Pfeiltasten lenken, Treibstoff), Kamikaze |
| 7.3 | Graber und Schwärme: Maulwurfbombe, Bienenschwarm |
| 7.4 | Verrückt: Gummiente, Schwarzes Loch, Tauschgranate, Diskokugel, Klavier, Gravitationsumkehr, Ballonbombe, Magnet, Verwandlungsstab, Kühlschrank-Regen, Napalmschlag, Gasgranate, Molotow, Minigun, Präzisionsgewehr, Bogen, Haftmine, Konfetti-Bombe |
| 7.5 | Superwaffen-Regeln (Schema-Schalter, Lieblings-Superwaffe aus dem Team-Profil) |

**Abnahme:** Jede Waffe hat Test + Icon + KI-Hinweis oder ist bewusst als „KI nutzt nicht“
markiert. Leistungsbudget hält mit 3 aktiven Läufern + Bienenschwarm.

---

### Phase 8 – Karten-Editor (v0.11) · M · *W4*

| # | Aufgabe |
| --- | --- |
| 8.1 | Szene **Editor**: Leinwand mit Kamera und Zoom, Werkzeuge Pinsel/Radierer (Größe), Rechteck, Ellipse, Polygon, Füllen, unzerstörbarer Pinsel |
| 8.2 | Generator-Start: „Neue Insel“ mit den Reglern aus 4.6 als Ausgangspunkt |
| 8.3 | Objekte platzieren: Startpunkte (pro Team oder frei), Minen, Fässer, Kisten, Missionsziele (Markierungen mit ID für Phase 9) |
| 8.4 | Thema, Wasserspiegel, Hintergrund wählen; Rückgängig/Wiederholen (Befehlsstapel, 50 Schritte) |
| 8.5 | Speichern/Laden im Kartenformat (ADR-0005), PNG-Import (eigene Zeichnungen) |
| 8.6 | „Testspielen“-Knopf: startet ein Schnellspiel direkt auf der Editor-Karte |

**Abnahme:** Gespeicherte Karte lädt pixelgenau. Rückgängig über 50 Schritte stellt den
Ausgangszustand her. Editor-Smoke-Test zeichnet, platziert, speichert und startet ein Match.

---

### Phase 9 – Missionen, Tutorials, Kampagne (v0.12 → v0.14) · L · *W9, W10*

| # | Aufgabe |
| --- | --- |
| 9.1 | Missionssystem (ADR-0007): Ziele `alle_besiegen`, `wurm_ueberlebt`, `kiste_einsammeln`, `position_erreichen`, `ueberleben_runden`, `ziel_zerstoeren`, `in_runden`; Trigger auf Ereignisse; Aktionen `nachricht`, `kamera`, `kiste_spawnen`, `wasser_steigen`, `waffe_geben`, `team_spawnen`, `sieg`/`niederlage` |
| 9.2 | Briefing-, Pausen- und Ergebnis-Bildschirm mit Medaillen (Bronze = geschafft, Silber/Gold = optionale Ziele/Rundenzahl) |
| 9.3 | **Tutorials (8)**: 1 Laufen & Springen (alle 3 Sprünge) · 2 Zielen & Bazooka · 3 Wind lesen · 4 Granate, Zünder & Abprall · 5 Werkzeuge: Teleporter, Brückenteil, Fallschirm · 6 Enterseil-Parcours · 7 Kisten, Minen & Fässer · 8 Superwaffen & Sudden Death. Mit Hinweis-Overlay („Drücke Rücktaste“), Schritt-Triggern und Wiederholen |
| 9.4 | **Kampagne**: 4 Kapitel × 5 Missionen (+ Bosskampf pro Kapitel) mit thematischen Karten (Erde, Eis, Mond, Lava). Freischaltungen von Waffen, Hüten und Grabsteinen. Fortschritt in `progress.json` |
| 9.5 | Kampagnenkarte als Szene (Kapitelpfad, Medaillen) |

**Abnahme:** Jede Mission ist headless lösbar (Test steuert ein Skript-Eingabeprotokoll) und
verlierbar. Tutorials setzen kein Vorwissen voraus (manueller Test mit einer Person, die das Spiel
nicht kennt). Fortschritt bleibt nach Neustart erhalten.

---

### Phase 10 – Spaß und Politur → 1.0 · M

| # | Aufgabe |
| --- | --- |
| 10.1 | Prozeduraler Sound (Synth: Explosion, Wurf, Platschen, Quietschen, Kistenlandung), Lautstärke in Optionen, stumm bei fehlendem Audio-Gerät |
| 10.2 | Zeitlupe/Kill-Kamera bei großen Momenten, Replay der letzten Runde (aus Eingabeprotokoll) |
| 10.3 | Spielmodi König des Hügels, Kopfgeld, Schatzsuche (über Missionsziele realisiert) |
| 10.4 | Tägliche Herausforderung |
| 10.5 | Gamepad-Unterstützung, Tastenbelegung in Optionen |
| 10.6 | Leistungs- und Balance-Pass (Waffenwerte aus KI-Turnier-Statistik), PyInstaller-Build prüfen |

**Abnahme 1.0:** Alle Wünsche W1–W10 sind abgedeckt und getestet, Build startet auf einem Rechner
ohne Python, 60 FPS bei 4 Teams × 4 Würmern auf der Referenzmaschine.

---

### C.2 Zusammenfassung der Reihenfolge

| Version | Phase | Spürbarer Nutzen |
| --- | --- | --- |
| 0.3 | Fundament | (intern) alles Weitere wird schneller |
| 0.4 | Bewegung, Animation, Kollision | Würmer fühlen sich lebendig an |
| 0.5 | Waffen-Welle 1 | 16 Waffen, Waffenmenü |
| 0.6 | Objekte & Kisten | Ketten, Kisten, Minen |
| 0.7 | Battle-Einstellungen & Umwelt | jedes Spiel anders einstellbar |
| 0.8 | Teams & KI-Stufen | eigene Teams, faire KI |
| 0.9 | Werkzeuge | Seil, Jetpack, Bungee |
| 0.10 | Verrückte Waffen | ca. 45 Waffen insgesamt |
| 0.11 | Karten-Editor | eigene Welten |
| 0.12–0.14 | Missionen, Tutorials, Kampagne | Einzelspieler-Inhalt |
| 1.0 | Spaß & Politur | Sound, Replays, Modi |

### C.3 Offene Fragen (mit meiner Standardannahme)

1. **Sound:** prozedural erzeugt (Annahme) oder eigene Sounddateien?
2. **Grafikstil:** bleibt prozedural gezeichnet (Annahme). Eigene Sprites später optional über `assets/sprites/`.
3. **Steuerung:** Klassiker-Belegung wie oben (Annahme), frei belegbar ab Phase 10.
4. **Kampagnen-Ton:** humorvoll mit eigener kleiner Geschichte (Annahme), z. B. „Die Würmer erobern die vier Elemente zurück“.
5. **Maximale Teamanzahl:** 8 Teams × 8 Würmer (Annahme), Leistungsbudget wird darauf ausgelegt.
6. **`pygame_gui` als neue Abhängigkeit** für Editoren und Formulare (Annahme, ADR-0004). Alternative: eigenes Mini-Widget-Set.
