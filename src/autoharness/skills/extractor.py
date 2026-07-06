"""Skill Extractor — detect repeated subgraphs in traces, compress into reusable skills."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from autoharness.ir.upir import UPIR, UPIRNode


class Pattern(BaseModel):
    """A detected repeated pattern in a trace."""

    node_ids: list[str]
    count: int = 0


class SkillExtractor:
    """Detects repeated subgraphs in execution traces and extracts them as skills."""

    def __init__(self, min_occurrences: int = 2) -> None:
        self.min_occurrences = min_occurrences
        self.skill_table: dict[str, UPIR] = {}
        self._skill_counter = 0

    def detect_patterns(self, trace: Any) -> list[Pattern]:
        """Find repeated consecutive node-id sequences in a trace.

        Uses a sliding-window count map to avoid O(n^3) recomputation:
        - Build all windows of each length in O(n).
        - Count occurrences via a dict lookup instead of re-scanning.
        """
        events = trace.events if hasattr(trace, "events") else trace
        if len(events) < 2:
            return []

        node_ids = [e.node_id for e in events]
        n = len(node_ids)
        patterns: list[Pattern] = []

        for length in range(2, n // self.min_occurrences + 1):
            counts: dict[tuple[str, ...], int] = {}
            for start in range(n - length + 1):
                key = tuple(node_ids[start : start + length])
                counts[key] = counts.get(key, 0) + 1

            for candidate, count in counts.items():
                if count >= self.min_occurrences:
                    patterns.append(Pattern(node_ids=list(candidate), count=count))

        patterns.sort(key=lambda p: (-len(p.node_ids), -p.count))
        return patterns

    def extract_skill(self, pattern: Pattern, source_graph: UPIR) -> UPIRNode | None:
        """Extract a pattern into a nested UPIR skill and store in skill_table."""
        if pattern.count < self.min_occurrences:
            return None

        skill_nodes: dict[str, UPIRNode] = {}
        for nid in pattern.node_ids:
            if nid in source_graph.nodes:
                node = source_graph.nodes[nid]
                if isinstance(node, UPIRNode):
                    skill_nodes[nid] = node
                else:
                    skill_nodes[nid] = UPIRNode.model_validate(node)

        if not skill_nodes:
            return None

        # Derive entry from actual skill_nodes to avoid invalid reference
        if pattern.node_ids[0] in skill_nodes:
            entry = pattern.node_ids[0]
        else:
            entry = next(iter(skill_nodes))

        skill_edges = [
            {"from": pattern.node_ids[i], "to": pattern.node_ids[i + 1], "kind": "sequential"}
            for i in range(len(pattern.node_ids) - 1)
            if pattern.node_ids[i] in skill_nodes and pattern.node_ids[i + 1] in skill_nodes
        ]

        skill_upir = UPIR(
            entry=entry,
            nodes=skill_nodes,
            edges=skill_edges,
            harness_table={},
            skill_table={},
        )

        self._skill_counter += 1
        skill_id = f"skill_{self._skill_counter}"
        self.skill_table[skill_id] = skill_upir

        return UPIRNode(
            kind="skill",
            node_id=skill_id,
            skill_id=skill_id,
            pattern=pattern.model_dump(),
        )
