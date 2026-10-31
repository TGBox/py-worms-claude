"""Procedural worm animation: segmented body, crawl wave, faces and held weapons.

The core only knows movement states (`WormState`); poses like aiming, hurt or victory are
derived here from the match. All animation data lives in this module.
"""

import math
import random

import pygame

from src.core.entities import Worm, WormState
from src.core.events import Damage, Event
from src.core.match import Match, Phase
from src.core.weapons import AimMode
from src.render.camera import Camera
from src.render.weapon_icons import draw_weapon

SKIN = (255, 168, 176)
SKIN_SHADE = (214, 120, 132)
OUTLINE = (120, 52, 66)
EYE_WHITE = (255, 255, 255)
PUPIL = (20, 20, 24)

# Spine in local coordinates (facing right, worm centre at 0,0), from tail to head.
IDLE_SPINE = ((-8.0, 5.0), (-5.0, 5.5), (-2.0, 4.5), (0.5, 2.0), (2.0, -1.5), (3.0, -5.5))
STRETCH_SPINE = ((-3.0, 6.0), (-2.0, 3.5), (-1.0, 1.0), (0.0, -1.5), (1.0, -4.0), (2.0, -7.0))
RADII = (3.2, 3.8, 4.4, 5.0, 5.6, 6.2)
ARCH = (0.0, 0.6, 1.0, 0.6, 0.2, 0.0)  # how much each segment lifts during the crawl wave
CRAWL_WAVELENGTH = 9.0  # px walked per crawl cycle
BACKFLIP_TIME = 0.75
HURT_TIME = 0.45

POSES = ("idle", "walk", "jump", "high_jump", "backflip", "fall", "aim", "hurt", "victory")


class WormAnimator:
    def __init__(self, match: Match, seed: int = 0) -> None:
        self.match = match
        self.time = 0.0
        self.rng = random.Random(seed)
        self._hurt: dict[int, float] = {}
        self._next_blink: dict[int, float] = {}
        self.drawn_poses: set[str] = set()  # for tests: which poses have been rendered

    # -------------------------------------------------------------- bookkeeping
    def on_event(self, event: Event) -> None:
        if isinstance(event, Damage):
            self._hurt[id(event.worm)] = HURT_TIME

    def update(self, dt: float) -> None:
        self.time += dt
        for key in list(self._hurt):
            self._hurt[key] -= dt
            if self._hurt[key] <= 0:
                del self._hurt[key]

    def pose(self, worm: Worm) -> str:
        match = self.match
        if match.phase == Phase.GAME_OVER and match.winner is match.teams[worm.team_index]:
            return "victory"
        if id(worm) in self._hurt:
            return "hurt"
        state = worm.state
        if state == WormState.WALK:
            return "walk"
        if state in (WormState.JUMP, WormState.HIGH_JUMP, WormState.BACKFLIP, WormState.FALL):
            return state.value
        active = worm is match.active_worm and match.phase == Phase.AIMING
        if active and match.weapon.aim != AimMode.TARGET_POINT:
            return "aim"
        return "idle"

    def _blinking(self, worm: Worm) -> bool:
        key = id(worm)
        due = self._next_blink.get(key)
        if due is None or self.time > due + 0.14:
            self._next_blink[key] = self.time + self.rng.uniform(2.0, 5.0)
            return False
        return self.time >= due

    # ------------------------------------------------------------------ geometry
    def spine(self, worm: Worm, pose: str) -> tuple[list[tuple[float, float]], float]:
        """Local spine points (facing right) and the body rotation for the pose."""
        t = self.time
        rotation = 0.0
        if pose in ("jump", "high_jump", "backflip"):
            points = list(STRETCH_SPINE)
            if pose == "backflip":
                progress = min(1.0, worm.state_time / BACKFLIP_TIME)
                rotation = -2 * math.pi * progress
        elif pose == "walk":
            phase = worm.walk_distance / CRAWL_WAVELENGTH * 2 * math.pi
            s = (1 - math.cos(phase)) / 2  # 0 = stretched, 1 = bunched up (inchworm)
            points = []
            for i, (x, y) in enumerate(IDLE_SPINE):
                pull = 4.0 * s * (1 - i / 5)  # the tail is pulled towards the head
                points.append((x + pull, y - 3.0 * s * ARCH[i]))
        else:
            breathe = math.sin(t * 2.5 + worm.x * 0.1) * 0.6
            points = [(x, y + breathe * i / 5) for i, (x, y) in enumerate(IDLE_SPINE)]
            if pose == "fall":
                points = [
                    (x + math.sin(t * 18 + i) * 1.6 * (1 - i / 5), y)
                    for i, (x, y) in enumerate(points)
                ]
            elif pose == "hurt":
                shake = math.sin(t * 60) * 1.2
                points = [(x + shake, y) for x, y in points]
            elif pose == "aim":
                dx, dy = math.cos(worm.aim), -math.sin(worm.aim)
                hx, hy = points[-1]
                points[-1] = (hx + dx * 1.5, hy + dy * 1.5)
            elif pose == "victory":
                hop = -abs(math.sin(t * 6)) * 6
                points = [(x, y + hop) for x, y in points]
        return points, rotation

    def _to_screen(
        self, worm: Worm, camera: Camera, local: tuple[float, float], rotation: float
    ) -> tuple[float, float]:
        x, y = local[0] * worm.facing, local[1]
        if rotation:
            angle = rotation * worm.facing
            cos, sin = math.cos(angle), math.sin(angle)
            x, y = x * cos - y * sin, x * sin + y * cos
        sx, sy = camera.to_screen(worm.x, worm.y)
        return (sx + x, sy + y)

    # ---------------------------------------------------------------------- draw
    def draw(self, canvas: pygame.Surface, camera: Camera, worm: Worm) -> None:
        pose = self.pose(worm)
        self.drawn_poses.add(pose)
        points, rotation = self.spine(worm, pose)
        screen = [self._to_screen(worm, camera, p, rotation) for p in points]
        for (sx, sy), radius in zip(screen, RADII):
            pygame.draw.circle(canvas, OUTLINE, (sx, sy), radius + 1)
        for i, ((sx, sy), radius) in enumerate(zip(screen, RADII)):
            pygame.draw.circle(canvas, SKIN_SHADE if i < 2 else SKIN, (sx, sy), radius)
        # Team-coloured collar between body and head.
        team_color = self.match.teams[worm.team_index].color
        collar = screen[3]
        pygame.draw.circle(canvas, team_color, (collar[0], collar[1]), 2)
        self._draw_face(canvas, camera, worm, pose, points[-1], rotation)
        if pose == "aim":
            dx, dy = math.cos(worm.aim) * worm.facing, -math.sin(worm.aim)
            hand = self._to_screen(worm, camera, (points[3][0] + 1.5, points[3][1]), rotation)
            angle = math.atan2(dy, dx)
            draw_weapon(canvas, self.match.weapon.key, (hand[0] + dx * 2, hand[1] + dy * 2), angle)

    def _draw_face(
        self,
        canvas: pygame.Surface,
        camera: Camera,
        worm: Worm,
        pose: str,
        head: tuple[float, float],
        rotation: float,
    ) -> None:
        hx, hy = head

        def at(dx: float, dy: float) -> tuple[float, float]:
            return self._to_screen(worm, camera, (hx + dx, hy + dy), rotation)

        scared = pose not in ("victory", "hurt") and self.match.world.danger_near(worm)
        if pose == "aim":
            look = (math.cos(worm.aim), -math.sin(worm.aim))
        elif scared:
            look = (-0.6, -0.3)  # glance back at the danger
        else:
            look = (1.0, 0.0)
        eyes = ((-1.0, -2.6), (2.4, -2.2))
        if pose == "victory":
            for ex, ey in eyes:
                pygame.draw.lines(
                    canvas,
                    PUPIL,
                    False,
                    [at(ex - 1.5, ey + 0.8), at(ex, ey - 0.8), at(ex + 1.5, ey + 0.8)],
                )
            pygame.draw.lines(canvas, PUPIL, False, [at(-0.5, 1.5), at(1.5, 2.8), at(3.5, 1.5)])
            return
        if pose == "hurt":
            for ex, ey in eyes:
                pygame.draw.line(canvas, PUPIL, at(ex - 1.3, ey - 1.3), at(ex + 1.3, ey + 1.3))
                pygame.draw.line(canvas, PUPIL, at(ex - 1.3, ey + 1.3), at(ex + 1.3, ey - 1.3))
            pygame.draw.circle(canvas, PUPIL, at(1.5, 2.2), 1)
            return
        if self._blinking(worm) and not scared:
            for ex, ey in eyes:
                pygame.draw.line(canvas, PUPIL, at(ex - 1.6, ey), at(ex + 1.6, ey))
        else:
            white = 2.9 if scared else 2.3
            pupil = 0.8 if scared else 1.1
            for ex, ey in eyes:
                pygame.draw.circle(canvas, EYE_WHITE, at(ex, ey), white)
                pygame.draw.circle(canvas, PUPIL, at(ex + look[0] * 1.0, ey + look[1] * 1.0), pupil)
        if scared:
            pygame.draw.circle(canvas, PUPIL, at(1.2, 2.4), 1.3, 1)  # "o" mouth
        else:
            pygame.draw.line(canvas, OUTLINE, at(0.0, 2.0), at(2.6, 2.0))
