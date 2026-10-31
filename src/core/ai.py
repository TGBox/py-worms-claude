"""Computer opponent: brute-force ballistic search using the real projectile physics."""

import math
import random
import time
from collections.abc import Generator
from dataclasses import dataclass

from src.core.entities import Projectile, Worm
from src.core.match import Match, Phase
from src.core.weapons import WEAPONS, FireMode, Weapon
from src.core.world import World, step_projectile
from src.settings import AIM_MAX, AIM_MIN, AIM_SPEED, MAX_SHOT_SPEED, WORM_RADIUS

SIM_DT = 1 / 60
SIM_MAX_TIME = 5.0
AIM_STEPS = [round(AIM_MIN + 0.1 * i, 2) for i in range(int((AIM_MAX - AIM_MIN) / 0.1) + 1)]
POWER_STEPS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
ALLY_PENALTY = 1.5
KILL_BONUS = 40.0
AIRSTRIKE_THRESHOLD = 40.0  # only spend the airstrike when nothing else scores this well


@dataclass
class ShotPlan:
    weapon_index: int
    facing: int
    aim: float
    power: float = 1.0
    target_x: float | None = None
    score: float = -math.inf


def simulate_shot(
    world: World, shooter: Worm, weapon: Weapon, facing: int, aim: float, power: float
) -> tuple[float, float] | None:
    """Dry-run a charged shot and return the detonation point (None if lost)."""
    dx, dy = math.cos(aim) * facing, -math.sin(aim)
    speed = power * MAX_SHOT_SPEED
    projectile = Projectile(
        weapon_key=weapon.key,
        x=shooter.x + dx * (WORM_RADIUS + 4),
        y=shooter.y + dy * (WORM_RADIUS + 4),
        vx=dx * speed,
        vy=dy * speed,
        explosion_radius=weapon.explosion_radius,
        damage=weapon.damage,
        wind_factor=weapon.wind_factor,
        fuse=weapon.fuse,
        bounce=weapon.bounce,
        owner=shooter,
    )
    live = [w for w in world.worms if w.alive]
    elapsed = 0.0
    while elapsed < SIM_MAX_TIME:
        result = step_projectile(
            projectile, world.terrain, live, world.wind, SIM_DT, world.water_level
        )
        if result == "explode":
            return (projectile.x, projectile.y)
        if result == "gone":
            return None
        elapsed += SIM_DT
    return None


def score_explosion(
    world: World, team_index: int, x: float, y: float, radius: float, damage: int
) -> float:
    """Expected value of an explosion for the given team (enemy damage minus own damage)."""
    score = 0.0
    nearest_enemy = math.inf
    reach = radius + WORM_RADIUS
    for worm in world.worms:
        if not worm.alive:
            continue
        distance = math.hypot(worm.x - x, worm.y - y)
        enemy = worm.team_index != team_index
        if enemy:
            nearest_enemy = min(nearest_enemy, distance)
        if distance >= reach:
            continue
        dealt = damage * min(1.0, (reach - distance) / radius)
        value = dealt + (KILL_BONUS if dealt >= worm.hp else 0.0)
        score += value if enemy else -ALLY_PENALTY * value
    # Tie-breaker: prefer shots that land close to an enemy.
    return score - min(nearest_enemy, 2000) * 0.01


def has_line_of_sight(world: World, x0: float, y0: float, x1: float, y1: float) -> bool:
    distance = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(distance / 3))
    for i in range(1, steps):
        t = i / steps
        if world.terrain.is_solid(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
            return False
    return True


def plan_turn(match: Match) -> Generator[None, None, ShotPlan]:
    """Search for the best shot; yields regularly so the caller can spread work over frames."""
    world = match.world
    shooter = match.active_worm
    team_index = shooter.team_index
    enemies = [w for w in world.worms if w.alive and w.team_index != team_index]
    best = ShotPlan(0, shooter.facing, 0.6, 0.6)
    if not enemies:
        return best
    facings = sorted({1 if e.x >= shooter.x else -1 for e in enemies}) or [shooter.facing]

    for index, weapon in enumerate(WEAPONS):
        if not match.has_ammo(weapon):
            continue
        if weapon.mode == FireMode.CHARGED:
            for facing in facings:
                for aim in AIM_STEPS:
                    for power in POWER_STEPS:
                        impact = simulate_shot(world, shooter, weapon, facing, aim, power)
                        yield None
                        if impact is None:
                            continue
                        score = score_explosion(
                            world, team_index, *impact, weapon.explosion_radius, weapon.damage
                        )
                        if score > best.score:
                            best = ShotPlan(index, facing, aim, power, score=score)
        elif weapon.mode == FireMode.DIRECT:
            for enemy in enemies:
                dx, dy = enemy.x - shooter.x, enemy.y - shooter.y
                if math.hypot(dx, dy) > weapon.range * 0.9 or abs(dx) < 1:
                    continue
                facing = 1 if dx > 0 else -1
                aim = math.atan2(-dy, abs(dx))
                if not AIM_MIN <= aim <= AIM_MAX:
                    continue
                if not has_line_of_sight(world, shooter.x, shooter.y, enemy.x, enemy.y):
                    continue
                score = score_explosion(
                    world, team_index, enemy.x, enemy.y, weapon.explosion_radius, weapon.damage
                )
                if score > best.score:
                    best = ShotPlan(index, facing, aim, score=score)
        elif weapon.mode == FireMode.TARGETED and best.score < AIRSTRIKE_THRESHOLD:
            for enemy in enemies:
                score = 0.0
                for i in range(weapon.missiles):
                    mx = enemy.x + (i - (weapon.missiles - 1) / 2) * 26
                    top = world.terrain.surface_y(mx)
                    my = top if top is not None else world.water_level
                    score += 0.5 * score_explosion(
                        world, team_index, mx, my, weapon.explosion_radius, weapon.damage
                    )
                yield None
                if score > best.score:
                    best = ShotPlan(
                        index, shooter.facing, shooter.aim, target_x=enemy.x, score=score
                    )
    return best


class AIController:
    """Drives the active worm of AI teams through the normal match commands."""

    def __init__(self, match: Match, rng: random.Random | None = None, noise: float = 0.03) -> None:
        self.match = match
        self.rng = rng or random.Random()
        self.noise = noise
        self.think_budget = 0.010  # seconds of planning per frame
        self.thinking = False
        self._turn = -1
        self._planner: Generator[None, None, ShotPlan] | None = None
        self._plan: ShotPlan | None = None
        self._delay = 0.0
        self._done = False

    def update(self, dt: float) -> None:
        match = self.match
        if match.phase != Phase.AIMING or not match.active_team.is_ai:
            self.thinking = False
            return
        if self._turn != match.turn_number:
            self._turn = match.turn_number
            self._planner = plan_turn(match)
            self._plan = None
            self._delay = 0.6
            self._done = False
            self.thinking = True
        if self._plan is None:
            self._think()
            return
        if self._delay > 0:
            self._delay -= dt
            return
        if not self._done:
            self._execute(dt)

    def _think(self) -> None:
        assert self._planner is not None
        deadline = time.perf_counter() + self.think_budget
        while time.perf_counter() < deadline:
            try:
                next(self._planner)
            except StopIteration as stop:
                plan: ShotPlan = stop.value
                plan.aim = max(AIM_MIN, min(AIM_MAX, plan.aim + self.rng.gauss(0, self.noise)))
                plan.power = max(0.1, min(1.0, plan.power + self.rng.gauss(0, self.noise)))
                self._plan = plan
                self.thinking = False
                return

    def _execute(self, dt: float) -> None:
        match = self.match
        plan = self._plan
        assert plan is not None
        worm = match.active_worm
        match.select_weapon(plan.weapon_index)
        weapon = match.weapon
        if weapon.mode == FireMode.TARGETED and plan.target_x is not None:
            match.fire_at(plan.target_x)
            self._done = True
            return
        if worm.facing != plan.facing:
            match.face(plan.facing)
            return
        difference = plan.aim - worm.aim
        if abs(difference) > 0.01:
            step = math.copysign(min(abs(difference), AIM_SPEED * dt), difference)
            match.aim(step)
            return
        if weapon.mode == FireMode.DIRECT:
            match.fire_direct()
            self._done = True
        elif not match.charging:
            match.start_charge()
        elif match.power >= plan.power:
            match.release_charge()
            self._done = True
