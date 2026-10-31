"""Computer opponent: searches shots using the weapons' AI hints and the real physics."""

import math
import random
from collections.abc import Generator
from dataclasses import dataclass, replace

from src.core.constants import AIM_MAX, AIM_MIN, AIM_SPEED, SIM_DT, WORM_RADIUS
from src.core.entities import JumpKind, Projectile, Worm
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

# Movement planning (walk/jump to a better firing position before shooting)
MOVE_RANGE = 160  # px explored to each side
MOVE_SAMPLE = 16  # px between candidate positions
MOVE_MIN_GAIN = 12.0  # required score improvement to bother moving
MOVE_COST = 0.03  # score penalty per px travelled
MOVE_MIN_TURN_TIME = 15.0  # do not start moving with less turn time left
MOVE_MAX_SIM_STEPS = 420  # enough for MOVE_RANGE at crawling speed
COARSE_AIMS = AIM_STEPS[::2]
COARSE_POWERS = [0.45, 0.65, 0.85, 1.0]


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
    world: World,
    team_index: int,
    x: float,
    y: float,
    radius: float,
    damage: float,
    moved: tuple[Worm, float, float] | None = None,
) -> float:
    """Expected value of an explosion for the given team (enemy damage minus own damage).

    `moved` evaluates as if one worm (the shooter) stood somewhere else.
    """
    score = 0.0
    nearest_enemy = math.inf
    reach = radius + WORM_RADIUS
    for worm in world.worms:
        if not worm.alive:
            continue
        wx, wy = (moved[1], moved[2]) if moved and moved[0] is worm else (worm.x, worm.y)
        distance = math.hypot(wx - x, wy - y)
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


def plan_turn(
    match: Match,
    aim_steps: list[float] = AIM_STEPS,
    power_steps: list[float] = POWER_STEPS,
    charged_only: bool = False,
    shooter: Worm | None = None,
) -> Generator[None, None, ShotPlan]:
    """Search for the best shot; yields after each candidate so work spreads over frames.

    `charged_only` with coarse steps gives a cheap estimate used to compare positions;
    `shooter` may be a stand-in copy of the active worm at another position.
    """
    world = match.world
    real = match.active_worm
    shooter = shooter or real
    moved = (real, shooter.x, shooter.y) if shooter is not real else None
    team_index = shooter.team_index
    enemies = [w for w in world.worms if w.alive and w.team_index != team_index]
    fallback = next((w for w in all_weapons() if match.is_available(w)), all_weapons()[0])
    best = ShotPlan(fallback.key, shooter.facing, 0.6, 0.6)
    if not enemies:
        return best
    facings = sorted({1 if e.x >= shooter.x else -1 for e in enemies}) or [shooter.facing]
    usable = [w for w in all_weapons() if w.ai is not None and match.is_available(w)]
    if charged_only:
        usable = [w for w in usable if w.aim == AimMode.CHARGED]
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
                for aim in aim_steps:
                    for power in power_steps:
                        impact = simulate_shot(world, shooter, weapon, facing, aim, power)
                        yield None
                        if impact is None:
                            continue
                        score = score_explosion(world, team_index, *impact, radius, damage, moved)
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


@dataclass
class Route:
    """Movement before shooting: ("walk", target_x) and ("jump", kind) steps."""

    steps: list[tuple[str, float | str]]
    x: float
    y: float
    distance: float


def explore_routes(match: Match, allow_jumps: bool = True) -> list[Route]:
    """Positions the active worm can reach by walking (and one jump over an obstacle).

    Runs the real movement code inside `world.look_ahead`, so nothing changes in the match.
    Synchronous on purpose: the look-ahead must never span a frame.
    """
    world = match.world
    worm = match.active_worm
    routes = [Route([], worm.x, worm.y, 0.0)]
    for direction in (-1, 1):
        with world.look_ahead(worm):
            steps: list[tuple[str, float | str]] = []
            start_x = last_sample = worm.x
            jumped = False
            for _ in range(MOVE_MAX_SIM_STEPS):
                if abs(worm.x - start_x) >= MOVE_RANGE:
                    break
                before = worm.x
                world.walk(worm, direction, SIM_DT)
                world._update_worm(worm, SIM_DT)
                if not worm.grounded:
                    break  # never walk off ledges
                blocked = worm.x == before and worm.walk_progress == 0.0
                if blocked:
                    jump = None if jumped or not allow_jumps else _jump_over(world, worm, direction)
                    if jump is None:
                        break
                    run_up_x, kind = jump
                    steps += [("walk", run_up_x), ("face", direction), ("jump", kind.value)]
                    jumped = True
                    last_sample = worm.x
                    routes.append(Route(list(steps), worm.x, worm.y, abs(worm.x - start_x)))
                elif abs(worm.x - last_sample) >= MOVE_SAMPLE:
                    last_sample = worm.x
                    route_steps = [*steps, ("walk", worm.x)]
                    routes.append(Route(route_steps, worm.x, worm.y, abs(worm.x - start_x)))
    return routes


def _jump_over(world: World, worm: Worm, direction: int) -> tuple[float, JumpKind] | None:
    """Find a run-up distance and jump that lands safely beyond the obstacle in front."""
    for run_up in (0, 12, 24):
        for kind in (JumpKind.FORWARD, JumpKind.HIGH):
            saved = dict(vars(worm))
            damage_before = world.dry_damage
            for _ in range(int(run_up / (55 * SIM_DT)) + 2):
                if abs(worm.x - saved["x"]) >= run_up:
                    break
                world.walk(worm, -direction, SIM_DT)
                world._update_worm(worm, SIM_DT)
            run_up_x = worm.x
            worm.facing = direction
            if worm.grounded:
                world.jump(worm, kind)
                for _ in range(int(3 / SIM_DT)):
                    world._update_worm(worm, SIM_DT)
                    if worm.grounded or not worm.alive:
                        break
            progressed = (worm.x - saved["x"]) * direction > 6
            safe = worm.alive and worm.grounded and world.dry_damage == damage_before
            if safe and progressed:
                return run_up_x, kind
            vars(worm).update(saved)
    return None


def plan_move(match: Match, allow_jumps: bool = True) -> Generator[None, None, Route]:
    """Pick the reachable position with the best (coarse) shot, if it is worth the walk."""
    worm = match.active_worm
    routes = explore_routes(match, allow_jumps)
    yield None
    best_route, best_score = routes[0], -math.inf
    for route in routes:
        stand_in = replace(worm, x=route.x, y=route.y)
        estimate = yield from plan_turn(
            match, COARSE_AIMS, COARSE_POWERS, charged_only=True, shooter=stand_in
        )
        score = estimate.score - MOVE_COST * route.distance
        if route.steps:
            score -= MOVE_MIN_GAIN
        if score > best_score:
            best_route, best_score = route, score
    return best_route


class AIController:
    """Drives the active worm of AI teams through the normal (recorded) match commands.

    Per turn: plan a move (optional) -> walk/jump there -> plan the shot -> aim and fire.
    """

    def __init__(
        self,
        match: Match,
        rng: random.Random | None = None,
        noise: float = 0.03,
        use_movement: bool = True,
        use_jumps: bool = True,
    ) -> None:
        self.match = match
        self.rng = rng or match.rng.stream("ai")
        self.noise = noise
        self.use_movement = use_movement
        self.use_jumps = use_jumps
        self.think_steps = DEFAULT_THINK_STEPS
        self.thinking = False
        self._turn = -1
        self._planner: Generator[None, None, object] | None = None
        self._stage = "idle"  # think_move -> move -> think_shot -> shoot -> done
        self._route: list[tuple[str, float | str]] = []
        self._plan: ShotPlan | None = None
        self._delay = 0.0
        self._stuck = 0.0
        self._last_x = 0.0

    def update(self, dt: float) -> None:
        match = self.match
        if match.phase != Phase.AIMING or not match.active_team.is_ai:
            self.thinking = False
            return
        if self._turn != match.turn_number:
            self._start_turn()
        if self._stage == "think_move":
            route = self._think()
            if route is not None:
                assert isinstance(route, Route)
                self._route = list(route.steps)
                self._stage = "move" if self._route else "think_shot"
                if self._stage == "think_shot":
                    self._planner = plan_turn(match)
                self._last_x, self._stuck = match.active_worm.x, 0.0
        elif self._stage == "move":
            self._move(dt)
        elif self._stage == "think_shot":
            plan = self._think()
            if plan is not None:
                assert isinstance(plan, ShotPlan)
                plan.aim = max(AIM_MIN, min(AIM_MAX, plan.aim + self.rng.gauss(0, self.noise)))
                plan.power = max(0.1, min(1.0, plan.power + self.rng.gauss(0, self.noise)))
                self._plan = plan
                self._stage = "shoot"
                self._delay = 0.6
        elif self._stage == "shoot":
            if self._delay > 0:
                self._delay -= dt
            else:
                self._execute(dt)

    def _start_turn(self) -> None:
        match = self.match
        self._turn = match.turn_number
        self._plan = None
        self._route = []
        self.thinking = True
        if self.use_movement and match.turn_timer >= MOVE_MIN_TURN_TIME:
            self._stage = "think_move"
            self._planner = plan_move(match, self.use_jumps)
        else:
            self._stage = "think_shot"
            self._planner = plan_turn(match)

    def _think(self) -> object | None:
        assert self._planner is not None
        for _ in range(self.think_steps):
            try:
                next(self._planner)
            except StopIteration as stop:
                self.thinking = self._stage == "think_move"
                return stop.value
        return None

    def _finish_move(self) -> None:
        self._route = []
        self._stage = "think_shot"
        self._planner = plan_turn(self.match)
        self.thinking = True

    def _move(self, dt: float) -> None:
        match = self.match
        worm = match.active_worm
        if not self._route or match.turn_timer < MOVE_MIN_TURN_TIME / 2:
            self._finish_move()
            return
        action, value = self._route[0]
        if action == "walk":
            target = float(value)
            if abs(worm.x - target) < 1.0:
                self._route.pop(0)
                return
            match.move(1 if target > worm.x else -1, dt)
            if abs(worm.x - self._last_x) < 1e-6:
                self._stuck += dt
                if self._stuck > 0.6:  # blocked unexpectedly: shoot from here
                    self._finish_move()
            else:
                self._stuck, self._last_x = 0.0, worm.x
        elif action == "face":
            match.face(int(value))
            self._route.pop(0)
        elif action == "jump":
            if worm.grounded and worm.state.value not in ("jump", "high_jump", "backflip"):
                if value == "_landed":
                    self._route.pop(0)
                    return
                match.jump(str(value))
                self._route[0] = ("jump", "_landed")
            elif not worm.alive:
                self._finish_move()

    def _execute(self, dt: float) -> None:
        match = self.match
        plan = self._plan
        assert plan is not None
        worm = match.active_worm
        match.select_weapon_key(plan.weapon_key)
        weapon = match.weapon
        if weapon.aim == AimMode.TARGET_POINT and plan.target_x is not None:
            match.fire_at(plan.target_x)
            self._stage = "done"
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
            self._stage = "done"
        elif not match.charging:
            match.start_charge()
        elif match.power >= plan.power:
            match.release_charge()
            self._stage = "done"
