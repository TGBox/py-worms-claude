"""Smooth-follow camera (pure math, no pygame)."""

import math

SKY_MARGIN = 300  # how far the camera may look above the top of the world


class Camera:
    def __init__(self, view_width: int, view_height: int, world_width: int, world_height: int):
        self.view_width = view_width
        self.view_height = view_height
        self.world_width = world_width
        self.world_height = world_height
        self.x = 0.0
        self.y = 0.0

    def _clamp(self) -> None:
        max_x = max(0.0, self.world_width - self.view_width)
        max_y = max(0.0, self.world_height - self.view_height)
        self.x = min(max(self.x, 0.0), max_x)
        self.y = min(max(self.y, -SKY_MARGIN), max_y)

    def center_on(self, x: float, y: float) -> None:
        self.x = x - self.view_width / 2
        self.y = y - self.view_height / 2
        self._clamp()

    def follow(self, x: float, y: float, dt: float, stiffness: float = 4.0) -> None:
        blend = 1.0 - math.exp(-stiffness * dt)
        self.x += (x - self.view_width / 2 - self.x) * blend
        self.y += (y - self.view_height / 2 - self.y) * blend
        self._clamp()

    def pan(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        self._clamp()

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (round(x - self.x), round(y - self.y))

    def to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx + self.x, sy + self.y)
