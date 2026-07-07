"""Tests for Critic — consolidates rollout failures into structured feedback."""

from __future__ import annotations

from typing import Any

from tracedge.intelligence.critic import Critic, CriticOutput


class TestCriticFailureClustering:
    """Critic groups failures by type and root cause."""

    def test_clusters_exception_failures(self) -> None:
        traces = [
            [
                {"node_id": "n1", "kind": "act", "raised": "TimeoutError: tool timed out"},
                {"node_id": "n2", "kind": "harness_call", "verdict": "fail"},
            ],
            [
                {"node_id": "n1", "kind": "act", "raised": "TimeoutError: tool timed out"},
            ],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        timeout_clusters = [c for c in output.failure_clusters if c["root_cause"] == "TimeoutError"]
        assert timeout_clusters, "Expected a failure cluster with root_cause 'TimeoutError'"
        assert timeout_clusters[0]["count"] == 2

    def test_clusters_empty_trace(self) -> None:
        critic = Critic()
        output = critic.analyze([])
        assert output.failure_clusters == []
        assert output.legality_violations == []
        assert output.inefficiency_patterns == []

    def test_no_failures_clean_trace(self) -> None:
        traces: list[list[dict[str, Any]]] = [
            [
                {"node_id": "n1", "kind": "act", "outputs": {"result": "ok"}},
                {"node_id": "n2", "kind": "harness_call", "verdict": "ok"},
            ],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert output.failure_clusters == []
        assert output.legality_violations == []
        assert output.inefficiency_patterns == []


class TestCriticLegalityViolations:
    """Critic detects illegal actions in game environments."""

    def test_detects_illegal_actions(self) -> None:
        traces = [
            [
                {"node_id": "n1", "kind": "act", "legal": False, "outputs": {"action": "invalid"}},
                {"node_id": "n2", "kind": "act", "legal": True, "outputs": {"action": "valid"}},
            ],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert len(output.legality_violations) == 1
        assert output.legality_violations[0]["node_id"] == "n1"

    def test_no_legal_flags_ignored(self) -> None:
        traces = [
            [{"node_id": "n1", "kind": "act", "outputs": {"action": "ok"}}],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert output.legality_violations == []


class TestCriticInefficiencyPatterns:
    """Critic detects redundant or suboptimal execution paths."""

    def test_detects_high_step_count(self) -> None:
        traces = [
            [{"node_id": f"n{i}", "kind": "act"} for i in range(20)],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert len(output.inefficiency_patterns) >= 1

    def test_short_trace_no_inefficiency(self) -> None:
        traces = [
            [{"node_id": "n1", "kind": "act"}, {"node_id": "n2", "kind": "act"}],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert output.inefficiency_patterns == []

    def test_custom_inefficiency_threshold(self) -> None:
        traces = [
            [{"node_id": f"n{i}", "kind": "act"} for i in range(4)],
        ]
        critic = Critic(inefficiency_threshold=3)
        output = critic.analyze(traces)
        assert len(output.inefficiency_patterns) >= 1


class TestCriticMultipleTraces:
    """Critic consolidates across multiple rollout traces."""

    def test_merges_failures_across_traces(self) -> None:
        traces = [
            [
                {"node_id": "n1", "kind": "act", "raised": "ValueError: bad input"},
            ],
            [
                {"node_id": "n1", "kind": "act", "raised": "ValueError: bad input"},
            ],
            [
                {"node_id": "n1", "kind": "act", "raised": "KeyError: missing key"},
            ],
        ]
        critic = Critic()
        output = critic.analyze(traces)
        assert len(output.failure_clusters) >= 1
        total_count = sum(c["count"] for c in output.failure_clusters)
        assert total_count == 3


class TestCriticOutputModel:
    """CriticOutput is a valid Pydantic model."""

    def test_empty_output(self) -> None:
        output = CriticOutput()
        assert output.failure_clusters == []
        assert output.legality_violations == []
        assert output.inefficiency_patterns == []

    def test_no_shared_mutable_defaults(self) -> None:
        a = CriticOutput()
        b = CriticOutput()
        a.failure_clusters.append({"root_cause": "test", "count": 1})
        assert b.failure_clusters == []


class TestCriticRealHarnessErrors:
    """Critic handles real run_harness error strings without crashing."""

    def test_real_exception_string_through_critic(self) -> None:
        from tracedge.sandbox.harness_runner import run_harness

        result = run_harness(code="raise NameError('oops')")
        assert result["verdict"] == "error"
        assert isinstance(result["raised"], str)

        trace = [{"node_id": "n1", "kind": "harness_call", **result}]
        critic = Critic()
        output = critic.analyze([trace])
        assert len(output.failure_clusters) >= 1
        assert output.failure_clusters[0]["root_cause"] == "NameError"
