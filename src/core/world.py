"""World simulation: worm movement, projectiles, explosions and damage."""

import math
import random
from dataclasses import dataclass

from src.core.entities import Projectile, Worm
from src.core.terrain import Terrain
from src.core.weapons import Weapon
from src.settings import (
    FALL_DAMAGE_FACTOR,
    FALL_DAMAGE_SPEED,
    GRAVITY,
    MAX_SHOT_SPEED,
    WATER_LEVEL,
    WIND_MAX,
    WORM_BOUNCE,
    WORM_JUMP_VELOCITY,
    WORM_MAX_CLIMB,
    WORM_RADIUS,
    WORM_WALK_SPEED,
)

PROJECTILE_MAX_AGE = 20.0
LANDING_SPEED = 170.0


@dataclass
class Event:
    """Something the presentation layer may want to visualise."""

    kind: str  # explosion | damage | drown | splash | tracer | death
    x: float
    y: float
    radius: float = 0.0
    value: int = 0
    x2: float = 0.0
    y2: float = 0.0


def step_projectile(
    p: Projectile,
    terrain: Terrain,
    worms: list[Worm],
    wind: float,
    dt: float,
    water_level: float,
) -> str | None:
    """Advance a projectile by dt.

    Returns "explode" or "gone" when the projectile ends, otherwise None. The position of
    the projectile is the impact point. Used by the world and by the AI's dry-run simulation.
    """
    p.age += dt
    if p.fuse is not None:
        p.fuse -= dt
        if p.fuse <= 0:
            return "explode"
    if p.age > PROJECTILE_MAX_AGE:
        return "explode"
    if p.resting:
        if terrain.is_solid(p.x, p.y + 3):
            return None
        p.resting = False

    p.vx += wind * WIND_MAX * p.wind_factor * dt
    p.vy += GRAVITY * dt
    dx, dy = p.vx * dt, p.vy * dt
    steps = max(1, math.ceil(max(abs(dx), abs(dy)) / 2.0))
    sx, sy = dx / steps, dy / steps
    hit_radius_sq = (WORM_RADIUS + 2) ** 2
    for _ in range(steps):
        nx, ny = p.x + sx, p.y + sy
        if p.bounce is None:
            for worm in worms:
                if not worm.alive or (worm is p.owner and p.age < 0.3):
                    continue
                if (worm.x - nx) ** 2 + (worm.y - ny) ** 2 <= hit_radius_sq:
                    p.x, p.y = nx, ny
                    return "explode"
        if terrain.is_solid(nx, ny):
            if p.bounce is None:
                p.x, p.y = nx, ny
                return "explode"
            normal_x, normal_y = terrain.normal_at(nx, ny, 4)
            dot = p.vx * normal_x + p.vy * normal_y
            if dot < 0:
                p.vx -= 2 * dot * normal_x
                p.vy -= 2 * dot * normal_y
            p.vx *= p.bounce
            p.vy *= p.bounce
            if math.hypot(p.vx, p.vy) < 30 and normal_y < -0.5:
                p.vx = p.vy = 0.0
                p.resting = True
            return None
        p.x, p.y = nx, ny

    if p.y > water_level or p.x < -300 or p.x > terrain.width + 300:
        return "gone"
    return None


class World:
    def __init__(self, terrain: Terrain, water_level: float = WATER_LEVEL) -> None:
        self.terrain = terrain
        self.water_level = water_level
        self.worms: list[Worm] = []
        self.projectiles: list[Projectile] = []
        self.events: list[Event] = []
        self.wind = 0.0

    # ----------------------------------------------------------------- setup
    def spawn_positions(self, count: int, rng: random.Random) -> list[tuple[float, float]]:
        """Random standing spots on solid ground above the water, spread apart."""
        positions: list[tuple[float, float]] = []
        margin = 40
        for attempt in range(4000):
            min_gap = 80 if attempt < 2000 else 25
            x = rng.uniform(margin, self.terrain.width - margin)
            start = rng.choice([0, 0, rng.randint(0, int(self.water_level))])
            top = self.terrain.surface_y(x, start)
            if top is None or top > self.water_level - 30 or top < WORM_RADIUS + 4:
                continue
            y = top - WORM_RADIUS - 1
            if self.worm_collides(x, y):
                continue
            if all(abs(x - px) >= min_gap or abs(y - py) > 40 for px, py in positions):
                positions.append((x, y))
                if len(positions) == count:
                    return positions
        raise RuntimeError("Kein Platz für alle Würmer gefunden")

    def add_worm(self, worm: Worm) -> Worm:
        self.worms.append(worm)
        return worm

    # ------------------------------------------------------------- queries
    def worm_collides(self, x: float, y: float) -> bool:
        return self.terrain.circle_collides(x, y, WORM_RADIUS)

    def is_settled(self) -> bool:
        if self.projectiles:
            return False
        return all(w.grounded or not w.alive for w in self.worms)

    # ------------------------------------------------------------ movement
    def walk(self, worm: Worm, direction: int, dt: float) -> None:
        if not worm.alive:
            return
        worm.facing = direction
        if not worm.grounded:
            return
        worm.walk_progress += WORM_WALK_SPEED * dt
        while worm.walk_progress >= 1.0:
            worm.walk_progress -= 1.0
            if not self._walk_step(worm, direction) or not worm.grounded:
                worm.walk_progress = 0.0
                break

    def _walk_step(self, worm: Worm, direction: int) -> bool:
        nx = worm.x + direction
        if nx < WORM_RADIUS or nx > self.terrain.width - WORM_RADIUS:
            return False
        for climb in range(WORM_MAX_CLIMB + 1):
            if self.worm_collides(nx, worm.y - climb):
                continue
            worm.x = nx
            worm.y -= climb
            for _ in range(WORM_MAX_CLIMB + 1):
                if self.worm_collides(worm.x, worm.y + 1):
                    break
                worm.y += 1
            else:
                worm.grounded = False  # walked off a ledge
            return True
        return False

    def jump(self, worm: Worm) -> None:
        if worm.alive and worm.grounded:
            worm.vx = WORM_JUMP_VELOCITY[0] * worm.facing
            worm.vy = WORM_JUMP_VELOCITY[1]
            worm.grounded = False

    def _update_worm(self, worm: Worm, dt: float) -> None:
        if worm.grounded:
            if self.worm_collides(worm.x, worm.y + 1):
                return
            worm.grounded = False
        worm.vy += GRAVITY * dt
        dx, dy = worm.vx * dt, worm.vy * dt
        steps = max(1, math.ceil(max(abs(dx), abs(dy))))
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            nx, ny = worm.x + sx, worm.y + sy
            if not self.worm_collides(nx, ny):
                worm.x, worm.y = nx, ny
                continue
            self._resolve_worm_contact(worm, nx, ny)
            break
        self._check_out_of_world(worm)

    def _resolve_worm_contact(self, worm: Worm, nx: float, ny: float) -> None:
        normal_x, normal_y = self.terrain.normal_at(nx, ny, WORM_RADIUS + 2)
        speed = worm.speed
        if normal_y < -0.55 and speed > FALL_DAMAGE_SPEED:
            self.damage_worm(worm, round((speed - FALL_DAMAGE_SPEED) * FALL_DAMAGE_FACTOR))
        on_floor = normal_y < -0.55 or self.worm_collides(worm.x, worm.y + 1)
        if on_floor and speed < LANDING_SPEED:
            worm.vx = worm.vy = 0.0
            worm.grounded = True
            return
        dot = worm.vx * normal_x + worm.vy * normal_y
        if dot < 0:
            worm.vx -= 2 * dot * normal_x
            worm.vy -= 2 * dot * normal_y
        worm.vx *= WORM_BOUNCE
        worm.vy *= WORM_BOUNCE

    def _check_out_of_world(self, worm: Worm) -> None:
        out_sideways = worm.x < -60 or worm.x > self.terrain.width + 60
        if worm.y - WORM_RADIUS > self.water_level or out_sideways:
            worm.hp = 0
            worm.alive = False
            worm.grounded = False
            self.events.append(Event("drown", worm.x, min(worm.y, self.water_level)))

    # ------------------------------------------------------------- weapons
    def fire_projectile(self, worm: Worm, weapon: Weapon, power: float) -> Projectile:
        dx, dy = worm.aim_vector()
        speed = max(0.05, min(1.0, power)) * MAX_SHOT_SPEED
        projectile = Projectile(
            weapon_key=weapon.key,
            x=worm.x + dx * (WORM_RADIUS + 4),
            y=worm.y + dy * (WORM_RADIUS + 4),
            vx=dx * speed,
            vy=dy * speed,
            explosion_radius=weapon.explosion_radius,
            damage=weapon.damage,
            wind_factor=weapon.wind_factor,
            fuse=weapon.fuse,
            bounce=weapon.bounce,
            owner=worm,
        )
        self.projectiles.append(projectile)
        return projectile

    def fire_hitscan(self, worm: Worm, weapon: Weapon) -> tuple[float, float]:
        dx, dy = worm.aim_vector()
        x = worm.x + dx * (WORM_RADIUS + 2)
        y = worm.y + dy * (WORM_RADIUS + 2)
        start = (x, y)
        hit = False
        for _ in range(int(weapon.range / 2)):
            x += dx * 2
            y += dy * 2
            if self.terrain.is_solid(x, y):
                hit = True
                break
            if any(
                w.alive and w is not worm and (w.x - x) ** 2 + (w.y - y) ** 2 <= WORM_RADIUS**2
                for w in self.worms
            ):
                hit = True
                break
        self.events.append(Event("tracer", start[0], start[1], x2=x, y2=y))
        if hit:
            self.explode(x, y, weapon.explosion_radius, weapon.damage)
        return (x, y)

    def launch_airstrike(self, target_x: float, weapon: Weapon, owner: Worm) -> None:
        direction = 1 if target_x >= owner.x else -1
        for i in range(weapon.missiles):
            offset = (i - (weapon.missiles - 1) / 2) * 26
            self.projectiles.append(
                Projectile(
                    weapon_key=weapon.key,
                    x=target_x + offset - direction * 60,
                    y=-60 - i * 18,
                    vx=direction * 90,
                    vy=220,
                    explosion_radius=weapon.explosion_radius,
                    damage=weapon.damage,
                    wind_factor=weapon.wind_factor,
                    owner=owner,
                )
            )

    def explode(self, x: float, y: float, radius: float, damage: int) -> None:
        self.terrain.carve_circle(x, y, radius)
        self.events.append(Event("explosion", x, y, radius=radius))
        reach = radius + WORM_RADIUS
        for worm in self.worms:
            if not worm.alive:
                continue
            dx, dy = worm.x - x, worm.y - y
            distance = math.hypot(dx, dy)
            if distance >= reach:
                continue
            factor = min(1.0, (reach - distance) / radius)
            self.damage_worm(worm, max(1, round(damage * factor)))
            if distance < 1e-6:
                dx, dy, distance = 0.0, -1.0, 1.0
            strength = 420 * factor
            worm.vx += dx / distance * strength
            worm.vy += dy / distance * strength - 140 * factor
            worm.grounded = False
        for p in self.projectiles:
            if (p.x - x) ** 2 + (p.y - y) ** 2 < reach**2:
                p.resting = False

    def damage_worm(self, worm: Worm, amount: int) -> None:
        if amount <= 0 or not worm.alive:
            return
        worm.hp -= amount
        worm.damage_taken += amount
        self.events.append(Event("damage", worm.x, worm.y - 20, value=amount))

    def kill_worm(self, worm: Worm) -> None:
        """Remove a worm whose health has run out (with a small blast like the original)."""
        worm.alive = False
        worm.hp = 0
        self.events.append(Event("death", worm.x, worm.y))
        self.explode(worm.x, worm.y, 18, 8)

    # -------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        live_worms = [w for w in self.worms if w.alive]
        for p in self.projectiles:
            result = step_projectile(p, self.terrain, live_worms, self.wind, dt, self.water_level)
            if result == "explode":
                p.alive = False
                self.explode(p.x, p.y, p.explosion_radius, p.damage)
            elif result == "gone":
                p.alive = False
                if p.y > self.water_level:
                    self.events.append(Event("splash", p.x, self.water_level))
        self.projectiles = [p for p in self.projectiles if p.alive]
        for worm in self.worms:
            if worm.alive:
                self._update_worm(worm, dt)
