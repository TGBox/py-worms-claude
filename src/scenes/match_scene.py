"""In-game scene: input handling, AI, simulation, camera and drawing."""

import random

import pygame

from src.core.ai import AIController
from src.core.match import Match, Phase, TeamConfig
from src.core.weapons import FireMode
from src.maps import RANDOM_MAP, load_map
from src.render import fonts
from src.render.camera import Camera
from src.render.effects import Effects
from src.render.hud import Hud
from src.render.terrain_view import TerrainView
from src.render.world_renderer import WorldRenderer
from src.scenes.base import Scene
from src.settings import (
    AIM_SPEED,
    COLOR_ACCENT,
    COLOR_MUTED,
    COLOR_TEXT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WATER_LEVEL,
)

HELP = (
    "Pfeile/WASD: Laufen & Zielen  ·  Enter: Springen",
    "1-4: Waffe  ·  P: Pause  ·  ESC: Menü",
)
FREE_CAMERA_TIME = 2.5


class MatchScene(Scene):
    def __init__(
        self, configs: list[TeamConfig], map_name: str, worms_per_team: int, seed: int
    ) -> None:
        super().__init__()
        loaded = load_map(map_name, seed)
        try:
            match = Match.create(configs, loaded.terrain, seed, worms_per_team, WATER_LEVEL)
        except RuntimeError:  # map too small for all worms: use a generated island instead
            loaded = load_map(RANDOM_MAP, seed)
            match = Match.create(configs, loaded.terrain, seed, worms_per_team, WATER_LEVEL)
        self.match = match
        self.view_size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        terrain = match.world.terrain
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, terrain.width, terrain.height)
        self.camera.center_on(match.active_worm.x, match.active_worm.y)
        self.renderer = WorldRenderer(
            match, TerrainView(terrain, loaded.texture, seed), self.view_size
        )
        self.hud = Hud(match, self.view_size)
        self.effects = Effects(seed)
        self.ai = AIController(match, random.Random(seed))
        self.paused = False
        self.mouse_pos = (0, 0)
        self.dragging = False
        self.free_camera = 0.0
        self.last_dt = 0.0

    @property
    def human_turn(self) -> bool:
        return not self.match.active_team.is_ai and self.match.phase != Phase.GAME_OVER

    # -------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        match = self.match
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._back_to_menu()
            elif event.key == pygame.K_p and match.phase != Phase.GAME_OVER:
                self.paused = not self.paused
            elif match.phase == Phase.GAME_OVER:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self._back_to_menu()
            elif self.paused or not self.human_turn:
                return
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                match.jump()
            elif pygame.K_1 <= event.key <= pygame.K_4:
                match.select_weapon(event.key - pygame.K_1)
            elif event.key == pygame.K_SPACE:
                if match.weapon.mode == FireMode.CHARGED:
                    match.start_charge()
                elif match.weapon.mode == FireMode.DIRECT:
                    match.fire_direct()
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            if self.human_turn and not self.paused:
                match.release_charge()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.dragging = True
            elif (
                event.button == 1
                and self.human_turn
                and not self.paused
                and match.weapon.mode == FireMode.TARGETED
            ):
                world_x, _ = self.camera.to_world(*event.pos)
                match.fire_at(world_x)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.camera.pan(-event.rel[0], -event.rel[1])
            self.free_camera = FREE_CAMERA_TIME

    def _back_to_menu(self) -> None:
        from src.scenes.menu import MenuScene  # avoid an import cycle

        self.next_scene = MenuScene()

    # -------------------------------------------------------------- update
    def update(self, dt: float, mouse_pos: tuple[int, int]) -> None:
        self.mouse_pos = mouse_pos
        self.last_dt = 0.0 if self.paused else dt
        if self.paused:
            return
        match = self.match
        if self.human_turn and match.can_move:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                match.move(-1, dt)
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                match.move(1, dt)
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                match.aim(AIM_SPEED * dt)
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                match.aim(-AIM_SPEED * dt)
        self.ai.update(dt)
        match.update(dt)

        world = match.world
        for event in world.events:
            self.effects.spawn(event)
        world.events.clear()
        self.effects.update(dt, world.terrain, world.water_level)
        self._update_camera(dt)

    def _update_camera(self, dt: float) -> None:
        match = self.match
        if self.free_camera > 0:
            self.free_camera -= dt
            if not match.world.projectiles:
                return
        if match.world.projectiles:
            target = match.world.projectiles[0]
            self.camera.follow(target.x, target.y, dt, stiffness=6.0)
        elif match.active_worm.alive:
            self.camera.follow(match.active_worm.x, match.active_worm.y, dt)

    # ---------------------------------------------------------------- draw
    def draw(self, canvas: pygame.Surface) -> None:
        self.renderer.draw(canvas, self.camera, self.effects, self.last_dt)
        match = self.match
        if (
            self.human_turn
            and match.phase == Phase.AIMING
            and match.weapon.mode == FireMode.TARGETED
        ):
            mx, my = self.mouse_pos
            pygame.draw.line(canvas, COLOR_ACCENT, (mx, 0), (mx, my - 12), 1)
            pygame.draw.circle(canvas, COLOR_ACCENT, (mx, my), 12, 2)
            pygame.draw.line(canvas, COLOR_ACCENT, (mx - 16, my), (mx + 16, my), 1)
        self.hud.draw(canvas, self.ai.thinking)
        for index, line in enumerate(HELP):
            canvas.blit(fonts.outlined(line, 20, COLOR_MUTED), (10, 8 + index * 18))
        if self.paused:
            label = fonts.outlined("Pausiert  (P: Weiter)", 64, COLOR_TEXT)
            canvas.blit(
                label, label.get_rect(center=(canvas.get_width() // 2, canvas.get_height() // 2))
            )
