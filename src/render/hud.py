"""Screen-space overlay: timer, teams, weapons, wind and messages (German UI)."""

import math

import pygame

from src.core.match import Match, Phase
from src.core.weapons import WEAPONS, FireMode
from src.render import fonts
from src.settings import COLOR_ACCENT, COLOR_MUTED, COLOR_PRIMARY, COLOR_TEXT, WORM_MAX_HP

PANEL = (14, 17, 26, 200)


def _panel(canvas: pygame.Surface, rect: pygame.Rect) -> None:
    surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surface, PANEL, surface.get_rect(), border_radius=8)
    canvas.blit(surface, rect.topleft)


class Hud:
    def __init__(self, match: Match, view_size: tuple[int, int]) -> None:
        self.match = match
        self.width, self.height = view_size

    def draw(self, canvas: pygame.Surface, ai_thinking: bool) -> None:
        self._draw_turn_info(canvas, ai_thinking)
        self._draw_teams(canvas)
        self._draw_weapons(canvas)
        self._draw_wind(canvas)
        if self.match.phase == Phase.GAME_OVER:
            self._draw_game_over(canvas)

    def _draw_turn_info(self, canvas: pygame.Surface, ai_thinking: bool) -> None:
        match = self.match
        if match.phase == Phase.GAME_OVER:
            return
        team = match.active_team
        rect = pygame.Rect(self.width // 2 - 170, 10, 340, 64)
        _panel(canvas, rect)
        title = fonts.text(f"{team.name}: {match.active_worm.name}", 28, team.color)
        canvas.blit(title, title.get_rect(midtop=(rect.centerx, rect.top + 8)))
        if match.phase == Phase.AIMING:
            seconds = max(0, math.ceil(match.turn_timer))
            color = COLOR_ACCENT if seconds <= 5 else COLOR_TEXT
            status = f"{seconds} s"
            if ai_thinking:
                status += "  ·  KI denkt nach ..."
        elif match.phase == Phase.RETREAT:
            color, status = COLOR_PRIMARY, f"Rückzug! {max(0, math.ceil(match.phase_timer))} s"
        else:
            color, status = COLOR_MUTED, "Warte ..."
        line = fonts.text(status, 24, color)
        canvas.blit(line, line.get_rect(midtop=(rect.centerx, rect.top + 36)))

    def _draw_teams(self, canvas: pygame.Surface) -> None:
        teams = self.match.teams
        bar_width = 220
        rect = pygame.Rect(self.width // 2 - bar_width // 2 - 90, 0, bar_width + 180, 0)
        rect.height = 12 + 22 * len(teams)
        rect.bottom = self.height - 10
        _panel(canvas, rect)
        full = max(1, max(len(t.worms) for t in teams) * WORM_MAX_HP)
        for i, team in enumerate(teams):
            y = rect.top + 8 + i * 22
            name = fonts.text(team.name, 20, team.color if team.alive else COLOR_MUTED)
            canvas.blit(name, (rect.left + 10, y))
            width = int(bar_width * team.total_hp / full)
            pygame.draw.rect(canvas, (40, 44, 56), (rect.left + 140, y + 2, bar_width, 14), 0, 4)
            if width > 0:
                pygame.draw.rect(canvas, team.color, (rect.left + 140, y + 2, width, 14), 0, 4)
            hp = fonts.text(str(team.total_hp), 18, COLOR_TEXT)
            canvas.blit(hp, (rect.left + 146 + bar_width, y + 2))

    def _draw_weapons(self, canvas: pygame.Surface) -> None:
        match = self.match
        rect = pygame.Rect(10, 0, 210, 18 + 26 * len(WEAPONS))
        rect.bottom = self.height - 10
        _panel(canvas, rect)
        team = match.active_team
        for i, weapon in enumerate(WEAPONS):
            y = rect.top + 10 + i * 26
            ammo = team.ammo.get(weapon.key, -1)
            selected = i == team.weapon_index
            if selected:
                pygame.draw.rect(
                    canvas, (56, 70, 100), (rect.left + 4, y - 3, rect.width - 8, 24), 0, 5
                )
            color = COLOR_MUTED if ammo == 0 else (COLOR_TEXT if selected else (200, 205, 215))
            label = fonts.text(f"{i + 1}  {weapon.name}", 22, color)
            canvas.blit(label, (rect.left + 12, y))
            count = fonts.text("" if ammo < 0 else f"{ammo}x", 20, COLOR_MUTED)
            canvas.blit(count, count.get_rect(topright=(rect.right - 12, y + 2)))
        if match.phase == Phase.AIMING and not team.is_ai:
            hint = {
                FireMode.CHARGED: "Leertaste halten zum Laden",
                FireMode.DIRECT: "Leertaste: Schießen",
                FireMode.TARGETED: "Linksklick: Ziel wählen",
            }[match.weapon.mode]
            label = fonts.outlined(hint, 20, COLOR_TEXT)
            canvas.blit(label, (rect.left + 4, rect.top - 24))

    def _draw_wind(self, canvas: pygame.Surface) -> None:
        wind = self.match.world.wind
        rect = pygame.Rect(self.width - 210, self.height - 58, 200, 48)
        _panel(canvas, rect)
        label = fonts.text("Wind", 20, COLOR_MUTED)
        canvas.blit(label, (rect.left + 10, rect.top + 6))
        center = rect.centerx + 20
        bar_y = rect.top + 30
        pygame.draw.line(canvas, (60, 66, 80), (center - 70, bar_y), (center + 70, bar_y), 8)
        end = center + int(70 * wind)
        if abs(wind) > 0.01:
            color = COLOR_PRIMARY if abs(wind) < 0.6 else COLOR_ACCENT
            pygame.draw.line(canvas, color, (center, bar_y), (end, bar_y), 8)
            tip = 1 if wind > 0 else -1
            pygame.draw.polygon(
                canvas, color, [(end + tip * 8, bar_y), (end, bar_y - 7), (end, bar_y + 7)]
            )
        pygame.draw.line(canvas, COLOR_TEXT, (center, bar_y - 8), (center, bar_y + 8), 2)

    def _draw_game_over(self, canvas: pygame.Surface) -> None:
        shade = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        shade.fill((8, 10, 16, 150))
        canvas.blit(shade, (0, 0))
        winner = self.match.winner
        if winner is None:
            title = fonts.outlined("Unentschieden!", 72, COLOR_TEXT)
        else:
            title = fonts.outlined(f"{winner.name} gewinnt!", 72, winner.color)
        canvas.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 30)))
        hint = fonts.text("Enter: Zurück zum Menü  ·  ESC: Beenden", 28, COLOR_TEXT)
        canvas.blit(hint, hint.get_rect(center=(self.width // 2, self.height // 2 + 30)))
