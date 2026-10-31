"""Minimal scene interface used by the application loop."""

import pygame


class Scene:
    def __init__(self) -> None:
        self.next_scene: Scene | None = None
        self.quit_requested = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Mouse positions in events are already converted to canvas coordinates."""

    def update(self, dt: float, mouse_pos: tuple[int, int]) -> None:
        pass

    def draw(self, canvas: pygame.Surface) -> None:
        pass
