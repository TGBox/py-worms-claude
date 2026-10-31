"""In-game scene: input handling, AI, fixed-step simulation, camera and drawing."""

import pygame

from src.controls import WEAPON_ACTIONS, Action, get_controls
from src.core.ai import AIController
from src.core.constants import AIM_SPEED, SIM_DT
from src.core.match import Match, Phase, TeamConfig
from src.core.scheme import GameScheme
from src.core.weapons import AimMode
from src.jump_input import JumpBuffer
from src.maps import RANDOM_MAP, load_map
from src.render import fonts
from src.render.camera import Camera
from src.render.effects import Effects
from src.render.hud import Hud
from src.render.terrain_view import TerrainView
from src.render.world_renderer import WorldRenderer
from src.scenes.base import Scene
from src.settings import COLOR_ACCENT, COLOR_MUTED, COLOR_TEXT, SCREEN_HEIGHT, SCREEN_WIDTH

HELP = (
    "Pfeile/WASD: Laufen & Zielen  ·  1-4: Waffe",
    "Enter: Sprung  ·  Rücktaste: Hochsprung  ·  2×: Salto",
    "P: Pause  ·  ESC: Menü",
)
FREE_CAMERA_TIME = 2.5
MAX_STEPS_PER_FRAME = 5


class MatchScene(Scene):
    def __init__(
        self, configs: list[TeamConfig], map_name: str, scheme: GameScheme, seed: int
    ) -> None:
        super().__init__()
        water_level = scheme.terrain.water_level
        loaded = load_map(map_name, seed, water_level)
        try:
            match = Match.create(configs, loaded.terrain, seed, scheme)
        except RuntimeError:  # map too small for all worms: use a generated island instead
            loaded = load_map(RANDOM_MAP, seed, water_level)
            match = Match.create(configs, loaded.terrain, seed, scheme)
        self.match = match
        self.seed = seed
        self.view_size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        terrain = match.world.terrain
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, terrain.width, terrain.height)
        self.camera.center_on(match.active_worm.x, match.active_worm.y)
        self.renderer = WorldRenderer(
            match, TerrainView(terrain, loaded.texture, seed), self.view_size
        )
        self.hud = Hud(match, self.view_size)
        self.effects = Effects(seed)
        self.ai = AIController(match)
        self.controls = get_controls()
        self.jump_buffer = JumpBuffer()
        self.paused = False
        self.mouse_pos = (0, 0)
        self.dragging = False
        self.free_camera = 0.0
        self.last_dt = 0.0
        self._accumulator = 0.0

    @property
    def human_turn(self) -> bool:
        return not self.match.active_team.is_ai and self.match.phase != Phase.GAME_OVER

    # -------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        match = self.match
        controls = self.controls
        if event.type == pygame.KEYDOWN:
            key = event.key
            if controls.matches(Action.BACK, key):
                self._back_to_menu()
            elif match.phase == Phase.GAME_OVER:
                if controls.matches(Action.CONFIRM, key):
                    self._back_to_menu()
            elif controls.matches(Action.PAUSE, key):
                self.paused = not self.paused
            elif self.paused or not self.human_turn:
                return
            elif controls.matches(Action.JUMP, key) or controls.matches(Action.HIGH_JUMP, key):
                kind = "forward" if controls.matches(Action.JUMP, key) else "high"
                if self.jump_buffer.press(kind) == "backflip":
                    match.jump("backflip")
            elif controls.matches(Action.FIRE, key):
                if match.weapon.aim == AimMode.CHARGED:
                    match.start_charge()
                elif match.weapon.aim in (AimMode.ANGLE, AimMode.NONE):
                    match.fire_direct()
            else:
                for index, action in enumerate(WEAPON_ACTIONS):
                    if controls.matches(action, key):
                        match.select_weapon(index)
        elif event.type == pygame.KEYUP and controls.matches(Action.FIRE, event.key):
            if self.human_turn and not self.paused:
                match.release_charge()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.dragging = True
            elif (
                event.button == 1
                and self.human_turn
                and not self.paused
                and match.weapon.aim == AimMode.TARGET_POINT
            ):
                world_x, _ = self.camera.to_world(*event.pos)
                match.fire_at(world_x)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.camera.pan(-event.rel[0], -event.rel[1])
            self.free_camera = FREE_CAMERA_TIME

    def _back_to_menu(self) -> None:
        from src.scenes.menu import MainMenuScene  # avoid an import cycle

        self.next_scene = MainMenuScene()

    # -------------------------------------------------------------- update
    def update(self, dt: float, mouse_pos: tuple[int, int]) -> None:
        self.mouse_pos = mouse_pos
        self.last_dt = 0.0 if self.paused else dt
        if self.paused:
            return
        # Fixed simulation step: identical results for any frame rate (replays, determinism).
        self._accumulator = min(self._accumulator + dt, SIM_DT * MAX_STEPS_PER_FRAME)
        while self._accumulator >= SIM_DT:
            self._accumulator -= SIM_DT
            self._step(SIM_DT)

        world = self.match.world
        for event in world.bus.drain():
            self.effects.spawn(event)
            self.renderer.animator.on_event(event)
        self.effects.update(dt, world.terrain, world.water_level)
        self._update_camera(dt)

    def _step(self, dt: float) -> None:
        match = self.match
        if not (self.human_turn and match.can_move):
            self.jump_buffer.clear()
        kind = self.jump_buffer.update(dt)
        if kind is not None:
            match.jump(kind)
        if self.human_turn and match.can_move:
            pressed = pygame.key.get_pressed()
            held = self.controls.held
            if held(Action.MOVE_LEFT, pressed):
                match.move(-1, dt)
            elif held(Action.MOVE_RIGHT, pressed):
                match.move(1, dt)
            if held(Action.AIM_UP, pressed):
                match.aim(AIM_SPEED * dt)
            elif held(Action.AIM_DOWN, pressed):
                match.aim(-AIM_SPEED * dt)
        self.ai.update(dt)
        match.update(dt)

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
            and match.weapon.aim == AimMode.TARGET_POINT
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
