"""VM execution engine — step-by-step interpreter over UPIR graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoharness.ir.upir import UPIR, UPIRNode

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

    def _step_node(self, node: UPIRNode) -> StepResult:
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

        # Look up harness code from the UPIR harness table
        harness_code = self.upir.harness_table.get(harness_id, "")

        # Execute via sandboxed runner
        from autoharness.sandbox.harness_runner import run_harness

        result = run_harness(
            harness_code,
            state=self.state.flatten(),
            environment=self.environment,
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
        args = getattr(node, "args", {})

        # Skill calls delegate to the LLM for now
        response = self.llm.chat(f"Execute skill: {skill_id} with {args}")

        self.state.set(node_id, "skill_id", skill_id)
        self.state.set(node_id, "response", response)

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"skill_id": skill_id, "response": response}},
            trace_event={
                "node_id": node_id,
                "kind": "skill_call",
                "skill_id": skill_id,
                "response": response,
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
