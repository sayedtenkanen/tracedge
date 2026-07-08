"""Tests for phi nodes — SSA-style merging of branch values."""

from tracedge.compiler.passes import insert_phi_nodes
from tracedge.ir.nodes import Phi
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.runtime.vm import VM


def _get(upir: UPIR, nid: str) -> UPIRNode:
    """Get a UPIRNode from the nodes dict (coercing if needed)."""
    raw = upir.nodes[nid]
    return raw if isinstance(raw, UPIRNode) else UPIRNode.model_validate(raw)


class FakeLLM:
    def chat(self, prompt: str) -> str:
        return "true"


class FakeLLMFalse:
    def chat(self, prompt: str) -> str:
        return "false"


class TestPhiNodeIR:
    def test_phi_has_branch_source(self) -> None:
        """Phi node tracks which branch it merges from."""
        phi = Phi(node_id="p1", branch_source="b1", values={"true": "v1", "false": "v2"})
        assert phi.branch_source == "b1"
        assert phi.values == {"true": "v1", "false": "v2"}

    def test_phi_has_sources_for_backward_compat(self) -> None:
        """Phi node still has sources list for backward compatibility."""
        phi = Phi(node_id="p1", sources=["n1", "n2"])
        assert phi.sources == ["n1", "n2"]

    def test_upir_accepts_phi_nodes(self) -> None:
        """UPIR graph can contain phi nodes."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
                "p1": {
                    "kind": "phi",
                    "node_id": "p1",
                    "branch_source": "n1",
                    "values": {"true": "path_a_result", "false": "path_b_result"},
                },
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch_true"),
                Edge(from_="n1", to="n3", kind="branch_false"),
                Edge(from_="n2", to="p1", kind="sequential"),
                Edge(from_="n3", to="p1", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        assert _get(upir, "p1").kind == "phi"


class TestPhiNodeVM:
    def test_phi_selects_true_value_after_true_branch(self) -> None:
        """Phi node selects the 'true' value when branch was taken as true."""
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
                "p1": {
                    "kind": "phi",
                    "node_id": "p1",
                    "branch_source": "n1",
                    "values": {"true": "val_true", "false": "val_false"},
                },
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
                Edge(from_="n2", to="p1", kind="sequential"),
                Edge(from_="n3", to="p1", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        trace = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        phi_event = next(e for e in trace if e["kind"] == "phi")
        assert phi_event["selected"] == "val_true"

    def test_phi_selects_false_value_after_false_branch(self) -> None:
        """Phi node selects the 'false' value when branch was taken as false."""
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
                "p1": {
                    "kind": "phi",
                    "node_id": "p1",
                    "branch_source": "n1",
                    "values": {"true": "val_true", "false": "val_false"},
                },
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
                Edge(from_="n2", to="p1", kind="sequential"),
                Edge(from_="n3", to="p1", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        trace = VM(upir=upir, llm=FakeLLMFalse(), seed=42).run()
        phi_event = next(e for e in trace if e["kind"] == "phi")
        assert phi_event["selected"] == "val_false"

    def test_phi_with_empty_values_returns_none(self) -> None:
        """Phi node with no values dict returns None for selected."""
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
                "p1": {
                    "kind": "phi",
                    "node_id": "p1",
                    "branch_source": "n1",
                },
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
                Edge(from_="n2", to="p1", kind="sequential"),
                Edge(from_="n3", to="p1", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        trace = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        phi_event = next(e for e in trace if e["kind"] == "phi")
        assert phi_event["selected"] is None


class TestPhiInsertionPass:
    def test_inserts_phi_at_convergence(self) -> None:
        """Phi node inserted where two branches reconverge."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
                "n4": {"kind": "act", "node_id": "n4"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
                Edge(from_="n2", to="n4", kind="sequential"),
                Edge(from_="n3", to="n4", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        result = insert_phi_nodes(upir)
        # phi_n4 should exist
        assert "phi_n4" in result.nodes
        phi = _get(result, "phi_n4")
        assert phi.kind == "phi"
        assert phi.branch_source == "n1"  # type: ignore[attr-defined]
        # Edges should be: n1→n2, n1→n3, n2→phi_n4, n3→phi_n4, phi_n4→n4
        assert any(e.from_ == "n2" and e.to == "phi_n4" for e in result.edges)
        assert any(e.from_ == "n3" and e.to == "phi_n4" for e in result.edges)
        assert any(e.from_ == "phi_n4" and e.to == "n4" for e in result.edges)
        # Old direct edges to n4 should be removed
        assert not any(e.from_ == "n2" and e.to == "n4" for e in result.edges)
        assert not any(e.from_ == "n3" and e.to == "n4" for e in result.edges)

    def test_no_phi_for_single_predecessor(self) -> None:
        """No phi inserted for nodes with only one incoming edge."""
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
        result = insert_phi_nodes(upir)
        assert len(result.nodes) == 2  # No new nodes added
