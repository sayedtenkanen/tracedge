"""End-to-end integration tests — real seams, no fabricated dicts."""

from __future__ import annotations

from autoharness.intelligence.critic import Critic
from autoharness.ir.harness import Harness
from autoharness.ir.upir import UPIR
from autoharness.reward.scorer import score_trace, value
from autoharness.runtime.vm import VM
from autoharness.search.thompson import Branch, ThompsonTreeSearch


class FakeLLM:
    """Canned LLM for think/branch nodes."""

    def __init__(self, response: str = "true") -> None:
        self.call_count = 0
        self._response = response

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return self._response


class TestEndToEndHarnessCall:
    """VM -> trace -> scorer with real harness code."""

    def test_successful_harness_scores_success(self) -> None:
        upir = UPIR(
            entry="h1",
            nodes={
                "h1": {"kind": "harness_call", "node_id": "h1", "harness_id": "ok_harness"},
            },
            edges=[],
            harness_table={"ok_harness": "x = 42"},
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        assert len(trace) == 1
        assert trace[0]["verdict"] == "ok"
        r = score_trace(trace)
        assert r.task_success == 1.0

    def test_failing_harness_scores_failure(self) -> None:
        upir = UPIR(
            entry="h1",
            nodes={
                "h1": {"kind": "harness_call", "node_id": "h1", "harness_id": "bad_harness"},
            },
            edges=[],
            harness_table={"bad_harness": "raise ValueError('broken')"},
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        assert trace[0]["verdict"] == "error"
        assert "ValueError" in trace[0]["raised"]
        r = score_trace(trace)
        assert r.task_success == 0.0


class TestEndToEndCritic:
    """VM trace -> Critic without crash."""

    def test_critic_on_real_vm_trace(self) -> None:
        upir = UPIR(
            entry="h1",
            nodes={
                "h1": {"kind": "harness_call", "node_id": "h1", "harness_id": "fail_h"},
            },
            edges=[],
            harness_table={"fail_h": "raise RuntimeError('boom')"},
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()

        critic = Critic()
        output = critic.analyze([trace])
        assert len(output.failure_clusters) >= 1
        assert output.failure_clusters[0]["root_cause"] == "RuntimeError"


class TestEndToEndThompsonSearch:
    """Thompson search prefers working harness over broken one."""

    def test_search_prefers_good_harness(self) -> None:
        good_branch = Branch(harness=Harness(kind="action_filter", code="result = 'ok'"))
        bad_branch = Branch(harness=Harness(kind="action_filter", code="raise ValueError('bad')"))

        def real_rollout(h: Harness, seed: int) -> tuple[float, bool]:
            upir = UPIR(
                entry="h1",
                nodes={"h1": {"kind": "harness_call", "node_id": "h1", "harness_id": "t"}},
                edges=[],
                harness_table={"t": h.code},
            )
            vm = VM(upir=upir, llm=FakeLLM(), seed=seed)
            trace = vm.run()
            r = score_trace(trace)
            v = value(r)
            failed = trace[0].get("verdict") != "ok"
            return v, failed

        search = ThompsonTreeSearch()
        search.branches = [good_branch, bad_branch]
        result = search.run(real_rollout, rng_seed=42)
        assert result.best_branch is not None
        assert result.best_branch.harness.code == "result = 'ok'"
