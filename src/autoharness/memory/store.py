"""Persistent Memory Store — episodic traces, skill stats, global stats on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    """JSON-file-backed persistent store for episodes, skill stats, and global stats."""

    def __init__(self, data_dir: Path | str = ".autoharness_memory") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "episodes").mkdir(exist_ok=True)
        (self.data_dir / "skills").mkdir(exist_ok=True)

    def save_episode(
        self, episode_id: str, trace: list[dict[str, Any]], reward: float = 0.0
    ) -> None:
        """Write an episode trace + reward to disk."""
        path = self.data_dir / "episodes" / f"{episode_id}.json"
        path.write_text(json.dumps({"trace": trace, "reward": reward}))

    def load_episode(self, episode_id: str) -> dict[str, Any] | None:
        """Read an episode from disk. Returns None if not found."""
        path = self.data_dir / "episodes" / f"{episode_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def save_skill_stats(self, skill_id: str, usage: int = 0, successes: int = 0) -> None:
        """Write skill usage/success stats to disk."""
        path = self.data_dir / "skills" / f"{skill_id}.json"
        path.write_text(json.dumps({"usage": usage, "successes": successes}))

    def load_skill_stats(self, skill_id: str) -> dict[str, int]:
        """Read skill stats from disk. Returns zeros if not found."""
        path = self.data_dir / "skills" / f"{skill_id}.json"
        if not path.exists():
            return {"usage": 0, "successes": 0}
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def save_global_stats(self, total_runs: int = 0, success_rate: float = 0.0) -> None:
        """Write global stats to disk."""
        path = self.data_dir / "global_stats.json"
        path.write_text(json.dumps({"total_runs": total_runs, "success_rate": success_rate}))

    def load_global_stats(self) -> dict[str, Any]:
        """Read global stats from disk. Returns zeros if not found."""
        path = self.data_dir / "global_stats.json"
        if not path.exists():
            return {"total_runs": 0, "success_rate": 0.0}
        return json.loads(path.read_text())  # type: ignore[no-any-return]
