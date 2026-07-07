"""Tests for Refiner — LLM-guided harness rewrite with validation."""

from __future__ import annotations

import pytest

from tracedge.intelligence.critic import CriticOutput
from tracedge.intelligence.refiner import Refiner
from tracedge.ir.harness import Harness


class TestRefinerBasicRewrite:
    """Refiner produces a rewritten harness from critic feedback."""

    def test_returns_harness(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput(
            failure_clusters=[{"root_cause": "timeout", "count": 2}],
        )

        def mock_llm(prompt: str) -> str:
            return "return x if x else None"

        refiner = Refiner(llm=mock_llm)
        result = refiner.refine(harness, feedback)
        assert isinstance(result, Harness)
        assert result.kind == "action_filter"

    def test_preserves_kind(self) -> None:
        harness = Harness(kind="policy", code="return action")
        feedback = CriticOutput()

        def mock_llm(prompt: str) -> str:
            return "return action"

        refiner = Refiner(llm=mock_llm)
        result = refiner.refine(harness, feedback)
        assert result.kind == "policy"


class TestRefinerValidation:
    """Refiner validates output and rejects invalid code."""

    def test_rejects_try_except(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput()

        call_count = {"n": 0}

        def mock_llm(prompt: str) -> str:
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return "try:\n    return x\nexcept:\n    return None"
            return "return x"

        refiner = Refiner(llm=mock_llm, max_retries=3)
        result = refiner.refine(harness, feedback)
        assert isinstance(result, Harness)
        assert call_count["n"] >= 3

    def test_rejects_filesystem_access(self) -> None:
        harness = Harness(
            kind="action_filter",
            code="return x",
            effects={"filesystem": False, "network": False, "llm_calls": 0},
        )
        feedback = CriticOutput()

        call_count = {"n": 0}

        def mock_llm(prompt: str) -> str:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return "import os\nreturn os.listdir('.')"
            return "return x"

        refiner = Refiner(llm=mock_llm, max_retries=3)
        result = refiner.refine(harness, feedback)
        assert isinstance(result, Harness)
        assert call_count["n"] >= 2


class TestRefinerRetries:
    """Refiner retries on invalid output up to max_retries."""

    def test_exhausts_retries(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput()

        call_count = {"n": 0}

        def mock_llm(prompt: str) -> str:
            call_count["n"] += 1
            return "try:\n    pass\nexcept:\n    pass"

        refiner = Refiner(llm=mock_llm, max_retries=3)
        with pytest.raises(ValueError, match="retries"):
            refiner.refine(harness, feedback)
        assert call_count["n"] == 3

    def test_succeeds_within_retries(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput()

        call_count = {"n": 0}

        def mock_llm(prompt: str) -> str:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "try:\n    pass\nexcept:\n    pass"
            return "return x"

        refiner = Refiner(llm=mock_llm, max_retries=3)
        result = refiner.refine(harness, feedback)
        assert isinstance(result, Harness)
        assert call_count["n"] == 2

    def test_exception_chained(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput()

        def mock_llm(prompt: str) -> str:
            return "try:\n    pass\nexcept:\n    pass"

        refiner = Refiner(llm=mock_llm, max_retries=1)
        with pytest.raises(ValueError, match="retries") as exc_info:
            refiner.refine(harness, feedback)
        assert exc_info.value.__cause__ is not None


class TestRefinerPromptConstruction:
    """Refiner builds a prompt containing harness code and critic feedback."""

    def test_prompt_includes_harness_code(self) -> None:
        harness = Harness(kind="action_filter", code="return validate(x)")
        feedback = CriticOutput(
            failure_clusters=[{"root_cause": "type error", "count": 1}],
        )
        prompts: list[str] = []

        def mock_llm(prompt: str) -> str:
            prompts.append(prompt)
            return "return validate(x)"

        refiner = Refiner(llm=mock_llm)
        refiner.refine(harness, feedback)
        assert len(prompts) == 1
        assert "return validate(x)" in prompts[0]

    def test_prompt_includes_failure_clusters(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput(
            failure_clusters=[{"root_cause": "timeout", "count": 3}],
        )
        prompts: list[str] = []

        def mock_llm(prompt: str) -> str:
            prompts.append(prompt)
            return "return x"

        refiner = Refiner(llm=mock_llm)
        refiner.refine(harness, feedback)
        assert "timeout" in prompts[0].lower()

    def test_prompt_includes_legality_violations(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput(
            legality_violations=[
                {"node_id": "illegal-node-1"},
                {"node_id": "illegal-node-2"},
            ],
        )
        prompts: list[str] = []

        def mock_llm(prompt: str) -> str:
            prompts.append(prompt)
            return "return x"

        refiner = Refiner(llm=mock_llm)
        refiner.refine(harness, feedback)
        assert "illegal-node-1" in prompts[0]
        assert "illegal-node-2" in prompts[0]

    def test_prompt_includes_inefficiency_patterns(self) -> None:
        harness = Harness(kind="action_filter", code="return x")
        feedback = CriticOutput(
            inefficiency_patterns=[
                {"trace_index": 3, "step_count": 17, "threshold": 10},
            ],
        )
        prompts: list[str] = []

        def mock_llm(prompt: str) -> str:
            prompts.append(prompt)
            return "return x"

        refiner = Refiner(llm=mock_llm)
        refiner.refine(harness, feedback)
        assert "trace 3" in prompts[0].lower()
        assert "17 steps" in prompts[0]


class TestRefinerVersionIncrement:
    """Refiner increments harness version on rewrite and preserves metadata."""

    def test_version_increments(self) -> None:
        harness = Harness(kind="action_filter", code="return x", version=1)
        feedback = CriticOutput()

        def mock_llm(prompt: str) -> str:
            return "return x"

        refiner = Refiner(llm=mock_llm)
        result = refiner.refine(harness, feedback)
        assert result.version == 2

    def test_preserves_metadata(self) -> None:
        harness = Harness(
            kind="policy",
            code="return x",
            input_schema={"type": "object"},
            output_schema={"type": "string"},
            effects={"filesystem": False, "network": True, "llm_calls": 1},
            target_env_kind="game",
            version=5,
            legality_accuracy=0.9,
        )
        feedback = CriticOutput()

        def mock_llm(prompt: str) -> str:
            return "return x"

        refiner = Refiner(llm=mock_llm)
        result = refiner.refine(harness, feedback)
        assert result.kind == "policy"
        assert result.input_schema == {"type": "object"}
        assert result.output_schema == {"type": "string"}
        assert result.effects == {"filesystem": False, "network": True, "llm_calls": 1}
        assert result.target_env_kind == "game"
        assert result.legality_accuracy == 0.9
        assert result.version == 6
