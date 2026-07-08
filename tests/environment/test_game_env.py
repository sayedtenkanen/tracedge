"""Tests for GameEnvironment — legal-action-constrained game wrapper."""

from tracedge.environment.game_env import GameEnvironment


class TestGameEnvironment:
    """GameEnvironment: observe/step/legal_actions with legal move enforcement."""

    def test_game_env_observe(self) -> None:
        env = GameEnvironment()
        state = env.reset(seed=42)
        assert state is not None
        assert "board" in state
        assert "turn" in state

    def test_game_env_legal_actions_list(self) -> None:
        env = GameEnvironment()
        state = env.reset(seed=42)
        legal = env.legal_actions(state)
        assert isinstance(legal, list)
        assert len(legal) > 0

    def test_game_env_illegal_move_rejected(self) -> None:
        env = GameEnvironment()
        state = env.reset(seed=42)
        # Try an illegal move (occupied cell or out of range)
        new_state, reward, done, info = env.step(state, {"position": -1})
        assert info.get("illegal") is True
        assert reward == 0.0

    def test_game_env_illegal_move_tracking(self) -> None:
        env = GameEnvironment()
        state = env.reset(seed=42)
        env.step(state, {"position": -1})
        stats = env.get_stats()
        assert stats["illegal_moves"] > 0

    def test_game_env_sparse_reward(self) -> None:
        env = GameEnvironment()
        state = env.reset(seed=42)
        # Play a full game to get a sparse reward
        for pos in range(9):
            state, reward, done, info = env.step(state, {"position": pos})
            if done:
                break
        assert isinstance(reward, float)
        assert reward in (-1.0, 0.0, 1.0) or done

    def test_opponent_plays_after_agent(self) -> None:
        """After agent (X) plays, opponent (O) auto-plays and turn returns to X."""
        env = GameEnvironment(seed=42)
        state = env.reset(seed=42)
        assert state["turn"] == 1  # X's turn

        # Agent plays center
        state, reward, done, info = env.step(state, {"position": 4})
        # Opponent should have played, turn back to X
        assert info.get("opponent_played") is True
        assert state["turn"] == 1, "Turn should return to X after opponent plays"
        assert state["board"][4] == 1, "X should be at position 4"
        # At least one O on the board (opponent played)
        assert -1 in state["board"], "Opponent should have placed O"

    def test_game_reaches_terminal_state(self) -> None:
        """Game can reach done=True within reasonable steps with opponent."""
        env = GameEnvironment(seed=42)
        state = env.reset(seed=42)
        for _ in range(9):
            legal = env.legal_actions(state)
            if not legal:
                break
            state, reward, done, info = env.step(state, legal[0])
            if done:
                break
        # Game should finish within 9 moves (5 X + 4 O)
        assert done, f"Game should reach terminal state, got board={state['board']}"

    def test_opponent_does_not_play_on_illegal(self) -> None:
        """Opponent should not play if agent's move is illegal."""
        env = GameEnvironment(seed=42)
        state = env.reset(seed=42)
        # Fill position 4 first
        state, _, _, _ = env.step(state, {"position": 4})
        board_after_first = list(state["board"])
        o_count_before = board_after_first.count(-1)

        # Try illegal move (position 4 again)
        state, reward, done, info = env.step(state, {"position": 4})
        assert info.get("illegal") is True
        o_count_after = state["board"].count(-1)
        assert o_count_after == o_count_before, "Opponent should not play on illegal move"
