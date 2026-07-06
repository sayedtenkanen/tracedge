"""Workspace sandbox — path validation and tool timeout enforcement."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class Workspace:
    """Isolated workspace that rejects paths outside its root."""

    def __init__(self, root: str = "/tmp/workspace") -> None:  # nosec B108
        self.root = os.path.realpath(root)

    def validate_path(self, path: str) -> str:
        """Resolve *path* and raise PermissionError if it escapes the root.

        Returns the resolved (real) path on success.
        """
        resolved = os.path.realpath(path)
        if not resolved.startswith(self.root + os.sep) and resolved != self.root:
            raise PermissionError(
                f"Path {path!r} resolves to {resolved!r}, "
                f"which is outside workspace root {self.root!r}"
            )
        return resolved

    def run_tool(self, tool_fn: Callable[..., Any], timeout: float = 10.0) -> dict[str, Any]:
        """Run *tool_fn* with a wall-clock *timeout* (seconds).

        Returns ``{"result": <value>}`` on success or
        ``{"error": "Timeout", "timed_out": True}`` on timeout.
        """
        result_box: dict[str, Any] = {}
        error_box: list[Exception] = []

        def _target() -> None:
            try:
                result_box["result"] = tool_fn()
            except Exception as e:
                error_box.append(e)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return {"error": "Timeout", "timed_out": True}

        if error_box:
            return {"error": str(error_box[0])}

        return result_box
