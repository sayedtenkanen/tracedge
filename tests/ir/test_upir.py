import pytest
from pydantic import ValidationError

from autoharness.ir.upir import UPIR, Edge


class TestUPIRConstruction:
    """Test UPIR graph construction and basic invariants."""

    def test_upir_minimal(self) -> None:
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

    def test_upir_with_nodes_and_edges(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],  # type: ignore[call-arg]
            harness_table={},
            skill_table={},
        )
        assert len(upir.nodes) == 2
        assert len(upir.edges) == 1
        assert upir.edges[0].from_ == "n1"
        assert upir.edges[0].to == "n2"

    def test_upir_schema_label(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.schema_name == "typed-executable-graph"

    def test_upir_entry_must_exist_in_nodes(self) -> None:
        with pytest.raises(ValidationError):
            UPIR(
                entry="missing",
                nodes={"n1": {"kind": "observe", "node_id": "n1"}},
                edges=[],
                harness_table={},
                skill_table={},
            )

    def test_upir_edge_references_valid_nodes(self) -> None:
        with pytest.raises(ValidationError):
            UPIR(
                entry="n1",
                nodes={"n1": {"kind": "observe", "node_id": "n1"}},
                edges=[Edge(from_="n1", to="ghost", kind="sequential")],  # type: ignore[call-arg]
                harness_table={},
                skill_table={},
            )

    def test_upir_empty_nodes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UPIR(
                entry="n1",
                nodes={},
                edges=[],
                harness_table={},
                skill_table={},
            )

    def test_upir_skill_table_empty_by_default(self) -> None:
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

    def test_edge_sequential(self) -> None:
        e = Edge(from_="a", to="b", kind="sequential")  # type: ignore[call-arg]
        assert e.from_ == "a"
        assert e.to == "b"
        assert e.kind == "sequential"

    def test_edge_branch(self) -> None:
        e = Edge(from_="a", to="b", kind="branch")  # type: ignore[call-arg]
        assert e.kind == "branch"

    def test_edge_fallthrough(self) -> None:
        e = Edge(from_="a", to="b", kind="fallthrough")  # type: ignore[call-arg]
        assert e.kind == "fallthrough"

    def test_edge_invalid_kind_accepted(self) -> None:
        e = Edge(from_="a", to="b", kind="invalid")  # type: ignore[call-arg]
        assert e.kind == "invalid"
