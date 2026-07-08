"""Tests for compiler passes — dead branch elimination, constant folding, unreachable pruning."""

from tracedge.compiler.passes import (
    constant_fold,
    dead_branch_eliminate,
    unreachable_prune,
)
from tracedge.ir.upir import UPIR, Edge, UPIRNode


def _get(upir: UPIR, nid: str) -> UPIRNode:
    """Get a UPIRNode from the nodes dict (coercing if needed)."""
    raw = upir.nodes[nid]
    return raw if isinstance(raw, UPIRNode) else UPIRNode.model_validate(raw)


class TestDeadBranchEliminate:
    def test_removes_branch_with_one_dead_path(self) -> None:
        """Branch where one target has no incoming edges other than this branch."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        result = dead_branch_eliminate(upir)
        n1 = _get(result, "n1")
        assert n1.true_next == "n2"  # type: ignore[attr-defined]
        assert n1.false_next == ""  # type: ignore[attr-defined]

    def test_preserves_branch_with_both_paths_alive(self) -> None:
        """Branch where both targets have nodes — no elimination."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        result = dead_branch_eliminate(upir)
        n1 = _get(result, "n1")
        assert n1.true_next == "n2"  # type: ignore[attr-defined]
        assert n1.false_next == "n3"  # type: ignore[attr-defined]


class TestConstantFold:
    def test_folds_always_true_branch(self) -> None:
        """Branch with condition 'True' becomes sequential to true_next."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        result = constant_fold(upir)

        # Entry node should remain the same.
        assert result.entry == "n1"

        # Branch should be folded to act.
        n1 = _get(result, "n1")
        assert n1.kind == "act"

        # Branch successors should be cleared on the folded node.
        assert n1.true_next == ""  # type: ignore[attr-defined]
        assert n1.false_next == ""  # type: ignore[attr-defined]

        # A sequential edge from n1 to the original true_next should exist.
        assert any(
            e.from_ == "n1" and e.to == "n2" and e.kind == "sequential" for e in result.edges
        )
        # No edge from n1 to the original false_next.
        assert not any(e.from_ == "n1" and e.to == "n3" for e in result.edges)

    def test_folds_always_false_branch(self) -> None:
        """Branch with condition 'False' becomes sequential to false_next."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "False",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        result = constant_fold(upir)

        # Entry node should remain the same.
        assert result.entry == "n1"

        # Branch should be folded to act.
        n1 = _get(result, "n1")
        assert n1.kind == "act"

        # Branch successors should be cleared on the folded node.
        assert n1.true_next == ""  # type: ignore[attr-defined]
        assert n1.false_next == ""  # type: ignore[attr-defined]

        # A sequential edge from n1 to the original false_next should exist.
        assert any(
            e.from_ == "n1" and e.to == "n3" and e.kind == "sequential" for e in result.edges
        )
        # No edge from n1 to the original true_next.
        assert not any(e.from_ == "n1" and e.to == "n2" for e in result.edges)

    def test_preserves_dynamic_condition(self) -> None:
        """Branch with non-constant condition is preserved."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "x > 5",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        result = constant_fold(upir)
        assert _get(result, "n1").kind == "branch"


class TestUnreachablePrune:
    def test_removes_unreachable_nodes(self) -> None:
        """Nodes with no incoming edges (except entry) are removed."""
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
        result = unreachable_prune(upir)
        assert "n1" in result.nodes
        assert len(result.nodes) == 1

    def test_preserves_reachable_chain(self) -> None:
        """Nodes in a chain from entry are all preserved."""
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
        result = unreachable_prune(upir)
        assert len(result.nodes) == 3
