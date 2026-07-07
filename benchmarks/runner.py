"""Benchmark runner — executes tasks with and without skill reuse.

Two-phase design:
1. Training: run baseline variants to extract and persist skills.
2. Test: run baseline variants (no reuse) vs reuse variants (with persisted skills).
"""

from __future__ import annotations

import statistics
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tracedge.main import run_tracedge
from tracedge.memory.store import MemoryStore


def resolve_llm(task_llm: Any, override: Any | None = None) -> Any:
    """Return the override LLM if set, otherwise the task's default LLM."""
    return override if override is not None else task_llm


@dataclass
class TaskResult:
    """Result of running a single task across multiple seeds."""

    task_name: str
    category: str
    variant_type: str  # "baseline" or "reuse"
    successes: int = 0
    total: int = 0
    llm_calls: list[int] = field(default_factory=list)
    llm_calls_saved: list[int] = field(default_factory=list)
    skills_extracted: list[int] = field(default_factory=list)
    skills_loaded: list[int] = field(default_factory=list)
    converged_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.total if self.total > 0 else 0.0

    @property
    def mean_llm_calls(self) -> float:
        return statistics.mean(self.llm_calls) if self.llm_calls else 0.0

    @property
    def std_llm_calls(self) -> float:
        return statistics.stdev(self.llm_calls) if len(self.llm_calls) > 1 else 0.0

    @property
    def mean_llm_calls_saved(self) -> float:
        return statistics.mean(self.llm_calls_saved) if self.llm_calls_saved else 0.0

    @property
    def mean_skills_extracted(self) -> float:
        return statistics.mean(self.skills_extracted) if self.skills_extracted else 0.0

    @property
    def mean_skills_loaded(self) -> float:
        return statistics.mean(self.skills_loaded) if self.skills_loaded else 0.0


@dataclass
class BenchmarkSuite:
    """Full benchmark results."""

    task_results: list[TaskResult] = field(default_factory=list)

    def by_category(self, category: str) -> list[TaskResult]:
        return [r for r in self.task_results if r.category == category]

    def by_variant_type(self, variant_type: str) -> list[TaskResult]:
        return [r for r in self.task_results if r.variant_type == variant_type]

    def summary(self, category: str | None = None) -> dict[str, Any]:
        """Aggregate summary across tasks, comparing baseline vs reuse."""
        results = self.task_results
        if category:
            results = [r for r in results if r.category == category]

        baseline = [r for r in results if r.variant_type == "baseline"]
        reuse = [r for r in results if r.variant_type == "reuse"]

        total_tasks = len(baseline)

        avg_success_baseline = (
            statistics.mean([r.success_rate for r in baseline]) if baseline else 0.0
        )
        avg_success_reuse = statistics.mean([r.success_rate for r in reuse]) if reuse else 0.0

        all_calls_baseline = [c for r in baseline for c in r.llm_calls]
        all_calls_reuse = [c for r in reuse for c in r.llm_calls]

        mean_calls_baseline = statistics.mean(all_calls_baseline) if all_calls_baseline else 0.0
        mean_calls_reuse = statistics.mean(all_calls_reuse) if all_calls_reuse else 0.0
        mean_saved = mean_calls_baseline - mean_calls_reuse

        pct_reduction = (
            ((mean_calls_baseline - mean_calls_reuse) / mean_calls_baseline * 100)
            if mean_calls_baseline > 0
            else 0.0
        )

        return {
            "category": category or "all",
            "total_tasks": total_tasks,
            "avg_success_rate_baseline": avg_success_baseline,
            "avg_success_rate_reuse": avg_success_reuse,
            "mean_llm_calls_baseline": mean_calls_baseline,
            "mean_llm_calls_reuse": mean_calls_reuse,
            "mean_llm_calls_saved": mean_saved,
            "pct_llm_reduction": pct_reduction,
        }


def _run_baseline_phase(
    tasks: list[Any],
    data_dir: str,
    max_iterations: int,
    llm_override: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """Run baseline variants to extract and persist skills.

    Persists each task's predefined training_skills into MemoryStore so
    the reuse variant can reference them via skill_call nodes.

    Returns dict mapping task_name → last run_tracedge result.
    """
    results: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_dir = str(Path(data_dir) / "training" / task.name)

        # Persist predefined training skills
        store = MemoryStore(data_dir=Path(task_dir))
        for skill_id, skill_upir in task.training_skills.items():
            store.save_skill(skill_id, skill_upir)

        llm = resolve_llm(task.llm, llm_override)
        last_result: dict[str, Any] = {}
        for seed in task.seeds:
            last_result = run_tracedge(
                variants=task.baseline_variants,
                llm=llm,
                seed=seed,
                max_search_iterations=max_iterations,
                max_total_failures=task.max_total_failures,
                env_kind=task.env_kind,
                data_dir=task_dir,
                env_factory=task.env_factory,
            )
        results[task.name] = last_result
    return results


def _run_test_phase(
    tasks: list[Any],
    data_dir: str,
    variant_type: str,
    max_iterations: int,
    llm_override: Any | None = None,
) -> list[TaskResult]:
    """Run test phase: baseline or reuse variants across all seeds.

    Uses the same data_dir as training so persisted skills are available.
    """
    suite_results: list[TaskResult] = []

    for task in tasks:
        variants = task.baseline_variants if variant_type == "baseline" else task.reuse_variants
        llm = resolve_llm(task.llm, llm_override)
        task_result = TaskResult(
            task_name=task.name,
            category=task.category,
            variant_type=variant_type,
            total=len(task.seeds),
        )

        for seed in task.seeds:
            # Use the training data_dir so skills are visible
            task_dir = str(Path(data_dir) / "training" / task.name)
            result = run_tracedge(
                variants=variants,
                llm=llm,
                seed=seed,
                max_search_iterations=max_iterations,
                max_total_failures=task.max_total_failures,
                env_kind=task.env_kind,
                data_dir=task_dir,
                env_factory=task.env_factory,
                reuse_skills=(variant_type == "reuse"),
            )

            if task.passes(result):
                task_result.successes += 1

            if result["status"] == "converged":
                task_result.converged_count += 1

            task_result.llm_calls.append(result.get("llm_calls", 0))
            task_result.llm_calls_saved.append(result.get("llm_calls_saved", 0))
            task_result.skills_extracted.append(result.get("skills_extracted", 0))
            task_result.skills_loaded.append(result.get("skills_loaded", 0))

        suite_results.append(task_result)

    return suite_results


def run_benchmark(
    tasks: list[Any],
    data_dir_prefix: str | None = None,
    categories: list[str] | None = None,
    max_iterations: int = 15,
    llm_override: Any | None = None,
) -> BenchmarkSuite:
    """Run full benchmark: training phase → test phase (baseline vs reuse).

    Args:
        tasks: List of Task objects to benchmark.
        data_dir_prefix: Base directory for MemoryStore data. Uses tempdir if None.
        categories: If set, only run tasks in these categories.
        max_iterations: Max Thompson search iterations per run.
        llm_override: If set, use this LLM for all tasks instead of task.llm.

    Returns:
        BenchmarkSuite with baseline and reuse results for all tasks.
    """
    filtered = tasks
    if categories:
        filtered = [t for t in tasks if t.category in categories]

    suite = BenchmarkSuite()
    tmpdir_obj = (
        tempfile.TemporaryDirectory(prefix="autobench_") if data_dir_prefix is None else None
    )
    base = data_dir_prefix or tmpdir_obj.name  # type: ignore[union-attr]

    try:
        # Phase 1: Training — run baseline variants to extract skills
        print("Phase 1: Training (extracting skills from baseline variants)...")
        _run_baseline_phase(filtered, base, max_iterations, llm_override)

        # Phase 2a: Test baseline variants (no reuse)
        print("Phase 2a: Testing baseline variants (no skill reuse)...")
        baseline_results = _run_test_phase(filtered, base, "baseline", max_iterations, llm_override)
        suite.task_results.extend(baseline_results)

        # Phase 2b: Test reuse variants (with persisted skills)
        print("Phase 2b: Testing reuse variants (with skill reuse)...")
        reuse_results = _run_test_phase(filtered, base, "reuse", max_iterations, llm_override)
        suite.task_results.extend(reuse_results)

    finally:
        if tmpdir_obj is not None:
            tmpdir_obj.cleanup()

    return suite
