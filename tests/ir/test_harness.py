"""Tests for Harness IR — formalized harness types and result contract."""

import pytest


class TestHarness:
    """Harness IR model: kind, code, schemas, effects, guard_policy."""

    def test_harness_construction(self):
        from autoharness.ir.harness import Harness

        h = Harness(
            kind="action_verifier",
            code="def check(state, action): return True",
            effects={"filesystem": False, "network": False, "llm_calls": 0},
        )
        assert h.kind == "action_verifier"
        assert h.version == 1

    def test_harness_kind_options(self):
        from autoharness.ir.harness import Harness

        for kind in ("action_filter", "action_verifier", "policy"):
            h = Harness(
                kind=kind,
                code="def fn(): pass",
                effects={"filesystem": False, "network": False, "llm_calls": 0},
            )
            assert h.kind == kind

    def test_harness_invalid_kind_rejected(self):
        from autoharness.ir.harness import Harness

        with pytest.raises(ValueError):
            Harness(
                kind="invalid",
                code="def fn(): pass",
                effects={"filesystem": False, "network": False, "llm_calls": 0},
            )

    def test_harness_guard_policy_defaults(self):
        from autoharness.ir.harness import Harness

        h = Harness(
            kind="policy",
            code="def decide(state): return 0",
            effects={"filesystem": False, "network": False, "llm_calls": 0},
        )
        assert h.guard_policy["no_try_except"] is True
        assert h.guard_policy["max_runtime_ms"] > 0


class TestHarnessResult:
    """HarnessResult: verdict, raised, cost."""

    def test_harness_result_construction(self):
        from autoharness.ir.harness import HarnessResult

        r = HarnessResult(verdict=True, raised=None, cost=0.0)
        assert r.verdict is True
        assert r.raised is None
        assert r.cost == 0.0

    def test_harness_result_with_exception(self):
        from autoharness.ir.harness import HarnessResult

        r = HarnessResult(verdict=False, raised="ValueError", cost=0.1)
        assert r.raised == "ValueError"
