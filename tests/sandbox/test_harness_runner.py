"""Tests for harness runner — sandboxed execution with timeout and exception handling."""


class TestHarnessTimeout:
    """Harness code exceeding max_runtime_ms must be killed."""

    def test_harness_timeout_enforced(self) -> None:
        from autoharness.sandbox.harness_runner import run_harness

        code = """
import time
time.sleep(10)
x = 1
"""
        result = run_harness(code, max_runtime_ms=100)
        assert result["raised"] is not None or result.get("timed_out") is True


class TestHarnessPureComputation:
    """Pure computation harness code must execute successfully."""

    def test_harness_pure_computation_allowed(self) -> None:
        from autoharness.sandbox.harness_runner import run_harness

        code = """
x = 2 + 2
"""
        result = run_harness(code, max_runtime_ms=1000)
        assert result["verdict"] == "ok"
        assert result["raised"] is None
        assert result["outputs"]["x"] == 4


class TestHarnessException:
    """Harness exceptions must propagate for VM-level handling."""

    def test_harness_exception_propagates(self) -> None:
        from autoharness.sandbox.harness_runner import run_harness

        code = """
raise ValueError("test error")
"""
        result = run_harness(code, max_runtime_ms=1000)
        assert result["raised"] is not None
        assert "ValueError" in str(result["raised"])
