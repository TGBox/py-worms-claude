"""Entry point: window management, letterboxed rendering and the scene loop."""

import sys

import pygame

from src.controls import Action, get_controls
from src.scenes.base import Scene
from src.settings import COLOR_BACKGROUND, FPS, SCREEN_HEIGHT, SCREEN_WIDTH, TITLE

MOUSE_EVENTS = (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION)


def letterbox(window_size: tuple[int, int], canvas_size: tuple[int, int]) -> pygame.Rect:
    """Largest rect with the canvas aspect ratio, centred in the window."""
    window_w, window_h = window_size
    canvas_w, canvas_h = canvas_size
    scale = min(window_w / canvas_w, window_h / canvas_h)
    width, height = max(1, round(canvas_w * scale)), max(1, round(canvas_h * scale))
    return pygame.Rect((window_w - width) // 2, (window_h - height) // 2, width, height)


class Game:
    def __init__(self, scene: Scene | None = None) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.window_size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        self.is_fullscreen = False
        self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        self.clock = pygame.time.Clock()
        self.running = True
        if scene is None:
            from src.scenes.menu import MainMenuScene

            scene = MainMenuScene()
        self.scene = scene

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)

    def to_canvas(self, pos: tuple[int, int]) -> tuple[int, int]:
        rect = letterbox(self.screen.get_size(), self.canvas.get_size())
        x = (pos[0] - rect.x) * self.canvas.get_width() / rect.width
        y = (pos[1] - rect.y) * self.canvas.get_height() / rect.height
        return (int(x), int(y))

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN and get_controls().matches(
                Action.FULLSCREEN, event.key
            ):
                self.toggle_fullscreen()
                continue
            if event.type == pygame.VIDEORESIZE and not self.is_fullscreen:
                self.window_size = (max(320, event.w), max(180, event.h))
            if event.type in MOUSE_EVENTS:
                attributes = dict(event.dict)
                attributes["pos"] = self.to_canvas(event.pos)
                if "rel" in attributes:
                    rect = letterbox(self.screen.get_size(), self.canvas.get_size())
                    factor = self.canvas.get_width() / rect.width
                    attributes["rel"] = (event.rel[0] * factor, event.rel[1] * factor)
                event = pygame.event.Event(event.type, attributes)
            self.scene.handle_event(event)

    def update(self, dt: float) -> None:
        self.scene.update(dt, self.to_canvas(pygame.mouse.get_pos()))
        if self.scene.quit_requested:
            self.running = False
        elif self.scene.next_scene is not None:
            self.scene = self.scene.next_scene

    def draw(self) -> None:
        self.scene.draw(self.canvas)
        self.screen.fill(COLOR_BACKGROUND)
        rect = letterbox(self.screen.get_size(), self.canvas.get_size())
        if rect.size == self.canvas.get_size():
            self.screen.blit(self.canvas, rect)
        else:
            self.screen.blit(pygame.transform.smoothscale(self.canvas, rect.size), rect)
        pygame.display.flip()

    def step(self, dt: float) -> None:
        """One frame of the game loop (also used by the headless smoke test)."""
        self.handle_events()
        self.update(dt)
        self.draw()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.step(dt)
        pygame.quit()
        sys.exit(0)


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
