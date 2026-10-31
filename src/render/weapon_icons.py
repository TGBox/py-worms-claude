"""Procedurally drawn weapon icons, held by worms and shown in the HUD."""

import math

import pygame

DARK = (30, 32, 40)


def _rotated(
    origin: tuple[float, float], angle: float, dx: float, dy: float
) -> tuple[float, float]:
    cos, sin = math.cos(angle), math.sin(angle)
    return (origin[0] + dx * cos - dy * sin, origin[1] + dx * sin + dy * cos)


def draw_weapon(
    canvas: pygame.Surface, key: str, pos: tuple[float, float], angle: float, scale: float = 1.0
) -> None:
    """Draw weapon `key` at pos, pointing along `angle` (screen radians, 0 = right)."""

    def at(dx: float, dy: float) -> tuple[float, float]:
        return _rotated(pos, angle, dx * scale, dy * scale)

    width = max(1, round(4 * scale))
    if key == "bazooka":
        pygame.draw.line(canvas, (70, 96, 60), at(-4, 0), at(10, 0), width)
        pygame.draw.line(canvas, DARK, at(9, 0), at(11, 0), width + 1)
        pygame.draw.line(canvas, (120, 140, 90), at(-2, 2), at(1, 4), max(1, round(2 * scale)))
    elif key == "grenade":
        center = at(5, 0)
        pygame.draw.circle(canvas, (60, 120, 50), center, max(2, round(3.5 * scale)))
        pygame.draw.circle(canvas, DARK, center, max(2, round(3.5 * scale)), 1)
        pygame.draw.line(canvas, (190, 190, 200), at(5, -3), at(7, -5), 1)
    elif key == "shotgun":
        for offset in (-1, 1):
            pygame.draw.line(canvas, (90, 90, 100), at(-3, offset), at(11, offset), 2)
        pygame.draw.line(canvas, (120, 80, 40), at(-5, 1), at(1, 2), max(1, round(3 * scale)))
    elif key == "airstrike":
        box = [at(-1, -3), at(6, -3), at(6, 3), at(-1, 3)]
        pygame.draw.polygon(canvas, (80, 84, 96), box)
        pygame.draw.line(canvas, (200, 60, 60), at(4, -3), at(7, -9), 1)
        pygame.draw.circle(canvas, (240, 220, 80), at(1.5, 0), max(1, round(1.2 * scale)))
    else:
        pygame.draw.circle(canvas, (150, 150, 160), at(5, 0), max(2, round(3 * scale)))


def draw_icon(canvas: pygame.Surface, key: str, center: tuple[float, float], size: float) -> None:
    """HUD variant: the weapon horizontally, scaled to roughly `size` pixels."""
    draw_weapon(canvas, key, (center[0] - size * 0.25, center[1]), 0.0, size / 16)
