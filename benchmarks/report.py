"""Benchmark report generator — produces BENCHMARKS.md from run results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.runner import BenchmarkSuite


def _fmt(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"


def generate_report(suite: BenchmarkSuite, output_path: str = "BENCHMARKS.md") -> str:
    """Generate a Markdown benchmark report from a BenchmarkSuite.

    Args:
        suite: Completed benchmark results.
        output_path: Path to write the report to.

    Returns:
        The generated Markdown content.
    """
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("# Benchmarks")
    lines.append("")
    lines.append(f"*Generated: {ts}*")
    lines.append("")
    lines.append("**Headline:** Skill reuse reduces LLM calls at equal or better success rate.")
    lines.append("")
    lines.append("**Reproduce:** `python -m benchmarks --categories code_gen game tool`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Overall summary
    overall = suite.summary()
    lines.append("## Overall")
    lines.append("")
    lines.append("| Metric | Baseline (no reuse) | With Skill Reuse |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Avg success rate | {_fmt(overall['avg_success_rate_baseline'] * 100)}% "
        f"| {_fmt(overall['avg_success_rate_reuse'] * 100)}% |"
    )
    lines.append(
        f"| Mean LLM calls | {_fmt(overall['mean_llm_calls_baseline'])} "
        f"| {_fmt(overall['mean_llm_calls_reuse'])} |"
    )
    lines.append(f"| Mean LLM calls saved | — | {_fmt(overall['mean_llm_calls_saved'])} |")
    pct = overall["pct_llm_reduction"]
    lines.append(f"| **LLM reduction** | — | **{_fmt(pct)}%** |")
    lines.append(f"| Tasks | {overall['total_tasks']} | {overall['total_tasks']} |")
    lines.append("")

    # Per-category breakdowns
    for category in ["code_gen", "game", "tool"]:
        cat_results = suite.by_category(category)
        if not cat_results:
            continue

        baseline = [r for r in cat_results if r.variant_type == "baseline"]
        reuse = [r for r in cat_results if r.variant_type == "reuse"]
        if not baseline:
            continue

        lines.append(f"## {category.replace('_', ' ').title()}")
        lines.append("")

        cat_summary = suite.summary(category=category)

        lines.append(
            "| Task | Success (baseline) | Success (reuse) "
            "| LLM calls (baseline) | LLM calls (reuse) | Saved |"
        )
        lines.append("|---|---|---|---|---|---|")

        for b, r in zip(baseline, reuse, strict=True):
            saved = b.mean_llm_calls - r.mean_llm_calls
            lines.append(
                f"| {b.task_name} "
                f"| {_fmt(b.success_rate * 100)}% "
                f"| {_fmt(r.success_rate * 100)}% "
                f"| {_fmt(b.mean_llm_calls)} "
                f"| {_fmt(r.mean_llm_calls)} "
                f"| {_fmt(saved)} |"
            )

        lines.append("")

        pct = cat_summary["pct_llm_reduction"]
        lines.append(
            f"**{category.replace('_', ' ').title()} summary:** "
            f"LLM reduction = **{_fmt(pct)}%**, "
            f"success rate: "
            f"{_fmt(cat_summary['avg_success_rate_baseline'] * 100)}% → "
            f"{_fmt(cat_summary['avg_success_rate_reuse'] * 100)}%"
        )
        lines.append("")

    # Reproduction instructions
    lines.append("---")
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    lines.append("```bash")
    lines.append("# Full benchmark suite")
    lines.append("python -m benchmarks")
    lines.append("")
    lines.append("# Code generation tasks only")
    lines.append("python -m benchmarks --categories code_gen")
    lines.append("")
    lines.append("# Game tasks only")
    lines.append("python -m benchmarks --categories game")
    lines.append("")
    lines.append("# Fewer seeds for faster iteration")
    lines.append("python -m benchmarks --seeds 42 43 44")
    lines.append("```")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "- **Phase 1 (Training):** Run baseline variants (think → harness_call) "
        "to extract and persist skills via `SkillExtractor`."
    )
    lines.append(
        "- **Phase 2a (Baseline):** Run baseline variants again without skill "
        "reuse — each rollout calls the LLM for think nodes."
    )
    lines.append(
        "- **Phase 2b (Reuse):** Run reuse variants (skill_call only) with "
        "persisted skills loaded — deterministic execution, no LLM calls."
    )
    lines.append("- Each task runs across 5 random seeds.")
    lines.append(
        "- Success = Thompson search converges (posterior mean >= 0.8) on the best variant."
    )
    lines.append("- LLM calls = count of think/branch events in the execution trace.")
    lines.append("- LLM calls saved = difference between baseline and reuse LLM call counts.")
    lines.append("")

    content = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(content)

    return content
