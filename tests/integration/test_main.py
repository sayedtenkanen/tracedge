"""Integration test for autoharness.main — end-to-end loop with fake LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autoharness.main import run_autoharness

if TYPE_CHECKING:
    from pathlib import Path


class FakeLLM:
    """Canned LLM for testing."""

    def chat(self, prompt: str) -> str:
        return "ok"


def test_run_autoharness_end_to_end(tmp_path: Path) -> None:
    """Full loop: VM → trace → score → Thompson search → skill extraction → persist."""
    from autoharness.ir.upir import UPIR, UPIRNode

    variants = {
        "good": UPIR(
            entry="h1",
            nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
            edges=[],
            harness_table={"h": "result = 'ok'"},
        ),
        "bad": UPIR(
            entry="h1",
            nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
            edges=[],
            harness_table={"h": "result = 'fail'"},
        ),
    }

    result = run_autoharness(
        variants=variants,
        llm=FakeLLM(),
        seed=42,
        max_search_iterations=3,
        data_dir=str(tmp_path / "memory"),
    )

    assert result["status"] in ("converged", "max_iterations", "max_failures")
    assert result["best_variant"] is not None
    assert result["episodes_saved"] >= 0


def test_run_autoharness_empty_variants(tmp_path: Path) -> None:
    """Empty variants returns no_branches status."""
    result = run_autoharness(
        variants={},
        llm=FakeLLM(),
        seed=42,
        data_dir=str(tmp_path / "memory"),
    )
    assert result["status"] == "no_branches"
    assert result["best_variant"] is None


def test_cli_demo_mode(tmp_path: Path) -> None:
    """CLI --demo runs without error."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "autoharness.main", "--demo"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "AutoHarness Demo" in result.stdout
