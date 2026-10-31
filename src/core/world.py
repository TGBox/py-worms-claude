"""World simulation: worm movement, projectiles, explosions and damage."""

import math
import random

from src.core.constants import (
    FALL_DAMAGE_PER_SPEED,
    FALL_DAMAGE_SPEED,
    GRAVITY,
    LANDING_SPEED,
    PROJECTILE_MAX_AGE,
    WIND_ACCELERATION,
    WORM_BOUNCE,
    WORM_JUMP_VELOCITY,
    WORM_MAX_CLIMB,
    WORM_RADIUS,
    WORM_WALK_SPEED,
)
from src.core.entities import Projectile, Worm
from src.core.events import Damage, EventBus, Explosion, Splash, WormDied, WormDrowned
from src.core.physics import Body, PhysicsWorld
from src.core.scheme import GameScheme
from src.core.terrain import Terrain


def step_projectile(p: Projectile, world: "World", worms: list[Worm], dt: float) -> str | None:
    """Advance a projectile by dt.

    Returns "explode" or "gone" when the projectile ends, otherwise None; the projectile's
    position is then the impact point. Pure with respect to the world (no carving, no events),
    so the AI uses it for dry runs.
    """
    p.age += dt
    if p.fuse is not None:
        p.fuse -= dt
        if p.fuse <= 0:
            return "explode"
    if p.age > PROJECTILE_MAX_AGE:
        return "explode"
    terrain = world.terrain
    if p.asleep:
        if terrain.is_solid(p.x, p.y + 3):
            return None
        p.asleep = False

    p.vx += world.wind * world.wind_acceleration * p.wind_factor * dt
    p.vy += world.gravity * dt
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
                p.asleep = True
            return None
        p.x, p.y = nx, ny

    if p.y > world.water_level or p.x < -300 or p.x > terrain.width + 300:
        return "gone"
    return None


class World(PhysicsWorld):
    def __init__(self, terrain: Terrain, scheme: GameScheme | None = None) -> None:
        self.scheme = scheme or GameScheme()
        super().__init__(terrain, GRAVITY * self.scheme.environment.gravity)
        self.water_level = float(self.scheme.terrain.water_level)
        self.wind_acceleration = WIND_ACCELERATION * self.scheme.environment.wind_max
        self.worms: list[Worm] = []
        self.projectiles: list[Projectile] = []
        self.bus = EventBus()
        self.wind = 0.0

    def all_bodies(self) -> list[Body]:
        return [*self.worms, *self.projectiles]

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
            if self.terrain.circle_collides(x, y, WORM_RADIUS):
                continue
            if all(abs(x - px) >= min_gap or abs(y - py) > 40 for px, py in positions):
                positions.append((x, y))
                if len(positions) == count:
                    return positions
        raise RuntimeError("Kein Platz für alle Würmer gefunden")

    def add_worm(self, worm: Worm) -> Worm:
        self.worms.append(worm)
        return worm

    def add_projectile(self, projectile: Projectile) -> Projectile:
        self.projectiles.append(projectile)
        return projectile

    # ------------------------------------------------------------- queries
    def worm_collides(self, worm: Worm, x: float, y: float) -> bool:
        return self.body_collides(worm, x, y)

    def is_settled(self) -> bool:
        if self.projectiles:
            return False
        return all(w.grounded or not w.alive for w in self.worms)

    def trace_line(
        self,
        start: tuple[float, float],
        direction: tuple[float, float],
        max_range: float,
        ignore: Worm | None = None,
    ) -> tuple[float, float, bool]:
        """March a ray until it hits terrain or a worm; returns (x, y, hit)."""
        x, y = start
        dx, dy = direction
        for _ in range(int(max_range / 2)):
            x += dx * 2
            y += dy * 2
            if self.terrain.is_solid(x, y):
                return (x, y, True)
            for w in self.worms:
                close = (w.x - x) ** 2 + (w.y - y) ** 2 <= WORM_RADIUS**2
                if close and w.alive and w is not ignore:
                    return (x, y, True)
        return (x, y, False)

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
            if self.worm_collides(worm, nx, worm.y - climb):
                continue
            worm.x = nx
            worm.y -= climb
            for _ in range(WORM_MAX_CLIMB + 1):
                if self.worm_collides(worm, worm.x, worm.y + 1):
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
            if self.worm_collides(worm, worm.x, worm.y + 1):
                return
            worm.grounded = False
        worm.vy += self.gravity * dt
        dx, dy = worm.vx * dt, worm.vy * dt
        steps = max(1, math.ceil(max(abs(dx), abs(dy))))
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            nx, ny = worm.x + sx, worm.y + sy
            if not self.worm_collides(worm, nx, ny):
                worm.x, worm.y = nx, ny
                continue
            self._resolve_worm_contact(worm, nx, ny)
            break
        self._check_out_of_world(worm)

    def _resolve_worm_contact(self, worm: Worm, nx: float, ny: float) -> None:
        normal_x, normal_y = self.terrain.normal_at(nx, ny, WORM_RADIUS + 2)
        speed = worm.speed
        worms = self.scheme.worms
        if worms.fall_damage and normal_y < -0.55 and speed > FALL_DAMAGE_SPEED:
            factor = FALL_DAMAGE_PER_SPEED * worms.fall_damage_factor
            self.damage_worm(worm, round((speed - FALL_DAMAGE_SPEED) * factor))
        on_floor = normal_y < -0.55 or self.worm_collides(worm, worm.x, worm.y + 1)
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
            self.bus.emit(WormDrowned(worm, worm.x, min(worm.y, self.water_level)))

    # ------------------------------------------------------------ explosions
    def explode(self, x: float, y: float, radius: float, damage: int) -> None:
        self.terrain.carve_circle(x, y, radius)
        self.bus.emit(Explosion(x, y, radius, damage))
        self.rebuild_grid()
        reach = radius + WORM_RADIUS
        for body in self.bodies_in_radius(x, y, radius):
            body.wake()
            if not isinstance(body, Worm):
                continue
            dx, dy = body.x - x, body.y - y
            distance = math.hypot(dx, dy)
            if distance >= reach:
                continue
            factor = min(1.0, (reach - distance) / radius)
            self.damage_worm(body, max(1, round(damage * factor)))
            if distance < 1e-6:
                dx, dy, distance = 0.0, -1.0, 1.0
            strength = 420 * factor / body.mass
            body.vx += dx / distance * strength
            body.vy += dy / distance * strength - 140 * factor
            body.grounded = False

    def damage_worm(self, worm: Worm, amount: int) -> None:
        if amount <= 0 or not worm.alive:
            return
        worm.hp -= amount
        worm.damage_taken += amount
        self.bus.emit(Damage(worm, amount, worm.x, worm.y - 20))

    def kill_worm(self, worm: Worm) -> None:
        """Remove a worm whose health has run out (with a small blast like the original)."""
        worm.alive = False
        worm.hp = 0
        self.bus.emit(WormDied(worm, worm.x, worm.y))
        self.explode(worm.x, worm.y, 18, 8)

    # -------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        live_worms = [w for w in self.worms if w.alive]
        for p in self.projectiles:
            result = step_projectile(p, self, live_worms, dt)
            if result == "explode":
                p.alive = False
                self.explode(p.x, p.y, p.explosion_radius, p.damage)
            elif result == "gone":
                p.alive = False
                if p.y > self.water_level:
                    self.bus.emit(Splash(p.x, self.water_level))
        self.projectiles = [p for p in self.projectiles if p.alive]
        for worm in self.worms:
            if worm.alive:
                self._update_worm(worm, dt)
