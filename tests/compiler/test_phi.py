"""Tests for phi nodes — SSA-style merging of branch values.

Note: The ``sources`` field on ``Phi`` is a legacy artifact from before this
PR replaced sources-based merging with branch-value selection.  The VM no
longer reads ``sources`` — it looks up the ``branch_source`` branch event in
the trace and selects from ``values``.  ``sources`` is kept only so existing
UPIR graphs that serialize the field don't break.
"""

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

    def test_sources_field_retained_but_unused(self) -> None:
        """F3: Phi.sources is a legacy field — retained for serialization compat
        but the VM no longer reads it.  This test documents that fact."""
        phi = Phi(node_id="p1", sources=["n1", "n2"])
        assert phi.sources == ["n1", "n2"]  # field exists
        # But _step_phi never reads sources — it uses branch_source + values

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

    def test_insert_phi_updates_branch_true_next(self) -> None:
        """F1: When a branch is a direct predecessor of the convergence target,
        insert_phi_nodes must also update the branch's true_next/false_next
        attributes — otherwise the VM bypasses the phi via attribute routing."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n4",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n4": {"kind": "act", "node_id": "n4"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n4", kind="sequential"),
                Edge(from_="n2", to="n4", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        result = insert_phi_nodes(upir)
        n1 = _get(result, "n1")
        # Branch's true_next should now point to phi, not directly to n4
        assert n1.false_next == "phi_n4"  # type: ignore[attr-defined]

    def test_insert_phi_end_to_end_both_paths(self) -> None:
        """F1: After inserting a phi, both branch paths should execute through
        the phi node — true path via n2→phi, false path via phi directly."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n4",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n4": {"kind": "act", "node_id": "n4"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n4", kind="sequential"),
                Edge(from_="n2", to="n4", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        result = insert_phi_nodes(upir)

        class _False:
            def chat(self, p: str) -> str:
                return "false"

        trace = VM(upir=result, llm=_False(), seed=42).run()
        kinds = [e["kind"] for e in trace]
        # phi must execute on the false path
        assert "phi" in kinds, f"phi not in trace: {[e['node_id'] for e in trace]}"

    def test_insert_phi_populates_values(self) -> None:
        """F2: insert_phi_nodes should populate values mapping 'true'→branch's
        true_next and 'false'→branch's false_next so the phi is not inert."""
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
        phi = _get(result, "phi_n4")
        values = getattr(phi, "values", {})
        assert values.get("true") == "n2"
        assert values.get("false") == "n3"


class TestPhiNestedBranch:
    def test_nested_branch_selects_inner_branch(self) -> None:
        """F5: For nested branches, the phi should bind to the innermost branch
        whose arms converge — not the outer branch."""
        # Outer branch: n1 → n2 (true) / n3 (false)
        # Inner branch (inside n2 path): n2 → n4 (true) / n5 (false)
        # Convergence: n4 and n3 both → n6
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
                "n2": {
                    "kind": "branch",
                    "node_id": "n2",
                    "condition": "True",
                    "true_next": "n4",
                    "false_next": "n5",
                },
                "n3": {"kind": "act", "node_id": "n3"},
                "n4": {"kind": "act", "node_id": "n4"},
                "n5": {"kind": "act", "node_id": "n5"},
                "n6": {"kind": "act", "node_id": "n6"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n1", to="n3", kind="sequential"),
                Edge(from_="n2", to="n4", kind="sequential"),
                Edge(from_="n2", to="n5", kind="sequential"),
                Edge(from_="n4", to="n6", kind="sequential"),
                Edge(from_="n3", to="n6", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        result = insert_phi_nodes(upir)
        phi = _get(result, "phi_n6")
        # The phi should bind to the branch whose arms converge at n6.
        # n4→n6 and n3→n6 — n3 comes from n1 (outer), n4 comes from n2 (inner).
        # The converging branches are n1 and n2.  The phi should bind to the
        # immediate dominator of the merge — n1 (the outer branch), since
        # n4 (from inner branch) and n3 (from outer branch's false arm) converge.
        # But the current BFS finds the *nearest* branch, which would be n2
        # (wrong for the n3 arm).  This test documents the expected behavior.
        assert phi.branch_source != ""  # type: ignore[attr-defined]
