"""Skill Extractor — detect repeated subgraphs in traces, compress into reusable skills."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from autoharness.ir.upir import UPIR, UPIRNode


def _subsequences(seq: tuple[str, ...], length: int) -> set[tuple[str, ...]]:
    """Return all contiguous subsequences of `seq` with the given `length`."""
    return {seq[i : i + length] for i in range(len(seq) - length + 1)}


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

        node_ids: list[str] = []
        for e in events:
            if hasattr(e, "node_id"):
                node_id = e.node_id
            elif isinstance(e, dict):
                node_id = e.get("node_id")
            else:
                node_id = None
            if not node_id:
                continue
            node_ids.append(node_id)

        if len(node_ids) < 2:
            return []
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

    def extract_from_episodes(
        self,
        episodes: list[tuple[Any, float]],
        success_threshold: float = 0.0,
    ) -> list[Pattern]:
        """Extract patterns from successful episodes only.

        Args:
            episodes: List of (trace, reward) tuples.
            success_threshold: Minimum reward to consider a trace successful.

        Returns:
            Deduplicated patterns sorted by length (longest first), then count.
        """
        # Aggregate patterns across successful episodes.
        # Key: tuple(node_ids), Value: total occurrence count across all episodes.
        pattern_counts: dict[tuple[str, ...], int] = {}

        for trace, reward in episodes:
            if reward <= success_threshold:
                continue

            # Find patterns in this single episode
            episode_patterns = self.detect_patterns(trace)

            for pat in episode_patterns:
                key = tuple(pat.node_ids)
                pattern_counts[key] = pattern_counts.get(key, 0) + pat.count

        # Build Pattern objects
        patterns = [
            Pattern(node_ids=list(k), count=v)
            for k, v in pattern_counts.items()
            if v >= self.min_occurrences
        ]

        # Dedupe: if pattern A is a contiguous subsequence of pattern B,
        # and B meets min_occurrences, drop A.
        patterns = self._dedupe_subsequences(patterns)

        patterns.sort(key=lambda p: (-len(p.node_ids), -p.count))
        return patterns

    def _dedupe_subsequences(self, patterns: list[Pattern]) -> list[Pattern]:
        """Remove patterns that are contiguous subsequences of longer patterns.

        Indexes patterns by length to avoid redundant subsequence checks.
        A pattern of length L is only compared against kept patterns of length > L.
        """
        if not patterns:
            return patterns

        # Group patterns by length for efficient lookup
        by_length: dict[int, list[Pattern]] = {}
        for pat in patterns:
            ln = len(pat.node_ids)
            by_length.setdefault(ln, []).append(pat)

        kept: list[Pattern] = []
        kept_keys: set[tuple[str, ...]] = set()

        # Process longest patterns first — they are always kept
        for length in sorted(by_length, reverse=True):
            for pat in by_length[length]:
                pat_key = tuple(pat.node_ids)
                is_sub = False
                # Only compare against kept patterns strictly longer than this one
                for existing_key in kept_keys:
                    if len(existing_key) > length and pat_key in _subsequences(
                        existing_key, length
                    ):
                        is_sub = True
                        break
                if not is_sub:
                    kept.append(pat)
                    kept_keys.add(pat_key)

        return kept

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
