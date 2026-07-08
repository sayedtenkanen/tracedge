from tracedge.ir.upir import UPIR, Edge
from tracedge.runtime.vm import VM


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
        from tracedge.runtime.seed import SeedStream

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


class TestVMPhiNode:
    def test_phi_node_executes(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "phi", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        trace = vm.run()
        assert trace[0]["kind"] == "phi"


class TestVMUnsupportedKind:
    def test_unsupported_kind_returns_error(self) -> None:
        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "bogus", "node_id": "n1"}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42)
        trace = vm.run()
        assert "error" in trace[0]
        assert "unsupported kind" in trace[0]["error"]


class TestVMActWithEnvironment:
    def test_act_calls_environment(self) -> None:
        from unittest.mock import MagicMock

        mock_env = MagicMock()
        mock_env.step.return_value = ({"x": 1}, 0.5, False, {"success": True})
        mock_env.legal_actions.return_value = None

        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "act", "node_id": "n1", "tool": "write", "args": {}}},
            edges=[],
            harness_table={},
            skill_table={},
        )
        vm = VM(upir=upir, llm=FakeLLM(), seed=42, environment=mock_env)
        trace = vm.run()
        assert "env_result" in trace[0]
        assert trace[0]["env_result"]["reward"] == 0.5
        mock_env.step.assert_called_once()


class TestVMProbabilisticBranch:
    def test_branch_with_probability_skips_llm(self) -> None:
        """Branch with probability set samples from Bernoulli, no LLM call."""
        llm = FakeLLM()
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "some_condition",
                    "true_next": "n2",
                    "false_next": "n3",
                    "probability": 0.5,
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
        vm = VM(upir=upir, llm=llm, seed=42)
        trace = vm.run()
        # LLM should not be called for probabilistic branch
        assert llm.call_count == 0
        # Branch event should record the sampled probability
        assert trace[0]["kind"] == "branch"
        assert trace[0]["taken"] in ("true", "false")
        assert "sampled_probability" in trace[0]

    def test_branch_without_probability_calls_llm(self) -> None:
        """Branch without probability falls back to LLM evaluation."""
        llm = FakeLLM()
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
        vm = VM(upir=upir, llm=llm, seed=42)
        vm.run()
        # LLM should be called for deterministic branch
        assert llm.call_count == 1

    def test_probabilistic_branch_deterministic_replay(self) -> None:
        """Same seed with probabilistic branch produces identical trace."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "x",
                    "true_next": "n2",
                    "false_next": "n3",
                    "probability": 0.5,
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
        r1 = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        r2 = VM(upir=upir, llm=FakeLLM(), seed=42).run()
        assert r1 == r2

    def test_probabilistic_branch_different_seed(self) -> None:
        """Different seeds can produce different branch paths."""
        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "condition": "x",
                    "true_next": "n2",
                    "false_next": "n3",
                    "probability": 0.5,
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
        # Run with many seeds — should get both paths eventually
        true_count = 0
        for seed in range(100):
            trace = VM(upir=upir, llm=FakeLLM(), seed=seed).run()
            if trace[0]["taken"] == "true":
                true_count += 1
        # With p=0.5 and 100 seeds, expect roughly 50 true — not all same
        assert 20 < true_count < 80, f"Expected ~50 true, got {true_count}"

    def test_branch_probability_out_of_range_raises(self) -> None:
        """Branch with probability outside [0.0, 1.0] raises ValueError."""
        import pytest

        upir = UPIR(
            entry="n1",
            nodes={
                "n1": {
                    "kind": "branch",
                    "node_id": "n1",
                    "probability": 1.5,
                },
                "n2": {"kind": "act", "node_id": "n2"},
            },
            edges=[],
            harness_table={},
            skill_table={},
        )
        with pytest.raises(ValueError, match="Branch probability must be in"):
            VM(upir=upir, llm=FakeLLM(), seed=42).run()
