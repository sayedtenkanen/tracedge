from autoharness.runtime.seed import SeedStream


class TestSeedThreading:
    """Seed passed through all execution, not sampled from global random."""

    def test_deterministic_sequence(self):
        s1 = SeedStream(seed=42)
        s2 = SeedStream(seed=42)
        assert [s1.next() for _ in range(5)] == [s2.next() for _ in range(5)]

    def test_different_seeds_differ(self):
        s1 = SeedStream(seed=42)
        s2 = SeedStream(seed=99)
        assert s1.next() != s2.next()

    def test_next_returns_int(self):
        s = SeedStream(seed=42)
        val = s.next()
        assert isinstance(val, int)

    def test_current(self):
        s = SeedStream(seed=42)
        first = s.next()
        assert s.current == first
        second = s.next()
        assert s.current == second
