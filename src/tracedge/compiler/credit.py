"""Credit assignment compiler — attributes reward credit to individual nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracedge.ir.upir import UPIR


def assign_credits(
    upir: UPIR,
    trace: list[str],
    total_reward: float,
) -> dict[str, float]:
    """Distribute total_reward equally among nodes in the trace.

    Nodes not in the trace get 0 credit. Returns a dict of node_id → credit.
    """
    if not trace:
        return {nid: 0.0 for nid in upir.nodes}

    per_node = total_reward / len(trace)
    return {nid: per_node if nid in trace else 0.0 for nid in upir.nodes}
