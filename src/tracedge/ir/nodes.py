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
    node_id: str
    kind: str = "phi"
    sources: list[str] = []
