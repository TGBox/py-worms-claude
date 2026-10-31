"""Named, independent random streams derived from one match seed.

Each subsystem draws from its own stream, so adding randomness in one place (e.g. crates) does
not shift the sequence of another (e.g. wind). This keeps replays and tests deterministic.
"""

import random
import zlib


class RngStreams:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._streams: dict[str, random.Random] = {}

    def stream(self, name: str) -> random.Random:
        if name not in self._streams:
            self._streams[name] = random.Random(zlib.crc32(f"{self.seed}:{name}".encode()))
        return self._streams[name]
