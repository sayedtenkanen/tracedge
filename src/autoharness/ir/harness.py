"""Harness IR — formalized harness types, signatures, and result contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

VALID_HARNESS_KINDS = ("action_filter", "action_verifier", "policy")


class Harness(BaseModel):
    """A harness: sandboxed code that filters, verifies, or replaces LLM actions."""

    kind: str
    code: str
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    effects: dict[str, Any] = Field(
        default_factory=lambda: {"filesystem": False, "network": False, "llm_calls": 0}
    )
    target_env_kind: str = "both"
    version: int = 1
    legality_accuracy: float | None = None
    guard_policy: dict[str, Any] = Field(
        default_factory=lambda: {"no_try_except": True, "max_runtime_ms": 5000}
    )

    @model_validator(mode="after")
    def validate_kind(self) -> Harness:
        if self.kind not in VALID_HARNESS_KINDS:
            raise ValueError(f"kind must be one of {VALID_HARNESS_KINDS}, got {self.kind!r}")
        return self


class HarnessResult(BaseModel):
    """Result of executing a harness: verdict, raised exception, and cost."""

    verdict: Any = None
    raised: str | None = None
    cost: float = 0.0
