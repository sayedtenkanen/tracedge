"""Tests for Skill Extractor — Phase 2 meaningful extraction."""

from __future__ import annotations

from typing import Any

from tracedge.ir.upir import UPIR, UPIRNode
from tracedge.skills.extractor import SkillExtractor
from tracedge.trace.trace_ir import TraceEvent, TraceLog


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


class TestMeaningfulExtraction:
    """Phase 2 — extract from successful traces only, dedupe overlapping windows."""

    def test_successful_traces_only(self) -> None:
        """Only traces with reward > 0 contribute patterns."""
        extractor = SkillExtractor(min_occurrences=2)
        successful = _trace(
            [
                {"node_id": "read", "kind": "act"},
                {"node_id": "parse", "kind": "think"},
                {"node_id": "read", "kind": "act"},
                {"node_id": "parse", "kind": "think"},
            ]
        )
        failed = _trace(
            [
                {"node_id": "read", "kind": "act"},
                {"node_id": "crash", "kind": "act"},
            ]
        )
        patterns = extractor.extract_from_episodes([(successful, 1.0), (failed, 0.0)])
        # "read"→"parse" appears in successful traces only
        assert len(patterns) >= 1
        node_ids_sets = [tuple(p.node_ids) for p in patterns]
        assert ("read", "parse") in node_ids_sets or ("parse", "read") in node_ids_sets

    def test_no_patterns_from_all_failed(self) -> None:
        """No patterns when all traces failed."""
        extractor = SkillExtractor(min_occurrences=2)
        failed1 = _trace(
            [
                {"node_id": "n1", "kind": "act"},
                {"node_id": "n2", "kind": "act"},
            ]
        )
        failed2 = _trace(
            [
                {"node_id": "n1", "kind": "act"},
                {"node_id": "n2", "kind": "act"},
            ]
        )
        patterns = extractor.extract_from_episodes([(failed1, 0.0), (failed2, 0.0)])
        assert len(patterns) == 0

    def test_dedupe_overlapping_windows(self) -> None:
        """Overlapping windows are deduped; longest pattern kept."""
        extractor = SkillExtractor(min_occurrences=2)
        # Pattern "a"→"b"→"c" appears twice — but "a"→"b" is a subset
        trace = _trace(
            [
                {"node_id": "a", "kind": "act"},
                {"node_id": "b", "kind": "act"},
                {"node_id": "c", "kind": "act"},
                {"node_id": "a", "kind": "act"},
                {"node_id": "b", "kind": "act"},
                {"node_id": "c", "kind": "act"},
            ]
        )
        patterns = extractor.extract_from_episodes([(trace, 1.0)])
        # Should have the 3-node pattern, not the 2-node subsets
        node_ids_sets = [tuple(p.node_ids) for p in patterns]
        assert ("a", "b", "c") in node_ids_sets

    def test_extract_from_episodes_returns_patterns(self) -> None:
        """extract_from_episodes returns a list of Pattern objects."""
        extractor = SkillExtractor(min_occurrences=2)
        trace = _trace(
            [
                {"node_id": "x", "kind": "observe"},
                {"node_id": "y", "kind": "act"},
                {"node_id": "x", "kind": "observe"},
                {"node_id": "y", "kind": "act"},
            ]
        )
        patterns = extractor.extract_from_episodes([(trace, 1.0)])
        assert len(patterns) >= 1
        assert all(hasattr(p, "node_ids") for p in patterns)
        assert all(hasattr(p, "count") for p in patterns)

    def test_threshold_parameter(self) -> None:
        """Threshold parameter filters traces by reward."""
        extractor = SkillExtractor(min_occurrences=2)
        trace = _trace(
            [
                {"node_id": "a", "kind": "act"},
                {"node_id": "b", "kind": "act"},
                {"node_id": "a", "kind": "act"},
                {"node_id": "b", "kind": "act"},
            ]
        )
        # reward=0.5, threshold=0.8 → filtered out
        patterns = extractor.extract_from_episodes([(trace, 0.5)], success_threshold=0.8)
        assert len(patterns) == 0

        # reward=0.5, threshold=0.3 → included
        patterns = extractor.extract_from_episodes([(trace, 0.5)], success_threshold=0.3)
        assert len(patterns) >= 1
