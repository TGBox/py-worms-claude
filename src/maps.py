"""Map loading: procedural islands or PNG maps from assets/maps (transparent = air)."""

import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

from src.core.mapgen import generate_terrain
from src.core.terrain import Terrain
from src.settings import WATER_LEVEL, WORLD_HEIGHT, WORLD_WIDTH

RANDOM_MAP = "Zufällig"


def assets_dir() -> Path:
    """Asset folder, also inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / "assets"


def maps_dir() -> Path:
    return assets_dir() / "maps"


def available_maps() -> list[str]:
    """Selectable map names; the random generator always comes first."""
    directory = maps_dir()
    names = sorted(p.stem for p in directory.glob("*.png")) if directory.is_dir() else []
    return [RANDOM_MAP, *names]


@dataclass
class LoadedMap:
    terrain: Terrain
    texture: pygame.Surface | None
    name: str


def load_png_map(path: Path) -> LoadedMap:
    """Scale a PNG to the world size; its alpha channel defines solid ground."""
    image = pygame.image.load(str(path))
    image = image.convert_alpha() if pygame.display.get_surface() else image
    if image.get_size() != (WORLD_WIDTH, WORLD_HEIGHT):
        image = pygame.transform.scale(image, (WORLD_WIDTH, WORLD_HEIGHT))
    rgba = pygame.image.tobytes(image, "RGBA")
    terrain = Terrain.from_alpha(WORLD_WIDTH, WORLD_HEIGHT, rgba[3::4])
    texture = pygame.image.frombytes(rgba, (WORLD_WIDTH, WORLD_HEIGHT), "RGBA")
    return LoadedMap(terrain, texture, path.stem)


def load_map(name: str, seed: int) -> LoadedMap:
    """Load a named map, falling back to a generated island if the file is unusable."""
    if name != RANDOM_MAP:
        path = maps_dir() / f"{name}.png"
        try:
            loaded = load_png_map(path)
            if loaded.terrain.solid_count() > 0:
                return loaded
        except (pygame.error, OSError, FileNotFoundError) as error:
            print(f"Karte '{name}' konnte nicht geladen werden: {error}")
    terrain = generate_terrain(WORLD_WIDTH, WORLD_HEIGHT, WATER_LEVEL, seed)
    return LoadedMap(terrain, None, RANDOM_MAP)
