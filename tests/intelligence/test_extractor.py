"""Tests for Skill Extractor — detect repeated subgraphs, extract reusable skills."""

from __future__ import annotations

from typing import Any

from autoharness.ir.upir import UPIR, UPIRNode
from autoharness.skills.extractor import SkillExtractor
from autoharness.trace.trace_ir import TraceEvent, TraceLog


def _trace(events: list[dict[str, Any]]) -> TraceLog:
    """Helper to build a TraceLog from event dicts."""
    log = TraceLog()
    for e in events:
        log.append(TraceEvent(**e))
    return log


def _make_graph(nodes: dict[str, str], edges: list[tuple[str, str]]) -> UPIR:
    """Helper to build a minimal UPIR from node kinds and edge pairs."""
    upir_nodes = {nid: UPIRNode(kind=kind, node_id=nid) for nid, kind in nodes.items()}
    edge_list = [{"from": f, "to": t, "kind": "sequential"} for f, t in edges]
    return UPIR(
        entry="n1",
        nodes=upir_nodes,
        edges=edge_list,
        harness_table={},
        skill_table={},
    )


class TestSkillExtraction:
    """Slice 7 — skill extraction from repeated trace patterns."""

    def test_detect_repeated_subgraphs(self) -> None:
        """Extractor finds repeated trace patterns."""
        extractor = SkillExtractor(min_occurrences=2)
        trace = _trace(
            [
                {"node_id": "n1", "kind": "observe", "inputs": {"q": "a"}},
                {"node_id": "n2", "kind": "act", "inputs": {"tool": "read"}},
                {"node_id": "n3", "kind": "think", "inputs": {"prompt": "x"}},
                {"node_id": "n1", "kind": "observe", "inputs": {"q": "b"}},
                {"node_id": "n2", "kind": "act", "inputs": {"tool": "read"}},
                {"node_id": "n3", "kind": "think", "inputs": {"prompt": "x"}},
            ]
        )
        patterns = extractor.detect_patterns(trace)
        assert len(patterns) >= 1
        assert any(len(p.node_ids) >= 2 for p in patterns)

    def test_extract_skill_from_pattern(self) -> None:
        """Repeated pattern → Skill IR (nested UPIR)."""
        extractor = SkillExtractor(min_occurrences=2)
        graph = _make_graph(
            nodes={"n1": "observe", "n2": "act", "n3": "think"},
            edges=[("n1", "n2"), ("n2", "n3")],
        )
        trace = _trace(
            [
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
                {"node_id": "n3", "kind": "think"},
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
                {"node_id": "n3", "kind": "think"},
            ]
        )
        patterns = extractor.detect_patterns(trace)
        assert len(patterns) >= 1
        skill_node = extractor.extract_skill(patterns[0], graph)
        assert skill_node is not None
        assert skill_node.kind == "skill"
        skill_id: str = skill_node.skill_id
        nested_upir = extractor.skill_table[skill_id]
        assert len(nested_upir.nodes) >= 2

    def test_min_pattern_occurrences(self) -> None:
        """Pattern must appear >= min_occurrences to extract."""
        extractor = SkillExtractor(min_occurrences=3)
        trace = _trace(
            [
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
            ]
        )
        patterns = extractor.detect_patterns(trace)
        # Only 2 occurrences, min is 3 → no patterns
        assert len(patterns) == 0

    def test_extracted_skill_stored(self) -> None:
        """Extracted skill added to skill_table."""
        extractor = SkillExtractor(min_occurrences=2)
        graph = _make_graph(
            nodes={"n1": "observe", "n2": "act"},
            edges=[("n1", "n2")],
        )
        trace = _trace(
            [
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
                {"node_id": "n1", "kind": "observe"},
                {"node_id": "n2", "kind": "act"},
            ]
        )
        patterns = extractor.detect_patterns(trace)
        assert len(patterns) >= 1
        skill = extractor.extract_skill(patterns[0], graph)
        assert skill is not None
        # Extracted skill should be stored in skill_table via extractor
        assert extractor.skill_table.get(skill.skill_id) is not None
