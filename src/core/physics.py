"""Shared body model and spatial queries for every simulated object.

All objects are circles moving over the pixel terrain (see ADR-0003). Body-body collision is
opt-in per body (`collides_with_bodies`); terrain collision is always on.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.core.terrain import Terrain

GRID_CELL = 64


@dataclass(eq=False, kw_only=True)
class Body:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    radius: float = 0.0
    mass: float = 1.0
    collides_with_bodies: bool = False
    asleep: bool = False  # resting bodies are skipped by integration until woken
    alive: bool = True

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def wake(self) -> None:
        self.asleep = False


@dataclass
class SpatialGrid:
    """Uniform grid for broad-phase queries; rebuilt once per simulation step."""

    cell: int = GRID_CELL
    _cells: dict[tuple[int, int], list[Body]] = field(default_factory=dict)

    def rebuild(self, bodies: Iterable[Body]) -> None:
        self._cells.clear()
        for body in bodies:
            if not body.alive:
                continue
            r = body.radius
            for cx in range(int((body.x - r) // self.cell), int((body.x + r) // self.cell) + 1):
                for cy in range(int((body.y - r) // self.cell), int((body.y + r) // self.cell) + 1):
                    self._cells.setdefault((cx, cy), []).append(body)

    def query(self, x: float, y: float, radius: float) -> list[Body]:
        found: list[Body] = []
        seen: set[int] = set()
        for cx in range(int((x - radius) // self.cell), int((x + radius) // self.cell) + 1):
            for cy in range(int((y - radius) // self.cell), int((y + radius) // self.cell) + 1):
                for body in self._cells.get((cx, cy), ()):
                    if id(body) not in seen:
                        seen.add(id(body))
                        found.append(body)
        return found


class PhysicsWorld:
    """Terrain plus bodies; subclasses decide how each body type moves."""

    def __init__(self, terrain: Terrain, gravity: float) -> None:
        self.terrain = terrain
        self.gravity = gravity
        self.grid = SpatialGrid()

    def all_bodies(self) -> list[Body]:
        raise NotImplementedError

    def rebuild_grid(self) -> None:
        self.grid.rebuild(self.all_bodies())

    def bodies_in_radius(self, x: float, y: float, radius: float) -> list[Body]:
        """Living bodies whose circle overlaps the given circle (uses the last grid build)."""
        result = []
        for body in self.grid.query(x, y, radius):
            if body.alive and math.hypot(body.x - x, body.y - y) < radius + body.radius:
                result.append(body)
        return result

    def body_collides(self, body: Body, x: float, y: float) -> bool:
        """Would `body` at (x, y) overlap terrain or another solid body?"""
        if self.terrain.circle_collides(x, y, body.radius):
            return True
        if not body.collides_with_bodies:
            return False
        for other in self.all_bodies():
            if other is body or not other.alive or not other.collides_with_bodies:
                continue
            reach = body.radius + other.radius
            if (other.x - x) ** 2 + (other.y - y) ** 2 < reach * reach:
                return True
        return False
