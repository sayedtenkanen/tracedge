"""Example: Run a UPIR with OpenAI's API.

Requires: OPENAI_API_KEY environment variable set.

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/real_llm_task.py
"""

from __future__ import annotations

import os
import sys

from autoharness.ir.upir import UPIR, Edge, UPIRNode
from autoharness.reward.scorer import score_trace, value
from autoharness.runtime.vm import VM


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    from autoharness.intelligence.llm_client import OpenAIChatClient

    upir = UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(
                kind="observe",
                node_id="observe",
                query="What is the capital of France?",
            ),
            "think": UPIRNode(
                kind="think",
                node_id="think",
                prompt="Think step by step about the answer.",
            ),
            "act": UPIRNode(
                kind="act",
                node_id="act",
                tool="respond",
                args={"message": ""},
            ),
        },
        edges=[
            Edge(from_="observe", to="think", kind="sequential"),
            Edge(from_="think", to="act", kind="sequential"),
        ],
    )

    llm = OpenAIChatClient(model="gpt-4o")
    vm = VM(upir=upir, llm=llm, seed=42)
    trace = vm.run()

    for event in trace:
        kind = event.get("kind", "?")
        if kind == "think":
            print(f"[think] {event.get('response', '')[:100]}")
        elif kind == "observe":
            print(f"[observe] {event.get('query', '')}")
        else:
            print(f"[{kind}] {event}")

    reward = score_trace(trace, env_kind="tool")
    print(f"\nReward: {value(reward):.2f}")


if __name__ == "__main__":
    main()
