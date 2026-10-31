"""Purely cosmetic visual effects driven by world events."""

import math
import random
from dataclasses import dataclass

import pygame

from src.core.constants import GRAVITY
from src.core.events import (
    Damage,
    Event,
    Explosion,
    Splash,
    Tracer,
    WormDied,
    WormDrowned,
)
from src.core.terrain import Terrain
from src.render import fonts
from src.render.camera import Camera
from src.settings import COLOR_SOIL, COLOR_TEXT


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    size: float
    gravity: float = 1.0


@dataclass
class TimedEffect:
    kind: str  # flash | tracer | number
    x: float
    y: float
    life: float
    max_life: float
    radius: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    value: int = 0


@dataclass
class Gravestone:
    x: float
    y: float


class Effects:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.particles: list[Particle] = []
        self.timed: list[TimedEffect] = []
        self.gravestones: list[Gravestone] = []

    def spawn(self, event: Event) -> None:
        rng = self.rng
        if isinstance(event, Explosion):
            r = event.radius
            self.timed.append(TimedEffect("flash", event.x, event.y, 0.35, 0.35, radius=r))
            for _ in range(int(r * 1.2)):
                angle = rng.uniform(0, math.tau)
                speed = rng.uniform(60, 260) * (r / 40)
                color = rng.choice((COLOR_SOIL, (90, 60, 35), (150, 105, 60)))
                self.particles.append(
                    Particle(
                        event.x,
                        event.y,
                        math.cos(angle) * speed,
                        math.sin(angle) * speed - 80,
                        life := rng.uniform(0.5, 1.2),
                        life,
                        color,
                        rng.uniform(1.5, 3.5),
                    )
                )
            for _ in range(int(r / 3)):
                self.particles.append(
                    Particle(
                        event.x + rng.uniform(-r / 2, r / 2),
                        event.y + rng.uniform(-r / 2, r / 2),
                        rng.uniform(-20, 20),
                        rng.uniform(-60, -20),
                        life := rng.uniform(0.8, 1.6),
                        life,
                        (rng.randint(60, 90),) * 3,
                        rng.uniform(5, 10),
                        gravity=-0.05,
                    )
                )
        elif isinstance(event, Damage):
            self.timed.append(TimedEffect("number", event.x, event.y, 1.4, 1.4, value=event.amount))
        elif isinstance(event, Tracer):
            self.timed.append(
                TimedEffect("tracer", event.x, event.y, 0.25, 0.25, x2=event.x2, y2=event.y2)
            )
        elif isinstance(event, (Splash, WormDrowned)):
            for _ in range(24):
                self.particles.append(
                    Particle(
                        event.x,
                        event.y,
                        rng.uniform(-70, 70),
                        rng.uniform(-260, -90),
                        life := rng.uniform(0.4, 0.9),
                        life,
                        (120, 170, 230),
                        rng.uniform(1.5, 3),
                    )
                )
        elif isinstance(event, WormDied):
            self.gravestones.append(Gravestone(event.x, event.y))

    def smoke_trail(self, x: float, y: float) -> None:
        if self.rng.random() < 0.6:
            self.particles.append(
                Particle(x, y, 0, -10, 0.6, 0.6, (200, 200, 200), self.rng.uniform(2, 4), -0.02)
            )

    def update(self, dt: float, terrain: Terrain, water_level: float) -> None:
        for p in self.particles:
            p.vy += GRAVITY * p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for effect in self.timed:
            effect.life -= dt
            if effect.kind == "number":
                effect.y -= 25 * dt
        self.timed = [e for e in self.timed if e.life > 0]
        for stone in self.gravestones:  # let gravestones drop when the ground is blown away
            if not terrain.is_solid(stone.x, stone.y + 8) and stone.y < water_level + 20:
                stone.y += 120 * dt

    def draw(self, canvas: pygame.Surface, camera: Camera) -> None:
        for stone in self.gravestones:
            sx, sy = camera.to_screen(stone.x, stone.y)
            pygame.draw.rect(canvas, (150, 150, 160), (sx - 5, sy - 6, 10, 14), border_radius=4)
            pygame.draw.line(canvas, (90, 90, 100), (sx, sy - 3), (sx, sy + 4), 2)
            pygame.draw.line(canvas, (90, 90, 100), (sx - 3, sy - 1), (sx + 3, sy - 1), 2)
        for effect in self.timed:
            t = effect.life / effect.max_life
            sx, sy = camera.to_screen(effect.x, effect.y)
            if effect.kind == "flash":
                radius = int(effect.radius * (1.25 - 0.5 * t))
                glow = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 200, 80, int(200 * t)), (radius, radius), radius)
                pygame.draw.circle(
                    glow, (255, 255, 220, int(255 * t)), (radius, radius), max(1, radius // 2)
                )
                canvas.blit(glow, (sx - radius, sy - radius))
            elif effect.kind == "tracer":
                end = camera.to_screen(effect.x2, effect.y2)
                color = (255, int(200 + 55 * t), 120)
                pygame.draw.line(canvas, color, (sx, sy), end, max(1, int(3 * t)))
            elif effect.kind == "number":
                label = fonts.outlined(f"-{effect.value}", 24, COLOR_TEXT)
                canvas.blit(label, label.get_rect(center=(sx, sy)))
        for p in self.particles:
            sx, sy = camera.to_screen(p.x, p.y)
            pygame.draw.circle(canvas, p.color, (sx, sy), max(1, int(p.size)))
