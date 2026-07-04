from __future__ import annotations

from typing import Any, Optional


class State:
    """Namespaced state: state[node_id][key] = value."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, node_id: str, key: str, default: Any = None) -> Any:
        return self._data.get(node_id, {}).get(key, default)

    def set(self, node_id: str, key: str, value: Any) -> None:
        if node_id not in self._data:
            self._data[node_id] = {}
        self._data[node_id][key] = value

    def apply_delta(self, delta: dict[str, dict[str, Any]]) -> None:
        for node_id, updates in delta.items():
            if node_id not in self._data:
                self._data[node_id] = {}
            self._data[node_id].update(updates)

    def flatten(self) -> dict[str, dict[str, Any]]:
        return dict(self._data)
