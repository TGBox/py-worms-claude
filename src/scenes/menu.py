"""Menus: main menu and battle setup (teams, map, scheme)."""

import random
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from src.controls import Action, get_controls
from src.core import native
from src.core.match import TeamConfig
from src.core.scheme import list_schemes, load_scheme_by_name
from src.maps import RANDOM_MAP, available_maps
from src.render import fonts
from src.scenes.base import Scene
from src.settings import (
    COLOR_BACKGROUND,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_TEXT,
    TEAM_COLORS,
    TEAM_NAMES,
)

CONTROLS_HELP = (
    "Steuerung im Spiel",
    "Pfeiltasten links/rechts (A/D): Laufen   ·   hoch/runter (W/S): Zielen",
    "Enter: Springen   ·   1-4: Waffe   ·   Leertaste: Laden/Schießen",
    "Linksklick: Luftschlag-Ziel   ·   Rechte Maustaste ziehen: Kamera",
    "P: Pause   ·   ESC: Zurück   ·   F11: Vollbild",
)
COMING_SOON = (110, 116, 130)


@dataclass
class MenuItem:
    label: Callable[[], str]
    change: Callable[[int], None]
    color: tuple[int, int, int] = COLOR_TEXT
    enabled: bool = True


class ListMenuScene(Scene):
    """Vertical list of items, navigable with keys and mouse."""

    title = "py-worms-claude"
    subtitle = ""
    footer: tuple[str, ...] = ()

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.item_rects: list[pygame.Rect] = []

    def items(self) -> list[MenuItem]:
        raise NotImplementedError

    def back(self) -> None:
        self.quit_requested = True

    def _move_selection(self, items: list[MenuItem], step: int) -> None:
        for _ in range(len(items)):
            self.selected = (self.selected + step) % len(items)
            if items[self.selected].enabled:
                return

    def handle_event(self, event: pygame.event.Event) -> None:
        items = self.items()
        self.selected = min(self.selected, len(items) - 1)
        controls = get_controls()
        if event.type == pygame.KEYDOWN:
            if controls.matches(Action.BACK, event.key):
                self.back()
            elif controls.matches(Action.MENU_UP, event.key):
                self._move_selection(items, -1)
            elif controls.matches(Action.MENU_DOWN, event.key):
                self._move_selection(items, 1)
            elif controls.matches(Action.MENU_LEFT, event.key):
                self._activate(items[self.selected], -1)
            elif controls.matches(Action.MENU_RIGHT, event.key) or controls.matches(
                Action.CONFIRM, event.key
            ):
                self._activate(items[self.selected], 1)
        elif event.type == pygame.MOUSEMOTION:
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos) and index < len(items) and items[index].enabled:
                    self.selected = index
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos) and index < len(items):
                    self.selected = index
                    self._activate(items[index], 1 if event.button == 1 else -1)

    @staticmethod
    def _activate(item: MenuItem, direction: int) -> None:
        if item.enabled:
            item.change(direction)

    def draw(self, canvas: pygame.Surface) -> None:
        canvas.fill(COLOR_BACKGROUND)
        width = canvas.get_width()
        title = fonts.outlined(self.title, 84, COLOR_PRIMARY)
        canvas.blit(title, title.get_rect(midtop=(width // 2, 40)))
        if self.subtitle:
            subtitle = fonts.text(self.subtitle, 28, COLOR_MUTED)
            canvas.blit(subtitle, subtitle.get_rect(midtop=(width // 2, 112)))

        self.item_rects = []
        y = 160
        for index, item in enumerate(self.items()):
            selected = index == self.selected and item.enabled
            color = item.color if item.enabled else COMING_SOON
            label = fonts.text(item.label(), 38 if selected else 34, color)
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

        y = max(y + 16, canvas.get_height() - 30 - 24 * len(self.footer))
        for index, line in enumerate(self.footer):
            label = fonts.text(line, 22, COLOR_TEXT if index == 0 else COLOR_MUTED)
            canvas.blit(label, label.get_rect(midtop=(width // 2, y)))
            y += 24


class MainMenuScene(ListMenuScene):
    subtitle = f"Ein Worms-Klon in Python  ·  Physik: {native.backend_name()}"
    footer = CONTROLS_HELP

    def items(self) -> list[MenuItem]:
        def soon(label: str) -> MenuItem:
            return MenuItem(lambda: f"{label} (bald)", lambda _d: None, enabled=False)

        return [
            MenuItem(lambda: "Schnelles Spiel", lambda _d: self._quick_match(), COLOR_PRIMARY),
            MenuItem(lambda: "Battle einrichten", lambda _d: self._setup()),
            soon("Teams"),
            soon("Editor"),
            soon("Kampagne"),
            soon("Tutorial"),
            soon("Optionen"),
            MenuItem(lambda: "Beenden", lambda _d: self.back(), COLOR_MUTED),
        ]

    def _quick_match(self) -> None:
        from src.scenes.match_scene import MatchScene  # avoid an import cycle

        configs = [
            TeamConfig(TEAM_NAMES[0], TEAM_COLORS[0], is_ai=False),
            TeamConfig(TEAM_NAMES[1], TEAM_COLORS[1], is_ai=True),
        ]
        scheme = load_scheme_by_name("Standard")
        self.next_scene = MatchScene(configs, RANDOM_MAP, scheme, random.randrange(1_000_000))

    def _setup(self) -> None:
        self.next_scene = BattleSetupScene()


@dataclass
class SetupState:
    team_count: int = 2
    team_ai: tuple[bool, ...] = (False, True, True, True)
    map_index: int = 0
    scheme_name: str = "Standard"
    worm_count: int | None = None  # None = value from the scheme


class BattleSetupScene(ListMenuScene):
    title = "Battle einrichten"
    footer = CONTROLS_HELP
    state = SetupState()  # remembered across matches

    def __init__(self) -> None:
        super().__init__()
        self.maps = available_maps()
        self.schemes = list(list_schemes())
        if self.state.map_index >= len(self.maps):
            self.state.map_index = 0
        if self.state.scheme_name not in self.schemes:
            self.state.scheme_name = self.schemes[0]

    def back(self) -> None:
        self.next_scene = MainMenuScene()

    def items(self) -> list[MenuItem]:
        s = self.state
        result = [MenuItem(lambda: f"Teams: {s.team_count}", self._change_team_count)]
        for index in range(s.team_count):
            result.append(
                MenuItem(
                    lambda i=index: f"{TEAM_NAMES[i]}: {'KI' if s.team_ai[i] else 'Mensch'}",
                    lambda _d, i=index: self._toggle_ai(i),
                    TEAM_COLORS[index],
                )
            )
        worms = lambda: "Schema" if s.worm_count is None else str(s.worm_count)
        result += [
            MenuItem(lambda: f"Schema: {s.scheme_name}", self._change_scheme),
            MenuItem(lambda: f"Würmer pro Team: {worms()}", self._change_worms),
            MenuItem(lambda: f"Karte: {self.maps[s.map_index]}", self._change_map),
            MenuItem(lambda: "Spiel starten", lambda _d: self._start(), COLOR_PRIMARY),
            MenuItem(lambda: "Zurück", lambda _d: self.back(), COLOR_MUTED),
        ]
        return result

    def _change_team_count(self, direction: int) -> None:
        self.state.team_count = (self.state.team_count - 2 + direction) % 3 + 2

    def _toggle_ai(self, index: int) -> None:
        flags = list(self.state.team_ai)
        flags[index] = not flags[index]
        self.state.team_ai = tuple(flags)

    def _change_scheme(self, direction: int) -> None:
        index = self.schemes.index(self.state.scheme_name)
        self.state.scheme_name = self.schemes[(index + direction) % len(self.schemes)]

    def _change_worms(self, direction: int) -> None:
        options: list[int | None] = [None, 1, 2, 3, 4, 5, 6, 7, 8]
        index = options.index(self.state.worm_count)
        self.state.worm_count = options[(index + direction) % len(options)]

    def _change_map(self, direction: int) -> None:
        self.state.map_index = (self.state.map_index + direction) % len(self.maps)

    def _start(self) -> None:
        from src.scenes.match_scene import MatchScene  # avoid an import cycle

        s = self.state
        configs = [
            TeamConfig(TEAM_NAMES[i], TEAM_COLORS[i], s.team_ai[i]) for i in range(s.team_count)
        ]
        scheme = load_scheme_by_name(s.scheme_name)
        if s.worm_count is not None:
            scheme.worms.count = s.worm_count
        seed = random.randrange(1_000_000)
        self.next_scene = MatchScene(configs, self.maps[s.map_index], scheme, seed)
