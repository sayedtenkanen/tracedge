"""GameEnvironment — legal-action-constrained turn-based game wrapper."""

from __future__ import annotations

import random
from typing import Any


class GameEnvironment:
    """Turn-based game environment with legal move enforcement.

    Wraps a simple Tic-Tac-Toe game for testing. legal_actions() returns
    the list of legal moves; illegal moves are tracked and rejected.

    After the agent (X) plays, an opponent (O) automatically plays a random
    legal move, and the turn returns to X.
    """

    def __init__(self, seed: int = 42) -> None:
        self._illegal_moves = 0
        self._total_moves = 0
        self._rng = random.Random(seed)  # nosec B311 — game opponent, not crypto

    def reset(self, seed: int) -> dict[str, Any]:
        """Reset the game board and return initial state."""
        self._illegal_moves = 0
        self._total_moves = 0
        self._rng = random.Random(seed)  # nosec B311 — game opponent, not crypto
        return {
            "board": [0] * 9,  # 0=empty, 1=X, -1=O
            "turn": 1,  # 1=X, -1=O
            "winner": None,
            "done": False,
        }

    def step(
        self, state: dict[str, Any], action: dict[str, Any]
    ) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Execute one move. Returns (next_state, reward, done, info).

        After the agent's move, if the game is not done, the opponent
        (O) automatically plays a random legal move and the turn returns
        to X.
        """
        board = list(state["board"])
        turn = state["turn"]
        position = action.get("position", -1)
        info: dict[str, Any] = {"position": position, "illegal": False}

        # Validate move
        if position < 0 or position > 8 or board[position] != 0:
            self._illegal_moves += 1
            info["illegal"] = True
            return state, 0.0, False, info

        # Apply agent's move
        board[position] = turn
        self._total_moves += 1

        # Check win
        winner = self._check_winner(board)
        done = winner is not None or all(cell != 0 for cell in board)

        # Sparse reward: +1 win, -1 loss, 0 draw/in-progress
        reward = 0.0
        if winner == 1:
            reward = 1.0
        elif winner == -1:
            reward = -1.0

        # Opponent auto-plays if game not done
        opponent_played = False
        if not done:
            legal = _legal_positions(board)
            if legal:
                opp_pos = self._rng.choice(legal)
                board[opp_pos] = -turn  # opponent's mark
                self._total_moves += 1
                opponent_played = True

                # Check if opponent won (opponent is always -turn)
                winner = self._check_winner(board)
                done = winner is not None or all(cell != 0 for cell in board)
                if winner is not None:
                    reward = -1.0

        next_state = {
            "board": board,
            "turn": None if done else 1,
            "winner": winner,
            "done": done,
        }
        info["opponent_played"] = opponent_played
        return next_state, reward, done, info

    def legal_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of legal moves (empty board positions)."""
        return [{"position": i} for i in _legal_positions(state["board"])]

    def tools(self) -> dict[str, Any]:
        """No tools for game environments."""
        return {}

    def get_stats(self) -> dict[str, Any]:
        """Return game statistics including illegal move count."""
        return {
            "illegal_moves": self._illegal_moves,
            "total_moves": self._total_moves,
        }

    @staticmethod
    def _check_winner(board: list[int]) -> int | None:
        """Check if there's a winner. Returns 1 (X), -1 (O), or None."""
        lines = [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],  # rows
            [0, 3, 6],
            [1, 4, 7],
            [2, 5, 8],  # cols
            [0, 4, 8],
            [2, 4, 6],  # diags
        ]
        for line in lines:
            total = board[line[0]] + board[line[1]] + board[line[2]]
            if total == 3:
                return 1
            if total == -3:
                return -1
        return None


def _legal_positions(board: list[int]) -> list[int]:
    """Return indices of empty cells on the board."""
    return [i for i in range(9) if board[i] == 0]
