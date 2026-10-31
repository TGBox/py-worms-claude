"""Turns the logical terrain grid into a textured, alpha-masked pygame surface."""

import random

import pygame

from src.core.terrain import Terrain
from src.settings import COLOR_GRASS, COLOR_SOIL, COLOR_SOIL_DARK

GRASS_DEPTH = 5
_ALPHA_TABLE = bytes([0, 255] + [255] * 254)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def generate_texture(terrain: Terrain, seed: int = 0) -> pygame.Surface:
    """Procedural soil texture with depth shading, pebbles and grass on top edges."""
    width, height = terrain.width, terrain.height
    rng = random.Random(seed)
    texture = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        texture.fill((*_lerp(COLOR_SOIL, COLOR_SOIL_DARK, y / height), 255), (0, y, width, 1))
    for _ in range(width * height // 260):
        x, y = rng.randrange(width), rng.randrange(height)
        shade = rng.choice((-26, -16, 14, 22))
        base = _lerp(COLOR_SOIL, COLOR_SOIL_DARK, y / height)
        color = tuple(max(0, min(255, c + shade)) for c in base)
        pygame.draw.circle(texture, (*color, 255), (x, y), rng.choice((1, 1, 2, 3)))

    # Grass: solid pixels with air somewhere in the GRASS_DEPTH pixels above them.
    # Bitwise big-int operations process the whole map at C speed.
    size = width * height
    solid = int.from_bytes(terrain.data, "big")
    covered = solid
    for k in range(1, GRASS_DEPTH + 1):
        shifted = bytes(k * width) + bytes(terrain.data[: size - k * width])
        covered &= int.from_bytes(shifted, "big")
    grass = (solid & ~covered).to_bytes(size, "big")
    mask = int.from_bytes(grass.translate(_ALPHA_TABLE), "big")
    rgba = bytearray(pygame.image.tobytes(texture, "RGBA"))
    for channel, value in enumerate(COLOR_GRASS):
        current = int.from_bytes(rgba[channel::4], "big")
        fill = int.from_bytes(bytes([value]) * size, "big")
        rgba[channel::4] = ((current & ~mask) | (fill & mask)).to_bytes(size, "big")
    return pygame.image.frombytes(bytes(rgba), (width, height), "RGBA")


class TerrainView:
    """Keeps a drawable surface in sync with the destructible terrain."""

    def __init__(self, terrain: Terrain, texture: pygame.Surface | None = None, seed: int = 0):
        self.terrain = terrain
        if texture is None or texture.get_size() != (terrain.width, terrain.height):
            texture = generate_texture(terrain, seed)
        self._texture = pygame.image.tobytes(texture, "RGBA")
        rgba = bytearray(self._texture)
        rgba[3::4] = bytes(terrain.data).translate(_ALPHA_TABLE)
        self.surface = pygame.image.frombytes(bytes(rgba), (terrain.width, terrain.height), "RGBA")
        if pygame.display.get_surface() is not None:
            self.surface = self.surface.convert_alpha()  # much faster blits
        terrain.carved.clear()

    def sync(self) -> None:
        """Apply circles carved since the last call, pixel-exact with the logic grid."""
        width, height = self.terrain.width, self.terrain.height
        for cx, cy, radius in self.terrain.carved:
            x0, x1 = max(0, cx - radius - 1), min(width, cx + radius + 2)
            y0, y1 = max(0, cy - radius - 1), min(height, cy + radius + 2)
            if x1 <= x0 or y1 <= y0:
                continue
            patch = bytearray()
            alpha = bytearray()
            for y in range(y0, y1):
                row = y * width
                patch += self._texture[(row + x0) * 4 : (row + x1) * 4]
                alpha += self.terrain.data[row + x0 : row + x1]
            patch[3::4] = bytes(alpha).translate(_ALPHA_TABLE)
            rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
            self.surface.fill((0, 0, 0, 0), rect)
            self.surface.blit(pygame.image.frombytes(bytes(patch), rect.size, "RGBA"), rect)
        self.terrain.carved.clear()
