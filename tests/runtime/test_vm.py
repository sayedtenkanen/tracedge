from autoharness.ir.upir import UPIR, Edge
from autoharness.runtime.vm import VM


class FakeLLM:
    """Canned LLM for testing Think nodes."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return f"response {self.call_count} to: {prompt}"


class TestVMExecuteObserve:
    def test_observe_node(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        result = vm.run()
        assert result is not None
        assert len(result) > 0


class TestVMExecuteAct:
    def test_act_node(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "act", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        result = vm.run()
        assert result is not None


class TestVMExecuteThink:
    def test_think_node(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "think", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        result = vm.run()
        assert result is not None


class TestVMExecuteBranch:
    def test_branch_node(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "True",
                    "true_next": "n2",
                    "false_next": "n3",
                },
                "n2": {"kind": "act", "node_id": "n2"},
                "n3": {"kind": "act", "node_id": "n3"},
            },
            edges=[
                Edge(from_="n1", to="n2", kind="branch"),
                Edge(from_="n1", to="n3", kind="branch"),
            ],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        result = vm.run()
        assert result is not None


class TestVMDeterministicReplay:
    def test_same_seed_same_trace(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "think", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        r1 = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        r2 = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        assert r1 == r2

    def test_different_seed_different_trace(self) -> None:
        from autoharness.runtime.seed import SeedStream

        s1 = SeedStream(seed=42)
        s2 = SeedStream(seed=99)
        # Different seeds produce different random sequences
        assert s1.next() != s2.next()


class TestVMTermination:
    def test_terminate_on_end(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        result = vm.run()
        assert result is not None

    def test_max_steps_limit(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1"},
                "n2": {"kind": "observe", "node_id": "n2"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42, max_steps=1)
        result = vm.run()
        assert len(result) <= 2


class TestVMTemplateResolution:
    def test_resolved_template_in_think(self) -> None:
        """{observe.query} in think prompt is resolved from State."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {"kind": "observe", "node_id": "n1", "query": "hello"},
                "n2": {"kind": "think", "node_id": "n2", "prompt": "{n1.query}"},
            },
            edges=[Edge(from_="n1", to="n2", kind="sequential")],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        trace = vm.run()
        think_event = trace[1]
        assert think_event["prompt"] == "hello"

    def test_unresolved_template_produces_error(self) -> None:
        """Unresolved {nonexistent.key} produces an error in the trace event."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "think",
                    "node_id": "n1",
                    "prompt": "{nonexistent.response}",
                },
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        trace = vm.run()
        event = trace[0]
        assert "unresolved_refs" in event
        assert "{nonexistent.response}" in event["unresolved_refs"]

    def test_unresolved_template_in_act_args(self) -> None:
        """Unresolved template in act args produces an error."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "act",
                    "node_id": "n1",
                    "tool": "write",
                    "args": {"content": "{think.response}"},
                },
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        trace = vm.run()
        event = trace[0]
        assert "unresolved_refs" in event
        assert "{think.response}" in event["unresolved_refs"]
