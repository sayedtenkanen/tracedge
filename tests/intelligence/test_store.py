"""Tests for Persistent Memory — episodic store, skill persistence, reload."""

from __future__ import annotations

import tempfile
from pathlib import Path

from autoharness.memory.store import MemoryStore


class TestPersistentMemory:
    """Slice 10 — persistent memory store."""

    def test_store_episode(self) -> None:
        """Episode traces written to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            episode = [
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
            ]
            store.save_episode("ep1", episode, reward=0.8)
            loaded = store.load_episode("ep1")
            assert loaded is not None
            assert len(loaded["trace"]) == 2
            assert loaded["reward"] == 0.8

    def test_store_skill_stats(self) -> None:
        """Skill usage/success persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            store.save_skill_stats("skill_1", usage=10, successes=8)
            stats = store.load_skill_stats("skill_1")
            assert stats["usage"] == 10
            assert stats["successes"] == 8

    def test_store_global_stats(self) -> None:
        """Global success rate persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            store.save_global_stats(total_runs=100, success_rate=0.75)
            stats = store.load_global_stats()
            assert stats["total_runs"] == 100
            assert stats["success_rate"] == 0.75

    def test_reload_on_startup(self) -> None:
        """Data survives process restart (new MemoryStore instance)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = MemoryStore(data_dir=Path(tmpdir))
            store1.save_episode("ep1", [{"node_id": "n1"}], reward=0.9)
            store1.save_skill_stats("s1", usage=5, successes=4)

            # New instance — simulates restart
            store2 = MemoryStore(data_dir=Path(tmpdir))
            assert store2.load_episode("ep1") is not None
            assert store2.load_skill_stats("s1")["usage"] == 5

    def test_load_missing_episode_returns_none(self) -> None:
        """Missing episodes load as None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            assert store.load_episode("nonexistent") is None

    def test_load_missing_skill_stats_uses_defaults(self) -> None:
        """Missing skill stats load with default usage/successes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            stats = store.load_skill_stats("nonexistent")
            assert stats == {"usage": 0, "successes": 0}

    def test_load_global_stats_defaults_when_missing(self) -> None:
        """Global stats default to zeroed values when not yet persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            stats = store.load_global_stats()
            assert stats == {"total_runs": 0, "success_rate": 0.0}

    def test_load_corrupted_episode_returns_none(self) -> None:
        """Corrupted JSON file returns None instead of raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            path = Path(tmpdir) / "episodes" / "bad.json"
            path.write_text("NOT VALID JSON{{{")
            assert store.load_episode("bad") is None

    def test_load_corrupted_skill_stats_returns_defaults(self) -> None:
        """Corrupted skill stats file returns defaults instead of raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            path = Path(tmpdir) / "skills" / "bad.json"
            path.write_text("{truncated")
            stats = store.load_skill_stats("bad")
            assert stats == {"usage": 0, "successes": 0}

    def test_load_corrupted_global_stats_returns_defaults(self) -> None:
        """Corrupted global stats file returns defaults instead of raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(data_dir=Path(tmpdir))
            path = Path(tmpdir) / "global_stats.json"
            path.write_text("corrupt!")
            stats = store.load_global_stats()
            assert stats == {"total_runs": 0, "success_rate": 0.0}
