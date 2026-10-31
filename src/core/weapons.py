"""Weapon definitions."""

from dataclasses import dataclass
from enum import Enum


class FireMode(Enum):
    CHARGED = "charged"  # hold to build power, release to launch a projectile
    DIRECT = "direct"  # instant hitscan along the aim line
    TARGETED = "targeted"  # pick a target position on the map


@dataclass(frozen=True)
class Weapon:
    key: str
    name: str  # user-facing (German)
    mode: FireMode
    explosion_radius: float
    damage: int
    wind_factor: float = 0.0
    fuse: float | None = None
    bounce: float | None = None
    ammo: int = -1  # -1 = unlimited
    range: float = 0.0
    missiles: int = 0


BAZOOKA = Weapon("bazooka", "Bazooka", FireMode.CHARGED, 40, 50, wind_factor=1.0)
GRENADE = Weapon("grenade", "Granate", FireMode.CHARGED, 42, 50, fuse=3.0, bounce=0.45)
SHOTGUN = Weapon("shotgun", "Schrotflinte", FireMode.DIRECT, 14, 25, range=700)
AIRSTRIKE = Weapon(
    "airstrike", "Luftschlag", FireMode.TARGETED, 30, 30, wind_factor=0.4, ammo=1, missiles=5
)

WEAPONS: tuple[Weapon, ...] = (BAZOOKA, GRENADE, SHOTGUN, AIRSTRIKE)
