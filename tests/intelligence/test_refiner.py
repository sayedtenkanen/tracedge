"""Tests for Refiner — LLM-guided harness rewrite with validation."""

from __future__ import annotations

import pytest

from autoharness.intelligence.critic import CriticOutput
from autoharness.intelligence.refiner import Refiner
from autoharness.ir.harness import Harness


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

        def mock_llm(prompt: str) -> str:
            return "try:\n    pass\nexcept:\n    pass"

        refiner = Refiner(llm=mock_llm, max_retries=3)
        with pytest.raises(ValueError, match="try/except"):
            refiner.refine(harness, feedback)

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


class TestRefinerVersionIncrement:
    """Refiner increments harness version on rewrite."""

    def test_version_increments(self) -> None:
        harness = Harness(kind="action_filter", code="return x", version=1)
        feedback = CriticOutput()

        def mock_llm(prompt: str) -> str:
            return "return x"

        refiner = Refiner(llm=mock_llm)
        result = refiner.refine(harness, feedback)
        assert result.version == 2
