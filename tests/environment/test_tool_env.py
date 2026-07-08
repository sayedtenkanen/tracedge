import os
import tempfile

from tracedge.environment.tool_env import ToolEnvironment


class TestToolEnvironment:
    """ToolEnvironment: observe/step/legal_actions/tools."""

    def test_observe_returns_state(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        assert state is not None

    def test_legal_actions_returns_none(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        assert env.legal_actions(state) is None

    def test_tools_returns_dict(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        tools = env.tools()
        assert isinstance(tools, dict)
        assert "read_file" in tools
        assert "write_file" in tools

    def test_step_returns_tuple(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        result = env.step(state, {"tool": "read_file", "args": {}})
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_step_read_file_not_found(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        new_state, reward, done, info = env.step(
            state, {"tool": "read_file", "args": {"path": "/tmp/nonexistent"}}
        )
        assert new_state is not None
        assert isinstance(reward, int | float)
        assert isinstance(done, bool)
        assert isinstance(info, dict)
        assert "error" in info

    def test_step_write_and_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = ToolEnvironment(workspace=tmpdir)
            state = env.reset(seed=42)
            filepath = os.path.join(tmpdir, "test.txt")

            # Write
            new_state, _, _, info = env.step(
                state, {"tool": "write_file", "args": {"path": filepath, "content": "hello"}}
            )
            assert info.get("success") is True

            # Read
            new_state, _, _, info = env.step(
                new_state, {"tool": "read_file", "args": {"path": filepath}}
            )
            assert info.get("content") == "hello"

    def test_step_unknown_tool(self) -> None:
        env = ToolEnvironment(workspace="/tmp/test_ws")
        state = env.reset(seed=42)
        _, _, _, info = env.step(state, {"tool": "bogus", "args": {}})
        assert "error" in info
        assert "unknown tool" in info["error"]

    def test_read_file_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = ToolEnvironment(workspace=tmpdir)
            filepath = os.path.join(tmpdir, "r.txt")
            with open(filepath, "w") as f:
                f.write("content")
            assert env._read_file(filepath) == "content"

    def test_write_file_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = ToolEnvironment(workspace=tmpdir)
            filepath = os.path.join(tmpdir, "w.txt")
            env._write_file(filepath, "written")
            with open(filepath) as f:
                assert f.read() == "written"
