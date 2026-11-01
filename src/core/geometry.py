"""Shared geometry tables (also handed to the Rust kernel so both backends agree bit for bit)."""

import math

CIRCLE_SAMPLES = 12
CIRCLE_OFFSETS = [
    (math.cos(2 * math.pi * i / CIRCLE_SAMPLES), math.sin(2 * math.pi * i / CIRCLE_SAMPLES))
    for i in range(CIRCLE_SAMPLES)
]
CIRCLE_POINTS = [(0.0, 0.0), *CIRCLE_OFFSETS]  # centre first, then the rim
