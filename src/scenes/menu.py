"""Main menu: team setup (human/AI), worms per team and map selection."""

import random
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from src.core.match import TeamConfig
from src.maps import available_maps
from src.render import fonts
from src.scenes.base import Scene
from src.settings import (
    COLOR_BACKGROUND,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_TEXT,
    TEAM_COLORS,
    TEAM_NAMES,
    WORMS_PER_TEAM,
)

CONTROLS = [
    "Steuerung im Spiel",
    "Pfeiltasten links/rechts (A/D): Laufen",
    "Pfeiltasten hoch/runter (W/S): Zielen",
    "Enter: Springen   ·   1-4: Waffe wählen",
    "Leertaste: Laden/Schießen   ·   Linksklick: Luftschlag-Ziel",
    "Rechte Maustaste ziehen: Kamera   ·   P: Pause",
    "ESC: Menü   ·   F11: Vollbild",
]


@dataclass
class MenuSettings:
    team_count: int = 2
    team_ai: tuple[bool, ...] = (False, True, True, True)
    worms_per_team: int = WORMS_PER_TEAM
    map_index: int = 0


@dataclass
class MenuItem:
    label: Callable[[], str]
    change: Callable[[int], None]
    color: tuple[int, int, int] = COLOR_TEXT


class MenuScene(Scene):
    # Remember the last setup across matches.
    settings = MenuSettings()

    def __init__(self) -> None:
        super().__init__()
        self.maps = available_maps()
        if self.settings.map_index >= len(self.maps):
            self.settings.map_index = 0
        self.selected = 0
        self.item_rects: list[pygame.Rect] = []

    # --------------------------------------------------------------- items
    def items(self) -> list[MenuItem]:
        s = self.settings
        result = [MenuItem(lambda: f"Teams: {s.team_count}", self._change_team_count)]
        for index in range(s.team_count):
            result.append(
                MenuItem(
                    lambda i=index: f"{TEAM_NAMES[i]}: {'KI' if s.team_ai[i] else 'Mensch'}",
                    lambda _d, i=index: self._toggle_ai(i),
                    TEAM_COLORS[index],
                )
            )
        result += [
            MenuItem(lambda: f"Würmer pro Team: {s.worms_per_team}", self._change_worms),
            MenuItem(lambda: f"Karte: {self.maps[s.map_index]}", self._change_map),
            MenuItem(lambda: "Spiel starten", lambda _d: self._start(), COLOR_PRIMARY),
            MenuItem(lambda: "Beenden", lambda _d: self._quit(), COLOR_MUTED),
        ]
        return result

    def _change_team_count(self, direction: int) -> None:
        self.settings.team_count = (self.settings.team_count - 2 + direction) % 3 + 2

    def _toggle_ai(self, index: int) -> None:
        flags = list(self.settings.team_ai)
        flags[index] = not flags[index]
        self.settings.team_ai = tuple(flags)

    def _change_worms(self, direction: int) -> None:
        self.settings.worms_per_team = (self.settings.worms_per_team - 1 + direction) % 6 + 1

    def _change_map(self, direction: int) -> None:
        self.settings.map_index = (self.settings.map_index + direction) % len(self.maps)

    def _quit(self) -> None:
        self.quit_requested = True

    def _start(self) -> None:
        from src.scenes.match_scene import MatchScene  # avoid an import cycle

        s = self.settings
        configs = [
            TeamConfig(TEAM_NAMES[i], TEAM_COLORS[i], s.team_ai[i]) for i in range(s.team_count)
        ]
        seed = random.randrange(1_000_000)
        self.next_scene = MatchScene(configs, self.maps[s.map_index], s.worms_per_team, seed)

    # -------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        items = self.items()
        self.selected = min(self.selected, len(items) - 1)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._quit()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(items)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                items[self.selected].change(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                items[self.selected].change(1)
        elif event.type == pygame.MOUSEMOTION:
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos):
                    self.selected = index
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos) and index < len(items):
                    self.selected = index
                    items[index].change(1 if event.button == 1 else -1)

    # ---------------------------------------------------------------- draw
    def draw(self, canvas: pygame.Surface) -> None:
        canvas.fill(COLOR_BACKGROUND)
        width = canvas.get_width()
        title = fonts.outlined("py-worms-claude", 84, COLOR_PRIMARY)
        canvas.blit(title, title.get_rect(midtop=(width // 2, 40)))
        subtitle = fonts.text("Ein Worms-Klon in Python", 28, COLOR_MUTED)
        canvas.blit(subtitle, subtitle.get_rect(midtop=(width // 2, 112)))

        self.item_rects = []
        y = 160
        for index, item in enumerate(self.items()):
            selected = index == self.selected
            label = fonts.text(item.label(), 38 if selected else 34, item.color)
            rect = label.get_rect(midtop=(width // 2, y))
            hit = rect.inflate(160, 10)
            if selected:
                pygame.draw.rect(canvas, (34, 42, 60), hit, border_radius=8)
                left = fonts.text("<", 34, COLOR_MUTED)
                right = fonts.text(">", 34, COLOR_MUTED)
                canvas.blit(left, left.get_rect(midleft=(hit.left + 12, hit.centery)))
                canvas.blit(right, right.get_rect(midright=(hit.right - 12, hit.centery)))
            canvas.blit(label, rect)
            self.item_rects.append(hit)
            y += 40

        y = max(y + 16, canvas.get_height() - 30 - 24 * len(CONTROLS))
        for index, line in enumerate(CONTROLS):
            color = COLOR_TEXT if index == 0 else COLOR_MUTED
            label = fonts.text(line, 22, color)
            canvas.blit(label, label.get_rect(midtop=(width // 2, y)))
            y += 24
