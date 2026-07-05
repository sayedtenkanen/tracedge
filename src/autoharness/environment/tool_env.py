"""Tool-based environment with sandboxed file I/O tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autoharness.sandbox.workspace import Workspace

if TYPE_CHECKING:
    from collections.abc import Callable


class ToolEnvironment:
    """Tool-based environment with file I/O tools."""

    def __init__(self, workspace: str = "/tmp/workspace") -> None:  # nosec B108
        self.workspace = workspace
        self._sandbox = Workspace(root=workspace)

    def reset(self, seed: int) -> dict[str, Any]:
        return {"workspace": self.workspace, "seed": seed}

    def step(
        self, state: dict[str, Any], action: dict[str, Any]
    ) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        tool = action.get("tool", "")
        args = action.get("args", {})
        info: dict[str, Any] = {"tool": tool, "args": args}

        if tool == "read_file":
            path = args.get("path", "")
            try:
                self._sandbox.validate_path(path)
                with open(path) as f:  # path validated by sandbox
                    content = f.read()
                info["content"] = content
                return state, 0.0, False, info
            except PermissionError as e:
                info["error"] = str(e)
                return state, 0.0, False, info
            except FileNotFoundError:
                info["error"] = "file not found"
                return state, 0.0, False, info

        if tool == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            try:
                self._sandbox.validate_path(path)
                import os

                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:  # path validated by sandbox
                    f.write(content)
                info["success"] = True
                return state, 0.0, False, info
            except PermissionError as e:
                info["error"] = str(e)
                return state, 0.0, False, info
            except Exception as e:
                info["error"] = str(e)
                return state, 0.0, False, info

        info["error"] = f"unknown tool: {tool}"
        return state, 0.0, False, info

    def legal_actions(self, state: dict[str, Any]) -> list[dict[str, Any]] | None:
        return None

    def tools(self) -> dict[str, Callable[..., Any]]:
        return {
            "read_file": self._read_file,
            "write_file": self._write_file,
        }

    def _read_file(self, path: str) -> str:
        self._sandbox.validate_path(path)
        with open(path) as f:  # path validated by sandbox
            return f.read()

    def _write_file(self, path: str, content: str) -> None:
        self._sandbox.validate_path(path)
        import os

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:  # path validated by sandbox
            f.write(content)
