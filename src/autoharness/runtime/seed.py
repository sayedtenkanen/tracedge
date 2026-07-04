from __future__ import annotations

import random


class SeedStream:
    """Deterministic seed stream — no global random state."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self._current: int = seed

    def next(self) -> int:
        self._current = self._rng.randint(0, 2**31 - 1)
        return self._current

    @property
    def current(self) -> int:
        return self._current
