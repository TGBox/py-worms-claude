"""Weapon data model (see ADR-0001)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Category(Enum):
    ARTILLERY = "Artillerie"
    RIFLE = "Gewehre"
    MELEE = "Nahkampf"
    PLACED = "Gelegt"
    AIR = "Luft"
    ANIMAL = "Tiere"
    CRAZY = "Verrückt"
    TOOL = "Werkzeuge"


class AimMode(Enum):
    CHARGED = "charged"  # aim angle + hold to build power
    ANGLE = "angle"  # aim angle, fires instantly
    TARGET_POINT = "target_point"  # click a point on the map
    NONE = "none"  # used immediately (tools, turn modifiers)


class AIKind(Enum):
    SIMULATE = "simulate"  # AI dry-runs the projectiles the behavior would launch
    DIRECT = "direct"  # straight line of fire towards a target
    TARGET_POINT = "target_point"  # AI picks a map position


@dataclass(frozen=True)
class AIHint:
    kind: AIKind
    reserve: bool = False  # only used when nothing else scores well (precious weapons)


@dataclass(frozen=True)
class WeaponDef:
    key: str  # stable identifier, also used in scheme and save files
    name: str  # user-facing (German)
    category: Category
    aim: AimMode
    behavior: str  # key in the behavior registry
    params: dict[str, Any] = field(default_factory=dict, hash=False)
    shots_per_turn: int = 1
    ends_turn: bool = True
    ai: AIHint | None = None  # None = the AI never uses this weapon
    icon: str = ""
    default_ammo: int = -1  # -1 = unlimited; the scheme may override
    default_delay: int = 0

    def param(self, name: str, default: Any = None) -> Any:
        return self.params.get(name, default)
