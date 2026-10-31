"""Typed game events and a small synchronous event bus.

The simulation emits events; the presentation layer (effects), statistics and later the mission
system consume them. Subscribers are called immediately, and every event is also kept in a
bounded queue that frame-based consumers drain.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.core.entities import Worm

QUEUE_LIMIT = 4096


@dataclass(frozen=True, eq=False)
class Event:
    pass


@dataclass(frozen=True, eq=False)
class Explosion(Event):
    x: float
    y: float
    radius: float
    damage: int


@dataclass(frozen=True, eq=False)
class Damage(Event):
    worm: "Worm"
    amount: int
    x: float
    y: float


@dataclass(frozen=True, eq=False)
class WormDrowned(Event):
    worm: "Worm"
    x: float
    y: float


@dataclass(frozen=True, eq=False)
class WormDied(Event):
    worm: "Worm"
    x: float
    y: float


@dataclass(frozen=True, eq=False)
class Splash(Event):
    x: float
    y: float


@dataclass(frozen=True, eq=False)
class Tracer(Event):
    x: float
    y: float
    x2: float
    y2: float


@dataclass(frozen=True, eq=False)
class WeaponFired(Event):
    worm: "Worm"
    weapon_key: str


@dataclass(frozen=True, eq=False)
class TurnStarted(Event):
    team_index: int
    worm: "Worm"
    turn_number: int


@dataclass(frozen=True, eq=False)
class GameOver(Event):
    winner_index: int | None


E = TypeVar("E", bound=Event)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Callable[[Event], None]]] = {}
        self.queue: deque[Event] = deque(maxlen=QUEUE_LIMIT)

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> Callable[[], None]:
        """Register a handler (also called for subclasses); returns an unsubscribe function."""
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append(handler)  # type: ignore[arg-type]
        return lambda: handlers.remove(handler)  # type: ignore[arg-type]

    def emit(self, event: Event) -> None:
        self.queue.append(event)
        for event_type in type(event).__mro__:
            for handler in list(self._handlers.get(event_type, ())):
                handler(event)

    def drain(self) -> list[Event]:
        events = list(self.queue)
        self.queue.clear()
        return events

    def of_type(self, event_type: type[E]) -> list[E]:
        """Queued events of one type (without draining); handy for tests."""
        return [e for e in self.queue if isinstance(e, event_type)]
