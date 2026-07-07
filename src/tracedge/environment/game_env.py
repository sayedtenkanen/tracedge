"""GameEnvironment — legal-action-constrained turn-based game wrapper."""

from __future__ import annotations

from typing import Any


class GameEnvironment:
    """Turn-based game environment with legal move enforcement.

    Wraps a simple Tic-Tac-Toe game for testing. legal_actions() returns
    the list of legal moves; illegal moves are tracked and rejected.
    """

    def __init__(self) -> None:
        self._illegal_moves = 0
        self._total_moves = 0

    def reset(self, seed: int) -> dict[str, Any]:
        """Reset the game board and return initial state."""
        self._illegal_moves = 0
        self._total_moves = 0
        return {
            "board": [0] * 9,  # 0=empty, 1=X, -1=O
            "turn": 1,  # 1=X, -1=O
            "winner": None,
            "done": False,
        }

    def step(
        self, state: dict[str, Any], action: dict[str, Any]
    ) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Execute one move. Returns (next_state, reward, done, info)."""
        board = list(state["board"])
        turn = state["turn"]
        position = action.get("position", -1)
        info: dict[str, Any] = {"position": position, "illegal": False}

        # Validate move
        if position < 0 or position > 8 or board[position] != 0:
            self._illegal_moves += 1
            info["illegal"] = True
            return state, 0.0, False, info

        # Apply move
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

        next_state = {
            "board": board,
            "turn": -turn,
            "winner": winner,
            "done": done,
        }
        return next_state, reward, done, info

    def legal_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of legal moves (empty board positions)."""
        board = state["board"]
        return [{"position": i} for i in range(9) if board[i] == 0]

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
