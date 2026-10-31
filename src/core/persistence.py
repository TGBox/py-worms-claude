"""File locations and versioned, atomically written JSON documents."""

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

APP_NAME = "py-worms-claude"
DATA_DIR_ENV = "PY_WORMS_DATA_DIR"

Migration = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: dict[str, dict[int, Migration]] = {}


def assets_dir() -> Path:
    """Bundled, read-only assets (also inside a PyInstaller bundle)."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parents[2]
    return root / "assets"


def data_dir() -> Path:
    """Per-user writable folder for teams, schemes, maps, progress and options."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


def user_dir(kind: str) -> Path:
    path = data_dir() / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Write atomically: a crash never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} enthält kein JSON-Objekt")
    return data


def register_migration(kind: str, from_version: int) -> Callable[[Migration], Migration]:
    """Register a function upgrading a `kind` document from `from_version` to the next one."""

    def decorator(function: Migration) -> Migration:
        _MIGRATIONS.setdefault(kind, {})[from_version] = function
        return function

    return decorator


def migrate(kind: str, data: dict[str, Any], current_version: int) -> dict[str, Any]:
    """Apply registered migrations step by step until the document is current."""
    version = int(data.get("version", 1))
    if version > current_version:
        raise ValueError(f"{kind}: Version {version} ist neuer als unterstützt ({current_version})")
    while version < current_version:
        step = _MIGRATIONS.get(kind, {}).get(version)
        if step is None:
            raise ValueError(f"{kind}: keine Migration von Version {version}")
        data = step(dict(data))
        version += 1
        data["version"] = version
    return data
