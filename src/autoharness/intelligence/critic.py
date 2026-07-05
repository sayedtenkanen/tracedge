"""Critic — consolidates rollout failures into structured feedback."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, Field


class CriticOutput(BaseModel):
    """Structured feedback from the Critic."""

    failure_clusters: list[dict[str, Any]] = Field(default_factory=list)
    legality_violations: list[dict[str, Any]] = Field(default_factory=list)
    inefficiency_patterns: list[dict[str, Any]] = Field(default_factory=list)


class Critic:
    """Analyzes rollout traces and produces structured feedback.

    Consolidates failures across multiple rollouts into categorized clusters,
    detects legality violations (GameEnvironment), and identifies
    inefficiency patterns.
    """

    def __init__(self, inefficiency_threshold: int = 10) -> None:
        self.inefficiency_threshold = inefficiency_threshold

    def analyze(self, traces: list[list[dict[str, Any]]]) -> CriticOutput:
        """Analyze a list of rollout traces and return structured feedback.

        Args:
            traces: List of traces, where each trace is a list of trace events.
        """
        if not traces:
            return CriticOutput()

        failure_clusters = self._cluster_failures(traces)
        legality_violations = self._detect_legality_violations(traces)
        inefficiency_patterns = self._detect_inefficiency(traces)

        return CriticOutput(
            failure_clusters=failure_clusters,
            legality_violations=legality_violations,
            inefficiency_patterns=inefficiency_patterns,
        )

    def _cluster_failures(self, traces: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        """Group failures by root cause across all traces."""
        cause_counts: Counter[str] = Counter()

        for trace in traces:
            for event in trace:
                raised = event.get("raised")
                if raised:
                    root_cause = self._extract_root_cause(raised)
                    cause_counts[root_cause] += 1

        return [
            {"root_cause": cause, "count": count} for cause, count in cause_counts.most_common()
        ]

    def _extract_root_cause(self, error_str: str) -> str:
        """Extract a concise root cause from an error string."""
        if ":" in error_str:
            return error_str.split(":")[0].strip()
        return error_str.strip()

    def _detect_legality_violations(
        self, traces: list[list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Find events where legal=False."""
        violations = []
        for trace in traces:
            for event in trace:
                if event.get("legal") is False:
                    violations.append(
                        {
                            "node_id": event.get("node_id", "unknown"),
                            "outputs": event.get("outputs", {}),
                        }
                    )
        return violations

    def _detect_inefficiency(self, traces: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        """Flag traces with excessive step counts."""
        patterns = []
        for i, trace in enumerate(traces):
            if len(trace) > self.inefficiency_threshold:
                patterns.append(
                    {
                        "trace_index": i,
                        "step_count": len(trace),
                        "threshold": self.inefficiency_threshold,
                    }
                )
        return patterns
