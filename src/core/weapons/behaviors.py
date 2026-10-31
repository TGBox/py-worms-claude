"""Behavior building blocks. A weapon = definition data + one behavior from this registry."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.constants import MAX_SHOT_SPEED, WORM_RADIUS
from src.core.entities import Projectile, Worm
from src.core.events import Tracer
from src.core.weapons.definitions import WeaponDef
from src.core.weapons.registry import register_behavior

if TYPE_CHECKING:
    from src.core.world import World


@dataclass
class FireContext:
    world: "World"
    shooter: Worm
    weapon: WeaponDef
    facing: int
    aim: float
    power: float = 1.0  # charge 0..1 for CHARGED weapons
    target_x: float | None = None
    strength: float = 1.0  # damage multiplier from the scheme

    @classmethod
    def for_worm(
        cls,
        world: "World",
        worm: Worm,
        weapon: WeaponDef,
        power: float = 1.0,
        target_x: float | None = None,
        strength: float = 1.0,
    ) -> "FireContext":
        return cls(world, worm, weapon, worm.facing, worm.aim, power, target_x, strength)

    def direction(self) -> tuple[float, float]:
        return (math.cos(self.aim) * self.facing, -math.sin(self.aim))

    def damage(self, base: float) -> int:
        return max(0, round(base * self.strength))


class Behavior:
    def fire(self, ctx: FireContext) -> None:
        raise NotImplementedError

    def preview(self, ctx: FireContext) -> list[Projectile]:
        """Projectiles `fire` would launch, without adding them (used by the AI)."""
        return []


@register_behavior("ballistic")
class Ballistic(Behavior):
    """A single projectile thrown along the aim line; impact or fuse detonation."""

    def preview(self, ctx: FireContext) -> list[Projectile]:
        w = ctx.weapon
        dx, dy = ctx.direction()
        speed = max(0.05, min(1.0, ctx.power)) * MAX_SHOT_SPEED
        offset = WORM_RADIUS + 4
        return [
            Projectile(
                w.key,
                x=ctx.shooter.x + dx * offset,
                y=ctx.shooter.y + dy * offset,
                vx=dx * speed,
                vy=dy * speed,
                explosion_radius=w.param("radius", 40),
                damage=ctx.damage(w.param("damage", 50)),
                wind_factor=w.param("wind", 0.0),
                fuse=w.param("fuse"),
                bounce=w.param("bounce"),
                owner=ctx.shooter,
            )
        ]

    def fire(self, ctx: FireContext) -> None:
        for projectile in self.preview(ctx):
            ctx.world.add_projectile(projectile)


@register_behavior("hitscan")
class Hitscan(Behavior):
    """Instant shot along the aim line with a small explosion at the hit point."""

    def fire(self, ctx: FireContext) -> None:
        w = ctx.weapon
        dx, dy = ctx.direction()
        start = (ctx.shooter.x + dx * (WORM_RADIUS + 2), ctx.shooter.y + dy * (WORM_RADIUS + 2))
        x, y, hit = ctx.world.trace_line(start, (dx, dy), w.param("range", 700), ctx.shooter)
        ctx.world.bus.emit(Tracer(start[0], start[1], x, y))
        if hit:
            ctx.world.explode(x, y, w.param("radius", 14), ctx.damage(w.param("damage", 25)))


@register_behavior("airstrike")
class Airstrike(Behavior):
    """A row of missiles dropped from above onto a chosen x position."""

    def preview(self, ctx: FireContext) -> list[Projectile]:
        w = ctx.weapon
        target_x = ctx.target_x if ctx.target_x is not None else ctx.shooter.x
        direction = 1 if target_x >= ctx.shooter.x else -1
        count = w.param("missiles", 5)
        spacing = w.param("spacing", 26)
        missiles = []
        for i in range(count):
            offset = (i - (count - 1) / 2) * spacing
            missiles.append(
                Projectile(
                    w.key,
                    x=target_x + offset - direction * 60,
                    y=-60 - i * 18,
                    vx=direction * 90,
                    vy=220,
                    explosion_radius=w.param("radius", 30),
                    damage=ctx.damage(w.param("damage", 30)),
                    wind_factor=w.param("wind", 0.0),
                    owner=ctx.shooter,
                )
            )
        return missiles

    def fire(self, ctx: FireContext) -> None:
        for projectile in self.preview(ctx):
            ctx.world.add_projectile(projectile)
