import os
import tempfile

from autoharness.environment.tool_env import ToolEnvironment


class TestToolEnvironment:
    """ToolEnvironment: observe/step/legal_actions/tools."""

    def test_observe_returns_state(self):
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        assert state is not None

    def test_legal_actions_returns_none(self):
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        assert env.legal_actions(state) is None

    def test_tools_returns_dict(self):
        env = ToolEnvironment(workspace="/tmp/test_ws")
        tools = env.tools()
        assert isinstance(tools, dict)
        assert "read_file" in tools
        assert "write_file" in tools

    def test_step_returns_tuple(self):
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        result = env.step(state, {"tool": "read_file", "args": {}})
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_step_returns_new_state(self):
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        new_state, reward, done, info = env.step(
            state, {"tool": "read_file", "args": {"path": "/tmp/nonexistent"}}
        )
        assert new_state is not None
        assert isinstance(reward, (int, float))
        assert isinstance(done, bool)
        assert isinstance(info, dict)
