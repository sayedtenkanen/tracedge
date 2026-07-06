"""Conformance tests: Conventions and tooling commitments.

PLAN: test naming, lint config, type checking, pre-commit hooks.
"""

from __future__ import annotations

import pathlib
import tomllib

PYPROJECT = pathlib.Path("pyproject.toml")
PRECOMMIT = pathlib.Path(".pre-commit-config.yaml")


class TestLintConfig:
    """PLAN: ruff line-length = 100, target Python 3.12."""

    def test_ruff_line_length(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        assert data["tool"]["ruff"]["line-length"] == 100

    def test_ruff_target_version(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        assert data["tool"]["ruff"]["target-version"] == "py312"


class TestMypyConfig:
    """PLAN: mypy strict mode, Python 3.12, pydantic plugin."""

    def test_strict_mode(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        assert data["tool"]["mypy"]["strict"] is True

    def test_python_version(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        assert data["tool"]["mypy"]["python_version"] == "3.12"

    def test_pydantic_plugin(self) -> None:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        assert "pydantic.mypy" in data["tool"]["mypy"]["plugins"]


class TestPreCommitHooks:
    """PLAN: pre-commit has ruff, mypy, gitleaks, bandit."""

    def test_precommit_config_exists(self) -> None:
        assert PRECOMMIT.exists(), ".pre-commit-config.yaml not found"

    def test_has_ruff_hooks(self) -> None:
        content = PRECOMMIT.read_text()
        assert "ruff" in content

    def test_has_mypy_hook(self) -> None:
        content = PRECOMMIT.read_text()
        assert "mypy" in content

    def test_has_gitleaks_hook(self) -> None:
        content = PRECOMMIT.read_text()
        assert "gitleaks" in content

    def test_has_bandit_hook(self) -> None:
        content = PRECOMMIT.read_text()
        assert "bandit" in content


class TestCIWorkflow:
    """PLAN: CI runs lint, test, security on push/PR to main."""

    def test_ci_workflow_exists(self) -> None:
        ci = pathlib.Path(".github/workflows/ci.yml")
        assert ci.exists(), "CI workflow not found"

    def test_ci_has_lint_job(self) -> None:
        content = pathlib.Path(".github/workflows/ci.yml").read_text()
        assert "ruff check" in content

    def test_ci_has_test_job(self) -> None:
        content = pathlib.Path(".github/workflows/ci.yml").read_text()
        assert "pytest" in content

    def test_ci_has_security_job(self) -> None:
        content = pathlib.Path(".github/workflows/ci.yml").read_text()
        assert "gitleaks" in content
        # bandit runs via security-scan.sh, not directly in CI
        assert "security-scan" in content


class TestTestStructure:
    """PLAN: test directories match source module structure."""

    def test_ir_tests_exist(self) -> None:
        assert pathlib.Path("tests/ir").is_dir()

    def test_runtime_tests_exist(self) -> None:
        assert pathlib.Path("tests/runtime").is_dir()

    def test_environment_tests_exist(self) -> None:
        assert pathlib.Path("tests/environment").is_dir()

    def test_sandbox_tests_exist(self) -> None:
        assert pathlib.Path("tests/sandbox").is_dir()

    def test_trace_tests_exist(self) -> None:
        assert pathlib.Path("tests/trace").is_dir()

    def test_reward_tests_exist(self) -> None:
        assert pathlib.Path("tests/reward").is_dir()

    def test_search_tests_exist(self) -> None:
        assert pathlib.Path("tests/search").is_dir()

    def test_intelligence_tests_exist(self) -> None:
        assert pathlib.Path("tests/intelligence").is_dir()

    def test_integration_tests_exist(self) -> None:
        assert pathlib.Path("tests/integration").is_dir()

    def test_conftest_exists(self) -> None:
        assert pathlib.Path("tests/conftest.py").exists()
