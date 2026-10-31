"""Data-driven weapons: definitions, behavior registry and the catalog (see ADR-0001)."""

from src.core.weapons import behaviors as _behaviors  # noqa: F401  (registers behaviors)
from src.core.weapons import catalog as _catalog  # noqa: F401  (registers weapons)
from src.core.weapons.behaviors import Behavior, FireContext
from src.core.weapons.definitions import AIHint, AIKind, AimMode, Category, WeaponDef
from src.core.weapons.registry import (
    all_weapons,
    get_behavior,
    get_weapon,
    register_behavior,
    register_weapon,
    unregister_weapon,
)

__all__ = [
    "AIHint",
    "AIKind",
    "AimMode",
    "Behavior",
    "Category",
    "FireContext",
    "WeaponDef",
    "all_weapons",
    "get_behavior",
    "get_weapon",
    "register_behavior",
    "register_weapon",
    "unregister_weapon",
]
