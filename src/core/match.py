"""Turn-based match rules on top of the world simulation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.constants import AIM_MAX, AIM_MIN, CHARGE_TIME, DEFAULT_WORM_NAMES, SETTLE_MIN_TIME
from src.core.entities import JumpKind, Worm
from src.core.events import GameOver, TurnStarted, WeaponFired
from src.core.rng import RngStreams
from src.core.scheme import GameScheme
from src.core.terrain import Terrain
from src.core.weapons import AimMode, FireContext, WeaponDef, all_weapons, get_behavior, get_weapon
from src.core.world import World

MAX_DT = 1 / 30

# Commands that change the match; recorded for replays and applied by name.
COMMANDS = frozenset(
    {
        "select_weapon",
        "select_weapon_key",
        "move",
        "face",
        "jump",
        "aim",
        "start_charge",
        "release_charge",
        "fire_direct",
        "fire_at",
        "skip_turn",
    }
)


class Phase(Enum):
    AIMING = "aiming"  # active worm may move, aim and fire
    RETREAT = "retreat"  # shot fired, short time to move away
    SETTLING = "settling"  # waiting for everything to come to rest
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class Command:
    tick: int
    name: str
    args: tuple[Any, ...] = ()


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
    weapon_key: str = "bazooka"

    @property
    def alive(self) -> bool:
        return any(w.alive for w in self.worms)

    @property
    def total_hp(self) -> int:
        return sum(max(0, w.hp) for w in self.worms if w.alive)


class Match:
    def __init__(
        self,
        world: World,
        teams: list[Team],
        rng: RngStreams,
        scheme: GameScheme | None = None,
    ) -> None:
        self.world = world
        self.teams = teams
        self.rng = rng
        self.scheme = scheme or world.scheme
        for team in teams:
            for weapon in all_weapons():
                team.ammo.setdefault(weapon.key, self.scheme.weapon(weapon.key).ammo)
        self.phase = Phase.SETTLING
        self.team_index = -1
        self.active_worm: Worm = teams[0].worms[0]
        self.turn_timer = self.scheme.turn.turn_time
        self.phase_timer = 0.0
        self.power = 0.0
        self.charging = False
        self.shots_left = 0
        self.winner: Team | None = None
        self.turn_number = 0
        self.round_number = 0
        self.tick = 0
        self.log: list[Command] = []
        self._start_next_turn()

    @classmethod
    def create(
        cls,
        configs: list[TeamConfig],
        terrain: Terrain,
        seed: int,
        scheme: GameScheme | None = None,
    ) -> "Match":
        scheme = scheme or GameScheme()
        rng = RngStreams(seed)
        world = World(terrain, scheme)
        count = scheme.worms.count
        positions = world.spawn_positions(len(configs) * count, rng.stream("spawn"))
        rng.stream("spawn").shuffle(positions)
        names = list(DEFAULT_WORM_NAMES)
        rng.stream("names").shuffle(names)
        teams = []
        for team_index, config in enumerate(configs):
            worms = []
            for _ in range(count):
                x, y = positions.pop()
                name = names.pop() if names else f"Wurm {len(world.worms) + 1}"
                facing = 1 if x < terrain.width / 2 else -1
                worm = Worm(name, team_index, hp=scheme.worms.hp, facing=facing, x=x, y=y)
                worms.append(world.add_worm(worm))
            teams.append(Team(config.name, config.color, config.is_ai, worms))
        return cls(world, teams, rng, scheme)

    # ------------------------------------------------------------ queries
    @property
    def active_team(self) -> Team:
        return self.teams[self.team_index]

    @property
    def weapon(self) -> WeaponDef:
        return get_weapon(self.active_team.weapon_key)

    def ammo(self, weapon: WeaponDef, team: Team | None = None) -> int:
        return (team or self.active_team).ammo.get(weapon.key, -1)

    def is_available(self, weapon: WeaponDef, team: Team | None = None) -> bool:
        """Has ammo and its scheme delay (in rounds) has passed."""
        delayed = self.round_number <= self.scheme.weapon(weapon.key).delay
        return self.ammo(weapon, team) != 0 and not delayed

    def has_ammo(self, weapon: WeaponDef) -> bool:
        return self.is_available(weapon)

    @property
    def can_act(self) -> bool:
        return self.phase == Phase.AIMING and self.active_worm.alive

    @property
    def can_move(self) -> bool:
        return self.phase in (Phase.AIMING, Phase.RETREAT) and self.active_worm.alive

    # ----------------------------------------------------------- commands
    def _record(self, name: str, *args: Any) -> None:
        self.log.append(Command(self.tick, name, args))

    def apply(self, command: Command) -> None:
        """Execute a recorded command (replays, tests)."""
        if command.name not in COMMANDS:
            raise ValueError(f"Unbekannter Befehl '{command.name}'")
        getattr(self, command.name)(*command.args)

    def select_weapon(self, index: int) -> None:
        weapons = all_weapons()
        if 0 <= index < len(weapons):
            self.select_weapon_key(weapons[index].key)

    def select_weapon_key(self, key: str) -> None:
        weapon = get_weapon(key)
        if self.can_act and not self.charging and self.is_available(weapon):
            if self.active_team.weapon_key != key:
                self._record("select_weapon_key", key)
            self.active_team.weapon_key = key

    def move(self, direction: int, dt: float) -> None:
        if self.can_move and not self.charging:
            self._record("move", direction, dt)
            self.world.walk(self.active_worm, direction, dt)

    def face(self, direction: int) -> None:
        if self.can_move and not self.charging:
            self._record("face", direction)
            self.active_worm.facing = direction

    def jump(self, kind: str = "forward") -> None:
        """kind: "forward", "high" or "backflip" (strings keep the command log serializable)."""
        if self.can_move and not self.charging:
            self._record("jump", kind)
            self.world.jump(self.active_worm, JumpKind(kind))

    def aim(self, delta: float) -> None:
        if self.can_act:
            self._record("aim", delta)
            worm = self.active_worm
            worm.aim = max(AIM_MIN, min(AIM_MAX, worm.aim + delta))

    def start_charge(self) -> None:
        if self.can_act and self.weapon.aim == AimMode.CHARGED and not self.charging:
            self._record("start_charge")
            self.charging = True
            self.power = 0.0

    def release_charge(self) -> None:
        if not self.charging or not self.can_act:
            return
        self._record("release_charge")
        self.charging = False
        self._fire(power=self.power)

    def fire_direct(self) -> None:
        if self.can_act and self.weapon.aim in (AimMode.ANGLE, AimMode.NONE):
            self._record("fire_direct")
            self._fire()

    def fire_at(self, target_x: float) -> None:
        if self.can_act and self.weapon.aim == AimMode.TARGET_POINT:
            self._record("fire_at", target_x)
            self._fire(target_x=target_x)

    def skip_turn(self) -> None:
        if self.can_act:
            self._record("skip_turn")
            self._begin_settling()

    # ------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        dt = min(dt, MAX_DT)
        self.tick += 1
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
                    self.charging = False
                    self._fire(power=1.0)
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
    def _fire(self, power: float = 1.0, target_x: float | None = None) -> None:
        weapon = self.weapon
        team = self.active_team
        strength = self.scheme.weapon(weapon.key).power
        context = FireContext.for_worm(
            self.world, self.active_worm, weapon, power, target_x, strength
        )
        get_behavior(weapon.behavior).fire(context)
        self.world.bus.emit(WeaponFired(self.active_worm, weapon.key))
        if self.shots_left <= 0:
            self.shots_left = weapon.shots_per_turn
        self.shots_left -= 1
        self.charging = False
        self.power = 0.0
        if self.shots_left > 0 or not weapon.ends_turn:
            return  # more shots (or a tool): the worm keeps acting
        if team.ammo.get(weapon.key, -1) > 0:
            team.ammo[weapon.key] -= 1
        if not self.is_available(weapon):
            team.weapon_key = all_weapons()[0].key
        self.phase = Phase.RETREAT
        self.phase_timer = self.scheme.turn.retreat_time

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
            winner_index = self.teams.index(self.winner) if self.winner else None
            self.world.bus.emit(GameOver(winner_index))
            return
        count = len(self.teams)
        for offset in range(1, count + 1):
            index = (self.team_index + offset) % count
            if self.teams[index].alive:
                if index <= self.team_index or self.team_index < 0:
                    self.round_number += 1
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
        if not self.is_available(self.weapon):
            team.weapon_key = next(
                (w.key for w in all_weapons() if self.is_available(w)), all_weapons()[0].key
            )
        wind_max = self.scheme.environment.wind_max
        self.world.wind = round(self.rng.stream("wind").uniform(-1.0, 1.0), 2) if wind_max else 0.0
        self.turn_timer = self.scheme.turn.turn_time
        self.power = 0.0
        self.charging = False
        self.shots_left = 0
        self.phase = Phase.AIMING
        self.turn_number += 1
        self.world.bus.emit(TurnStarted(self.team_index, self.active_worm, self.turn_number))


def replay(match: Match, log: list[Command], ticks: int, dt: float) -> Match:
    """Re-run a match from its initial state by applying a command log tick by tick."""
    by_tick: dict[int, list[Command]] = {}
    for command in log:
        by_tick.setdefault(command.tick, []).append(command)
    for _ in range(ticks):
        for command in by_tick.get(match.tick, ()):
            match.apply(command)
        match.update(dt)
    return match
