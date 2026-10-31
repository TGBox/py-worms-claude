"""Registries for weapon definitions and behavior building blocks."""

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from src.core.weapons.definitions import WeaponDef

if TYPE_CHECKING:
    from src.core.weapons.behaviors import Behavior

_WEAPONS: dict[str, WeaponDef] = {}
_BEHAVIORS: dict[str, "Behavior"] = {}

B = TypeVar("B")


def register_weapon(definition: WeaponDef, replace: bool = False) -> WeaponDef:
    if definition.key in _WEAPONS and not replace:
        raise ValueError(f"Waffe '{definition.key}' ist bereits registriert")
    if definition.behavior not in _BEHAVIORS:
        raise ValueError(f"Unbekanntes Verhalten '{definition.behavior}' für '{definition.key}'")
    _WEAPONS[definition.key] = definition
    return definition


def unregister_weapon(key: str) -> None:
    _WEAPONS.pop(key, None)


def get_weapon(key: str) -> WeaponDef:
    try:
        return _WEAPONS[key]
    except KeyError:
        raise KeyError(f"Unbekannte Waffe '{key}'") from None


def all_weapons() -> list[WeaponDef]:
    """All weapons in catalog order."""
    return list(_WEAPONS.values())


def register_behavior(name: str) -> Callable[[type[B]], type[B]]:
    """Class decorator: register one shared instance of a behavior under `name`."""

    def decorator(cls: type[B]) -> type[B]:
        _BEHAVIORS[name] = cls()  # type: ignore[assignment]
        return cls

    return decorator


def get_behavior(name: str) -> "Behavior":
    return _BEHAVIORS[name]
