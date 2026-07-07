"""Tests for Trace IR — execution observability with structured trace events."""

from tracedge.ir.upir import UPIR, Edge
from tracedge.runtime.vm import VM


class FakeLLM:
    def __init__(self, response: str = "true") -> None:
        self.call_count = 0
        self._response = response

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return self._response


class TestTraceEventEmitted:
    """Every node execution produces a trace_event."""

    def test_trace_event_emitted_per_node(self) -> None:
        from tracedge.trace.trace_ir import TraceEvent

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1", "query": "test"},
                "n2": {"kind": "act", "node_id": "n2", "tool": "read_file"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        assert len(trace) == 2
        for event_dict in trace:
            te = TraceEvent.model_validate(event_dict)
            assert te.node_id != ""


class TestTraceEventFields:
    """trace_event has node_id, inputs, outputs, cost."""

    def test_trace_event_fields(self) -> None:
        from tracedge.trace.trace_ir import TraceEvent

        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1", "query": "hello"}},
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        te = TraceEvent.model_validate(trace[0])
        assert te.node_id == "n1"
        assert te.kind == "observe"
        assert isinstance(te.cost, float)


class TestTraceLegalFlag:
    """legal field: True/False for GameEnvironment, None for ToolEnvironment."""

    def test_trace_legal_flag_none_tool_env(self) -> None:
        from tracedge.environment.tool_env import ToolEnvironment
        from tracedge.trace.trace_ir import TraceEvent

        env = ToolEnvironment()
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
        )
        vm = VM(upir=upir, llm=FakeLLM(), environment=env)
        trace = vm.run()
        te = TraceEvent.model_validate(trace[0])
        assert te.legal is None

    def test_trace_legal_flag_game_env(self) -> None:
        from tracedge.environment.game_env import GameEnvironment
        from tracedge.trace.trace_ir import TraceEvent

        env = GameEnvironment()
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
        )
        vm = VM(upir=upir, llm=FakeLLM(), environment=env)
        trace = vm.run()
        te = TraceEvent.model_validate(trace[0])
        assert te.legal is None or isinstance(te.legal, bool)


class TestHarnessCallTrace:
    """HarnessCall nodes emit verdict, raised, cost in trace_event."""

    def test_trace_harness_result_fields(self) -> None:
        from tracedge.trace.trace_ir import TraceEvent

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "harness_call",
                    "node_id": "n1",
                    "harness_id": "h1",
                },
            },
            harness_table={
                "h1": {
                    "kind": "policy",
                    "code": "x = 2 + 2",
                    "effects": {"filesystem": False, "network": False, "llm_calls": 0},
                },
            },
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        te = TraceEvent.model_validate(trace[0])
        assert te.kind == "harness_call"
        assert "verdict" in trace[0]

    def test_trace_harness_raised_visible(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "harness_call",
                    "node_id": "n1",
                    "harness_id": "h1",
                },
            },
            harness_table={
                "h1": {
                    "kind": "policy",
                    "code": "raise ValueError('test error')",
                    "effects": {"filesystem": False, "network": False, "llm_calls": 0},
                },
            },
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        assert trace[0].get("raised") is not None


class TestDeterministicReplay:
    """Same execution produces identical trace."""

    def test_trace_deterministic_replay(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "think", "node_id": "n1", "prompt": "test"}},
        )
        t1 = VM(upir=upir, llm=FakeLLM("response"), seed=42).run()
        t2 = VM(upir=upir, llm=FakeLLM("response"), seed=42).run()
        assert t1 == t2


class TestCostAccumulated:
    """trace_event.cost values are consistent."""

    def test_trace_cost_accumulated(self) -> None:
        from tracedge.trace.trace_ir import TraceEvent

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
        )
        vm = VM(upir=upir, llm=FakeLLM())
        trace = vm.run()
        costs = [TraceEvent.model_validate(e).cost for e in trace]
        assert all(c >= 0 for c in costs)
