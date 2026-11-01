"""Parity of the Rust kernel with the Python reference (ADR-0008).

Every test runs the same computation twice, once through the kernel and once inside
`native.disabled()`, and requires bit-identical results. Skipped when the kernel is not built.
"""

import copy
import random
import time
import zlib

import pytest

from src.core import native
from src.core.ai import AIController, plan_turn, simulate_projectiles
from src.core.constants import WORM_RADIUS
from src.core.entities import Projectile, Worm
from src.core.mapgen import generate_terrain
from src.core.match import Match, TeamConfig
from src.core.scheme import GameScheme
from src.core.terrain import Terrain
from src.core.weapons import FireContext, get_behavior, get_weapon
from src.core.world import World

pytestmark = pytest.mark.skipif(not native.available(), reason="Rust-Kernel nicht gebaut")

DT = 1 / 60


def both(function):  # type: ignore[no-untyped-def]
    """(kernel result, Python result) of a zero-argument function."""
    fast = function()
    with native.disabled():
        slow = function()
    return fast, slow


def island(seed: int) -> Terrain:
    return generate_terrain(2000, 1000, 930, seed)


# ----------------------------------------------------------------------- terrain
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_terrain_queries_match(seed: int) -> None:
    terrain = island(seed)
    rng = random.Random(seed)
    points = [
        (rng.uniform(-20, 2020), rng.uniform(-20, 1020), rng.uniform(1, 12)) for _ in range(4000)
    ]
    fast, slow = both(lambda: [terrain.circle_collides(x, y, r) for x, y, r in points])
    assert fast == slow
    fast, slow = both(lambda: [terrain.normal_at(x, y, int(r)) for x, y, r in points[:800]])
    assert fast == slow


def test_carving_matches() -> None:
    rng = random.Random(4)
    circles = [
        (rng.uniform(-50, 2050), rng.uniform(-50, 1050), rng.uniform(0, 70)) for _ in range(60)
    ]

    def carve() -> bytes:
        terrain = island(5)
        for x, y, r in circles:
            terrain.carve_circle(x, y, r)
            terrain.fill_circle(y, x / 2, r / 3)
        return bytes(terrain.data)

    fast, slow = both(carve)
    assert fast == slow


# -------------------------------------------------------------------- projectiles
def projectile_run() -> list[tuple]:
    rng = random.Random(11)
    world = World(island(6), GameScheme())
    world.wind = 0.7
    for i in range(6):
        x = 200 + i * 300
        top = world.terrain.surface_y(x) or 500
        world.add_worm(Worm(f"W{i}", i % 2, x=x, y=top - WORM_RADIUS - 1, grounded=True))
    trace = []
    for frame in range(900):
        if frame % 20 == 0:
            owner = world.worms[rng.randrange(len(world.worms))]
            bounce = rng.choice([None, 0.45, 0.7])
            world.add_projectile(
                Projectile(
                    "test",
                    x=rng.uniform(0, 2000),
                    y=rng.uniform(-100, 400),
                    vx=rng.uniform(-600, 600),
                    vy=rng.uniform(-500, 300),
                    explosion_radius=rng.uniform(10, 45),
                    damage=30,
                    wind_factor=rng.choice([0.0, 0.5, 1.0]),
                    fuse=rng.choice([None, 1.5, 3.0]) if bounce else None,
                    bounce=bounce,
                    owner=owner,
                )
            )
        world.update(DT)
        trace.append(
            tuple((p.x, p.y, p.vx, p.vy, p.age, p.fuse, p.asleep) for p in world.projectiles)
        )
        trace.append(tuple((w.x, w.y, w.vx, w.vy, w.hp, w.alive) for w in world.worms))
    trace.append(zlib.crc32(world.terrain.data))
    return trace


def test_projectiles_and_explosions_match() -> None:
    fast, slow = both(projectile_run)
    assert len(fast) == len(slow)
    for frame, (a, b) in enumerate(zip(fast, slow)):
        assert a == b, f"Abweichung in Eintrag {frame}"


def test_ai_dry_runs_match_including_airstrikes() -> None:
    world = World(island(7), GameScheme())
    world.wind = -0.4
    shooter = world.add_worm(Worm("S", 0, x=600, y=(world.terrain.surface_y(600) or 500) - 8))
    for x in (900, 1300, 1700):
        world.add_worm(Worm("E", 1, x=x, y=(world.terrain.surface_y(x) or 500) - 8))
    shots = []
    for key in ("bazooka", "grenade", "airstrike"):
        weapon = get_weapon(key)
        for aim in (-0.3, 0.2, 0.7, 1.2):
            for power in (0.3, 0.6, 1.0):
                context = FireContext(world, shooter, weapon, 1, aim, power, 1300.0)
                shots.append(get_behavior(weapon.behavior).preview(context))

    def run() -> list:
        return [simulate_projectiles(world, copy.deepcopy(batch)) for batch in shots]

    fast, slow = both(run)
    assert fast == slow


# --------------------------------------------------------------------------- worms
@pytest.mark.parametrize("mode", ["aus", "blockieren", "ueberkriechen"])
def test_walking_jumping_and_flying_worms_match(mode: str) -> None:
    def run() -> list:
        rng = random.Random(21)
        scheme = GameScheme()
        scheme.worms.collision = mode
        world = World(island(8), scheme)
        worms = []
        for i in range(8):
            x = 700 + i * 22  # close together: lots of worm-worm contact
            top = world.terrain.surface_y(x) or 500
            worms.append(world.add_worm(Worm(f"W{i}", i % 2, x=x, y=top - 30)))
        trace = []
        for frame in range(1200):
            for worm in worms:
                if rng.random() < 0.7:
                    world.walk(worm, rng.choice((-1, 1)), DT)
                if rng.random() < 0.01:
                    from src.core.entities import JumpKind

                    world.jump(worm, rng.choice(list(JumpKind)))
            if frame % 150 == 75:
                target = worms[rng.randrange(len(worms))]
                world.explode(target.x + rng.uniform(-20, 20), target.y + 10, 30, 10)
            world.update(DT)
            trace.append(tuple((w.x, w.y, w.vx, w.vy, w.grounded, w.state, w.hp) for w in worms))
        return trace

    fast, slow = both(run)
    for frame, (a, b) in enumerate(zip(fast, slow)):
        assert a == b, f"Abweichung in Frame {frame}"


# --------------------------------------------------------------------- whole match
def test_full_ai_match_is_identical_on_both_backends() -> None:
    def run() -> int:
        scheme = GameScheme()
        scheme.worms.count = 2
        configs = [TeamConfig("A", (1, 1, 1), True), TeamConfig("B", (2, 2, 2), True)]
        match = Match.create(configs, island(9), 9, scheme)
        ai = AIController(match)
        for _ in range(60 * 30):
            ai.update(DT)
            match.update(DT)
        parts = [match.tick, match.turn_number, zlib.crc32(match.world.terrain.data)]
        for worm in match.world.worms:
            parts += [worm.x, worm.y, worm.hp, worm.alive]
        return zlib.crc32(repr(parts).encode())

    fast, slow = both(run)
    assert fast == slow


def test_kernel_speeds_up_ai_planning() -> None:
    configs = [TeamConfig("A", (1, 1, 1), True), TeamConfig("B", (2, 2, 2), True)]
    match = Match.create(configs, island(10), 10, GameScheme())
    for _ in range(60):
        match.update(DT)

    def plan() -> float:
        best = float("inf")
        for _ in range(2):
            start = time.perf_counter()
            planner = plan_turn(match)
            for _ in planner:
                pass
            best = min(best, time.perf_counter() - start)
        return best

    fast, slow = both(plan)
    assert slow / fast >= 3.0, f"nur {slow / fast:.1f}x schneller"
