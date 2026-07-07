"""AutoHarness end-to-end entry point — wires VM, scorer, search, skills, and memory."""

from __future__ import annotations

import argparse
import tempfile
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.memory.store import MemoryStore
from tracedge.reward.scorer import score_trace, value
from tracedge.runtime.vm import VM
from tracedge.search.thompson import SearchConfig, ThompsonTreeSearch
from tracedge.skills.extractor import SkillExtractor


def _has_llm_nodes(upir: UPIR) -> bool:
    """True if the UPIR has any think or branch nodes that call the LLM."""
    return any(
        n.kind in ("think", "branch") for n in upir.nodes.values() if isinstance(n, UPIRNode)
    )


def run_tracedge(
    variants: dict[str, UPIR],
    llm: Any,
    seed: int = 42,
    max_search_iterations: int = 10,
    max_total_failures: int = 5,
    env_kind: str = "tool",
    data_dir: str | None = None,
    env_factory: Callable[[int], Any] | None = None,
    reuse_skills: bool = False,
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
        env_factory: Callable taking a seed int and returning a fresh Environment.
                     If None, VM runs without an environment.
        reuse_skills: If True, load persisted skills from MemoryStore into
                      each variant's skill_table before execution.

    Returns:
        Dict with keys: status, best_variant, episodes_saved, skills_extracted,
        skills_loaded.
    """
    if not variants:
        return {
            "status": "no_branches",
            "best_variant": None,
            "episodes_saved": 0,
            "skills_extracted": 0,
            "skills_loaded": 0,
            "llm_calls": 0,
            "llm_calls_saved": 0,
            "per_variant_stats": {},
        }

    # 1. Set up Thompson search over harness variants
    config = SearchConfig(
        max_search_iterations=max_search_iterations,
        max_total_failures=max_total_failures,
    )
    search = ThompsonTreeSearch(config=config, env_kind=env_kind)

    from tracedge.ir.harness import Harness

    variant_list = list(variants.items())
    for name, _upir in variant_list:
        search.add_branch(Harness(kind="policy", code=name))

    # 1b. Load persisted skills if reuse_skills is enabled
    store_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp())
    store = MemoryStore(data_dir=store_dir)
    skills_loaded = 0

    if reuse_skills:
        stored_skills = store.load_skills()
        if stored_skills:
            for _name, upir in variant_list:
                upir.skill_table.update(stored_skills)
            skills_loaded = len(stored_skills)

    # 2. Define rollout function
    all_traces: list[list[dict[str, Any]]] = []
    all_rewards: list[float] = []
    llm_calls = 0
    llm_calls_saved = 0
    # Track per-variant stats: variant_name -> list of rollout values
    variant_values: dict[str, list[float]] = {name: [] for name in variants}
    variant_trials: dict[str, int] = {name: 0 for name in variants}

    def rollout(harness: Harness, roll_seed: int) -> tuple[float, bool]:
        nonlocal llm_calls, llm_calls_saved
        variant_name = harness.code
        upir = variants[variant_name]
        env = env_factory(roll_seed) if env_factory is not None else None
        vm = VM(upir=upir, llm=llm, seed=roll_seed, environment=env)
        trace = vm.run()
        all_traces.append(trace)
        r = score_trace(trace, env_kind=env_kind)
        v = value(r, env_kind=env_kind)
        all_rewards.append(v)
        failed = any(e.get("verdict") == "error" for e in trace)
        # Count actual LLM calls from think/branch events in the trace
        for event in trace:
            if event.get("kind") in ("think", "branch"):
                llm_calls += 1
        # Count LLM savings: skill_calls to deterministic skills (no think/branch)
        for event in trace:
            if event.get("kind") == "skill_call":
                skill_id = event.get("skill_id", "")
                skill_upir = upir.skill_table.get(skill_id)
                if skill_upir is not None and not _has_llm_nodes(skill_upir):
                    llm_calls_saved += 1
        variant_values[variant_name].append(v)
        variant_trials[variant_name] += 1
        return v, failed

    # 3. Run Thompson search
    result = search.run(rollout_fn=rollout, rng_seed=seed)

    # 4. Extract skills from successful episodes only
    skills_extracted = 0
    if all_traces and result.best_branch:
        best_upir = variants[result.best_branch.harness.code]
        extractor = SkillExtractor(min_occurrences=2)
        episodes = list(zip(all_traces, all_rewards, strict=True))
        patterns = extractor.extract_from_episodes(episodes, success_threshold=0.0)
        for pattern in patterns:
            skill_node = extractor.extract_skill(pattern, best_upir)
            if skill_node is not None:
                skills_extracted += 1

        # Persist all extracted skill UPIRs for reuse
        for skill_id, skill_upir in extractor.skill_table.items():
            store.save_skill(skill_id, skill_upir)

    # 5. Persist episodes to memory
    episodes_saved = 0
    for i, (trace, reward) in enumerate(zip(all_traces, all_rewards, strict=True)):
        store.save_episode(f"run_{i}", trace, reward=reward)
        episodes_saved += 1

    best_name = result.best_branch.harness.code if result.best_branch else None

    # 6. Build per-variant stats from search branches
    per_variant_stats: dict[str, dict[str, Any]] = {}
    for branch in search.branches:
        name = branch.harness.code
        per_variant_stats[name] = {
            "posterior_mean": branch.mean,
            "trials": branch.update_count,
            "alpha": branch.alpha,
            "beta": branch.beta,
            "rollout_values": variant_values.get(name, []),
        }

    return {
        "status": result.status,
        "best_variant": best_name,
        "episodes_saved": episodes_saved,
        "skills_extracted": skills_extracted,
        "skills_loaded": skills_loaded,
        "iterations": result.iterations,
        "llm_calls": llm_calls,
        "llm_calls_saved": llm_calls_saved,
        "per_variant_stats": per_variant_stats,
    }


def _run_demo() -> None:
    """Run the tic-tac-toe demo end-to-end with a fake LLM."""
    from tracedge.environment.game_env import GameEnvironment

    class DemoLLM:
        def chat(self, prompt: str) -> str:
            return "0"

    env = GameEnvironment()

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
    parser.add_argument("--version", action="version", version=_pkg_version("tracedge"))
    args = parser.parse_args()

    if args.demo:
        _run_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
