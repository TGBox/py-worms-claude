"""Draws the game world (sky, terrain, worms, projectiles, water) onto the canvas."""

import math
import random

import pygame

from src.core.entities import Worm
from src.core.match import Match, Phase
from src.core.weapons import AimMode
from src.render import fonts
from src.render.camera import Camera
from src.render.effects import Effects
from src.render.terrain_view import TerrainView
from src.settings import COLOR_SKY_BOTTOM, COLOR_SKY_TOP, COLOR_TEXT, COLOR_WATER

WORM_SKIN = (255, 168, 176)
WORM_SKIN_DARK = (214, 120, 132)
PARALLAX = 0.35


def _vertical_gradient(
    size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> pygame.Surface:
    width, height = size
    surface = pygame.Surface(size)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
        surface.fill(color, (0, y, width, 1))
    return surface


class WorldRenderer:
    def __init__(self, match: Match, terrain_view: TerrainView, view_size: tuple[int, int]):
        self.match = match
        self.terrain_view = terrain_view
        self.view_width, self.view_height = view_size
        self.sky = _vertical_gradient(view_size, COLOR_SKY_TOP, COLOR_SKY_BOTTOM)
        self.mountains = self._build_mountains()
        self.water = pygame.Surface((self.view_width, 1), pygame.SRCALPHA)
        self.water.fill((*COLOR_WATER, 190))
        self.time = 0.0

    def _build_mountains(self) -> pygame.Surface:
        world_width = self.match.world.terrain.width
        width = int(world_width * PARALLAX + self.view_width) + 4
        height = 420
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rng = random.Random(4)
        for layer, color in enumerate(((70, 90, 140, 255), (52, 70, 116, 255))):
            points = [(0, height)]
            x = 0
            y = rng.uniform(120, 260) + layer * 60
            while x <= width:
                points.append((x, y))
                x += rng.uniform(40, 110)
                y = min(height - 40, max(60 + layer * 60, y + rng.uniform(-70, 70)))
            points.append((width, height))
            pygame.draw.polygon(surface, color, points)
        return surface

    # ----------------------------------------------------------------- draw
    def draw(self, canvas: pygame.Surface, camera: Camera, effects: Effects, dt: float) -> None:
        self.time += dt
        world = self.match.world
        canvas.blit(self.sky, (0, 0))
        mountain_y = world.water_level - self.mountains.get_height() + 40
        canvas.blit(
            self.mountains, (round(-camera.x * PARALLAX), round((mountain_y - camera.y) * 0.9))
        )

        self.terrain_view.sync()
        canvas.blit(self.terrain_view.surface, (-round(camera.x), -round(camera.y)))

        for worm in world.worms:
            if worm.alive:
                self._draw_worm(canvas, camera, worm)
        for projectile in world.projectiles:
            sx, sy = camera.to_screen(projectile.x, projectile.y)
            if projectile.weapon_key == "grenade":
                pygame.draw.circle(canvas, (40, 110, 40), (sx, sy), 4)
                pygame.draw.circle(canvas, (20, 50, 20), (sx, sy), 4, 1)
                if projectile.fuse is not None:
                    label = fonts.outlined(str(max(1, math.ceil(projectile.fuse))), 18, COLOR_TEXT)
                    canvas.blit(label, label.get_rect(center=(sx, sy - 14)))
            else:
                angle = math.atan2(projectile.vy, projectile.vx)
                tail = (sx - math.cos(angle) * 9, sy - math.sin(angle) * 9)
                pygame.draw.line(canvas, (60, 60, 70), tail, (sx, sy), 5)
                pygame.draw.circle(canvas, (220, 60, 50), (sx, sy), 3)
                effects.smoke_trail(projectile.x - math.cos(angle) * 8, projectile.y)

        effects.draw(canvas, camera)
        self._draw_aim(canvas, camera)
        self._draw_water(canvas, camera)
        for worm in world.worms:
            if worm.alive:
                self._draw_label(canvas, camera, worm)

    def _draw_worm(self, canvas: pygame.Surface, camera: Camera, worm: Worm) -> None:
        sx, sy = camera.to_screen(worm.x, worm.y)
        f = worm.facing
        pygame.draw.ellipse(canvas, WORM_SKIN_DARK, (sx - 8 - f * 2, sy - 1, 14, 9))
        pygame.draw.circle(canvas, WORM_SKIN, (sx + f * 2, sy - 3), 6)
        pygame.draw.circle(canvas, (255, 255, 255), (sx + f * 4, sy - 5), 3)
        pygame.draw.circle(canvas, (20, 20, 20), (sx + f * 5, sy - 5), 1)
        team_color = self.match.teams[worm.team_index].color
        pygame.draw.line(canvas, team_color, (sx - 5, sy + 6), (sx + 5, sy + 6), 2)

    def _draw_label(self, canvas: pygame.Surface, camera: Camera, worm: Worm) -> None:
        sx, sy = camera.to_screen(worm.x, worm.y)
        color = self.match.teams[worm.team_index].color
        hp = fonts.outlined(str(max(0, worm.hp)), 18, color)
        name = fonts.outlined(worm.name, 16, color)
        canvas.blit(hp, hp.get_rect(midbottom=(sx, sy - 12)))
        canvas.blit(name, name.get_rect(midbottom=(sx, sy - 26)))
        match = self.match
        if worm is match.active_worm and match.phase == Phase.AIMING:
            bob = math.sin(self.time * 6) * 3
            top = sy - 52 + bob
            pygame.draw.polygon(canvas, COLOR_TEXT, [(sx - 6, top), (sx + 6, top), (sx, top + 8)])

    def _draw_aim(self, canvas: pygame.Surface, camera: Camera) -> None:
        match = self.match
        worm = match.active_worm
        if match.phase != Phase.AIMING or not worm.alive:
            return
        dx, dy = worm.aim_vector()
        sx, sy = camera.to_screen(worm.x, worm.y)
        if match.weapon.aim not in (AimMode.TARGET_POINT, AimMode.NONE):
            cross = (sx + dx * 46, sy + dy * 46)
            pygame.draw.circle(canvas, (255, 70, 70), cross, 6, 2)
            pygame.draw.circle(canvas, (255, 70, 70), cross, 1)
        if match.charging:
            for i in range(int(match.power * 14)):
                t = i / 14
                color = (255, int(230 - 200 * t), 40)
                center = (sx + dx * (14 + i * 3.2), sy + dy * (14 + i * 3.2))
                pygame.draw.circle(canvas, color, center, 2 + int(t * 4))

    def _draw_water(self, canvas: pygame.Surface, camera: Camera) -> None:
        water_y = self.match.world.water_level - camera.y
        if water_y >= self.view_height:
            return
        top = max(0, int(water_y))
        body = pygame.transform.scale(self.water, (self.view_width, self.view_height - top))
        canvas.blit(body, (0, top))
        points = []
        for x in range(0, self.view_width + 16, 16):
            wave = math.sin((x + camera.x) * 0.03 + self.time * 2.5) * 3
            points.append((x, water_y + wave))
        if len(points) > 1:
            pygame.draw.lines(canvas, (150, 200, 255), False, points, 2)
