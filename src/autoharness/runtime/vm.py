"""VM execution engine — step-by-step interpreter over UPIR graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoharness.ir.upir import UPIR, UPIRNode

from autoharness.ir.upir import UPIRNode as _UPIRNode
from autoharness.runtime.seed import SeedStream
from autoharness.runtime.state import State
from autoharness.runtime.step import StepResult


class VM:
    """Execute a UPIR graph step-by-step."""

    def __init__(
        self,
        upir: UPIR,
        llm: Any,
        seed: int = 42,
        max_steps: int = 100,
        environment: Any = None,
    ) -> None:
        self.upir = upir
        self.llm = llm
        self.seed_stream = SeedStream(seed)
        self.max_steps = max_steps
        self.state = State()
        self.environment = environment

    def run(self) -> list[dict[str, Any]]:
        """Execute the graph and return trace events."""
        trace: list[dict[str, Any]] = []
        current_id: str | None = self.upir.entry
        steps = 0

        while current_id is not None and steps < self.max_steps:
            node = self.upir.nodes[current_id]
            step_result = self._step_node(node)
            trace.append(step_result.trace_event)
            current_id = step_result.next
            steps += 1

        return trace

    def _step_node(self, node: UPIRNode | dict[str, Any]) -> StepResult:
        if isinstance(node, dict):
            node = _UPIRNode.model_validate(node)
        kind = node.kind

        if kind == "observe":
            return self._step_observe(node)
        elif kind == "act":
            return self._step_act(node)
        elif kind == "think":
            return self._step_think(node)
        elif kind == "branch":
            return self._step_branch(node)
        elif kind == "harness_call":
            return self._step_harness_call(node)
        elif kind == "skill_call":
            return self._step_skill_call(node)
        elif kind == "phi":
            return self._step_phi(node)
        else:
            return StepResult(
                next=None,
                trace_event={"node_id": node.node_id, "error": f"unsupported kind: {kind}"},
            )

    def _step_observe(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        query = getattr(node, "query", "")
        self.state.set(node_id, "query", query)
        self.state.set(node_id, "observed", True)
        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"query": query, "observed": True}},
            trace_event={"node_id": node_id, "kind": "observe", "query": query},
        )

    def _step_act(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        tool = getattr(node, "tool", "")
        args = getattr(node, "args", {})
        self.state.set(node_id, "tool", tool)
        self.state.set(node_id, "args", args)
        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"tool": tool, "args": args}},
            trace_event={"node_id": node_id, "kind": "act", "tool": tool, "args": args},
        )

    def _step_think(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        prompt = getattr(node, "prompt", "")
        response = self.llm.chat(prompt)
        self.state.set(node_id, "prompt", prompt)
        self.state.set(node_id, "response", response)
        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"prompt": prompt, "response": response}},
            trace_event={
                "node_id": node_id,
                "kind": "think",
                "prompt": prompt,
                "response": response,
            },
        )

    def _step_branch(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        condition = getattr(node, "condition", "")
        true_next = getattr(node, "true_next", "")
        false_next = getattr(node, "false_next", "")

        # Evaluate condition via LLM — ask for a boolean answer
        response = self.llm.chat(f"Answer only true or false: {condition}")
        taken = response.strip().lower().startswith("true")

        next_id = true_next if taken else false_next
        return StepResult(
            next=next_id,
            trace_event={
                "node_id": node_id,
                "kind": "branch",
                "condition": condition,
                "taken": "true" if taken else "false",
            },
        )

    def _step_harness_call(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        harness_id = getattr(node, "harness_id", "")

        # Look up harness code and effects from the UPIR harness table
        harness_entry = self.upir.harness_table.get(harness_id, "")
        harness_code = ""
        effects: dict[str, bool] | None = None
        if harness_entry is None or harness_entry == "":
            harness_code = ""
        elif isinstance(harness_entry, dict):
            if "code" not in harness_entry:
                raise ValueError(f"Harness '{harness_id}' in harness_table is missing 'code' key")
            harness_code = harness_entry["code"]
            effects = harness_entry.get("effects")
        else:
            harness_code = str(harness_entry)

        # Execute via sandboxed runner
        from autoharness.sandbox.harness_runner import run_harness

        result = run_harness(
            harness_code,
            state=self.state.flatten(),
            environment=self.environment,
            effects=effects,
        )

        self.state.set(node_id, "harness_id", harness_id)
        self.state.set(node_id, "verdict", result["verdict"])
        self.state.set(node_id, "raised", result["raised"])

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"harness_id": harness_id, "verdict": result["verdict"]}},
            trace_event={
                "node_id": node_id,
                "kind": "harness_call",
                "harness_id": harness_id,
                "verdict": result["verdict"],
                "raised": result["raised"],
            },
        )

    def _step_skill_call(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        skill_id = getattr(node, "skill_id", "")

        # Look up skill (nested UPIR) from skill_table
        nested_upir = self.upir.skill_table.get(skill_id)
        if nested_upir is None:
            return StepResult(
                next=self._next_node(node_id),
                trace_event={
                    "node_id": node_id,
                    "kind": "skill_call",
                    "skill_id": skill_id,
                    "error": f"skill '{skill_id}' not found in skill_table",
                },
            )

        # Execute nested UPIR with its own VM, passing current state
        nested_vm = VM(
            upir=nested_upir,
            llm=self.llm,
            seed=self.seed_stream.next(),
            max_steps=self.max_steps,
            environment=self.environment,
        )
        nested_trace = nested_vm.run()

        # Merge nested state into parent (namespaced under skill_call node)
        nested_state: dict[str, Any] = {}
        for nested_id, values in nested_vm.state.flatten().items():
            self.state.set(node_id, f"nested.{nested_id}", values)
            nested_state[f"nested.{nested_id}"] = values

        self.state.set(node_id, "skill_id", skill_id)
        self.state.set(node_id, "nested_steps", len(nested_trace))

        delta: dict[str, Any] = {
            "skill_id": skill_id,
            "nested_steps": len(nested_trace),
        }
        delta.update(nested_state)

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: delta},
            trace_event={
                "node_id": node_id,
                "kind": "skill_call",
                "skill_id": skill_id,
                "nested_trace": [
                    {"node_id": e.get("node_id"), "kind": e.get("kind")} for e in nested_trace
                ],
                "nested_steps": len(nested_trace),
            },
        )

    def _step_phi(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        sources = getattr(node, "sources", [])

        # Phi node merges values from source nodes
        merged: dict[str, Any] = {}
        for src_id in sources:
            flat = self.state.flatten()
            if src_id in flat:
                merged.update(flat[src_id])

        self.state.set(node_id, "merged", merged)

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"merged": merged}},
            trace_event={
                "node_id": node_id,
                "kind": "phi",
                "sources": sources,
            },
        )

    def _next_node(self, current_id: str) -> str | None:
        for edge in self.upir.edges:
            if edge.from_ == current_id and edge.kind == "sequential":
                return edge.to
        return None
