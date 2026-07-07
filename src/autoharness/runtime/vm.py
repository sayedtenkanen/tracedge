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
        self._env_state: dict[str, Any] = {}
        self._last_unresolved_refs: list[str] = []

    def run(self) -> list[dict[str, Any]]:
        """Execute the graph and return trace events."""
        trace: list[dict[str, Any]] = []
        current_id: str | None = self.upir.entry
        steps = 0

        # Reset environment if present
        if self.environment is not None:
            self._env_state = self.environment.reset(seed=self.seed_stream.next())
            self.state.set("__env__", "state", self._env_state)

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

        # If environment is present, observe its current state
        env_info: dict[str, Any] = {}
        if self.environment is not None and self._env_state:
            env_info["env_state"] = self._env_state
            legal = self.environment.legal_actions(self._env_state)
            if legal is not None:
                env_info["legal_actions"] = legal

        self.state.set(node_id, "query", query)
        self.state.set(node_id, "observed", True)
        if env_info:
            self.state.set(node_id, "env_info", env_info)

        trace_event: dict[str, Any] = {
            "node_id": node_id,
            "kind": "observe",
            "query": query,
        }
        if env_info:
            trace_event["env_info"] = env_info

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"query": query, "observed": True, **env_info}},
            trace_event=trace_event,
        )

    def _step_act(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        tool = getattr(node, "tool", "")
        args = getattr(node, "args", {})
        args = self._resolve_dict_templates(args)
        unresolved = list(self._last_unresolved_refs)
        self.state.set(node_id, "tool", tool)
        self.state.set(node_id, "args", args)

        # Execute via environment if present
        env_result: dict[str, Any] = {}
        if self.environment is not None:
            action = {"tool": tool, **args}
            next_env_state, reward, done, info = self.environment.step(self._env_state, action)
            self._env_state = next_env_state
            self.state.set("__env__", "state", self._env_state)
            env_result = {
                "reward": reward,
                "done": done,
                "info": info,
            }
            if info:
                env_result["tool_output"] = info

        trace_event: dict[str, Any] = {
            "node_id": node_id,
            "kind": "act",
            "tool": tool,
            "args": args,
        }
        if env_result:
            trace_event["env_result"] = env_result
        if unresolved:
            trace_event["unresolved_refs"] = unresolved

        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"tool": tool, "args": args, **env_result}},
            trace_event=trace_event,
        )

    def _step_think(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        prompt = getattr(node, "prompt", "")
        prompt = self._resolve_templates(prompt)
        unresolved = list(self._last_unresolved_refs)
        response = self.llm.chat(prompt)
        self.state.set(node_id, "prompt", prompt)
        self.state.set(node_id, "response", response)
        event: dict[str, Any] = {
            "node_id": node_id,
            "kind": "think",
            "prompt": prompt,
            "response": response,
        }
        if unresolved:
            event["unresolved_refs"] = unresolved
        return StepResult(
            next=self._next_node(node_id),
            state_delta={node_id: {"prompt": prompt, "response": response}},
            trace_event=event,
        )

    def _step_branch(self, node: UPIRNode) -> StepResult:
        node_id = node.node_id
        condition = getattr(node, "condition", "")
        condition = self._resolve_templates(condition)
        unresolved = list(self._last_unresolved_refs)
        true_next = getattr(node, "true_next", "")
        false_next = getattr(node, "false_next", "")

        # Evaluate condition via LLM — ask for a boolean answer
        response = self.llm.chat(f"Answer only true or false: {condition}")
        taken = response.strip().lower().startswith("true")

        next_id = true_next if taken else false_next
        event: dict[str, Any] = {
            "node_id": node_id,
            "kind": "branch",
            "condition": condition,
            "taken": "true" if taken else "false",
        }
        if unresolved:
            event["unresolved_refs"] = unresolved
        return StepResult(
            next=next_id,
            trace_event=event,
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

    def _resolve_templates(self, text: str) -> str:
        """Resolve {node_id.key} template references from State.

        Populates ``self._last_unresolved_refs`` with any references that could
        not be resolved, so callers can surface them as trace errors.
        """
        import re

        flat = self.state.flatten()
        unresolved: list[str] = []

        def _replace(match: re.Match[str]) -> str:
            ref = match.group(1)
            parts = ref.split(".", 1)
            if len(parts) == 2:
                node_id, key = parts
                node_data = flat.get(node_id, {})
                if key in node_data:
                    value = node_data[key]
                    return str(value) if not isinstance(value, str) else value
                # Key exists but value missing — record as unresolved
                unresolved.append(match.group(0))
                return match.group(0)
            # Not a node_id.key pattern — leave as-is
            unresolved.append(match.group(0))
            return match.group(0)

        self._last_unresolved_refs = unresolved
        return re.sub(r"\{([^}]+)\}", _replace, text)

    def _resolve_dict_templates(self, d: dict[str, Any]) -> dict[str, Any]:
        """Resolve template strings in all values of a dict."""
        resolved: dict[str, Any] = {}
        for key, value in d.items():
            if isinstance(value, str) and "{" in value and "}" in value:
                resolved[key] = self._resolve_templates(value)
            else:
                resolved[key] = value
        return resolved
