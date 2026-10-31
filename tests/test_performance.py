"""Performance budget for the simulation (see implementation plan C.0).

The scenario time is compared with a pure-Python calibration workload measured in the same run,
so the budget holds on fast and slow machines alike. Raise BASELINE_RATIO only on purpose.
"""

import math
import time

from src.core.constants import WORM_RADIUS
from src.core.entities import Projectile, Worm
from src.core.mapgen import generate_terrain
from src.core.scheme import GameScheme
from src.core.world import World

DT = 1 / 60
STEPS = 600
BASELINE_RATIO = 1.4  # scenario/calibration ratio measured in phase 0 (CPython 3.13)
TOLERANCE = 1.2  # +20 % allowed (plan C.0)


def calibration() -> float:
    start = time.perf_counter()
    total = 0.0
    for i in range(1_000_000):
        total += math.sqrt(i) * (i % 7)
    assert total > 0
    return time.perf_counter() - start


def scenario() -> float:
    world = World(generate_terrain(2000, 1000, 930, seed=99), GameScheme())
    for i in range(8):
        x = 250 + i * 200
        top = world.terrain.surface_y(x) or 600
        world.add_worm(Worm(f"W{i}", i % 2, x=x, y=top - WORM_RADIUS - 1))
    start = time.perf_counter()
    for step in range(STEPS):
        if step % 30 == 0:  # two rockets and three bouncing grenades every half second
            x = 300 + (step // 30) * 70
            for i in range(2):
                world.add_projectile(
                    Projectile(
                        "bazooka", x=x + i * 40, y=50, vx=60, vy=0, explosion_radius=40, damage=50
                    )
                )
            for i in range(3):
                world.add_projectile(
                    Projectile(
                        "grenade",
                        x=x + 60 + i * 30,
                        y=100,
                        vx=-80 + i * 60,
                        vy=-100,
                        explosion_radius=42,
                        damage=50,
                        fuse=2.5,
                        bounce=0.45,
                    )
                )
        for worm in world.worms:
            world.walk(worm, 1 if worm.team_index else -1, DT)
        world.update(DT)
    return time.perf_counter() - start


def measure_ratio(rounds: int = 5) -> float:
    """Interleave both workloads and keep the fastest of each: robust against load spikes."""
    scenario_times, calibration_times = [], []
    for _ in range(rounds):
        calibration_times.append(calibration())
        scenario_times.append(scenario())
    return min(scenario_times) / min(calibration_times)


def test_simulation_stays_within_budget() -> None:
    ratio = measure_ratio()
    assert ratio < BASELINE_RATIO * TOLERANCE, f"ratio {ratio:.2f}"
