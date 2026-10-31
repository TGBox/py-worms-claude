"""Destructible pixel terrain stored as a flat bytearray (1 = solid, 0 = air)."""

import math

_CIRCLE_SAMPLES = 12
_CIRCLE_OFFSETS = [
    (math.cos(2 * math.pi * i / _CIRCLE_SAMPLES), math.sin(2 * math.pi * i / _CIRCLE_SAMPLES))
    for i in range(_CIRCLE_SAMPLES)
]
_CIRCLE_POINTS = [(0.0, 0.0), *_CIRCLE_OFFSETS]  # centre first, then the rim


class Terrain:
    """Row-major solid/air grid. All geometry operations are pure Python."""

    def __init__(self, width: int, height: int, data: bytearray | None = None) -> None:
        self.width = width
        self.height = height
        self.data = data if data is not None else bytearray(width * height)
        if len(self.data) != width * height:
            raise ValueError("terrain data size does not match dimensions")
        # Circles (x, y, r) removed since the renderer last synced; consumed by the renderer.
        self.carved: list[tuple[int, int, int]] = []

    @classmethod
    def from_alpha(cls, width: int, height: int, alpha: bytes, threshold: int = 128) -> "Terrain":
        """Build terrain from one alpha byte per pixel (e.g. extracted from a PNG)."""
        table = bytes(1 if value >= threshold else 0 for value in range(256))
        return cls(width, height, bytearray(alpha.translate(table)))

    @classmethod
    def from_rows(cls, rows: list[str], solid: str = "#") -> "Terrain":
        """Build terrain from ASCII rows (handy for tests)."""
        width = len(rows[0])
        data = bytearray(1 if ch == solid else 0 for row in rows for ch in row)
        return cls(width, len(rows), data)

    def copy(self) -> "Terrain":
        return Terrain(self.width, self.height, bytearray(self.data))

    def is_solid(self, x: float, y: float) -> bool:
        # Hot path: int() truncation equals floor() once negatives are excluded.
        if x < 0 or y < 0:
            return False
        xi = int(x)
        yi = int(y)
        if xi >= self.width or yi >= self.height:
            return False
        return self.data[yi * self.width + xi] == 1

    def circle_collides(self, cx: float, cy: float, radius: float) -> bool:
        width, height, data = self.width, self.height, self.data
        for ox, oy in _CIRCLE_POINTS:
            x = cx + ox * radius
            y = cy + oy * radius
            if x < 0 or y < 0:
                continue
            xi, yi = int(x), int(y)
            if xi < width and yi < height and data[yi * width + xi] == 1:
                return True
        return False

    def _set_circle(self, cx: float, cy: float, radius: float, value: int) -> None:
        r = int(radius)
        icx, icy = int(cx), int(cy)
        for dy in range(-r, r + 1):
            y = icy + dy
            if y < 0 or y >= self.height:
                continue
            half = int(math.sqrt(max(0, r * r - dy * dy)))
            x0 = max(0, icx - half)
            x1 = min(self.width, icx + half + 1)
            if x1 <= x0:
                continue
            start = y * self.width
            self.data[start + x0 : start + x1] = bytes([value]) * (x1 - x0)

    def carve_circle(self, cx: float, cy: float, radius: float) -> None:
        self._set_circle(cx, cy, radius, 0)
        self.carved.append((int(cx), int(cy), int(radius)))

    def fill_circle(self, cx: float, cy: float, radius: float) -> None:
        self._set_circle(cx, cy, radius, 1)

    def fill_column(self, x: int, top: int) -> None:
        """Make column x solid from row `top` down to the bottom edge."""
        if not 0 <= x < self.width:
            return
        top = max(0, min(self.height, top))
        count = self.height - top
        if count > 0:
            self.data[top * self.width + x :: self.width] = b"\x01" * count

    def surface_y(self, x: float, start_y: int = 0) -> int | None:
        """First solid row in column x at or below start_y, or None."""
        xi = int(x)
        if not 0 <= xi < self.width:
            return None
        column = self.data[xi :: self.width]
        index = column.find(1, max(0, start_y))
        return None if index < 0 else index

    def normal_at(self, x: float, y: float, radius: int = 5) -> tuple[float, float]:
        """Approximate surface normal pointing away from solid ground."""
        nx = ny = 0.0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius and self.is_solid(x + dx, y + dy):
                    nx -= dx
                    ny -= dy
        length = math.hypot(nx, ny)
        if length < 1e-6:
            return (0.0, -1.0)
        return (nx / length, ny / length)

    def solid_count(self) -> int:
        return self.data.count(1)
