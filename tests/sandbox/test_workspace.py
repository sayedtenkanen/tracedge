"""Tests for workspace sandbox — path validation and isolation."""

import os
import tempfile

import pytest


class TestPathTraversal:
    """Paths outside the workspace root must be rejected."""

    def test_path_traversal_blocked(self, tmp_path: str) -> None:
        from autoharness.sandbox.workspace import Workspace

        ws = Workspace(root=str(tmp_path))
        outside = os.path.join(str(tmp_path), "..", "etc", "passwd")
        with pytest.raises(PermissionError):
            ws.validate_path(outside)

    def test_path_within_workspace_allowed(self, tmp_path: str) -> None:
        from autoharness.sandbox.workspace import Workspace

        ws = Workspace(root=str(tmp_path))
        inside = os.path.join(str(tmp_path), "subdir", "file.txt")
        resolved = ws.validate_path(inside)
        assert resolved.startswith(str(tmp_path))


class TestSymlinkEscape:
    """Symlinks that resolve outside the workspace must be blocked."""

    def test_symlink_escape_blocked(self, tmp_path: str) -> None:
        from autoharness.sandbox.workspace import Workspace

        ws = Workspace(root=str(tmp_path))
        target = os.path.join(str(tmp_path), "target.txt")
        link = os.path.join(str(tmp_path), "link.txt")
        outside_file = os.path.join(str(tmp_path), "..", "escaped.txt")
        with open(outside_file, "w") as f:
            f.write("secret")
        os.symlink(outside_file, target)
        with pytest.raises(PermissionError):
            ws.validate_path(target)


class TestToolTimeout:
    """Tool execution must be bounded by a timeout."""

    def test_tool_timeout_enforced(self) -> None:
        from autoharness.sandbox.workspace import Workspace

        ws = Workspace(root="/tmp/workspace")  # nosec B108

        def slow_tool() -> str:
            import time
            time.sleep(5)
            return "done"

        result = ws.run_tool(slow_tool, timeout=0.5)
        assert "error" in result or result.get("timed_out") is True
