"""Double-tap detection for the jump keys (no pygame, unit-testable).

Enter = forward jump, Backspace = high jump; pressing either key twice within the window is a
backflip. A single press therefore fires only once the window has passed without a second press.
"""

from src.core.constants import DOUBLE_TAP_WINDOW


class JumpBuffer:
    def __init__(self, window: float = DOUBLE_TAP_WINDOW) -> None:
        self.window = window
        self._pending: str | None = None
        self._age = 0.0

    @property
    def pending(self) -> bool:
        return self._pending is not None

    def press(self, kind: str) -> str | None:
        """Register a press of "forward" or "high"; returns "backflip" on a double tap."""
        if self._pending is not None:
            self._pending = None
            return "backflip"
        self._pending = kind
        self._age = 0.0
        return None

    def update(self, dt: float) -> str | None:
        """Advance time; returns the single jump once the double-tap window has expired."""
        if self._pending is None:
            return None
        self._age += dt
        if self._age >= self.window:
            kind, self._pending = self._pending, None
            return kind
        return None

    def clear(self) -> None:
        self._pending = None
