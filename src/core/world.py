"""World simulation: worm movement, projectiles, explosions and damage."""

import ctypes
import math
import random
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.core import native
from src.core.constants import (
    CRAWL_CLIMB,
    CRAWL_SPEED_FACTOR,
    FALL_DAMAGE_PER_SPEED,
    FALL_DAMAGE_SPEED,
    GRAVITY,
    JUMP_BACKFLIP,
    JUMP_FORWARD,
    JUMP_HIGH,
    LANDING_SPEED,
    PROJECTILE_MAX_AGE,
    SLIDE_SPEED,
    WIND_ACCELERATION,
    WORM_BOUNCE,
    WORM_MAX_CLIMB,
    WORM_RADIUS,
    WORM_WALK_SPEED,
)
from src.core.entities import AIRBORNE_STATES, JumpKind, Projectile, Worm, WormState
from src.core.events import Damage, EventBus, Explosion, Splash, WormDied, WormDrowned
from src.core.physics import Body, PhysicsWorld
from src.core.scheme import GameScheme
from src.core.terrain import Terrain


def step_projectile(p: Projectile, world: "World", worms: list[Worm], dt: float) -> str | None:
    """Advance a projectile by dt.

    Returns "explode" or "gone" when the projectile ends, otherwise None; the projectile's
    position is then the impact point. Pure with respect to the world (no carving, no events),
    so the AI uses it for dry runs. Runs in the Rust kernel when it is loaded.
    """
    kernel = native.kernel
    if kernel is not None:
        owner = next((i for i, w in enumerate(worms) if w is p.owner), -1)
        state = native.scratch.fill("single", native.pack_projectile(p, owner))
        flat = [value for worm in worms for value in (worm.x, worm.y)]
        terrain = world.terrain
        code = kernel.wk_step_projectiles(
            terrain.address,
            terrain.width,
            terrain.height,
            state,
            0,
            1,
            world.wind,
            world.wind_acceleration,
            world.gravity,
            dt,
            world.water_level,
            native.scratch.fill("worms", flat),
            len(worms),
        )
        native.unpack_projectile(p, state)
        return native.RESULT_NAMES[code % 4] if code < 4 else None
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
    distance = max(abs(dy), abs(dx))
    steps = int(distance / 2.0) + 1
    sx, sy = dx / steps, dy / steps
    hit_radius_sq = (WORM_RADIUS + 2) * (WORM_RADIUS + 2)
    # Worms the projectile can hit along this frame's path (cheap broad phase).
    targets = []
    if p.bounce is None:
        reach = distance + WORM_RADIUS + 4
        for worm in worms:
            if not worm.alive or (worm is p.owner and p.age < 0.3):
                continue
            if abs(worm.x - p.x) < reach and abs(worm.y - p.y) < reach:
                targets.append(worm)
    is_solid = terrain.is_solid
    x, y = p.x, p.y
    for _ in range(steps):
        nx, ny = x + sx, y + sy
        for worm in targets:
            ax, ay = worm.x - nx, worm.y - ny
            if ax * ax + ay * ay <= hit_radius_sq:
                p.x, p.y = nx, ny
                return "explode"
        if is_solid(nx, ny):
            p.x, p.y = x, y
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
            if math.sqrt(p.vx * p.vx + p.vy * p.vy) < 30 and normal_y < -0.5:
                p.vx = p.vy = 0.0
                p.asleep = True
            return None
        x, y = nx, ny
    p.x, p.y = x, y

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
        self.dry_run = False  # AI look-ahead: no damage, no events
        self.dry_damage = 0

    def all_bodies(self) -> list[Body]:
        return [*self.worms, *self.projectiles]

    def solid_bodies(self) -> list[Body]:
        return self.worms  # type: ignore[return-value]

    @property
    def collision_mode(self) -> str:
        return self.scheme.worms.collision

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
        worm.collides_with_bodies = self.collision_mode != "aus"
        self.worms.append(worm)
        return worm

    def add_projectile(self, projectile: Projectile) -> Projectile:
        self.projectiles.append(projectile)
        return projectile

    # ------------------------------------------------------------- queries
    def worm_collides(self, worm: Worm, x: float, y: float) -> bool:
        kernel = native.kernel
        if kernel is None:
            return self.body_collides(worm, x, y)
        table, count, index = self._table_for(worm)
        terrain = self.terrain
        result = kernel.wk_body_collides(
            terrain.address,
            terrain.width,
            terrain.height,
            x,
            y,
            worm.radius,
            worm.x,
            worm.y,
            table,
            count,
            index,
            1 if worm.collides_with_bodies else 0,
        )
        return result != -1

    # Native kernel: worm table of (x, y, radius, flags) in self.worms order. Inside update()
    # it is built once and patched after each worm moves; elsewhere it is rebuilt per call.
    _table_live = False

    def _fill_worm_table(self) -> ctypes.Array:
        flat: list[float] = []
        for worm in self.worms:
            flags = (1.0 if worm.alive else 0.0) + (2.0 if worm.collides_with_bodies else 0.0)
            flat += (worm.x, worm.y, worm.radius, flags)
        return native.scratch.fill("worm_table", flat)

    def _table_for(self, worm: Worm) -> tuple[ctypes.Array, int, int]:
        table = native.scratch.get("worm_table", 4) if self._table_live else self._fill_worm_table()
        index = next((i for i, w in enumerate(self.worms) if w is worm), -1)
        return table, len(self.worms), index

    def _patch_worm_table(self, index: int) -> None:
        worm = self.worms[index]
        table = native.scratch.get("worm_table", 4 * len(self.worms))
        flags = (1.0 if worm.alive else 0.0) + (2.0 if worm.collides_with_bodies else 0.0)
        table[4 * index : 4 * index + 4] = (worm.x, worm.y, worm.radius, flags)

    def danger_near(self, worm: Worm, radius: float = 90.0) -> bool:
        """A live projectile (ticking or incoming) is close to the worm."""
        for p in self.projectiles:
            if p.owner is worm and p.age < 0.4:
                continue
            if (p.x - worm.x) ** 2 + (p.y - worm.y) ** 2 < radius * radius:
                return True
        return False

    @contextmanager
    def look_ahead(self, worm: Worm) -> Iterator[None]:
        """Try moves on the real worm without side effects; restores it afterwards."""
        saved: dict[str, Any] = dict(vars(worm))
        self.dry_run, self.dry_damage = True, 0
        try:
            yield
        finally:
            vars(worm).update(saved)
            self.dry_run = False

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
    def walk(self, worm: Worm, direction: int, dt: float) -> bool:
        """Walk for dt seconds; returns False when the worm could not move at all."""
        if not worm.alive:
            return False
        worm.facing = direction
        if not worm.grounded:
            return False
        worm.walked = True
        worm.set_state(WormState.WALK)
        speed = WORM_WALK_SPEED
        if self.collision_mode == "ueberkriechen" and self._touching_worm(worm):
            speed *= CRAWL_SPEED_FACTOR
        worm.walk_progress += speed * dt
        kernel = native.kernel
        if kernel is None:
            return self._walk_steps(worm, direction)
        table, count, index = self._table_for(worm)
        state = native.scratch.fill(
            "walk", [worm.x, worm.y, worm.walk_progress, 1.0 if worm.grounded else 0.0]
        )
        out = native.scratch.get("walk_out", 3)
        terrain = self.terrain
        kernel.wk_walk(
            terrain.address,
            terrain.width,
            terrain.height,
            state,
            direction,
            worm.radius,
            WORM_MAX_CLIMB,
            CRAWL_CLIMB,
            1 if self.collision_mode == "ueberkriechen" else 0,
            table,
            count,
            index,
            1 if worm.collides_with_bodies else 0,
            out,
        )
        worm.x, worm.y, worm.walk_progress = state[0], state[1], state[2]
        worm.grounded = state[3] != 0.0
        worm.walk_distance += out[1]
        if out[2]:
            worm.set_state(WormState.FALL)
        return out[0] != 0.0

    def _walk_steps(self, worm: Worm, direction: int) -> bool:
        moved = True
        while worm.walk_progress >= 1.0:
            worm.walk_progress -= 1.0
            if not self._walk_step(worm, direction):
                worm.walk_progress = 0.0
                moved = False
                break
            worm.walk_distance += 1.0
            if not worm.grounded:
                worm.walk_progress = 0.0
                worm.set_state(WormState.FALL)
                break
        return moved

    def _touching_worm(self, worm: Worm) -> bool:
        reach = 2 * WORM_RADIUS + 2
        x, y = worm.x, worm.y
        for other in self.worms:
            near = -reach < other.x - x < reach and -reach < other.y - y < reach
            if near and other is not worm and other.alive:
                return True
        return False

    def _walk_step(self, worm: Worm, direction: int) -> bool:
        nx = worm.x + direction
        if nx < WORM_RADIUS or nx > self.terrain.width - WORM_RADIUS:
            return False
        # The terrain decides how high a step is; another worm never counts as a stair.
        terrain = self.terrain
        climb = next(
            (
                c
                for c in range(WORM_MAX_CLIMB + 1)
                if not terrain.circle_collides(nx, worm.y - c, worm.radius)
            ),
            None,
        )
        if climb is None:
            return False
        blocker = self.blocking_body(worm, nx, worm.y - climb)
        if blocker is None:
            self._commit_step(worm, nx, climb, WORM_MAX_CLIMB)
            return True
        if self.collision_mode != "ueberkriechen":
            return False  # "blockieren": the other worm is a wall
        # Crawl over the other worm, but only if the ground behind it is walkable.
        beyond = blocker.x + direction * (2 * WORM_RADIUS + 2)
        if terrain.circle_collides(beyond, worm.y - WORM_MAX_CLIMB, worm.radius):
            return False
        for crawl in range(climb + 1, CRAWL_CLIMB + 1):
            if not self.worm_collides(worm, nx, worm.y - crawl):
                self._commit_step(worm, nx, crawl, CRAWL_CLIMB)
                return True
        return False

    def _commit_step(self, worm: Worm, nx: float, climb: int, max_drop: int) -> None:
        worm.x = nx
        worm.y -= climb
        for _ in range(max_drop + 1):
            if self.worm_collides(worm, worm.x, worm.y + 1):
                return
            worm.y += 1
        worm.grounded = False  # walked off a ledge

    def jump(self, worm: Worm, kind: JumpKind = JumpKind.FORWARD) -> None:
        if not (worm.alive and worm.grounded):
            return
        vx, vy = {
            JumpKind.FORWARD: JUMP_FORWARD,
            JumpKind.HIGH: JUMP_HIGH,
            JumpKind.BACKFLIP: JUMP_BACKFLIP,
        }[kind]
        strength = self.scheme.worms.jump_strength
        worm.vx = vx * worm.facing * strength
        worm.vy = vy * strength
        worm.grounded = False
        worm.slide_count = 0
        worm.set_state(
            {
                JumpKind.FORWARD: WormState.JUMP,
                JumpKind.HIGH: WormState.HIGH_JUMP,
                JumpKind.BACKFLIP: WormState.BACKFLIP,
            }[kind]
        )

    def _update_worm(self, worm: Worm, dt: float, standing: bool | None = None) -> None:
        """`standing`: precomputed result of the ground check (native batch), if known."""
        worm.state_time += dt
        if worm.grounded:
            if not worm.walked and worm.state == WormState.WALK:
                worm.set_state(WormState.IDLE)
            worm.walked = False
            if standing is None:
                standing = self.worm_collides(worm, worm.x, worm.y + 1)
            if standing:
                return
            worm.grounded = False
        if worm.state not in AIRBORNE_STATES:
            worm.set_state(WormState.FALL)
        worm.vy += self.gravity * dt
        dx, dy = worm.vx * dt, worm.vy * dt
        steps = max(1, math.ceil(max(abs(dx), abs(dy))))
        sx, sy = dx / steps, dy / steps
        kernel = native.kernel
        if kernel is not None:
            state = native.scratch.fill("fly", [worm.x, worm.y])
            hit = native.scratch.get("fly_hit", 2)
            table, count, index = self._table_for(worm)
            terrain = self.terrain
            contact = kernel.wk_fly(
                terrain.address,
                terrain.width,
                terrain.height,
                state,
                sx,
                sy,
                steps,
                worm.radius,
                table,
                count,
                index,
                1 if worm.collides_with_bodies else 0,
                hit,
            )
            worm.x, worm.y = state[0], state[1]
            if contact:
                self._resolve_worm_contact(worm, hit[0], hit[1])
            self._check_out_of_world(worm)
            return
        for _ in range(steps):
            nx, ny = worm.x + sx, worm.y + sy
            if not self.worm_collides(worm, nx, ny):
                worm.x, worm.y = nx, ny
                continue
            self._resolve_worm_contact(worm, nx, ny)
            break
        self._check_out_of_world(worm)

    def _resolve_worm_contact(self, worm: Worm, nx: float, ny: float) -> None:
        other = None
        if self.terrain.circle_collides(nx, ny, worm.radius):
            normal_x, normal_y = self.terrain.normal_at(nx, ny, WORM_RADIUS + 2)
        else:
            other = self.blocking_body(worm, nx, ny)
            dx, dy = (worm.x - other.x, worm.y - other.y) if other else (0.0, -1.0)
            length = math.hypot(dx, dy) or 1.0
            normal_x, normal_y = dx / length, dy / length
        speed = worm.speed
        worms = self.scheme.worms
        if worms.fall_damage and normal_y < -0.55 and speed > FALL_DAMAGE_SPEED:
            factor = FALL_DAMAGE_PER_SPEED * worms.fall_damage_factor
            self.damage_worm(worm, round((speed - FALL_DAMAGE_SPEED) * factor))
        if other is not None and normal_y < -0.3 and worm.slide_count < 3:
            # Landed on another worm: slide off sideways so worms never stack up.
            worm.slide_count += 1
            side = 1 if worm.x > other.x else -1 if worm.x < other.x else worm.facing
            worm.vx = side * SLIDE_SPEED
            worm.vy = -60.0
            return
        if other is not None and normal_y >= -0.3:
            # Side contact with another worm: keep only the tangential part of the motion,
            # so worms glide past each other instead of bouncing (e.g. high jump from contact).
            dot = worm.vx * normal_x + worm.vy * normal_y
            if dot < 0:
                worm.vx -= dot * normal_x
                worm.vy -= dot * normal_y
            return
        on_floor = normal_y < -0.55 or self.worm_collides(worm, worm.x, worm.y + 1)
        if on_floor and speed < LANDING_SPEED:
            worm.vx = worm.vy = 0.0
            worm.grounded = True
            worm.slide_count = 0
            worm.set_state(WormState.IDLE)
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
            worm.set_state(WormState.DROWNED)
            if not self.dry_run:
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
        if self.dry_run:
            self.dry_damage += amount
            return
        worm.hp -= amount
        worm.damage_taken += amount
        self.bus.emit(Damage(worm, amount, worm.x, worm.y - 20))

    def kill_worm(self, worm: Worm) -> None:
        """Remove a worm whose health has run out (with a small blast like the original)."""
        worm.alive = False
        worm.hp = 0
        worm.set_state(WormState.DEAD)
        self.bus.emit(WormDied(worm, worm.x, worm.y))
        self.explode(worm.x, worm.y, 18, 8)

    # -------------------------------------------------------------- update
    def _finish_projectile(self, p: Projectile, result: str | None) -> None:
        if result == "explode":
            p.alive = False
            self.explode(p.x, p.y, p.explosion_radius, p.damage)
        elif result == "gone":
            p.alive = False
            if p.y > self.water_level:
                self.bus.emit(Splash(p.x, self.water_level))

    def _step_projectiles_native(self, live_worms: list[Worm], dt: float) -> None:
        """Same order and semantics as the Python loop, but one kernel call per explosion."""
        kernel = native.kernel
        assert kernel is not None
        terrain = self.terrain
        start = 0
        while start < len(self.projectiles):
            batch = self.projectiles  # explosions may append projectiles (clusters): re-pack
            owners = {id(w): i for i, w in enumerate(live_worms)}
            flat: list[float] = []
            for p in batch[start:]:
                flat += native.pack_projectile(p, owners.get(id(p.owner), -1))
            states = native.scratch.fill("projectiles", flat)
            worms = native.scratch.fill(
                "worms", [value for w in live_worms for value in (w.x, w.y)]
            )
            count = len(batch) - start
            code = kernel.wk_step_projectiles(
                terrain.address,
                terrain.width,
                terrain.height,
                states,
                0,
                count,
                self.wind,
                self.wind_acceleration,
                self.gravity,
                dt,
                self.water_level,
                worms,
                len(live_worms),
            )
            ended, result = divmod(code, 4)
            stepped = min(ended + 1, count)
            for offset in range(stepped):
                native.unpack_projectile(batch[start + offset], states, offset * native.P_LEN)
            if ended >= count:
                return
            self._finish_projectile(batch[start + ended], native.RESULT_NAMES[result])
            start += ended + 1

    def update(self, dt: float) -> None:
        live_worms = [w for w in self.worms if w.alive]
        if native.kernel is not None:
            self._step_projectiles_native(live_worms, dt)
        else:
            for p in self.projectiles:
                self._finish_projectile(p, step_projectile(p, self, live_worms, dt))
        self.projectiles = [p for p in self.projectiles if p.alive]
        if native.kernel is None:
            for worm in self.worms:
                if worm.alive:
                    self._update_worm(worm, dt)
            return
        kernel = native.kernel
        table = self._fill_worm_table()
        count = len(self.worms)
        mask = native.scratch.get("ground_mask", count)
        terrain = self.terrain
        kernel.wk_ground_mask(terrain.address, terrain.width, terrain.height, table, count, mask)
        self._table_live = True
        moved = False  # once a worm moved, later ground checks must be recomputed
        try:
            for index, worm in enumerate(self.worms):
                if not worm.alive:
                    continue
                before = (worm.x, worm.y, worm.alive)
                self._update_worm(worm, dt, None if moved else mask[index] == 1.0)
                if (worm.x, worm.y, worm.alive) != before:
                    moved = True
                    self._patch_worm_table(index)
        finally:
            self._table_live = False
