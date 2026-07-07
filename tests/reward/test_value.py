"""Tests for value() function — unified scalar reward for bandit search."""

from tracedge.reward.scorer import Reward, value


class TestValueFunctionGameEnv:
    """value() uses legality + task_success weights for game env."""

    def test_game_env_weights(self) -> None:
        r = Reward(task_success=1.0, legality=1.0)
        v = value(r, env_kind="game")
        assert v > 0.8

    def test_game_env_illegal_penalizes(self) -> None:
        r = Reward(task_success=1.0, legality=0.0)
        v = value(r, env_kind="game")
        assert v < 0.8  # legality=0.0 reduces from 1.0


class TestValueFunctionToolEnv:
    """value() uses task_success + efficiency weights for tool env."""

    def test_tool_env_weights(self) -> None:
        r = Reward(task_success=1.0, efficiency=1.0)
        v = value(r, env_kind="tool")
        assert v > 0.8

    def test_tool_env_inefficient_penalizes(self) -> None:
        r = Reward(task_success=1.0, efficiency=0.2)
        v = value(r, env_kind="tool")
        assert v < 0.9  # efficiency=0.2 reduces from 1.0


class TestValueClamped:
    """value() output always in [0, 1]."""

    def test_clamped_low(self) -> None:
        r = Reward(task_success=0.0, efficiency=0.0, safety=0.0)
        v = value(r, env_kind="tool")
        assert 0.0 <= v <= 1.0

    def test_clamped_high(self) -> None:
        r = Reward(task_success=1.0, efficiency=1.0, safety=1.0, legality=1.0)
        v = value(r, env_kind="game")
        assert 0.0 <= v <= 1.0

    def test_clamped_out_of_range_low_components(self) -> None:
        r = Reward(task_success=0.5, efficiency=-0.5, safety=-1.0)
        v = value(r, env_kind="tool")
        assert 0.0 <= v <= 1.0

    def test_clamped_out_of_range_high_components(self) -> None:
        r = Reward(task_success=2.0, efficiency=0.5, safety=1.5, legality=0.0)
        v = value(r, env_kind="game")
        assert 0.0 <= v <= 1.0

    def test_clamped_mixed_out_of_range_components(self) -> None:
        r = Reward(task_success=1.2, efficiency=-0.3, safety=0.8, legality=1.7)
        v = value(r, env_kind="tool")
        assert 0.0 <= v <= 1.0


class TestValueDeterministic:
    """Same reward + same weights → same value."""

    def test_deterministic(self) -> None:
        r = Reward(task_success=0.7, efficiency=0.8, safety=0.9)
        v1 = value(r, env_kind="tool")
        v2 = value(r, env_kind="tool")
        assert v1 == v2


class TestValueLegalityNoneFallback:
    """When legality is None, falls back to efficiency."""

    def test_none_fallback_to_efficiency(self) -> None:
        r_with = Reward(task_success=1.0, efficiency=0.5, legality=0.5)
        r_none = Reward(task_success=1.0, efficiency=0.5, legality=None)
        v_with = value(r_with, env_kind="game")
        v_none = value(r_none, env_kind="game")
        assert v_with == v_none
