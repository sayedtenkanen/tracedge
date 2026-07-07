"""End-to-end demo — full AutoHarness loop with a fake LLM.

Demonstrates: variants → Thompson search → skill extraction → memory persistence.
The 'good' variant always succeeds; the 'bad' variant always fails.
Thompson search discovers the winner.

No API key required. Run with:

    python examples/end_to_end.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from autoharness.ir.upir import UPIR, UPIRNode
from autoharness.main import run_autoharness


class DemoLLM:
    """Fake LLM — always returns 'ok'."""

    def chat(self, prompt: str) -> str:
        return "ok"


def main() -> None:
    # 1. Define strategy variants — one succeeds, one fails
    variants = {
        "good": UPIR(
            entry="h1",
            nodes={
                "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
            },
            edges=[],
            harness_table={"h": "result = True"},
        ),
        "bad": UPIR(
            entry="h1",
            nodes={
                "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
            },
            edges=[],
            harness_table={"h": "raise ValueError('always fails')"},
        ),
    }

    # 2. Run the full AutoHarness loop
    print("=== AutoHarness End-to-End Demo ===\n")
    print(f"Searching over {len(variants)} variants...")
    print("  good: always succeeds (harness_call verdict='ok')")
    print("  bad:  always fails   (harness_call verdict='error')\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_autoharness(
            variants=variants,
            llm=DemoLLM(),
            seed=42,
            max_search_iterations=15,
            max_total_failures=10,
            env_kind="tool",
            data_dir=tmpdir,
        )

        # 3. Print results
        print(f"Status:           {result['status']}")
        print(f"Best variant:     {result['best_variant']}")
        print(f"Iterations:       {result['iterations']}")
        print(f"Episodes saved:   {result['episodes_saved']}")
        print(f"Skills extracted: {result['skills_extracted']}")

        # 4. Show what was saved to memory
        memory_dir = Path(tmpdir)
        episodes_dir = memory_dir / "episodes"
        episodes = list(episodes_dir.glob("*.json")) if episodes_dir.exists() else []
        print(f"\nMemory: {len(episodes)} episodes saved")
        for ep in sorted(episodes)[:5]:
            data = json.loads(ep.read_text())
            print(f"  {ep.stem}: reward={data.get('reward', 'n/a')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
