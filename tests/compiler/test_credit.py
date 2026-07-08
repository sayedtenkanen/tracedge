"""Tests for credit assignment compiler — per-node reward attribution."""

import pytest

from tracedge.compiler.credit import assign_credits
from tracedge.ir.upir import UPIR


class TestCreditAssignment:
    def test_equal_credit_for_linear_chain(self) -> None:
        """3-node chain gets equal credit (1/3 each)."""
        from tracedge.ir.upir import Edge

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n2", to="n3", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        trace = ["n1", "n2", "n3"]
        result = assign_credits(upir, trace, total_reward=1.0)
        assert result["n1"] == pytest.approx(1 / 3)
        assert result["n2"] == pytest.approx(1 / 3)
        assert result["n3"] == pytest.approx(1 / 3)

    def test_zero_reward(self) -> None:
        """Zero reward → all credits zero."""
        from tracedge.ir.upir import Edge

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
            harness_table={},
            skill_table={},
        )
        trace = ["n1", "n2"]
        result = assign_credits(upir, trace, total_reward=0.0)
        assert result["n1"] == 0.0
        assert result["n2"] == 0.0

    def test_partial_trace(self) -> None:
        """Only nodes in the trace get credit; others get 0."""
        from tracedge.ir.upir import Edge

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "act", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        trace = ["n1", "n3"]
        result = assign_credits(upir, trace, total_reward=1.0)
        assert result["n1"] == pytest.approx(0.5)
        assert result["n2"] == 0.0
        assert result["n3"] == pytest.approx(0.5)
