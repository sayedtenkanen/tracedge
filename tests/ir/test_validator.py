"""Validate UPIR construction via Pydantic model validation."""

from autoharness.ir.upir import UPIR, Edge, UPIRNode


class TestEdgeConsistency:
    """Validate edge list matches node-level references."""

    def test_valid_sequential_chain(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        assert upir.entry == "n1"
        assert len(upir.edges) == 1

    def test_valid_branch_edges(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "branch", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch"),
                Edge(from_="n1", to="n3", kind="branch"),
            ],
            harness_table={},
            skill_table={},
        )
        assert len(upir.edges) == 2

    def test_valid_graph_with_all_edge_kinds(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "branch", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch"),
                Edge(from_="n1", to="n3", kind="fallthrough"),
            ],
            harness_table={},
            skill_table={},
        )
        assert upir.schema_name == "typed-executable-graph"

    def test_valid_linear_chain(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "think", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),
                Edge(from_="n2", to="n3", kind="sequential"),
            ],
            harness_table={},
            skill_table={},
        )
        node = upir.nodes["n2"]
        assert isinstance(node, UPIRNode)
        assert node.kind == "think"

    def test_empty_edges_valid(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert upir.edges == []
