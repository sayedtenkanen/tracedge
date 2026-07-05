"""Tests for Reward scorer — trace → reward vector."""

from autoharness.reward.scorer import Reward, score_trace


class TestRewardVectorSchema:
    """Reward has task_success, efficiency, safety, skill_gain, legality."""

    def test_reward_has_all_fields(self) -> None:
        r = Reward()
        assert hasattr(r, "task_success")
        assert hasattr(r, "efficiency")
        assert hasattr(r, "safety")
        assert hasattr(r, "skill_gain")
        assert hasattr(r, "legality")

    def test_reward_defaults(self) -> None:
        r = Reward()
        assert r.task_success == 0.0
        assert r.efficiency == 1.0
        assert r.safety == 1.0
        assert r.skill_gain == 0.0
        assert r.legality is None


class TestRewardSuccessDetection:
    """Successful task completion → task_success=1.0."""

    def test_success_detected(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "harness_call", "verdict": "ok"},
        ]
        r = score_trace(trace)
        assert r.task_success == 1.0

    def test_failure_detected(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "harness_call", "verdict": "error"},
        ]
        r = score_trace(trace)
        assert r.task_success == 0.0

    def test_no_harness_call(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "observe"},
        ]
        r = score_trace(trace)
        assert r.task_success == 0.0


class TestRewardEfficiencyPenalty:
    """More steps → lower efficiency."""

    def test_fewer_steps_higher_efficiency(self) -> None:
        short = [{"node_id": "n1", "kind": "observe"}]
        long_ = [
            {"node_id": "n1", "kind": "observe"},
            {"node_id": "n2", "kind": "act"},
            {"node_id": "n3", "kind": "think"},
            {"node_id": "n4", "kind": "act"},
        ]
        r_short = score_trace(short)
        r_long = score_trace(long_)
        assert r_short.efficiency > r_long.efficiency

    def test_efficiency_clamped(self) -> None:
        trace = [{"node_id": "n1", "kind": "observe"}] * 200
        r = score_trace(trace)
        assert 0.0 <= r.efficiency <= 1.0


class TestRewardSafetyScore:
    """Unsafe actions → safety < 1.0."""

    def test_safe_trace(self) -> None:
        trace = [{"node_id": "n1", "kind": "observe"}]
        r = score_trace(trace)
        assert r.safety == 1.0

    def test_raised_exception_reduces_safety(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "harness_call", "verdict": "ok", "raised": "ValueError"},
        ]
        r = score_trace(trace)
        assert r.safety < 1.0

    def test_multiple_exceptions_saturate_safety_at_zero(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "harness_call", "verdict": "ok", "raised": "ValueError"},
            {"node_id": "n2", "kind": "harness_call", "verdict": "ok", "raised": "RuntimeError"},
            {"node_id": "n3", "kind": "harness_call", "verdict": "ok", "raised": "TypeError"},
            {"node_id": "n4", "kind": "harness_call", "verdict": "ok", "raised": "IndexError"},
        ]
        r = score_trace(trace)
        assert r.safety == 0.0


class TestRewardLegalityGameEnv:
    """GameEnvironment rewards legality."""

    def test_legal_actions_high_legality(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "act", "legal": True},
            {"node_id": "n2", "kind": "act", "legal": True},
        ]
        r = score_trace(trace, env_kind="game")
        assert r.legality == 1.0

    def test_illegal_actions_low_legality(self) -> None:
        trace = [
            {"node_id": "n1", "kind": "act", "legal": True},
            {"node_id": "n2", "kind": "act", "legal": False},
        ]
        r = score_trace(trace, env_kind="game")
        assert r.legality is not None
        assert r.legality < 1.0

    def test_no_legality_flags_defaults_to_legal(self) -> None:
        """When no events have a `legal` flag, legality defaults to 1.0."""
        trace = [
            {"node_id": "n1", "kind": "act"},
            {"node_id": "n2", "kind": "act"},
        ]
        r = score_trace(trace, env_kind="game")
        assert r.legality == 1.0


class TestRewardLegalityNoneToolEnv:
    """ToolEnvironment → legality is None."""

    def test_tool_env_legality_none(self) -> None:
        trace = [{"node_id": "n1", "kind": "act"}]
        r = score_trace(trace, env_kind="tool")
        assert r.legality is None
