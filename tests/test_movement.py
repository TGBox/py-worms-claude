"""Phase 1: jump kinds, worm states and worm-worm collision modes."""

import random

import pytest

from src.core.constants import WORM_RADIUS
from src.core.entities import JumpKind, Projectile, Worm, WormState
from src.core.match import Match, Team, replay
from src.core.rng import RngStreams
from src.core.scheme import GameScheme
from src.core.terrain import Terrain
from src.core.world import World

DT = 1 / 60
GROUND = 300
STAND_Y = GROUND - WORM_RADIUS - 1


def world_with(collision: str = "ueberkriechen", jump_strength: float = 1.0) -> World:
    scheme = GameScheme()
    scheme.terrain.water_level = 380
    scheme.worms.collision = collision
    scheme.worms.jump_strength = jump_strength
    terrain = Terrain(800, 400)
    for x in range(800):
        terrain.fill_column(x, GROUND)
    return World(terrain, scheme)


def place(world: World, x: float, team: int = 0, facing: int = 1) -> Worm:
    worm = Worm(f"W{len(world.worms)}", team, facing=facing, x=x, y=STAND_Y, grounded=True)
    return world.add_worm(worm)


def run(world: World, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        world.update(DT)


def jump_and_track(world: World, worm: Worm, kind: JumpKind) -> tuple[float, float]:
    """Jump and return (peak height above start, landing x)."""
    start_y = worm.y
    world.jump(worm, kind)
    peak = 0.0
    for _ in range(240):
        world.update(DT)
        peak = max(peak, start_y - worm.y)
        if worm.grounded:
            break
    assert worm.grounded
    return peak, worm.x


# --------------------------------------------------------------------- jumps
def test_high_jump_and_backflip() -> None:
    results = {}
    for kind in JumpKind:
        world = world_with()
        worm = place(world, 400)
        results[kind] = jump_and_track(world, worm, kind)
    forward_peak, forward_x = results[JumpKind.FORWARD]
    high_peak, high_x = results[JumpKind.HIGH]
    flip_peak, flip_x = results[JumpKind.BACKFLIP]
    assert forward_x > 430
    assert high_peak >= 1.4 * forward_peak
    assert abs(high_x - 400) < abs(forward_x - 400)
    assert flip_x < 400  # lands behind the starting point
    assert flip_peak > high_peak * 0.9


def test_jump_strength_from_scheme() -> None:
    peaks = []
    for strength in (1.0, 1.5):
        world = world_with(jump_strength=strength)
        peaks.append(jump_and_track(world, place(world, 400), JumpKind.HIGH)[0])
    assert peaks[1] > peaks[0] * 1.8


def test_match_jump_command_is_recorded_and_replayable() -> None:
    def make() -> Match:
        world = world_with()
        a = place(world, 200)
        b = place(world, 600, team=1)
        return Match(
            world,
            [Team("A", (1, 1, 1), False, [a]), Team("B", (1, 1, 1), False, [b])],
            RngStreams(3),
        )

    match = make()
    match.jump("backflip")
    for _ in range(90):
        match.update(DT)
    assert match.log[0].name == "jump" and match.log[0].args == ("backflip",)
    copy = replay(make(), match.log, 90, DT)
    assert (copy.active_worm.x, copy.active_worm.y) == (match.active_worm.x, match.active_worm.y)


# -------------------------------------------------------------------- states
def test_worm_state_transitions() -> None:
    world = world_with()
    worm = place(world, 200)
    assert worm.state == WormState.IDLE
    for _ in range(20):
        world.walk(worm, 1, DT)
        world.update(DT)
    assert worm.state == WormState.WALK and worm.walk_distance > 10
    world.update(DT)
    assert worm.state == WormState.IDLE
    world.jump(worm, JumpKind.BACKFLIP)
    assert worm.state == WormState.BACKFLIP
    run(world, 2)
    assert worm.state == WormState.IDLE
    world.explode(worm.x - 20, worm.y + 5, 25, 1)
    world.update(DT)
    assert worm.state == WormState.FALL
    run(world, 3)
    assert worm.state == WormState.IDLE
    world.kill_worm(worm)
    assert worm.state == WormState.DEAD

    sinker = world.add_worm(Worm("S", 1, x=700, y=50))
    world.terrain.carve_circle(700, 330, 90)
    run(world, 3)
    assert sinker.state == WormState.DROWNED


def test_danger_and_look_ahead() -> None:
    world = world_with()
    worm = place(world, 400)
    other = place(world, 600, team=1)
    assert not world.danger_near(worm)
    world.add_projectile(Projectile("grenade", x=430, y=280, fuse=3, bounce=0.4, owner=other))
    assert world.danger_near(worm)
    before = (worm.x, worm.y, worm.hp, worm.state)
    with world.look_ahead(worm):
        world.jump(worm, JumpKind.FORWARD)
        run(world, 1)
        world.damage_worm(worm, 30)
    assert (worm.x, worm.y, worm.hp, worm.state) == before
    assert world.dry_damage == 30 and not world.dry_run


# ----------------------------------------------------------------- collision
def walk_until(world: World, worm: Worm, target_x: float, seconds: float) -> float:
    """Walk right until target_x is passed; returns the time needed (inf if never)."""
    for step in range(int(seconds / DT)):
        world.walk(worm, 1, DT)
        world.update(DT)
        if worm.x >= target_x and worm.grounded:
            return (step + 1) * DT
    return float("inf")


def test_collision_off_walks_through() -> None:
    world = world_with("aus")
    walker = place(world, 100)
    place(world, 130, team=1)
    assert walk_until(world, walker, 160, 2) < 1.5


def test_collision_block_requires_jump() -> None:
    world = world_with("blockieren")
    walker = place(world, 100)
    blocker = place(world, 130, team=1)
    assert walk_until(world, walker, 160, 3) == float("inf")
    assert walker.x < blocker.x - 2 * WORM_RADIUS + 2
    for _ in range(int(0.4 / DT)):  # step back a little, then jump over
        world.walk(walker, -1, DT)
        world.update(DT)
    walker.facing = 1
    world.jump(walker, JumpKind.FORWARD)
    run(world, 2)
    assert walker.x > blocker.x + WORM_RADIUS


def test_touching_worms_can_always_separate() -> None:
    world = world_with("blockieren")
    left = place(world, 116, facing=-1)  # pressed against the other worm
    place(world, 130, team=1)
    world.jump(left, JumpKind.FORWARD)  # jumps away (facing left)
    run(world, 2)
    assert left.x < 90 and left.grounded


def test_collision_crawl_over_on_flat_ground() -> None:
    world = world_with("ueberkriechen")
    walker = place(world, 100)
    other = place(world, 130, team=1)
    assert walk_until(world, walker, 160, 2) < 2.0
    assert other.x == 130 and other.y == STAND_Y  # the crawled-over worm stays put


def test_crawl_blocked_when_worm_stands_at_a_wall() -> None:
    world = world_with("ueberkriechen")
    for x in range(140, 170):
        world.terrain.fill_column(x, GROUND - 12)  # 12 px wall: above the normal step height
    walker = place(world, 100)
    place(world, 131, team=1)  # leaning against the wall
    assert walk_until(world, walker, 150, 3) == float("inf")


@pytest.mark.parametrize("seed", range(10))
def test_landing_on_a_worm_slides_off(seed: int) -> None:
    rng = random.Random(seed)
    world = world_with("ueberkriechen")
    base = place(world, 400, team=1)
    dropped = world.add_worm(Worm("D", 0, x=400 + rng.uniform(-4, 4), y=rng.uniform(150, 260)))
    run(world, 3)
    assert dropped.grounded
    assert dropped.y == pytest.approx(STAND_Y, abs=2)  # on the ground, not on top
    assert abs(dropped.x - base.x) >= 2 * WORM_RADIUS - 1


# ------------------------------------------------------------------ input buffer
def test_jump_buffer_single_and_double_tap() -> None:
    from src.jump_input import JumpBuffer

    buffer = JumpBuffer(window=0.25)
    assert buffer.press("high") is None
    assert buffer.update(0.1) is None and buffer.pending
    assert buffer.update(0.2) == "high"  # window passed: single high jump
    assert buffer.press("forward") is None
    assert buffer.update(0.1) is None
    assert buffer.press("forward") == "backflip"  # second press within the window
    assert buffer.update(1.0) is None and not buffer.pending


# ------------------------------------------------------------------- AI movement
def ai_match(world: World) -> Match:
    teams = [
        Team(f"T{i}", (1, 1, 1), i == 0, [w for w in world.worms if w.team_index == i])
        for i in range(2)
    ]
    return Match(world, teams, RngStreams(5))


def test_ai_explores_walk_and_jump_routes() -> None:
    from src.core.ai import explore_routes

    world = world_with("ueberkriechen")
    for x in range(150, 400):
        world.terrain.fill_column(x, GROUND - 25)  # plateau edge too high to walk up
    shooter = place(world, 100)
    place(world, 600, team=1)
    match = ai_match(world)
    before = (shooter.x, shooter.y, shooter.state)
    routes = explore_routes(match)
    assert (shooter.x, shooter.y, shooter.state) == before  # exploration has no side effects
    assert any(r.steps and r.x < 90 for r in routes)  # walking left
    jump_routes = [r for r in routes if any(step[0] == "jump" for step in r.steps)]
    assert jump_routes and all(r.y < STAND_Y for r in jump_routes)  # up on the step


def test_ai_walks_out_from_under_a_roof_to_shoot() -> None:
    from src.core.ai import AIController

    world = world_with("ueberkriechen")
    for y in range(GROUND - 26, GROUND - 18):  # low roof just above the shooter's head
        start = y * world.terrain.width
        world.terrain.data[start + 40 : start + 230] = b"\x01" * 190
    for x in range(500, 640):  # the enemy stands on a plateau: no straight shot from below
        world.terrain.fill_column(x, GROUND - 80)
    shooter = place(world, 100)
    enemy = world.add_worm(Worm("E", 1, x=570, y=GROUND - 80 - WORM_RADIUS - 1, grounded=True))
    match = ai_match(world)
    ai = AIController(match, noise=0.0)
    ai.think_steps = 100_000
    for _ in range(int(25 / DT)):
        ai.update(DT)
        match.update(DT)
        if match.turn_number > 1:
            break
    assert not 40 <= shooter.x <= 230  # left the shelter (either side)
    assert enemy.hp < 100 or not enemy.alive
