"""Tests for the phase-0 foundation: scheme, RNG streams, events, physics, weapon registry,
persistence, command log and determinism."""

import json
import re
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from src.core import persistence
from src.core.ai import AIController
from src.core.constants import WORM_RADIUS
from src.core.entities import Projectile, Worm
from src.core.events import Damage, EventBus, Explosion, TurnStarted
from src.core.mapgen import generate_terrain
from src.core.match import Match, Phase, Team, TeamConfig, replay
from src.core.physics import Body, PhysicsWorld
from src.core.rng import RngStreams
from src.core.scheme import (
    GameScheme,
    list_schemes,
    load_scheme,
    load_scheme_by_name,
    save_scheme,
)
from src.core.terrain import Terrain
from src.core.weapons import (
    AimMode,
    get_weapon,
    register_weapon,
    unregister_weapon,
)
from src.core.world import World

DT = 1 / 60
SRC_CORE = Path(__file__).resolve().parent.parent / "src" / "core"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(persistence.DATA_DIR_ENV, str(tmp_path / "data"))
    return tmp_path / "data"


def flat_world(scheme: GameScheme | None = None, width: int = 800) -> World:
    scheme = scheme or GameScheme()
    scheme.terrain.water_level = 380
    terrain = Terrain(width, 400)
    for x in range(width):
        terrain.fill_column(x, 300)
    return World(terrain, scheme)


def place(world: World, x: float, team: int = 0, hp: int = 100) -> Worm:
    worm = Worm(f"W{len(world.worms)}", team, hp=hp, x=x, y=300 - WORM_RADIUS - 1, grounded=True)
    return world.add_worm(worm)


def two_team_match(world: World) -> Match:
    teams = [
        Team(f"T{i}", (200, 0, 0), False, [w for w in world.worms if w.team_index == i])
        for i in range(2)
    ]
    return Match(world, teams, RngStreams(1))


def run(target: World | Match, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        target.update(DT)


# ---------------------------------------------------------------- architecture rules
def test_core_has_no_pygame_and_no_settings_imports() -> None:
    pattern = re.compile(r"^\s*(import pygame|from pygame|from src\.settings|import src\.settings)")
    offenders = [
        str(path)
        for path in SRC_CORE.rglob("*.py")
        if any(pattern.match(line) for line in path.read_text(encoding="utf-8").splitlines())
    ]
    assert offenders == []


# ------------------------------------------------------------------------- scheme
def test_scheme_round_trip_and_files(isolated_data_dir: Path) -> None:
    scheme = GameScheme(name="Mein Schema")
    scheme.turn.turn_time = 30
    scheme.worms.hp = 150
    scheme.weapon("airstrike").delay = 3
    data = scheme.to_dict()
    assert set(data["weapons"]) >= {"bazooka", "grenade", "shotgun", "airstrike"}
    assert GameScheme.from_dict(json.loads(json.dumps(data))).to_dict() == data

    path = save_scheme(scheme)
    assert path.parent == isolated_data_dir / "schemes"
    assert load_scheme(path).to_dict() == data
    assert "Mein Schema" in list_schemes()
    assert load_scheme_by_name("Mein Schema").worms.hp == 150


def test_bundled_schemes_load() -> None:
    names = list_schemes()
    assert next(iter(names)) == "Standard"
    assert {"Standard", "Schnell"} <= set(names)
    assert load_scheme_by_name("Standard").to_dict() == GameScheme().to_dict()
    assert load_scheme_by_name("Schnell").turn.turn_time < GameScheme().turn.turn_time


def test_scheme_tolerates_unknown_and_missing_fields() -> None:
    scheme = GameScheme.from_dict(
        {"version": 1, "name": "Alt", "turn": {"turn_time": 20, "future_option": 5}, "neu": {}}
    )
    assert scheme.turn.turn_time == 20.0
    assert scheme.turn.retreat_time == GameScheme().turn.retreat_time
    assert scheme.worms == GameScheme().worms


def test_migrations_run_step_by_step() -> None:
    @persistence.register_migration("test-doc", 1)
    def _one_to_two(data: dict) -> dict:
        data["b"] = data.pop("a")
        return data

    @persistence.register_migration("test-doc", 2)
    def _two_to_three(data: dict) -> dict:
        data["c"] = data["b"] * 2
        return data

    result = persistence.migrate("test-doc", {"version": 1, "a": 4}, 3)
    assert result == {"version": 3, "b": 4, "c": 8}
    with pytest.raises(ValueError):
        persistence.migrate("test-doc", {"version": 9}, 3)


def test_atomic_json_save(tmp_path: Path) -> None:
    path = tmp_path / "x" / "doc.json"
    persistence.save_json(path, {"version": 1, "name": "Größe"})
    assert persistence.load_json(path)["name"] == "Größe"
    assert not path.with_name("doc.json.tmp").exists()


# ----------------------------------------------------------- scheme drives the rules
def test_scheme_turn_time_hp_and_worm_count() -> None:
    scheme = GameScheme()
    scheme.turn.turn_time = 12
    scheme.worms.count = 2
    scheme.worms.hp = 77
    terrain = generate_terrain(2000, 1000, 930, seed=4)
    match = Match.create(
        [TeamConfig("A", (1, 1, 1)), TeamConfig("B", (2, 2, 2))], terrain, 4, scheme
    )
    assert match.turn_timer == 12
    assert len(match.world.worms) == 4
    assert all(w.hp == 77 for w in match.world.worms)


def test_scheme_gravity_changes_jump_height() -> None:
    heights = {}
    for gravity in (1.0, 0.5):
        scheme = GameScheme()
        scheme.environment.gravity = gravity
        world = flat_world(scheme)
        worm = place(world, 400)
        world.jump(worm)
        top = worm.y
        for _ in range(120):
            world.update(DT)
            top = min(top, worm.y)
        heights[gravity] = worm.y - top if worm.grounded else 300 - top
    assert heights[0.5] > heights[1.0] * 1.6


def test_scheme_disables_fall_damage_and_wind() -> None:
    scheme = GameScheme()
    scheme.worms.fall_damage = False
    scheme.environment.wind_max = 0.0
    scheme.terrain.water_level = 1380
    terrain = Terrain(800, 1400)
    for x in range(800):
        terrain.fill_column(x, 1300)
    world = World(terrain, scheme)
    worm = world.add_worm(Worm("W", 0, x=400, y=20))
    other = world.add_worm(Worm("V", 1, x=100, y=1300 - WORM_RADIUS - 1, grounded=True))
    match = Match(
        world,
        [Team("A", (1, 1, 1), False, [worm]), Team("B", (1, 1, 1), False, [other])],
        RngStreams(2),
    )
    assert world.wind == 0.0
    run(match, 4)
    assert worm.grounded and worm.hp == 100


def test_scheme_weapon_power_ammo_and_delay() -> None:
    scheme = GameScheme()
    scheme.weapon("shotgun").power = 2.0
    scheme.weapon("grenade").ammo = 0
    scheme.weapon("airstrike").delay = 1
    world = flat_world(scheme)
    shooter = place(world, 100)
    target = place(world, 300, team=1, hp=200)
    match = two_team_match(world)
    assert not match.is_available(get_weapon("grenade"))
    assert not match.is_available(get_weapon("airstrike"))  # round 1, delay 1
    match.select_weapon_key("grenade")
    assert match.weapon.key == "bazooka"  # unavailable weapons cannot be selected
    match.select_weapon_key("shotgun")
    shooter.aim = 0.0
    match.fire_direct()
    assert target.hp == 200 - 2 * get_weapon("shotgun").param("damage")
    for _ in range(2):  # finish team 0's turn and skip team 1's turn
        run(match, 5)
        match.skip_turn()
    run(match, 2)
    assert match.round_number == 2
    assert match.is_available(get_weapon("airstrike"))


# ------------------------------------------------------------------- weapon registry
def test_new_weapon_is_just_a_catalog_entry() -> None:
    big = replace(
        get_weapon("bazooka"),
        key="test_big_bazooka",
        name="Riesen-Bazooka",
        params={"radius": 60, "damage": 50, "wind": 0.0},
    )
    register_weapon(big)
    try:
        craters = {}
        for key in ("bazooka", "test_big_bazooka"):
            world = flat_world()
            place(world, 100)
            place(world, 700, team=1)
            match = two_team_match(world)
            match.select_weapon_key(key)
            match.active_worm.aim = -0.4  # straight into the ground in front
            match.start_charge()
            run(match, 0.3)
            match.release_charge()
            before = world.terrain.solid_count()
            run(match, 2)
            craters[key] = before - world.terrain.solid_count()
            assert world.bus.of_type(Explosion)[-1].radius == get_weapon(key).param("radius")
        assert craters["test_big_bazooka"] > craters["bazooka"] * 1.8
        assert GameScheme().to_dict()["weapons"]["test_big_bazooka"]["ammo"] == -1
    finally:
        unregister_weapon("test_big_bazooka")


def test_multi_shot_and_non_turn_ending_weapons() -> None:
    double = replace(get_weapon("shotgun"), key="test_double", shots_per_turn=2)
    tool = replace(
        get_weapon("shotgun"),
        key="test_tool",
        ends_turn=False,
        aim=AimMode.NONE,
        params={"range": 10, "radius": 1, "damage": 0},
    )
    register_weapon(double)
    register_weapon(tool)
    try:
        world = flat_world()
        shooter = place(world, 100)
        place(world, 700, team=1)
        match = two_team_match(world)
        shooter.aim = 1.3
        match.select_weapon_key("test_double")
        match.fire_direct()
        assert match.phase == Phase.AIMING  # one shot left
        match.fire_direct()
        assert match.phase == Phase.RETREAT

        run(match, 6)
        match.skip_turn()
        run(match, 2)
        match.select_weapon_key("test_tool")
        match.fire_direct()
        assert match.phase == Phase.AIMING  # tools do not end the turn
    finally:
        unregister_weapon("test_double")
        unregister_weapon("test_tool")


# --------------------------------------------------------------------- rng / events
def test_rng_streams_are_independent_and_reproducible() -> None:
    a, b = RngStreams(42), RngStreams(42)
    b.stream("crates").random()  # drawing elsewhere must not shift the wind sequence
    assert [a.stream("wind").random() for _ in range(5)] == [
        b.stream("wind").random() for _ in range(5)
    ]
    assert RngStreams(43).stream("wind").random() != RngStreams(42).stream("wind").random()


def test_event_bus_dispatch_queue_and_unsubscribe() -> None:
    bus = EventBus()
    seen: list[Explosion] = []
    unsubscribe = bus.subscribe(Explosion, seen.append)
    bus.emit(Explosion(1, 2, 3, 4))
    unsubscribe()
    bus.emit(Explosion(5, 6, 7, 8))
    assert [e.x for e in seen] == [1]
    assert len(bus.of_type(Explosion)) == 2
    assert len(bus.drain()) == 2 and not bus.queue


def test_world_emits_typed_events() -> None:
    world = flat_world()
    worm = place(world, 400)
    turns: list[TurnStarted] = []
    world.bus.subscribe(TurnStarted, turns.append)
    two_team = [worm, place(world, 600, team=1)]
    match = two_team_match(world)
    world.explode(400, 300, 30, 20)
    damage = world.bus.of_type(Damage)
    assert damage and damage[0].worm is worm and damage[0].amount > 0
    assert turns and turns[0].worm is match.active_worm and two_team


# ------------------------------------------------------------------------ physics
def test_spatial_queries_and_body_collision() -> None:
    world = flat_world()
    a = place(world, 100)
    b = place(world, 112, team=1)
    far = place(world, 500, team=1)
    world.rebuild_grid()
    found = world.bodies_in_radius(100, 292, 10)
    assert a in found and b in found and far not in found
    a.collides_with_bodies = b.collides_with_bodies = False
    assert not world.body_collides(a, a.x + 3, a.y)  # body collision is opt-in
    a.collides_with_bodies = b.collides_with_bodies = True
    assert world.body_collides(a, a.x + 3, a.y)
    assert isinstance(a, Body) and issubclass(World, PhysicsWorld)


def test_resting_projectile_sleeps_and_wakes_on_explosion() -> None:
    world = flat_world()
    grenade = world.add_projectile(
        Projectile("grenade", x=400, y=290, explosion_radius=10, damage=0, fuse=10, bounce=0.4)
    )
    run(world, 2)
    assert grenade.asleep
    world.explode(410, 300, 30, 0)
    assert not grenade.asleep


# ------------------------------------------------------------- determinism / replays
def state_hash(match: Match) -> int:
    parts = [match.tick, match.turn_number, match.phase.value, zlib.crc32(match.world.terrain.data)]
    for worm in match.world.worms:
        parts += [worm.name, round(worm.x, 3), round(worm.y, 3), worm.hp, worm.alive]
    return zlib.crc32(repr(parts).encode())


def ai_match(seed: int, ticks: int) -> Match:
    terrain = generate_terrain(2000, 1000, 930, seed)
    scheme = GameScheme()
    scheme.worms.count = 2
    configs = [TeamConfig("A", (1, 1, 1), True), TeamConfig("B", (2, 2, 2), True)]
    match = Match.create(configs, terrain, seed, scheme)
    ai = AIController(match)
    for _ in range(ticks):
        ai.update(DT)
        match.update(DT)
    return match


def test_simulation_is_deterministic_and_replayable() -> None:
    ticks = 60 * 40
    first = ai_match(7, ticks)
    second = ai_match(7, ticks)
    assert first.turn_number >= 3 and first.log
    assert state_hash(first) == state_hash(second)

    terrain = generate_terrain(2000, 1000, 930, 7)
    scheme = GameScheme()
    scheme.worms.count = 2
    configs = [TeamConfig("A", (1, 1, 1), True), TeamConfig("B", (2, 2, 2), True)]
    fresh = Match.create(configs, terrain, 7, scheme)  # no AI: only the recorded commands
    replay(fresh, first.log, ticks, DT)
    assert state_hash(fresh) == state_hash(first)
