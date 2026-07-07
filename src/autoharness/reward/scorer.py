"""Reward Engine — trace → structured reward vector with scalar value() function."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Reward(BaseModel):
    """Structured reward vector with dual-mode signal."""

    task_success: float = 0.0
    efficiency: float = 1.0
    safety: float = 1.0
    skill_gain: float = 0.0
    legality: float | None = None


def score_trace(
    trace: list[dict[str, Any]],
    env_kind: str = "tool",
    max_steps: int = 50,
) -> Reward:
    """Convert a trace into a Reward vector.

    Args:
        trace: List of trace events from VM execution.
        env_kind: "game" or "tool" — affects legality handling.
        max_steps: Reference step count for efficiency normalization.
    """
    task_success = _score_success(trace)
    efficiency = _score_efficiency(len(trace), max_steps)
    safety = _score_safety(trace)
    legality = _score_legality(trace) if env_kind == "game" else None

    return Reward(
        task_success=task_success,
        efficiency=efficiency,
        safety=safety,
        legality=legality,
    )


def _score_success(trace: list[dict[str, Any]]) -> float:
    """1.0 if task succeeded, else 0.0.

    Success signals (checked in order):
    1. harness_call with verdict='ok' — sandboxed code ran successfully
    2. act event with env_result.done=True and reward>0 — environment reported success
    3. act event with env_result.info.success=True — tool reported success

    Known-generous: ToolEnvironment rewards every successful write_file call,
    so task_success=1 fires for any write — not just completed programs.
    Acceptable for MVP because efficiency and safety still penalize waste.
    """
    for event in trace:
        # Signal 1: harness_call verdict
        if event.get("kind") == "harness_call" and event.get("verdict") == "ok":
            return 1.0

        # Signal 2: environment terminal success (game won, task complete)
        env_result = event.get("env_result", {})
        if env_result.get("done") and env_result.get("reward", 0) > 0:
            return 1.0

        # Signal 3: tool-level success flag
        info = env_result.get("info")
        if isinstance(info, dict) and info.get("success"):
            return 1.0

    return 0.0


def _score_efficiency(num_steps: int, max_steps: int) -> float:
    """1.0 for 1 step, decays toward 0 as steps approach max_steps.

    `max_steps` is clamped to a minimum of 1 to avoid division by zero.
    """
    effective_max_steps = max(1, max_steps)
    if num_steps <= 1:
        return 1.0
    return max(0.0, 1.0 - (num_steps - 1) / effective_max_steps)


def _score_safety(trace: list[dict[str, Any]]) -> float:
    """1.0 if no exceptions raised, < 1.0 for each raised exception."""
    penalty = 0.0
    for event in trace:
        if event.get("raised"):
            penalty += 0.25
    return max(0.0, 1.0 - penalty)


def _score_legality(trace: list[dict[str, Any]]) -> float:
    """Fraction of legal actions. None if no legal flags present."""
    legal_events = [e for e in trace if e.get("legal") is not None]
    if not legal_events:
        return 1.0
    legal_count = sum(1 for e in legal_events if e["legal"] is True)
    return legal_count / len(legal_events)


def value(reward: Reward, env_kind: str = "tool") -> float:
    """Unified scalar reward function for bandit-style search.

    Converts a Reward vector to a single float in [0, 1].

    Weights differ by environment kind:
    - game: task_success=0.5, legality=0.3, safety=0.2
    - tool: task_success=0.6, efficiency=0.2, safety=0.2
    """
    if env_kind == "game":
        legality = reward.legality if reward.legality is not None else reward.efficiency
        raw = 0.5 * reward.task_success + 0.3 * legality + 0.2 * reward.safety
    else:
        raw = 0.6 * reward.task_success + 0.2 * reward.efficiency + 0.2 * reward.safety

    return max(0.0, min(1.0, raw))
