"""Persistent Memory Store — episodic traces, skill stats, global stats on disk."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracedge.ir.upir import UPIR

logger = logging.getLogger(__name__)


class MemoryStore:
    """JSON-file-backed persistent store for episodes, skill stats, and global stats."""

    def __init__(self, data_dir: Path | str = ".tracedge_memory") -> None:
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
        """Read an episode from disk. Returns None if not found or corrupted."""
        path = self.data_dir / "episodes" / f"{episode_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load episode %s: %s", episode_id, exc)
            return None

    def save_skill_stats(self, skill_id: str, usage: int = 0, successes: int = 0) -> None:
        """Write skill usage/success stats to disk."""
        path = self.data_dir / "skills" / f"{skill_id}.json"
        path.write_text(json.dumps({"usage": usage, "successes": successes}))

    def load_skill_stats(self, skill_id: str) -> dict[str, int]:
        """Read skill stats from disk. Returns zeros if not found or corrupted."""
        path = self.data_dir / "skills" / f"{skill_id}.json"
        if not path.exists():
            return {"usage": 0, "successes": 0}
        try:
            return json.loads(path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load skill stats %s: %s", skill_id, exc)
            return {"usage": 0, "successes": 0}

    def save_global_stats(self, total_runs: int = 0, success_rate: float = 0.0) -> None:
        """Write global stats to disk."""
        path = self.data_dir / "global_stats.json"
        path.write_text(json.dumps({"total_runs": total_runs, "success_rate": success_rate}))

    def load_global_stats(self) -> dict[str, Any]:
        """Read global stats from disk. Returns zeros if not found or corrupted."""
        path = self.data_dir / "global_stats.json"
        if not path.exists():
            return {"total_runs": 0, "success_rate": 0.0}
        try:
            return json.loads(path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load global stats: %s", exc)
            return {"total_runs": 0, "success_rate": 0.0}

    def save_skill(self, skill_id: str, skill: UPIR) -> None:
        """Write a skill UPIR to disk as JSON."""
        path = self.data_dir / "skills" / f"{skill_id}_upir.json"
        path.write_text(skill.model_dump_json())

    def load_skill(self, skill_id: str) -> UPIR | None:
        """Read a skill UPIR from disk. Returns None if not found or corrupted."""
        from tracedge.ir.upir import UPIR as _UPIR

        path = self.data_dir / "skills" / f"{skill_id}_upir.json"
        if not path.exists():
            return None
        try:
            return _UPIR.model_validate_json(path.read_text())
        except Exception as exc:
            logger.warning("Failed to load skill %s: %s", skill_id, exc)
            return None

    def load_skills(self) -> dict[str, UPIR]:
        """Load all stored skills from disk. Returns dict of skill_id → UPIR."""
        from tracedge.ir.upir import UPIR as _UPIR

        skills_dir = self.data_dir / "skills"
        result: dict[str, UPIR] = {}
        if not skills_dir.exists():
            return result
        for path in sorted(skills_dir.glob("*_upir.json")):
            skill_id = path.stem.replace("_upir", "")
            try:
                result[skill_id] = _UPIR.model_validate_json(path.read_text())
            except Exception as exc:
                logger.warning("Failed to load skill %s: %s", skill_id, exc)
        return result
