"""Headless smoke tests of the full pygame application (menu, maps, rendering, AI match)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from src.core.match import Phase, TeamConfig
from src.main import Game, letterbox
from src.maps import RANDOM_MAP, available_maps, load_map
from src.scenes.match_scene import MatchScene
from src.scenes.menu import MenuScene
from src.settings import TEAM_COLORS, TEAM_NAMES, WORLD_HEIGHT, WORLD_WIDTH

DT = 1 / 30


def post(event_type: int, **attributes: object) -> None:
    pygame.event.post(pygame.event.Event(event_type, attributes))


def configs(*ai: bool) -> list[TeamConfig]:
    return [TeamConfig(TEAM_NAMES[i], TEAM_COLORS[i], flag) for i, flag in enumerate(ai)]


def test_letterbox_keeps_aspect_ratio() -> None:
    rect = letterbox((1920, 1200), (1280, 720))
    assert rect.size == (1920, 1080) and rect.y == 60
    assert letterbox((1280, 720), (1280, 720)) == pygame.Rect(0, 0, 1280, 720)


def test_bundled_maps_load() -> None:
    names = available_maps()
    assert names[0] == RANDOM_MAP and len(names) >= 2
    pygame.init()
    pygame.display.set_mode((320, 200))
    for name in names:
        loaded = load_map(name, seed=1)
        assert (loaded.terrain.width, loaded.terrain.height) == (WORLD_WIDTH, WORLD_HEIGHT)
        assert loaded.terrain.solid_count() > WORLD_WIDTH * 100
        assert loaded.name == name


def test_menu_navigation_starts_match_and_returns() -> None:
    MenuScene.settings.team_count = 2
    game = Game()
    assert isinstance(game.scene, MenuScene)
    for key in (pygame.K_RIGHT, pygame.K_LEFT, pygame.K_DOWN, pygame.K_DOWN, pygame.K_UP):
        post(pygame.KEYDOWN, key=key)
    post(pygame.MOUSEMOTION, pos=(640, 200), rel=(0, 0), buttons=(0, 0, 0))
    game.step(DT)
    menu = game.scene
    assert isinstance(menu, MenuScene)
    menu.selected = len(menu.items()) - 2  # "Spiel starten"
    post(pygame.KEYDOWN, key=pygame.K_RETURN)
    game.step(DT)
    game.step(DT)
    assert isinstance(game.scene, MatchScene)
    post(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    game.step(DT)
    game.step(DT)
    assert isinstance(game.scene, MenuScene)
    post(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    game.step(DT)
    assert not game.running


@pytest.mark.parametrize("map_name", available_maps())
def test_human_turn_inputs_on_every_map(map_name: str) -> None:
    scene = MatchScene(configs(False, False), map_name, worms_per_team=2, seed=5)
    game = Game(scene)
    match = scene.match
    game.step(DT)
    # Walk, aim, jump, switch weapons, toggle fullscreen and resize the window.
    for key in (pygame.K_2, pygame.K_3, pygame.K_1, pygame.K_RETURN, pygame.K_F11, pygame.K_F11):
        post(pygame.KEYDOWN, key=key)
    post(pygame.VIDEORESIZE, w=900, h=700, size=(900, 700))
    post(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=3)
    post(pygame.MOUSEMOTION, pos=(140, 120), rel=(40, 20), buttons=(0, 0, 1))
    post(pygame.MOUSEBUTTONUP, pos=(140, 120), button=3)
    post(pygame.KEYDOWN, key=pygame.K_p)
    post(pygame.KEYDOWN, key=pygame.K_p)
    for _ in range(20):
        game.step(DT)
    # Charge and fire the bazooka.
    post(pygame.KEYDOWN, key=pygame.K_SPACE)
    for _ in range(10):
        game.step(DT)
    post(pygame.KEYUP, key=pygame.K_SPACE)
    game.step(DT)
    assert match.phase in (Phase.RETREAT, Phase.SETTLING)
    for _ in range(400):
        game.step(DT)
        if match.turn_number > 1 and match.phase == Phase.AIMING:
            break
    assert match.turn_number == 2
    # Second team: airstrike via mouse click, then shotgun on the next turn.
    post(pygame.KEYDOWN, key=pygame.K_4)
    game.step(DT)
    post(pygame.MOUSEBUTTONDOWN, pos=(640, 300), button=1)
    for _ in range(400):
        game.step(DT)
        if match.turn_number > 2 and match.phase == Phase.AIMING:
            break
    assert match.turn_number >= 3
    post(pygame.KEYDOWN, key=pygame.K_3)
    post(pygame.KEYDOWN, key=pygame.K_SPACE)
    for _ in range(30):
        game.step(DT)
    assert any(e.kind == "flash" for e in scene.effects.timed) or match.turn_number >= 3


def test_ai_versus_ai_match_runs_to_the_end() -> None:
    scene = MatchScene(configs(True, True, True), RANDOM_MAP, worms_per_team=1, seed=11)
    scene.ai.think_budget = 1.0
    game = Game(scene)
    match = scene.match
    for frame in range(int(15 * 60 / DT)):
        game.handle_events()
        game.update(DT)
        if frame % 6 == 0:
            game.draw()
        if match.phase == Phase.GAME_OVER:
            break
    assert match.phase == Phase.GAME_OVER
    game.draw()
    post(pygame.KEYDOWN, key=pygame.K_RETURN)
    game.step(DT)
    game.step(DT)
    assert isinstance(game.scene, MenuScene)
