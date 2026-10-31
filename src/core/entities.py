"""Plain data objects for worms and projectiles."""

import math
from dataclasses import dataclass

from src.settings import WORM_MAX_HP


@dataclass(eq=False)
class Worm:
    name: str
    team_index: int
    x: float
    y: float
    hp: int = WORM_MAX_HP
    vx: float = 0.0
    vy: float = 0.0
    facing: int = 1
    aim: float = 0.5  # radians above the horizon, relative to facing
    grounded: bool = False
    alive: bool = True
    walk_progress: float = 0.0
    damage_taken: int = 0  # accumulated since the counter was last reset

    def aim_vector(self) -> tuple[float, float]:
        return (math.cos(self.aim) * self.facing, -math.sin(self.aim))

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)


@dataclass(eq=False)
class Projectile:
    weapon_key: str
    x: float
    y: float
    vx: float
    vy: float
    explosion_radius: float
    damage: int
    wind_factor: float = 0.0
    fuse: float | None = None  # seconds until detonation, None = impact fuse
    bounce: float | None = None  # restitution on terrain hits, None = explode on impact
    owner: Worm | None = None
    age: float = 0.0
    resting: bool = False
    alive: bool = True
