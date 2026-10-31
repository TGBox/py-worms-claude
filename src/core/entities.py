"""Worms and projectiles: concrete bodies of the simulation."""

import math
from dataclasses import dataclass, field

from src.core.constants import WORM_RADIUS
from src.core.physics import Body


@dataclass(eq=False)
class Worm(Body):
    name: str
    team_index: int
    hp: int = 100
    facing: int = 1
    aim: float = 0.5  # radians above the horizon, relative to facing
    grounded: bool = False
    walk_progress: float = 0.0
    damage_taken: int = 0  # accumulated since the counter was last reset
    radius: float = field(default=WORM_RADIUS, kw_only=True)

    def aim_vector(self) -> tuple[float, float]:
        return (math.cos(self.aim) * self.facing, -math.sin(self.aim))


@dataclass(eq=False)
class Projectile(Body):
    weapon_key: str
    explosion_radius: float = 0.0
    damage: int = 0
    wind_factor: float = 0.0
    fuse: float | None = None  # seconds until detonation, None = impact fuse
    bounce: float | None = None  # restitution on terrain hits, None = explode on impact
    owner: Worm | None = None
    age: float = 0.0

    @property
    def resting(self) -> bool:
        return self.asleep
