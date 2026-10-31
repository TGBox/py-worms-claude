"""Game scheme: every option a player can tune for a battle, stored as versioned JSON.

Fields carry metadata (label, range, choices) so that the scheme editor can be generated from
the dataclasses. Unknown keys in files are ignored and missing keys fall back to defaults, which
keeps old and newer files loadable.
"""

import copy
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.persistence import assets_dir, load_json, migrate, save_json, user_dir

SCHEME_VERSION = 1
SCHEME_KIND = "scheme"


def option(default: Any, label: str, **meta: Any) -> Any:
    """Dataclass field with editor metadata (label, min, max, step, choices)."""
    return field(default=default, metadata={"label": label, **meta})


@dataclass
class TurnOptions:
    turn_time: float = option(45.0, "Zugzeit (s)", min=5, max=180, step=5)
    retreat_time: float = option(3.0, "Rückzugszeit (s)", min=0, max=10, step=0.5)


@dataclass
class WormOptions:
    count: int = option(3, "Würmer pro Team", min=1, max=8, step=1)
    hp: int = option(100, "Gesundheit", min=1, max=400, step=10)
    fall_damage: bool = option(True, "Fallschaden")
    fall_damage_factor: float = option(1.0, "Fallschaden-Faktor", min=0.0, max=3.0, step=0.25)


@dataclass
class TerrainOptions:
    water_level: int = option(930, "Wasserspiegel (px)", min=600, max=990, step=10)


@dataclass
class EnvironmentOptions:
    wind_max: float = option(1.0, "Maximaler Wind", min=0.0, max=2.0, step=0.1)
    gravity: float = option(1.0, "Schwerkraft", min=0.25, max=2.0, step=0.05)


@dataclass
class WeaponOptions:
    ammo: int = option(-1, "Munition (-1 = unbegrenzt)", min=-1, max=9, step=1)
    delay: int = option(0, "Verfügbar ab Runde", min=0, max=20, step=1)
    power: float = option(1.0, "Stärke", min=0.25, max=3.0, step=0.25)


GROUPS: dict[str, type] = {
    "turn": TurnOptions,
    "worms": WormOptions,
    "terrain": TerrainOptions,
    "environment": EnvironmentOptions,
}


@dataclass
class GameScheme:
    name: str = "Standard"
    turn: TurnOptions = field(default_factory=TurnOptions)
    worms: WormOptions = field(default_factory=WormOptions)
    terrain: TerrainOptions = field(default_factory=TerrainOptions)
    environment: EnvironmentOptions = field(default_factory=EnvironmentOptions)
    weapons: dict[str, WeaponOptions] = field(default_factory=dict)

    def weapon(self, key: str) -> WeaponOptions:
        """Options for one weapon; falls back to the weapon's catalog defaults."""
        if key not in self.weapons:
            from src.core.weapons import get_weapon

            definition = get_weapon(key)
            self.weapons[key] = WeaponOptions(
                ammo=definition.default_ammo, delay=definition.default_delay
            )
        return self.weapons[key]

    def copy(self) -> "GameScheme":
        return copy.deepcopy(self)

    # -------------------------------------------------------------- serialization
    def to_dict(self) -> dict[str, Any]:
        from src.core.weapons import all_weapons

        data: dict[str, Any] = {"version": SCHEME_VERSION, "name": self.name}
        for group in GROUPS:
            data[group] = dataclasses.asdict(getattr(self, group))
        data["weapons"] = {w.key: dataclasses.asdict(self.weapon(w.key)) for w in all_weapons()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameScheme":
        data = migrate(SCHEME_KIND, data, SCHEME_VERSION)
        scheme = cls(name=str(data.get("name", "Unbenannt")))
        for group, group_type in GROUPS.items():
            setattr(scheme, group, _load_group(group_type, data.get(group, {})))
        for key, values in dict(data.get("weapons", {})).items():
            scheme.weapons[key] = _load_group(WeaponOptions, values)
        return scheme


def _load_group(group_type: type, values: Any) -> Any:
    """Build a group dataclass, coercing known fields and ignoring unknown ones."""
    instance = group_type()
    if not isinstance(values, dict):
        return instance
    for f in dataclasses.fields(group_type):
        if f.name in values:
            default = getattr(instance, f.name)
            setattr(instance, f.name, type(default)(values[f.name]))
    return instance


# ------------------------------------------------------------------- files
def bundled_schemes_dir() -> Path:
    return assets_dir() / "schemes"


def list_schemes() -> dict[str, Path]:
    """Scheme name -> file. User schemes override bundled ones with the same name."""
    found: dict[str, Path] = {}
    for directory in (bundled_schemes_dir(), user_dir("schemes")):
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                try:
                    name = str(load_json(path).get("name", path.stem))
                except (OSError, ValueError, TypeError):
                    continue
                found[name] = path
    if "Standard" not in found:
        found = {"Standard": Path(), **found}
    return dict(sorted(found.items(), key=lambda item: (item[0] != "Standard", item[0])))


def load_scheme(path: Path) -> GameScheme:
    return GameScheme.from_dict(load_json(path))


def load_scheme_by_name(name: str) -> GameScheme:
    path = list_schemes().get(name)
    if path is None or path == Path():
        return GameScheme()
    return load_scheme(path)


def save_scheme(scheme: GameScheme, path: Path | None = None) -> Path:
    target = path or user_dir("schemes") / f"{_slug(scheme.name)}.json"
    save_json(target, scheme.to_dict())
    return target


def _slug(name: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    return cleaned or "schema"
