import pytest
from pydantic import ValidationError

from autoharness.ir.upir import UPIR, Edge


class TestUPIRConstruction:
    """Test UPIR graph construction and basic invariants."""

    def test_upir_minimal(self):
        upir = UPIR(
            entry="start",
            nodes={"start": {"kind": "observe", "node_id": "start"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.entry == "start"
        assert "start" in upir.nodes
        assert upir.edges == []
        assert upir.harness_table == {}
        assert upir.skill_table == {}

    def test_upir_with_nodes_and_edges(self):
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
            harness_table={},
            skill_table={},
        )
        assert len(upir.nodes) == 2
        assert len(upir.edges) == 1
        assert upir.edges[0].from_ == "n1"
        assert upir.edges[0].to == "n2"

    def test_upir_schema_label(self):
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.schema == "typed-executable-graph"

    def test_upir_entry_must_exist_in_nodes(self):
        with pytest.raises(ValidationError):
            UPIR(
                entry="missing",
                nodes={"n1": {"kind": "observe", "node_id": "n1"}},
                edges=[],
                harness_table={},
                skill_table={},
            )

    def test_upir_edge_references_valid_nodes(self):
        with pytest.raises(ValidationError):
            UPIR(
                entry="n1",
                nodes={"n1": {"kind": "observe", "node_id": "n1"}},
                edges=[Edge(from_="n1", to="ghost", kind="sequential")],
                harness_table={},
                skill_table={},
            )

    def test_upir_empty_nodes_rejected(self):
        with pytest.raises(ValidationError):
            UPIR(
                entry="n1",
                nodes={},
                edges=[],
                harness_table={},
                skill_table={},
            )

    def test_upir_skill_table_empty_by_default(self):
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.skill_table == {}


class TestEdge:
    """Test Edge model."""

    def test_edge_sequential(self):
        e = Edge(from_="a", to="b", kind="sequential")
        assert e.from_ == "a"
        assert e.to == "b"
        assert e.kind == "sequential"

    def test_edge_branch(self):
        e = Edge(from_="a", to="b", kind="branch")
        assert e.kind == "branch"

    def test_edge_fallthrough(self):
        e = Edge(from_="a", to="b", kind="fallthrough")
        assert e.kind == "fallthrough"

    def test_edge_invalid_kind_accepted(self):
        e = Edge(from_="a", to="b", kind="invalid")
        assert e.kind == "invalid"
