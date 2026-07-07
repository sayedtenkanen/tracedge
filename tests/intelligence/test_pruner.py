"""Tests for Skill Pruner — usage/success-rate tracking, delete bad skills."""

from __future__ import annotations

from tracedge.ir.upir import UPIR, UPIRNode
from tracedge.skills.pruner import SkillPruner


def _skill_table() -> dict[str, UPIR]:
    """Build a skill_table with known skills."""
    return {
        "good_skill": UPIR(
            entry="n1",
            nodes={"n1": UPIRNode(kind="observe", node_id="n1")},
            edges=[],
            harness_table={},
            skill_table={},
        ),
        "bad_skill": UPIR(
            entry="n1",
            nodes={"n1": UPIRNode(kind="act", node_id="n1")},
            edges=[],
            harness_table={},
            skill_table={},
        ),
        "unused_skill": UPIR(
            entry="n1",
            nodes={"n1": UPIRNode(kind="think", node_id="n1")},
            edges=[],
            harness_table={},
            skill_table={},
        ),
    }


class TestSkillPruning:
    """Slice 9 — skill pruning by usage and success rate."""

    def test_prune_zero_usage(self) -> None:
        """Skills with usage == 0 are deleted."""
        table = _skill_table()
        pruner = SkillPruner(
            table,
            stats={
                "good_skill": {"usage": 10, "successes": 8},
                "bad_skill": {"usage": 5, "successes": 1},
                "unused_skill": {"usage": 0, "successes": 0},
            },
        )
        pruned = pruner.prune()
        assert "unused_skill" not in pruned
        assert "good_skill" in pruned

    def test_prune_low_success_rate(self) -> None:
        """Skills with success_rate < threshold are deleted."""
        table = _skill_table()
        pruner = SkillPruner(
            table,
            stats={
                "good_skill": {"usage": 10, "successes": 8},
                "bad_skill": {"usage": 10, "successes": 1},
            },
            min_success_rate=0.5,
        )
        pruned = pruner.prune()
        assert "bad_skill" not in pruned
        assert "good_skill" in pruned

    def test_prune_preserves_good_skills(self) -> None:
        """High-usage, high-success skills are kept."""
        table = _skill_table()
        pruner = SkillPruner(
            table,
            stats={
                "good_skill": {"usage": 100, "successes": 95},
                "bad_skill": {"usage": 10, "successes": 9},
            },
            min_success_rate=0.5,
        )
        pruned = pruner.prune()
        assert "good_skill" in pruned
        assert "bad_skill" in pruned

    def test_prune_missing_stats_defaults_to_zero_usage(self) -> None:
        """Skills without stats default to usage=0 and are pruned."""
        table = _skill_table()
        pruner = SkillPruner(
            table,
            stats={
                "good_skill": {"usage": 10, "successes": 8},
            },
        )
        pruned = pruner.prune()
        assert "unused_skill" not in pruned
        assert "good_skill" in pruned

    def test_keep_success_rate_at_threshold(self) -> None:
        """Skills with success_rate == threshold are retained."""
        table = _skill_table()
        pruner = SkillPruner(
            table,
            stats={
                "bad_skill": {"usage": 10, "successes": 5},
            },
            min_success_rate=0.5,
        )
        pruned = pruner.prune()
        assert "bad_skill" in pruned

    def test_min_success_rate_out_of_range(self) -> None:
        """min_success_rate outside [0, 1] raises ValueError."""
        table = _skill_table()
        import pytest

        with pytest.raises(ValueError, match="min_success_rate must be between 0.0 and 1.0"):
            SkillPruner(table, min_success_rate=-0.1)
        with pytest.raises(ValueError, match="min_success_rate must be between 0.0 and 1.0"):
            SkillPruner(table, min_success_rate=1.5)
