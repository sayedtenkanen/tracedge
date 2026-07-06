"""Skill Pruner — delete skills with zero usage or low success rate."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autoharness.ir.upir import UPIR


class SkillPruner:
    """Prune skills from a skill_table based on usage and success rate."""

    def __init__(
        self,
        skill_table: dict[str, UPIR],
        stats: dict[str, dict[str, int]] | None = None,
        min_success_rate: float = 0.0,
    ) -> None:
        if not 0.0 <= min_success_rate <= 1.0:
            raise ValueError(
                f"min_success_rate must be between 0.0 and 1.0 inclusive; got {min_success_rate!r}"
            )
        self.skill_table = skill_table
        self.stats = stats or {}
        self.min_success_rate = min_success_rate

    def prune(self) -> dict[str, UPIR]:
        """Remove skills with usage == 0 or success_rate < threshold. Return remaining."""
        result: dict[str, UPIR] = {}
        for skill_id, upir in self.skill_table.items():
            skill_stats = self.stats.get(skill_id, {"usage": 0, "successes": 0})
            usage = skill_stats.get("usage", 0)
            successes = skill_stats.get("successes", 0)

            if usage == 0:
                continue

            success_rate = successes / usage if usage > 0 else 0.0
            if success_rate < self.min_success_rate:
                continue

            result[skill_id] = upir

        return result
