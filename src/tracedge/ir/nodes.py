from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Observe(BaseModel):
    node_id: str
    kind: str = "observe"
    query: str = ""


class Act(BaseModel):
    node_id: str
    kind: str = "act"
    tool: str = ""
    args: dict[str, Any] = {}


class Think(BaseModel):
    node_id: str
    kind: str = "think"
    prompt: str = ""


class Branch(BaseModel):
    node_id: str
    kind: str = "branch"
    condition: str = ""
    true_next: str = ""
    false_next: str = ""
    probability: float | None = None  # None = LLM-evaluated; 0.0-1.0 = Bernoulli sample


class SkillCall(BaseModel):
    node_id: str
    kind: str = "skill_call"
    skill_id: str = ""
    args: dict[str, Any] = {}


class HarnessCall(BaseModel):
    node_id: str
    kind: str = "harness_call"
    harness_id: str = ""
    args: dict[str, Any] = {}


class Phi(BaseModel):
    """SSA-style phi node for merging branch values.

    ``branch_source`` identifies the branch node whose outcome selects the
    value.  ``values`` maps ``"true"``/``"false"`` → a node ID; the VM reads
    the trace to find which branch was taken and selects the corresponding
    value into ``selected``.

    ``sources`` is a legacy field from before branch-value selection was
    implemented.  The VM no longer reads it — retained only so existing UPIR
    graphs that serialize the field don't break.
    """

    node_id: str
    kind: str = "phi"
    sources: list[str] = []  # legacy — unused by VM, kept for serialization compat
    branch_source: str = ""
    values: dict[str, str] = {}
