"""Procedural island generator based on layered 1D value noise."""

import math
import random

from src.core.terrain import Terrain


def _value_noise(rng: random.Random, length: int, step: int) -> list[float]:
    """Smoothly interpolated random values in [-1, 1] for each x."""
    points = [rng.uniform(-1.0, 1.0) for _ in range(length // step + 2)]
    values = []
    for x in range(length):
        i, frac = divmod(x / step, 1.0)
        i = int(i)
        t = (1 - math.cos(frac * math.pi)) / 2
        values.append(points[i] * (1 - t) + points[i + 1] * t)
    return values


def surface_profile(width: int, height: int, water_level: int, seed: int) -> list[int]:
    """Top surface row per column; edges sink below the water line."""
    rng = random.Random(seed)
    octaves = [(260, 1.0), (110, 0.45), (40, 0.15)]
    layers = [_value_noise(rng, width, step) for step, _ in octaves]
    total = sum(weight for _, weight in octaves)
    base = height * 0.55
    amplitude = height * 0.22
    profile = []
    for x in range(width):
        noise = sum(layer[x] * weight for layer, (_, weight) in zip(layers, octaves)) / total
        # Falloff towards both edges so the map reads as an island.
        edge = min(x, width - 1 - x) / (width * 0.12)
        falloff = min(1.0, edge)
        top = base + noise * amplitude
        top = top * falloff + (water_level + 40) * (1 - falloff)
        profile.append(int(top))
    return profile


def generate_terrain(width: int, height: int, water_level: int, seed: int) -> Terrain:
    """Build an island with caves and a few floating platforms."""
    rng = random.Random(seed * 7919 + 13)
    terrain = Terrain(width, height)
    for x, top in enumerate(surface_profile(width, height, water_level, seed)):
        terrain.fill_column(x, top)

    # Floating islands above the main land mass.
    for _ in range(rng.randint(2, 4)):
        cx = rng.uniform(width * 0.2, width * 0.8)
        cy = rng.uniform(height * 0.18, height * 0.4)
        for _ in range(rng.randint(3, 6)):
            terrain.fill_circle(
                cx + rng.uniform(-60, 60), cy + rng.uniform(-10, 14), rng.uniform(18, 34)
            )

    # Caves: random walks of carved circles beneath the surface.
    for _ in range(rng.randint(3, 6)):
        x = rng.uniform(width * 0.15, width * 0.85)
        surface = terrain.surface_y(x) or water_level
        y = rng.uniform(surface + 60, water_level - 30)
        angle = rng.uniform(0, math.tau)
        for _ in range(rng.randint(10, 25)):
            terrain.carve_circle(x, y, rng.uniform(14, 26))
            angle += rng.uniform(-0.6, 0.6)
            x += math.cos(angle) * 14
            y = min(water_level - 20, y + math.sin(angle) * 8)
    terrain.carved.clear()
    return terrain
