"""Worms and projectiles: concrete bodies of the simulation."""

import math
from dataclasses import dataclass, field
from enum import Enum

from src.core.constants import WORM_RADIUS
from src.core.physics import Body


class WormState(Enum):
    """Movement state of a worm. Purely presentational states (aiming, hurt flash, victory)
    are derived by the renderer from the match instead."""

    IDLE = "idle"
    WALK = "walk"
    JUMP = "jump"
    HIGH_JUMP = "high_jump"
    BACKFLIP = "backflip"
    FALL = "fall"  # airborne without an own jump (knocked away, walked off a ledge)
    DROWNED = "drowned"
    DEAD = "dead"


AIRBORNE_STATES = frozenset(
    {WormState.JUMP, WormState.HIGH_JUMP, WormState.BACKFLIP, WormState.FALL}
)


class JumpKind(Enum):
    FORWARD = "forward"
    HIGH = "high"
    BACKFLIP = "backflip"


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
    state: WormState = WormState.IDLE
    state_time: float = 0.0  # seconds spent in the current state
    walk_distance: float = 0.0  # total px walked, drives the crawl animation
    walked: bool = False  # walked during the current simulation step
    slide_count: int = 0  # consecutive landings on other worms
    radius: float = field(default=WORM_RADIUS, kw_only=True)

    def aim_vector(self) -> tuple[float, float]:
        return (math.cos(self.aim) * self.facing, -math.sin(self.aim))

    def set_state(self, state: WormState) -> None:
        if state != self.state:
            self.state = state
            self.state_time = 0.0


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
