"""Trace IR — structured trace events for execution observability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TraceEvent(BaseModel):
    """A single trace event from one node execution."""

    node_id: str = ""
    kind: str = ""
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    cost: float = 0.0
    legal: bool | None = None
    # HarnessCall-specific fields
    harness_id: str | None = None
    verdict: Any = None
    raised: str | None = None
    # Branch-specific
    condition: str | None = None
    taken: str | None = None
    # Generic extra fields
    extra: dict[str, Any] = {}


class TraceLog:
    """Ordered collection of TraceEvents from a single execution run."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def append(self, event: TraceEvent) -> None:
        self.events.append(event)

    def __len__(self) -> int:
        return len(self.events)

    def __getitem__(self, idx: int) -> TraceEvent:
        return self.events[idx]
