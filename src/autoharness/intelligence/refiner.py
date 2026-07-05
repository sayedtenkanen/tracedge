"""Refiner — LLM-guided harness rewrite with validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autoharness.sandbox.guardrails import check_harness_code

if TYPE_CHECKING:
    from collections.abc import Callable

    from autoharness.intelligence.critic import CriticOutput
    from autoharness.ir.harness import Harness


class Refiner:
    """Rewrites harness code using LLM feedback from the Critic.

    Takes a harness + critic feedback, prompts the LLM to produce improved
    code, validates the output against safety constraints, and retries
    on failure.
    """

    def __init__(
        self,
        llm: Callable[[str], str],
        max_retries: int = 3,
    ) -> None:
        self.llm = llm
        self.max_retries = max_retries

    def refine(self, harness: Harness, feedback: CriticOutput) -> Harness:
        """Refine a harness based on critic feedback.

        Args:
            harness: The current harness to refine.
            feedback: Structured feedback from the Critic.

        Returns:
            A new Harness with rewritten code and incremented version.

        Raises:
            ValueError: If all retries produce invalid code.
        """
        from autoharness.ir.harness import Harness as HarnessClass

        prompt = self._build_prompt(harness, feedback)

        last_error: Exception | None = None
        for _attempt in range(self.max_retries):
            code = self.llm(prompt)

            try:
                check_harness_code(code, effects=harness.effects)
            except ValueError as e:
                last_error = e
                continue

            return HarnessClass(
                kind=harness.kind,
                code=code,
                input_schema=harness.input_schema,
                output_schema=harness.output_schema,
                effects=harness.effects,
                target_env_kind=harness.target_env_kind,
                version=harness.version + 1,
                legality_accuracy=harness.legality_accuracy,
                guard_policy=harness.guard_policy,
            )

        raise ValueError(
            f"Refiner failed to produce valid code after {self.max_retries} retries: {last_error}"
        )

    def _build_prompt(self, harness: Harness, feedback: CriticOutput) -> str:
        """Build the LLM prompt from harness code and critic feedback."""
        parts = [
            "You are refining harness code. Return ONLY the new code, no explanation.",
            "",
            f"Current code (kind={harness.kind}):",
            harness.code,
            "",
        ]

        if feedback.failure_clusters:
            parts.append("Failure clusters:")
            for cluster in feedback.failure_clusters:
                parts.append(
                    f"  - {cluster.get('root_cause', 'unknown')} (count={cluster.get('count', 0)})"
                )
            parts.append("")

        if feedback.legality_violations:
            parts.append("Legality violations:")
            for v in feedback.legality_violations:
                parts.append(f"  - node {v.get('node_id', 'unknown')}: illegal action")
            parts.append("")

        if feedback.inefficiency_patterns:
            parts.append("Inefficiency patterns:")
            for p in feedback.inefficiency_patterns:
                parts.append(
                    f"  - trace {p.get('trace_index', '?')}: "
                    f"{p.get('step_count', 0)} steps (threshold={p.get('threshold', 10)})"
                )
            parts.append("")

        parts.append("Rewrite the code to fix the issues above. Return only the code.")

        return "\n".join(parts)
