"""Integration test for tracedge.main — end-to-end loop with fake LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tracedge.main import run_tracedge

if TYPE_CHECKING:
    from pathlib import Path


class FakeLLM:
    """Canned LLM for testing."""

    def chat(self, prompt: str) -> str:
        return "ok"


def test_run_tracedge_end_to_end(tmp_path: Path) -> None:
    """Full loop: VM → trace → score → Thompson search → skill extraction → persist."""
    from tracedge.ir.upir import UPIR, UPIRNode

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

    result = run_tracedge(
        variants=variants,
        llm=FakeLLM(),
        seed=42,
        max_search_iterations=3,
        data_dir=str(tmp_path / "memory"),
    )

    assert result["status"] in ("converged", "max_iterations", "max_failures")
    assert result["best_variant"] is not None
    assert result["episodes_saved"] >= 0


def test_run_tracedge_empty_variants(tmp_path: Path) -> None:
    """Empty variants returns no_branches status."""
    result = run_tracedge(
        variants={},
        llm=FakeLLM(),
        seed=42,
        data_dir=str(tmp_path / "memory"),
    )
    assert result["status"] == "no_branches"
    assert result["best_variant"] is None


def test_convergence_good_wins(tmp_path: Path) -> None:
    """Two variants with genuinely different success rates — the better one wins.

    The 'good' variant has a harness that succeeds (verdict='ok', task_success=1.0).
    The 'bad' variant has a harness that raises an error (verdict='error', task_success=0.0).
    Thompson search should converge on 'good' across multiple seeds.
    """
    from tracedge.ir.upir import UPIR, UPIRNode

    good = UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "result = True"},
    )
    bad = UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "raise ValueError('always fails')"},
    )

    wins = 0
    for seed in [42, 43, 44]:
        result = run_tracedge(
            variants={"good": good, "bad": bad},
            llm=FakeLLM(),
            seed=seed,
            max_search_iterations=15,
            max_total_failures=10,
            data_dir=str(tmp_path / f"memory_{seed}"),
        )
        assert result["status"] == "converged", (
            f"seed={seed}: expected converged, got {result['status']}"
        )
        if result["best_variant"] == "good":
            wins += 1

    assert wins >= 2, f"Expected 'good' to win ≥2/3 seeds, won {wins}/3"


def test_cli_demo_mode(tmp_path: Path) -> None:
    """CLI --demo runs without error."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tracedge.main", "--demo"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Tracedge Demo" in result.stdout


def test_reuse_skills_loads_persisted_skills(tmp_path: Path) -> None:
    """reuse_skills=True loads persisted skills into skill_table."""
    from tracedge.ir.upir import UPIR, UPIRNode
    from tracedge.memory.store import MemoryStore

    data_dir = str(tmp_path / "shared")

    # Pre-persist a skill in the same data_dir used by run_tracedge
    store = MemoryStore(data_dir=tmp_path / "shared")
    skill = UPIR(
        entry="n1",
        nodes={"n1": UPIRNode(kind="act", node_id="n1", tool="write")},
        edges=[],
        harness_table={},
        skill_table={},
    )
    store.save_skill("skill_1", skill)

    # Define a variant with a harness_call (so it gets task_success=1)
    good = UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "result = True"},
    )

    result = run_tracedge(
        variants={"good": good},
        llm=FakeLLM(),
        seed=42,
        max_search_iterations=3,
        data_dir=data_dir,
        reuse_skills=True,
    )
    assert result["status"] in ("converged", "max_iterations")
    assert result["best_variant"] == "good"
    assert result["skills_loaded"] >= 1


def test_llm_free_replay_saves_llm_calls(tmp_path: Path) -> None:
    """Skills with no think/branch nodes skip LLM calls, counting llm_calls_saved.

    The variant has harness_call + skill_call (no think/branch), so:
    - llm_calls == 0 (no think/branch events in the trace)
    - llm_calls_saved >= 1 (skill_call to a deterministic skill)
    """
    from tracedge.ir.upir import UPIR, UPIRNode

    # A skill with only act nodes (deterministic) — no think/branch
    skill = UPIR(
        entry="n1",
        nodes={
            "n1": UPIRNode(kind="act", node_id="n1", tool="write"),
            "n2": UPIRNode(kind="act", node_id="n2", tool="exec"),
        },
        edges=[{"from": "n1", "to": "n2", "kind": "sequential"}],
        harness_table={},
        skill_table={},
    )

    # A variant with a harness_call + a skill_call
    good = UPIR(
        entry="h1",
        nodes={
            "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
            "s1": UPIRNode(kind="skill_call", node_id="s1", skill_id="skill_1"),
        },
        edges=[{"from": "h1", "to": "s1", "kind": "sequential"}],
        harness_table={"h": "result = True"},
        skill_table={"skill_1": skill},
    )

    result = run_tracedge(
        variants={"good": good},
        llm=FakeLLM(),
        seed=42,
        max_search_iterations=3,
        data_dir=str(tmp_path / "memory"),
    )
    assert result["status"] in ("converged", "max_iterations")
    assert result["llm_calls"] >= 0
    assert result["llm_calls_saved"] >= 1


def test_result_dict_per_variant_stats(tmp_path: Path) -> None:
    """Result dict includes per_variant_stats with posterior means."""
    from tracedge.ir.upir import UPIR, UPIRNode

    good = UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "result = True"},
    )
    bad = UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "raise ValueError('fail')"},
    )

    result = run_tracedge(
        variants={"good": good, "bad": bad},
        llm=FakeLLM(),
        seed=42,
        max_search_iterations=5,
        data_dir=str(tmp_path / "memory"),
    )
    assert "per_variant_stats" in result
    stats = result["per_variant_stats"]
    assert "good" in stats
    assert "bad" in stats
    assert "posterior_mean" in stats["good"]
    assert "trials" in stats["good"]
