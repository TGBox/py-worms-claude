"""The weapon catalog. Adding a weapon usually means adding one entry here plus a test."""

from src.core.weapons.definitions import AIHint, AIKind, AimMode, Category, WeaponDef
from src.core.weapons.registry import register_weapon

CATALOG: tuple[WeaponDef, ...] = (
    WeaponDef(
        key="bazooka",
        name="Bazooka",
        category=Category.ARTILLERY,
        aim=AimMode.CHARGED,
        behavior="ballistic",
        params={"radius": 40, "damage": 50, "wind": 1.0},
        ai=AIHint(AIKind.SIMULATE),
        icon="bazooka",
    ),
    WeaponDef(
        key="grenade",
        name="Granate",
        category=Category.ARTILLERY,
        aim=AimMode.CHARGED,
        behavior="ballistic",
        params={"radius": 42, "damage": 50, "fuse": 3.0, "bounce": 0.45},
        ai=AIHint(AIKind.SIMULATE),
        icon="grenade",
    ),
    WeaponDef(
        key="shotgun",
        name="Schrotflinte",
        category=Category.RIFLE,
        aim=AimMode.ANGLE,
        behavior="hitscan",
        params={"range": 700, "radius": 14, "damage": 25},
        ai=AIHint(AIKind.DIRECT),
        icon="shotgun",
    ),
    WeaponDef(
        key="airstrike",
        name="Luftschlag",
        category=Category.AIR,
        aim=AimMode.TARGET_POINT,
        behavior="airstrike",
        params={"missiles": 5, "spacing": 26, "radius": 30, "damage": 30, "wind": 0.4},
        ai=AIHint(AIKind.TARGET_POINT, reserve=True),
        icon="airstrike",
        default_ammo=1,
    ),
)

for _definition in CATALOG:
    register_weapon(_definition, replace=True)
