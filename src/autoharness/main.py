"""AutoHarness end-to-end entry point — wires VM, scorer, search, skills, and memory."""

from __future__ import annotations

import argparse
import tempfile
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from autoharness.ir.upir import UPIR, Edge, UPIRNode
from autoharness.memory.store import MemoryStore
from autoharness.reward.scorer import score_trace, value
from autoharness.runtime.vm import VM
from autoharness.search.thompson import SearchConfig, ThompsonTreeSearch
from autoharness.skills.extractor import SkillExtractor
from autoharness.trace.trace_ir import TraceEvent, TraceLog


def run_autoharness(
    variants: dict[str, UPIR],
    llm: Any,
    seed: int = 42,
    max_search_iterations: int = 10,
    max_total_failures: int = 5,
    env_kind: str = "tool",
    data_dir: str | None = None,
) -> dict[str, Any]:
    """Run the full AutoHarness loop: execute → score → search → extract → persist.

    Args:
        variants: Named UPIR variants to search over.
        llm: Object satisfying the LLMClient protocol (has chat(prompt) -> str).
        seed: Random seed for reproducibility.
        max_search_iterations: Budget for Thompson search.
        max_total_failures: Failure budget for Thompson search.
        env_kind: "tool" or "game" — affects reward weights.
        data_dir: Directory for MemoryStore. Uses temp dir if None.

    Returns:
        Dict with keys: status, best_variant, episodes_saved, skills_extracted.
    """
    if not variants:
        return {
            "status": "no_branches",
            "best_variant": None,
            "episodes_saved": 0,
            "skills_extracted": 0,
        }

    # 1. Set up Thompson search over harness variants
    config = SearchConfig(
        max_search_iterations=max_search_iterations,
        max_total_failures=max_total_failures,
    )
    search = ThompsonTreeSearch(config=config, env_kind=env_kind)

    from autoharness.ir.harness import Harness

    variant_list = list(variants.items())
    for name, _upir in variant_list:
        search.add_branch(Harness(kind="policy", code=name))

    # 2. Define rollout function
    all_traces: list[list[dict[str, Any]]] = []

    def rollout(harness: Harness, roll_seed: int) -> tuple[float, bool]:
        variant_name = harness.code
        upir = variants[variant_name]
        vm = VM(upir=upir, llm=llm, seed=roll_seed, environment=None)
        trace = vm.run()
        all_traces.append(trace)
        r = score_trace(trace, env_kind=env_kind)
        v = value(r, env_kind=env_kind)
        failed = any(e.get("verdict") == "error" for e in trace)
        return v, failed

    # 3. Run Thompson search
    result = search.run(rollout_fn=rollout, rng_seed=seed)

    # 4. Extract skills from the best variant's traces
    skills_extracted = 0
    if all_traces:
        trace_log = TraceLog()
        for trace in all_traces:
            for event in trace:
                trace_log.append(
                    TraceEvent(
                        node_id=event.get("node_id", ""),
                        kind=event.get("kind", ""),
                    )
                )

        extractor = SkillExtractor(min_occurrences=2)
        patterns = extractor.detect_patterns(trace_log)
        if patterns and result.best_branch:
            best_upir = variants[result.best_branch.harness.code]
            for pattern in patterns:
                skill = extractor.extract_skill(pattern, best_upir)
                if skill is not None:
                    skills_extracted += 1

    # 5. Persist to memory
    episodes_saved = 0
    store_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp())
    store = MemoryStore(data_dir=store_dir)

    for i, trace in enumerate(all_traces):
        r = score_trace(trace, env_kind=env_kind)
        store.save_episode(f"run_{i}", trace, reward=value(r, env_kind=env_kind))
        episodes_saved += 1

    best_name = result.best_branch.harness.code if result.best_branch else None

    return {
        "status": result.status,
        "best_variant": best_name,
        "episodes_saved": episodes_saved,
        "skills_extracted": skills_extracted,
        "iterations": result.iterations,
    }


def _run_demo() -> None:
    """Run the tic-tac-toe demo end-to-end with a fake LLM."""
    from autoharness.environment.game_env import GameEnvironment

    class DemoLLM:
        def chat(self, prompt: str) -> str:
            return "0"

    env = GameEnvironment()
    env.reset(seed=42)

    upir = UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="Board state"),
            "act": UPIRNode(kind="act", node_id="act", tool="place_move"),
        },
        edges=[Edge(from_="observe", to="act", kind="sequential")],
    )

    print("=== AutoHarness Demo ===\n")

    llm = DemoLLM()
    vm = VM(upir=upir, llm=llm, environment=env)
    trace = vm.run()

    for event in trace:
        print(f"  {event.get('kind', '?')}: {event}")

    r = score_trace(trace, env_kind="game")
    v = value(r, env_kind="game")
    print(f"\nReward: {v:.3f}")
    print("Done.")


def cli() -> None:
    """Minimal CLI entry point."""
    parser = argparse.ArgumentParser(description="AutoHarness — probabilistic program compiler")
    parser.add_argument("--demo", action="store_true", help="Run the tic-tac-toe demo")
    parser.add_argument("--version", action="version", version=_pkg_version("autoharness"))
    args = parser.parse_args()

    if args.demo:
        _run_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
