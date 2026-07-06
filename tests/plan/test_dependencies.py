"""Conformance tests: Dependency budget and config commitments.

PLAN: runtime deps are only openai + pydantic. Python >= 3.12.
"""

from __future__ import annotations

import pathlib
import tomllib

PYPROJECT = pathlib.Path("pyproject.toml")


class TestDependencyBudget:
    """PLAN: only openai and pydantic as runtime dependencies."""

    def _load_deps(self) -> list[str]:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        deps: list[str] = data["project"]["dependencies"]
        return deps

    def test_runtime_deps_count(self) -> None:
        """PLAN: exactly 2 runtime dependencies."""
        deps = self._load_deps()
        assert len(deps) == 2, f"Expected 2 runtime deps, got {len(deps)}: {deps}"

    def test_openai_present(self) -> None:
        deps = self._load_deps()
        assert any("openai" in d for d in deps), "openai not in dependencies"

    def test_pydantic_present(self) -> None:
        deps = self._load_deps()
        assert any("pydantic" in d for d in deps), "pydantic not in dependencies"

    def test_no_heavy_ml_deps(self) -> None:
        """PLAN: no torch, tensorflow, transformers, etc. in runtime deps."""
        deps = self._load_deps()
        forbidden = ["torch", "tensorflow", "transformers", "numpy", "scipy", "jax"]
        for dep in deps:
            forbidden_found = [f for f in forbidden if f in dep.lower()]
            assert not forbidden_found, f"Forbidden dep in runtime: {dep}"


class TestPythonVersion:
    """PLAN: requires-python >= 3.12."""

    def test_requires_python(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        version = data["project"]["requires-python"]
        assert "3.12" in version, f"Expected Python 3.12+, got {version}"


class TestConfigDefaults:
    """PLAN: config.py exists with centralized defaults."""

    def test_config_module_exists(self) -> None:
        from autoharness import config

        assert config is not None

    def test_has_vm_max_steps(self) -> None:
        from autoharness.config import VM_MAX_STEPS

        assert isinstance(VM_MAX_STEPS, int)
        assert VM_MAX_STEPS > 0

    def test_has_sandbox_max_runtime(self) -> None:
        from autoharness.config import SANDBOX_MAX_RUNTIME_MS

        assert isinstance(SANDBOX_MAX_RUNTIME_MS, int)
        assert SANDBOX_MAX_RUNTIME_MS > 0

    def test_has_thompson_defaults(self) -> None:
        from autoharness.config import (
            THOMPSON_MAX_SEARCH_ITERATIONS,
            THOMPSON_MAX_TOTAL_FAILURES,
            THOMPSON_PRIOR_ALPHA,
            THOMPSON_PRIOR_BETA,
        )

        assert THOMPSON_MAX_SEARCH_ITERATIONS > 0
        assert THOMPSON_MAX_TOTAL_FAILURES > 0
        assert THOMPSON_PRIOR_ALPHA > 0
        assert THOMPSON_PRIOR_BETA > 0

    def test_has_reward_weights(self) -> None:
        from autoharness.config import REWARD_WEIGHTS_GAME, REWARD_WEIGHTS_TOOL

        assert "task_success" in REWARD_WEIGHTS_TOOL
        assert "task_success" in REWARD_WEIGHTS_GAME
        # Weights should sum to ~1.0
        assert abs(sum(REWARD_WEIGHTS_TOOL.values()) - 1.0) < 0.01
        assert abs(sum(REWARD_WEIGHTS_GAME.values()) - 1.0) < 0.01
