"""Tests for Skill Execution — SkillCall node executes nested UPIR from skill_table."""

from __future__ import annotations

from tracedge.ir.upir import UPIR, UPIRNode
from tracedge.runtime.vm import VM
from tracedge.skills.extractor import SkillExtractor
from tracedge.trace.trace_ir import TraceEvent, TraceLog


def _make_upir_with_skill() -> UPIR:
    """Build a UPIR with a skill_call node and a skill_table entry."""
    extractor = SkillExtractor(min_occurrences=2)
    trace = TraceLog()
    for _ in range(2):
        trace.append(TraceEvent(node_id="n1", kind="observe"))
        trace.append(TraceEvent(node_id="n2", kind="act"))
    patterns = extractor.detect_patterns(trace)
    skill_node = extractor.extract_skill(
        patterns[0],
        UPIR(
            entry="n1",
            nodes={
                "n1": UPIRNode(kind="observe", node_id="n1"),
                "n2": UPIRNode(kind="act", node_id="n2"),
            },
            edges=[{"from": "n1", "to": "n2", "kind": "sequential"}],
            harness_table={},
            skill_table={},
        ),
    )
    skill_id = skill_node.skill_id  # type: ignore[union-attr]

    return UPIR(
        entry="call1",
        nodes={
            "call1": UPIRNode(kind="skill_call", node_id="call1", skill_id=skill_id),
            "after": UPIRNode(kind="act", node_id="after"),
        },
        edges=[
            {"from": "call1", "to": "after", "kind": "sequential"},
        ],
        harness_table={},
        skill_table=extractor.skill_table,
    )


class FakeLLM:
    def chat(self, prompt: str) -> str:
        return "ok"


class TestSkillExecution:
    """Slice 8 — SkillCall node executes nested UPIR."""

    def test_skill_call_node_executes(self) -> None:
        """SkillCall node runs nested UPIR — trace includes nested_trace with nested events."""
        upir = _make_upir_with_skill()
        vm = VM(upir=upir, llm=FakeLLM(), seed=1)
        trace = vm.run()
        skill_event = next(e for e in trace if e.get("kind") == "skill_call")
        nested_trace = skill_event.get("nested_trace", [])
        nested_node_ids = [e.get("node_id") for e in nested_trace]
        assert "n1" in nested_node_ids, f"nested node n1 not in trace: {nested_node_ids}"
        assert "n2" in nested_node_ids, f"nested node n2 not in trace: {nested_node_ids}"

    def test_skill_not_found_error(self) -> None:
        """SkillCall emits error when skill_id is missing from skill_table."""
        upir = _make_upir_with_skill()
        skill_id = upir.nodes["call1"].skill_id  # type: ignore[union-attr]
        assert skill_id in upir.skill_table
        del upir.skill_table[skill_id]

        vm = VM(upir=upir, llm=FakeLLM(), seed=1)
        trace = vm.run()
        skill_event = next(e for e in trace if e.get("kind") == "skill_call")

        assert skill_event["error"] == f"skill '{skill_id}' not found in skill_table"
        assert not skill_event.get("nested_trace")
        assert not skill_event.get("nested_steps")

    def test_skill_registry_lookup(self) -> None:
        """SkillCall resolves skill by ID from skill_table."""
        upir = _make_upir_with_skill()
        skill_id = upir.nodes["call1"].skill_id  # type: ignore[union-attr]
        assert skill_id in upir.skill_table
        nested = upir.skill_table[skill_id]
        assert isinstance(nested, UPIR)
        assert len(nested.nodes) >= 2

    def test_skill_nested_state(self) -> None:
        """Nested UPIR state is namespaced under the skill_call node."""
        upir = _make_upir_with_skill()
        vm = VM(upir=upir, llm=FakeLLM(), seed=1)
        vm.run()
        flat = vm.state.flatten()
        # Nested state stored as nested.<node_id> under the skill_call node
        assert "call1" in flat
        assert "nested.n1" in flat["call1"], f"missing nested.n1: {list(flat['call1'].keys())}"
        assert "nested.n2" in flat["call1"], f"missing nested.n2: {list(flat['call1'].keys())}"
