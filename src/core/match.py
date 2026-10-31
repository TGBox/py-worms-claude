"""Turn-based match rules on top of the world simulation."""

import random
from dataclasses import dataclass, field
from enum import Enum

from src.core.entities import Worm
from src.core.terrain import Terrain
from src.core.weapons import WEAPONS, FireMode, Weapon
from src.core.world import World
from src.settings import (
    AIM_MAX,
    AIM_MIN,
    CHARGE_TIME,
    RETREAT_TIME,
    SETTLE_MIN_TIME,
    TURN_TIME,
    WATER_LEVEL,
    WORM_NAMES,
    WORMS_PER_TEAM,
)

MAX_DT = 1 / 30


class Phase(Enum):
    AIMING = "aiming"  # active worm may move, aim and fire
    RETREAT = "retreat"  # shot fired, short time to move away
    SETTLING = "settling"  # waiting for everything to come to rest
    GAME_OVER = "game_over"


@dataclass
class TeamConfig:
    name: str
    color: tuple[int, int, int]
    is_ai: bool = False


@dataclass(eq=False)
class Team:
    name: str
    color: tuple[int, int, int]
    is_ai: bool
    worms: list[Worm]
    ammo: dict[str, int] = field(default_factory=dict)
    next_worm: int = 0
    weapon_index: int = 0

    @property
    def alive(self) -> bool:
        return any(w.alive for w in self.worms)

    @property
    def total_hp(self) -> int:
        return sum(max(0, w.hp) for w in self.worms if w.alive)


class Match:
    def __init__(self, world: World, teams: list[Team], rng: random.Random) -> None:
        self.world = world
        self.teams = teams
        self.rng = rng
        self.phase = Phase.SETTLING
        self.team_index = -1
        self.active_worm: Worm = teams[0].worms[0]
        self.turn_timer = TURN_TIME
        self.phase_timer = 0.0
        self.power = 0.0
        self.charging = False
        self.winner: Team | None = None
        self.turn_number = 0
        self._start_next_turn()

    @classmethod
    def create(
        cls,
        configs: list[TeamConfig],
        terrain: Terrain,
        seed: int,
        worms_per_team: int = WORMS_PER_TEAM,
        water_level: float = WATER_LEVEL,
    ) -> "Match":
        rng = random.Random(seed)
        world = World(terrain, water_level)
        positions = world.spawn_positions(len(configs) * worms_per_team, rng)
        rng.shuffle(positions)
        names = list(WORM_NAMES)
        rng.shuffle(names)
        teams = []
        for team_index, config in enumerate(configs):
            worms = []
            for _ in range(worms_per_team):
                x, y = positions.pop()
                name = names.pop() if names else f"Wurm {len(world.worms) + 1}"
                facing = 1 if x < terrain.width / 2 else -1
                worms.append(world.add_worm(Worm(name, team_index, x, y, facing=facing)))
            ammo = {w.key: w.ammo for w in WEAPONS}
            teams.append(Team(config.name, config.color, config.is_ai, worms, ammo))
        return cls(world, teams, rng)

    # ------------------------------------------------------------ queries
    @property
    def active_team(self) -> Team:
        return self.teams[self.team_index]

    @property
    def weapon(self) -> Weapon:
        return WEAPONS[self.active_team.weapon_index]

    def has_ammo(self, weapon: Weapon) -> bool:
        return self.active_team.ammo.get(weapon.key, -1) != 0

    @property
    def can_act(self) -> bool:
        return self.phase == Phase.AIMING and self.active_worm.alive

    @property
    def can_move(self) -> bool:
        return self.phase in (Phase.AIMING, Phase.RETREAT) and self.active_worm.alive

    # ----------------------------------------------------------- commands
    def select_weapon(self, index: int) -> None:
        valid = 0 <= index < len(WEAPONS)
        if self.can_act and not self.charging and valid and self.has_ammo(WEAPONS[index]):
            self.active_team.weapon_index = index

    def move(self, direction: int, dt: float) -> None:
        if self.can_move and not self.charging:
            self.world.walk(self.active_worm, direction, dt)

    def face(self, direction: int) -> None:
        if self.can_move and not self.charging:
            self.active_worm.facing = direction

    def jump(self) -> None:
        if self.can_move and not self.charging:
            self.world.jump(self.active_worm)

    def aim(self, delta: float) -> None:
        if self.can_act:
            worm = self.active_worm
            worm.aim = max(AIM_MIN, min(AIM_MAX, worm.aim + delta))

    def start_charge(self) -> None:
        if self.can_act and self.weapon.mode == FireMode.CHARGED and not self.charging:
            self.charging = True
            self.power = 0.0

    def release_charge(self) -> None:
        if not self.charging or not self.can_act:
            return
        self.charging = False
        self.world.fire_projectile(self.active_worm, self.weapon, self.power)
        self._after_fire()

    def fire_direct(self) -> None:
        if self.can_act and self.weapon.mode == FireMode.DIRECT:
            self.world.fire_hitscan(self.active_worm, self.weapon)
            self._after_fire()

    def fire_at(self, target_x: float) -> None:
        if self.can_act and self.weapon.mode == FireMode.TARGETED:
            self.world.launch_airstrike(target_x, self.weapon, self.active_worm)
            self._after_fire()

    def skip_turn(self) -> None:
        if self.can_act:
            self._begin_settling()

    # ------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        dt = min(dt, MAX_DT)
        self.world.update(dt)
        if self.phase == Phase.GAME_OVER:
            return
        worm = self.active_worm
        worm_out = not worm.alive or worm.damage_taken > 0
        if self.phase in (Phase.AIMING, Phase.RETREAT) and worm_out:
            self._begin_settling()
            return
        if self.phase == Phase.AIMING:
            self.turn_timer -= dt
            if self.charging:
                self.power = min(1.0, self.power + dt / CHARGE_TIME)
                if self.power >= 1.0:
                    self.release_charge()
            if self.phase == Phase.AIMING and self.turn_timer <= 0:
                self._begin_settling()
        elif self.phase == Phase.RETREAT:
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self._begin_settling()
        elif self.phase == Phase.SETTLING:
            self.phase_timer -= dt
            if self.phase_timer <= 0 and self.world.is_settled():
                dying = [w for w in self.world.worms if w.alive and w.hp <= 0]
                if dying:
                    for doomed in dying:
                        self.world.kill_worm(doomed)
                    self.phase_timer = SETTLE_MIN_TIME
                else:
                    self._start_next_turn()

    # ------------------------------------------------------------ helpers
    def _after_fire(self) -> None:
        team = self.active_team
        weapon = self.weapon
        if team.ammo.get(weapon.key, -1) > 0:
            team.ammo[weapon.key] -= 1
        if not self.has_ammo(weapon):
            team.weapon_index = 0
        self.charging = False
        self.phase = Phase.RETREAT
        self.phase_timer = RETREAT_TIME

    def _begin_settling(self) -> None:
        self.phase = Phase.SETTLING
        self.phase_timer = SETTLE_MIN_TIME
        self.charging = False
        self.power = 0.0

    def _start_next_turn(self) -> None:
        alive_teams = [t for t in self.teams if t.alive]
        if len(alive_teams) <= 1:
            self.phase = Phase.GAME_OVER
            self.winner = alive_teams[0] if alive_teams else None
            return
        count = len(self.teams)
        for offset in range(1, count + 1):
            index = (self.team_index + offset) % count
            if self.teams[index].alive:
                self.team_index = index
                break
        team = self.active_team
        for offset in range(len(team.worms)):
            index = (team.next_worm + offset) % len(team.worms)
            if team.worms[index].alive:
                self.active_worm = team.worms[index]
                team.next_worm = (index + 1) % len(team.worms)
                break
        for worm in self.world.worms:
            worm.damage_taken = 0
        self.world.wind = round(self.rng.uniform(-1.0, 1.0), 2)
        self.turn_timer = TURN_TIME
        self.power = 0.0
        self.charging = False
        self.phase = Phase.AIMING
        self.turn_number += 1
