"""Action mapping: game code asks for actions, keys are configurable in settings.json."""

from enum import Enum
from typing import Any

import pygame

from src.core.persistence import data_dir, load_json, save_json


class Action(Enum):
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    AIM_UP = "aim_up"
    AIM_DOWN = "aim_down"
    JUMP = "jump"
    FIRE = "fire"
    WEAPON_1 = "weapon_1"
    WEAPON_2 = "weapon_2"
    WEAPON_3 = "weapon_3"
    WEAPON_4 = "weapon_4"
    PAUSE = "pause"
    BACK = "back"
    CONFIRM = "confirm"
    MENU_UP = "menu_up"
    MENU_DOWN = "menu_down"
    MENU_LEFT = "menu_left"
    MENU_RIGHT = "menu_right"
    FULLSCREEN = "fullscreen"


# Key names as understood by pygame.key.key_code().
DEFAULT_BINDINGS: dict[Action, tuple[str, ...]] = {
    Action.MOVE_LEFT: ("left", "a"),
    Action.MOVE_RIGHT: ("right", "d"),
    Action.AIM_UP: ("up", "w"),
    Action.AIM_DOWN: ("down", "s"),
    Action.JUMP: ("return", "enter"),
    Action.FIRE: ("space",),
    Action.WEAPON_1: ("1",),
    Action.WEAPON_2: ("2",),
    Action.WEAPON_3: ("3",),
    Action.WEAPON_4: ("4",),
    Action.PAUSE: ("p",),
    Action.BACK: ("escape",),
    Action.CONFIRM: ("return", "enter", "space"),
    Action.MENU_UP: ("up", "w"),
    Action.MENU_DOWN: ("down", "s"),
    Action.MENU_LEFT: ("left", "a"),
    Action.MENU_RIGHT: ("right", "d"),
    Action.FULLSCREEN: ("f11",),
}

WEAPON_ACTIONS = (Action.WEAPON_1, Action.WEAPON_2, Action.WEAPON_3, Action.WEAPON_4)


def _key_code(name: str) -> int | None:
    try:
        return pygame.key.key_code(name)
    except ValueError:
        return None


class Controls:
    def __init__(self, bindings: dict[Action, tuple[str, ...]] | None = None) -> None:
        self.bindings = dict(DEFAULT_BINDINGS)
        self.bindings.update(bindings or {})
        self._keys: dict[Action, set[int]] = {}
        for action, names in self.bindings.items():
            codes = {_key_code(name) for name in names}
            self._keys[action] = {code for code in codes if code is not None}

    def matches(self, action: Action, key: int) -> bool:
        return key in self._keys.get(action, ())

    def actions_for(self, key: int) -> set[Action]:
        return {action for action, keys in self._keys.items() if key in keys}

    def held(self, action: Action, pressed: Any) -> bool:
        """`pressed` is the result of pygame.key.get_pressed()."""
        return any(pressed[key] for key in self._keys.get(action, ()))

    def to_dict(self) -> dict[str, list[str]]:
        return {action.value: list(names) for action, names in self.bindings.items()}


_controls: Controls | None = None


def settings_path() -> Any:
    return data_dir() / "settings.json"


def get_controls() -> Controls:
    """Controls loaded once from settings.json (defaults when missing or invalid)."""
    global _controls
    if _controls is None:
        bindings: dict[Action, tuple[str, ...]] = {}
        path = settings_path()
        if path.is_file():
            try:
                stored = load_json(path).get("controls", {})
                for action in Action:
                    names = stored.get(action.value)
                    if isinstance(names, list) and names:
                        bindings[action] = tuple(str(n) for n in names)
            except (OSError, ValueError, TypeError):
                bindings = {}
        _controls = Controls(bindings)
    return _controls


def save_controls(controls: Controls) -> None:
    path = settings_path()
    data: dict[str, Any] = {"version": 1}
    if path.is_file():
        try:
            data = load_json(path)
        except (OSError, ValueError, TypeError):
            pass
    data["controls"] = controls.to_dict()
    save_json(path, data)
