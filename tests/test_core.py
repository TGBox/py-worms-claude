"""Tests for the pure game logic in src.core (no pygame required)."""

import math
import random

import pytest

from src.core.ai import AIController, plan_turn, simulate_shot
from src.core.entities import Worm
from src.core.mapgen import generate_terrain
from src.core.match import Match, Phase, Team, TeamConfig
from src.core.terrain import Terrain
from src.core.weapons import AIRSTRIKE, BAZOOKA, GRENADE, SHOTGUN, WEAPONS
from src.core.world import World
from src.settings import RETREAT_TIME, TURN_TIME, WORM_MAX_HP, WORM_RADIUS

DT = 1 / 60


def flat_world(width: int = 800, height: int = 400, ground: int = 300, water: int = 380) -> World:
    terrain = Terrain(width, height)
    for x in range(width):
        terrain.fill_column(x, ground)
    return World(terrain, water_level=water)


def place(world: World, x: float, team: int = 0, name: str = "W") -> Worm:
    top = world.terrain.surface_y(x)
    assert top is not None
    worm = world.add_worm(Worm(name, team, x, top - WORM_RADIUS - 1, grounded=True))
    return worm


def run(world_or_match: World | Match, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        world_or_match.update(DT)


def make_match(world: World, ai: tuple[bool, bool] = (False, False)) -> Match:
    teams = []
    for index in range(2):
        worms = [w for w in world.worms if w.team_index == index]
        ammo = {w.key: w.ammo for w in WEAPONS}
        teams.append(Team(f"T{index}", (255, 0, 0), ai[index], worms, ammo))
    return Match(world, teams, random.Random(1))


# ------------------------------------------------------------------ terrain
def test_terrain_from_rows_and_queries() -> None:
    terrain = Terrain.from_rows(["....", "..#.", "####"])
    assert terrain.is_solid(2, 1)
    assert not terrain.is_solid(1, 1)
    assert not terrain.is_solid(-1, 2)  # outside counts as air
    assert terrain.surface_y(2) == 1
    assert terrain.surface_y(0) == 2


def test_carve_circle_removes_pixels_and_records_it() -> None:
    world = flat_world()
    before = world.terrain.solid_count()
    world.terrain.carve_circle(400, 300, 20)
    assert world.terrain.solid_count() < before
    assert not world.terrain.is_solid(400, 310)
    assert world.terrain.carved == [(400, 300, 20)]


def test_from_alpha_threshold() -> None:
    terrain = Terrain.from_alpha(2, 2, bytes([0, 255, 127, 128]))
    assert list(terrain.data) == [0, 1, 0, 1]


def test_normal_points_away_from_ground() -> None:
    world = flat_world()
    nx, ny = world.terrain.normal_at(400, 300)
    assert ny < -0.9 and abs(nx) < 0.1


def test_generator_is_deterministic_island() -> None:
    a = generate_terrain(600, 400, 360, seed=7)
    b = generate_terrain(600, 400, 360, seed=7)
    c = generate_terrain(600, 400, 360, seed=8)
    assert a.data == b.data
    assert a.data != c.data
    middle = a.surface_y(300)
    assert middle is not None and middle < 360  # land in the middle
    assert (a.surface_y(0) or 400) > 360  # edges sink below the water line
    assert a.carved == []


# ------------------------------------------------------------------ worms
def test_worm_falls_and_lands() -> None:
    world = flat_world()
    worm = world.add_worm(Worm("W", 0, 400, 200))
    run(world, 2)
    assert worm.grounded
    assert worm.y == pytest.approx(300 - WORM_RADIUS - 1, abs=2)
    assert worm.hp == WORM_MAX_HP  # 100 px fall is harmless


def test_long_fall_causes_damage() -> None:
    world = flat_world(height=1400, ground=1300, water=1380)
    worm = world.add_worm(Worm("W", 0, 400, 20))
    run(world, 4)
    assert worm.grounded
    assert worm.hp < WORM_MAX_HP


def test_walk_climbs_small_steps_but_not_walls() -> None:
    world = flat_world()
    for x in range(420, 430):
        world.terrain.fill_column(x, 296)  # 4 px step
    for x in range(470, 480):
        world.terrain.fill_column(x, 250)  # 50 px wall
    worm = place(world, 400)
    run(world, 0.1)
    for _ in range(240):
        world.walk(worm, 1, DT)
        world.update(DT)
    assert 440 < worm.x < 470
    assert worm.facing == 1


def test_jump_leaves_ground() -> None:
    world = flat_world()
    worm = place(world, 400)
    world.jump(worm)
    world.update(DT)
    assert not worm.grounded and worm.y < 300 - WORM_RADIUS - 1
    run(world, 2)
    assert worm.grounded and worm.x > 400


def test_water_kills_worm() -> None:
    world = flat_world()
    world.terrain.carve_circle(400, 340, 120)  # hole down into the water
    worm = world.add_worm(Worm("W", 0, 400, 150))
    run(world, 3)
    assert not worm.alive
    assert any(e.kind == "drown" for e in world.events)


# ---------------------------------------------------------------- weapons
def test_explosion_damages_with_falloff_and_knocks_back() -> None:
    world = flat_world()
    near = place(world, 400)
    far = place(world, 430, team=1)
    away = place(world, 600, team=1)
    world.explode(400, 300, 40, 50)
    assert near.hp < far.hp < WORM_MAX_HP
    assert away.hp == WORM_MAX_HP
    assert far.vx > 0 and not far.grounded


def test_bazooka_explodes_on_terrain() -> None:
    world = flat_world()
    shooter = place(world, 100)
    shooter.aim = 0.5
    before = world.terrain.solid_count()
    world.fire_projectile(shooter, BAZOOKA, 0.6)
    run(world, 4)
    assert not world.projectiles
    assert world.terrain.solid_count() < before
    assert any(e.kind == "explosion" for e in world.events)


def test_bazooka_hits_worm_directly() -> None:
    world = flat_world()
    shooter = place(world, 100)
    target = place(world, 200, team=1)
    shooter.aim = 0.0
    world.fire_projectile(shooter, BAZOOKA, 1.0)
    run(world, 0.5)
    assert target.hp <= WORM_MAX_HP - 40


def test_wind_bends_bazooka_but_not_grenade() -> None:
    impacts = {}
    for weapon in (BAZOOKA, GRENADE):
        for wind in (-1.0, 1.0):
            world = flat_world(width=2000)
            shooter = place(world, 1000)
            shooter.aim = 1.0
            world.wind = wind
            impacts[(weapon.key, wind)] = simulate_shot(world, shooter, weapon, 1, 1.0, 0.6)
    bazooka_shift = impacts[("bazooka", 1.0)][0] - impacts[("bazooka", -1.0)][0]
    grenade_shift = impacts[("grenade", 1.0)][0] - impacts[("grenade", -1.0)][0]
    assert bazooka_shift > 50
    assert grenade_shift == pytest.approx(0, abs=1)


def test_grenade_bounces_and_waits_for_fuse() -> None:
    world = flat_world()
    shooter = place(world, 100)
    shooter.aim = 0.8
    grenade = world.fire_projectile(shooter, GRENADE, 0.5)
    run(world, 2.0)
    assert grenade.alive and grenade in world.projectiles  # still ticking after landing
    assert grenade.y < 300
    run(world, 1.2)
    assert not world.projectiles
    assert any(e.kind == "explosion" for e in world.events)


def test_shotgun_hits_worm_in_line_of_sight() -> None:
    world = flat_world()
    shooter = place(world, 100)
    target = place(world, 300, team=1)
    shooter.aim = 0.0
    x, _ = world.fire_hitscan(shooter, SHOTGUN)
    assert x == pytest.approx(target.x - WORM_RADIUS, abs=3)
    assert target.hp == WORM_MAX_HP - SHOTGUN.damage


def test_airstrike_drops_missiles_on_target() -> None:
    world = flat_world()
    owner = place(world, 100)
    target = place(world, 500, team=1)
    world.launch_airstrike(500, AIRSTRIKE, owner)
    assert len(world.projectiles) == AIRSTRIKE.missiles
    run(world, 4)
    assert not world.projectiles
    assert target.hp < WORM_MAX_HP


# ------------------------------------------------------------------ match
def test_turns_rotate_teams_and_worms() -> None:
    world = flat_world()
    a1, a2 = place(world, 100, 0, "a1"), place(world, 200, 0, "a2")
    b1 = place(world, 600, 1, "b1")
    match = make_match(world)
    order = []
    for _ in range(4):
        order.append(match.active_worm.name)
        match.skip_turn()
        run(match, 1.0)
    assert order == ["a1", "b1", "a2", "b1"]
    assert a1.alive and a2.alive and b1.alive


def test_turn_timer_and_retreat() -> None:
    world = flat_world()
    place(world, 100, 0)
    place(world, 600, 1)
    match = make_match(world)
    assert match.phase == Phase.AIMING and match.turn_timer == TURN_TIME
    match.select_weapon(2)
    match.active_worm.aim = 1.2  # shoot into the sky
    match.fire_direct()
    assert match.phase == Phase.RETREAT
    match.move(1, 0.5)  # moving is allowed while retreating
    run(match, RETREAT_TIME + 1.5)
    assert match.turn_number == 2

    run(match, TURN_TIME + 2)  # second team idles: time runs out
    assert match.turn_number == 3


def test_charge_fires_with_power_and_airstrike_ammo() -> None:
    world = flat_world()
    place(world, 100, 0)
    place(world, 600, 1)
    match = make_match(world)
    match.start_charge()
    run(match, 0.65)
    assert match.charging and 0.4 < match.power < 0.6
    match.release_charge()
    assert len(world.projectiles) == 1 and match.phase == Phase.RETREAT

    run(match, 8)  # next team uses its only airstrike
    match.select_weapon(3)
    assert match.weapon is AIRSTRIKE
    match.fire_at(100)
    assert match.active_team.ammo["airstrike"] == 0
    assert match.weapon is BAZOOKA  # falls back when empty


def test_self_damage_ends_turn_and_dead_team_loses() -> None:
    world = flat_world()
    shooter = place(world, 100, 0)
    victim = place(world, 140, 1)
    victim.hp = 5
    match = make_match(world)
    match.select_weapon(2)
    shooter.aim = 0.0
    match.fire_direct()
    run(match, 6)
    assert not victim.alive
    assert match.phase == Phase.GAME_OVER
    assert match.winner is match.teams[0]


def test_match_create_spawns_teams_on_ground() -> None:
    terrain = generate_terrain(2000, 1000, 930, seed=3)
    configs = [TeamConfig("A", (1, 1, 1)), TeamConfig("B", (2, 2, 2), is_ai=True)]
    match = Match.create(configs, terrain, seed=3, worms_per_team=4)
    assert len(match.world.worms) == 8
    assert all(not match.world.worm_collides(w.x, w.y) for w in match.world.worms)
    run(match, 1)
    assert all(w.alive and w.grounded for w in match.world.worms)


# --------------------------------------------------------------------- AI
def test_ai_plan_hits_enemy_on_flat_ground() -> None:
    world = flat_world()
    place(world, 150, 0)
    enemy = place(world, 550, 1)
    match = make_match(world, ai=(True, False))
    planner = plan_turn(match)
    try:
        while True:
            next(planner)
    except StopIteration as stop:
        plan = stop.value
    assert plan.score > 20
    if plan.target_x is None and WEAPONS[plan.weapon_index].key != "shotgun":
        impact = simulate_shot(
            world, match.active_worm, WEAPONS[plan.weapon_index], plan.facing, plan.aim, plan.power
        )
        assert impact is not None and math.hypot(impact[0] - enemy.x, impact[1] - enemy.y) < 45


def test_ai_controller_plays_its_turn() -> None:
    world = flat_world()
    place(world, 150, 0)
    enemy = place(world, 550, 1)
    match = make_match(world, ai=(True, False))
    ai = AIController(match, random.Random(0), noise=0.0)
    ai.think_budget = 1.0
    for _ in range(int(15 / DT)):
        ai.update(DT)
        match.update(DT)
        if match.turn_number > 1:
            break
    assert match.turn_number == 2
    assert enemy.hp < WORM_MAX_HP


def test_full_ai_match_finishes() -> None:
    terrain = generate_terrain(2000, 1000, 930, seed=1)
    configs = [TeamConfig("A", (1, 1, 1), True), TeamConfig("B", (2, 2, 2), True)]
    match = Match.create(configs, terrain, seed=1, worms_per_team=2)
    ai = AIController(match, random.Random(1))
    ai.think_budget = 1.0
    for _ in range(int(20 * 60 / DT)):
        ai.update(DT)
        match.update(DT)
        if match.phase == Phase.GAME_OVER:
            break
    assert match.phase == Phase.GAME_OVER
