"""Environment Protocol — shared interface for all environment types."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Environment(Protocol):
    """Protocol that all environments must satisfy."""

    def reset(self, seed: int) -> dict[str, Any]:
        """Reset the environment and return initial state."""
        ...

    def step(
        self, state: dict[str, Any], action: dict[str, Any]
    ) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Execute one step: returns (next_state, reward, done, info)."""
        ...

    def legal_actions(self, state: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Return legal actions, or None if unconstrained (tool-use envs)."""
        ...

    def tools(self) -> dict[str, Any]:
        """Return available tools (empty dict for game environments)."""
        ...
