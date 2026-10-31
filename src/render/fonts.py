"""Cached font and text rendering helpers."""

import pygame

_fonts: dict[int, pygame.font.Font] = {}
_texts: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_MAX_CACHED_TEXTS = 512


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def text(content: str, size: int, color: tuple[int, int, int]) -> pygame.Surface:
    key = (content, size, color)
    surface = _texts.get(key)
    if surface is None:
        if len(_texts) > _MAX_CACHED_TEXTS:
            _texts.clear()
        surface = font(size).render(content, True, color)
        _texts[key] = surface
    return surface


def outlined(content: str, size: int, color: tuple[int, int, int]) -> pygame.Surface:
    """Text with a 1px dark outline, readable on any background."""
    key = ("\0outline" + content, size, color)
    surface = _texts.get(key)
    if surface is None:
        inner = font(size).render(content, True, color)
        shadow = font(size).render(content, True, (10, 12, 18))
        surface = pygame.Surface((inner.get_width() + 2, inner.get_height() + 2), pygame.SRCALPHA)
        for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            surface.blit(shadow, (ox, oy))
        surface.blit(inner, (1, 1))
        _texts[key] = surface
    return surface
