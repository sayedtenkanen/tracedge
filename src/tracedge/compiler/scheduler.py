"""Cost-aware scheduler — counts LLM calls and enforces budget."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracedge.ir.upir import UPIR


class BudgetError(Exception):
    """Raised when a plan's LLM call count exceeds its budget."""


def check_budget(upir: UPIR) -> bool:
    """Return True if plan is within budget; raise BudgetError otherwise.

    Budget is the maximum number of ``act`` nodes (each costs one LLM call).
    ``budget=None`` means unlimited.
    """
    if upir.budget is None:
        return True

    act_count = sum(1 for node in upir.nodes.values() if getattr(node, "kind", "") == "act")
    if act_count > upir.budget:
        raise BudgetError(f"{act_count} acts exceed budget of {upir.budget}")
    return True
