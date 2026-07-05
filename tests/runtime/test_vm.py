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
                Edge(from_="n1", to="n2", kind="branch"),  # type: ignore[call-arg]
                Edge(from_="n1", to="n3", kind="branch"),  # type: ignore[call-arg]
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
            edges=[Edge(from_="n1", to="n2", kind="sequential")],  # type: ignore[call-arg]
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42, max_steps=1)
        result = vm.run()
        assert len(result) <= 2
