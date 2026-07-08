"""Tests for cost-aware scheduler — budget enforcement."""

import pytest

from tracedge.compiler.scheduler import BudgetError, check_budget


class TestBudgetField:
    def test_upir_has_budget_field(self) -> None:
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "act", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
            budget=10,
        )
        assert upir.budget == 10

    def test_upir_budget_defaults_to_none(self) -> None:
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "act", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.budget is None


class TestBudgetCheck:
    def test_plan_within_budget_passes(self) -> None:
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[],
            harness_table={},
            skill_table={},
            budget=5,
        )
        assert check_budget(upir) is True

    def test_plan_exceeding_budget_raises(self) -> None:
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
            budget=2,
        )
        with pytest.raises(BudgetError, match="3 acts exceed budget of 2"):
            check_budget(upir)

    def test_no_budget_always_passes(self) -> None:
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert check_budget(upir) is True

    def test_only_act_nodes_count_toward_budget(self) -> None:
        """observe/think/branch nodes are free (no LLM call)."""
        from tracedge.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "observe", "node_id": "n2"},
                "n3": {"kind": "think", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
            budget=1,
        )
        assert check_budget(upir) is True
