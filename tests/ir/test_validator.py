from autoharness.ir.upir import UPIR, Edge
from autoharness.ir.validator import validate_upir


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
                Edge(from_="n1", to="n2", kind="sequential"),  # type: ignore[call-arg]
            ],
            harness_table={},
            skill_table={},
        )
        assert validate_upir(upir) is True

    def test_valid_branch_edges(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "branch", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch"),  # type: ignore[call-arg]
                Edge(from_="n1", to="n3", kind="branch"),  # type: ignore[call-arg]
            ],
            harness_table={},
            skill_table={},
        )
        assert validate_upir(upir) is True

    def test_valid_graph_with_all_edge_kinds(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "branch", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch"),  # type: ignore[call-arg]
                Edge(from_="n1", to="n3", kind="fallthrough"),  # type: ignore[call-arg]
            ],
            harness_table={},
            skill_table={},
        )
        assert validate_upir(upir) is True

    def test_valid_linear_chain(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "think", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="sequential"),  # type: ignore[call-arg]
                Edge(from_="n2", to="n3", kind="sequential"),  # type: ignore[call-arg]
            ],
            harness_table={},
            skill_table={},
        )
        assert validate_upir(upir) is True

    def test_empty_edges_valid(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        assert validate_upir(upir) is True
