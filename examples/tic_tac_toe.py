"""Tic-Tac-Toe demo — GameEnvironment with UPIR VM."""

from autoharness.environment.game_env import GameEnvironment
from autoharness.ir.upir import UPIR, Edge
from autoharness.runtime.vm import VM


class RandomPlayer:
    """LLM stand-in that picks the first legal move."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return "0"  # Always pick position 0 (simplified)


def main() -> None:
    env = GameEnvironment()
    state = env.reset(seed=42)

    # Build a minimal UPIR: observe → act
    upir = UPIR(
        entry="observe",
        nodes={
            "observe": {
                "kind": "observe",
                "node_id": "observe",
                "query": "Current board state",
            },
            "act": {
                "kind": "act",
                "node_id": "act",
                "tool": "place_move",
            },
        },
        edges=[Edge(from_="observe", to="act", kind="sequential")],
    )

    llm = RandomPlayer()
    vm = VM(upir=upir, llm=llm, environment=env)

    print("=== Tic-Tac-Toe Demo ===\n")

    # Play a few moves
    for turn in range(5):
        legal = env.legal_actions(state)
        if not legal:
            break

        trace = vm.run()
        action = legal[0]  # Always pick first legal move
        state, reward, done, info = env.step(state, action)

        board = state["board"]
        print(f"Turn {turn + 1}: placed at {action['position']}")
        print(f"  Board: {board[:3]} / {board[3:6]} / {board[6:9]}")
        print(f"  Reward: {reward}, Done: {done}")

        if done:
            winner = state["winner"]
            if winner == 1:
                print("  X wins!")
            elif winner == -1:
                print("  O wins!")
            else:
                print("  Draw!")
            break

    stats = env.get_stats()
    print(f"\nStats: {stats}")


if __name__ == "__main__":
    main()
