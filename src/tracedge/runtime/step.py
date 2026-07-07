from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StepResult(BaseModel):
    next: str | None = None
    state_delta: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    reward_signal: dict[str, Any] = {}
    trace_event: dict[str, Any] = {}
