"""Computer opponent: searches shots using the weapons' AI hints and the real physics."""

import math
import random
from collections.abc import Generator
from dataclasses import dataclass

from src.core.constants import AIM_MAX, AIM_MIN, AIM_SPEED, SIM_DT, WORM_RADIUS
from src.core.entities import Projectile, Worm
from src.core.match import Match, Phase
from src.core.weapons import AIKind, AimMode, FireContext, WeaponDef, all_weapons, get_behavior
from src.core.world import World, step_projectile

SIM_MAX_TIME = 5.0
AIM_STEPS = [round(AIM_MIN + 0.1 * i, 2) for i in range(int((AIM_MAX - AIM_MIN) / 0.1) + 1)]
POWER_STEPS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
ALLY_PENALTY = 1.5
KILL_BONUS = 40.0
RESERVE_THRESHOLD = 40.0  # reserve weapons only when nothing else scores this well
DEFAULT_THINK_STEPS = 40  # candidate evaluations per frame (deterministic, unlike a time budget)


@dataclass
class ShotPlan:
    weapon_key: str
    facing: int
    aim: float
    power: float = 1.0
    target_x: float | None = None
    score: float = -math.inf


def simulate_projectiles(world: World, projectiles: list[Projectile]) -> list[tuple[float, float]]:
    """Dry-run projectiles and return their detonation points (lost ones are skipped)."""
    live = [w for w in world.worms if w.alive]
    impacts = []
    for projectile in projectiles:
        elapsed = 0.0
        while elapsed < SIM_MAX_TIME:
            result = step_projectile(projectile, world, live, SIM_DT)
            if result == "explode":
                impacts.append((projectile.x, projectile.y))
                break
            if result == "gone":
                break
            elapsed += SIM_DT
    return impacts


def simulate_shot(
    world: World,
    shooter: Worm,
    weapon: WeaponDef,
    facing: int,
    aim: float,
    power: float,
    target_x: float | None = None,
) -> tuple[float, float] | None:
    """Detonation point of the first projectile a shot would launch (None if lost)."""
    context = FireContext(world, shooter, weapon, facing, aim, power, target_x)
    impacts = simulate_projectiles(world, get_behavior(weapon.behavior).preview(context))
    return impacts[0] if impacts else None


def score_explosion(
    world: World, team_index: int, x: float, y: float, radius: float, damage: float
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
    """Search for the best shot; yields after each candidate so work spreads over frames."""
    world = match.world
    shooter = match.active_worm
    team_index = shooter.team_index
    enemies = [w for w in world.worms if w.alive and w.team_index != team_index]
    fallback = next((w for w in all_weapons() if match.is_available(w)), all_weapons()[0])
    best = ShotPlan(fallback.key, shooter.facing, 0.6, 0.6)
    if not enemies:
        return best
    facings = sorted({1 if e.x >= shooter.x else -1 for e in enemies}) or [shooter.facing]
    usable = [w for w in all_weapons() if w.ai is not None and match.is_available(w)]
    # Reserve weapons are considered last, once the normal options are known.
    usable.sort(key=lambda w: w.ai.reserve if w.ai else False)

    for weapon in usable:
        assert weapon.ai is not None
        strength = match.scheme.weapon(weapon.key).power
        if weapon.ai.reserve and best.score >= RESERVE_THRESHOLD:
            continue
        radius = weapon.param("radius", 30)
        damage = weapon.param("damage", 30) * strength

        if weapon.ai.kind == AIKind.SIMULATE and weapon.aim == AimMode.CHARGED:
            for facing in facings:
                for aim in AIM_STEPS:
                    for power in POWER_STEPS:
                        impact = simulate_shot(world, shooter, weapon, facing, aim, power)
                        yield None
                        if impact is None:
                            continue
                        score = score_explosion(world, team_index, *impact, radius, damage)
                        if score > best.score:
                            best = ShotPlan(weapon.key, facing, aim, power, score=score)

        elif weapon.ai.kind == AIKind.DIRECT:
            for enemy in enemies:
                dx, dy = enemy.x - shooter.x, enemy.y - shooter.y
                if math.hypot(dx, dy) > weapon.param("range", 700) * 0.9 or abs(dx) < 1:
                    continue
                facing = 1 if dx > 0 else -1
                aim = math.atan2(-dy, abs(dx))
                if not AIM_MIN <= aim <= AIM_MAX:
                    continue
                yield None
                if not has_line_of_sight(world, shooter.x, shooter.y, enemy.x, enemy.y):
                    continue
                score = score_explosion(world, team_index, enemy.x, enemy.y, radius, damage)
                if score > best.score:
                    best = ShotPlan(weapon.key, facing, aim, score=score)

        elif weapon.ai.kind == AIKind.TARGET_POINT:
            for enemy in enemies:
                context = FireContext(
                    world, shooter, weapon, shooter.facing, shooter.aim, 1.0, enemy.x, strength
                )
                projectiles = get_behavior(weapon.behavior).preview(context)
                score = 0.0
                for x, y in simulate_projectiles(world, projectiles):
                    score += 0.5 * score_explosion(world, team_index, x, y, radius, damage)
                yield None
                if score > best.score:
                    best = ShotPlan(
                        weapon.key, shooter.facing, shooter.aim, target_x=enemy.x, score=score
                    )
    return best


class AIController:
    """Drives the active worm of AI teams through the normal (recorded) match commands."""

    def __init__(self, match: Match, rng: random.Random | None = None, noise: float = 0.03):
        self.match = match
        self.rng = rng or match.rng.stream("ai")
        self.noise = noise
        self.think_steps = DEFAULT_THINK_STEPS
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
        for _ in range(self.think_steps):
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
        match.select_weapon_key(plan.weapon_key)
        weapon = match.weapon
        if weapon.aim == AimMode.TARGET_POINT and plan.target_x is not None:
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
        if weapon.aim in (AimMode.ANGLE, AimMode.NONE):
            match.fire_direct()
            self._done = True
        elif not match.charging:
            match.start_charge()
        elif match.power >= plan.power:
            match.release_charge()
            self._done = True
