"""Tests for GameEnvironment — legal-action-constrained game wrapper."""

from autoharness.environment.game_env import GameEnvironment


class TestGameEnvironment:
    """GameEnvironment: observe/step/legal_actions with legal move enforcement."""

    def test_game_env_observe(self):
        env = GameEnvironment()
        state = env.reset(seed=42)
        assert state is not None
        assert "board" in state
        assert "turn" in state

    def test_game_env_legal_actions_list(self):
        env = GameEnvironment()
        state = env.reset(seed=42)
        legal = env.legal_actions(state)
        assert isinstance(legal, list)
        assert len(legal) > 0

    def test_game_env_illegal_move_rejected(self):
        env = GameEnvironment()
        state = env.reset(seed=42)
        # Try an illegal move (occupied cell or out of range)
        new_state, reward, done, info = env.step(state, {"position": -1})
        assert info.get("illegal") is True
        assert reward == 0.0

    def test_game_env_illegal_move_tracking(self):
        env = GameEnvironment()
        state = env.reset(seed=42)
        env.step(state, {"position": -1})
        stats = env.get_stats()
        assert stats["illegal_moves"] > 0

    def test_game_env_sparse_reward(self):
        env = GameEnvironment()
        state = env.reset(seed=42)
        # Play a full game to get a sparse reward
        for pos in range(9):
            state, reward, done, info = env.step(state, {"position": pos})
            if done:
                break
        assert isinstance(reward, float)
        assert reward in (-1.0, 0.0, 1.0) or done
