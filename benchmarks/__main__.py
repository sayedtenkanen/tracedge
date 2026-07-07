"""CLI entry point for running benchmarks: python -m benchmarks"""

from __future__ import annotations

import argparse
import sys
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from benchmarks.tasks import Task

from benchmarks.report import generate_report
from benchmarks.runner import run_benchmark
from benchmarks.tasks import ALL_TASKS, TASKS_BY_CATEGORY


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AutoHarness benchmark suite — measure skill reuse impact",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        choices=list(TASKS_BY_CATEGORY.keys()),
        default=None,
        help="Run only these task categories (default: all)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="*",
        default=None,
        help="Override seeds for all tasks (e.g. --seeds 42 43 44)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=15,
        help="Max search iterations per task (default: 15)",
    )
    parser.add_argument(
        "--llm",
        choices=["fake", "ollama"],
        default="fake",
        help="LLM backend: fake (scripted, default) or ollama (local Ollama)",
    )
    parser.add_argument(
        "--output",
        default="BENCHMARKS.md",
        help="Output path for the report (default: BENCHMARKS.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List tasks without running them",
    )
    args = parser.parse_args(argv)

    tasks: list[Task] = ALL_TASKS
    if args.categories:
        tasks = []
        for cat in args.categories:
            tasks.extend(TASKS_BY_CATEGORY[cat])

    if args.seeds:
        for task in tasks:
            task.seeds = args.seeds

    if args.dry_run:
        print(f"Would run {len(tasks)} tasks:")
        for t in tasks:
            print(f"  [{t.category}] {t.name} ({len(t.seeds)} seeds)")
        return 0

    llm_override = None
    if args.llm == "ollama":
        from autoharness.intelligence.llm_client import OllamaChatClient

        llm_override = OllamaChatClient()
        print(f"Using local Ollama ({llm_override.model})")

    print(f"Running {len(tasks)} tasks ({len(tasks) * 2} runs: no_reuse + reuse)...")
    with tempfile.TemporaryDirectory(prefix="autobench_") as tmpdir:
        suite = run_benchmark(
            tasks,
            data_dir_prefix=tmpdir,
            max_iterations=args.max_iterations,
            llm_override=llm_override,
        )

    report = generate_report(suite, output_path=args.output)
    print(f"\nReport written to {args.output}")
    print("\n" + report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
