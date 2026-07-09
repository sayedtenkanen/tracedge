"""Tests for the CLI demo — must show legal play and positive reward."""

from tracedge.main import _run_demo


class TestDemo:
    def test_demo_trace_has_no_illegal_moves(self) -> None:
        """Demo must not produce any illegal move events."""
        import io
        import sys

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            _run_demo()
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert "illegal': True" not in output, f"Demo produced illegal move:\n{output}"

    def test_demo_outputs_positive_reward(self) -> None:
        """Demo must end with a non-negative reward (win or draw)."""
        import io
        import sys

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            _run_demo()
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        # Extract reward line
        for line in output.splitlines():
            if line.strip().startswith("Reward:"):
                reward_str = line.split(":")[1].strip()
                reward = float(reward_str)
                assert reward >= 0.0, f"Demo reward {reward} is negative"
                return
        raise AssertionError(f"No Reward line found in output:\n{output}")
