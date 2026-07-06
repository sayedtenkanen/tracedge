# Glossary

## Core Concepts

| Term | Definition | Code |
|------|------------|------|
| **UPIR** | Unified Probabilistic Intermediate Representation — a typed executable graph that unifies policy, harness, and skill IR into one substrate. | `src/autoharness/ir/upir.py` |
| **UPIRNode** | A node in a UPIR graph. Has a `kind` (observe, act, think, branch, harness_call, skill_call, phi) and extra fields for kind-specific attributes. | `src/autoharness/ir/upir.py:20` |
| **Edge** | A directed connection between two UPIR nodes with a `kind` (e.g. `sequential`). | `src/autoharness/ir/upir.py:12` |
| **Harness IR** | Typed executable code blocks with effects, guard policies, and a `kind` (policy, reward, utility). Compiled into the UPIR `harness_table`. | `src/autoharness/ir/harness.py` |
| **TraceEvent** | A structured observation emitted by the VM for each node execution. Contains `node_id`, `kind`, `inputs`, `outputs`, `cost`, `legal` flag. | `src/autoharness/trace/trace_ir.py` |
| **Skill** | A reusable subgraph extracted from repeated trace patterns. Stored in the UPIR `skill_table` as a nested UPIR. | `src/autoharness/skills/extractor.py` |
| **SkillExtractor** | Detects repeated node-id subsequences in execution traces and extracts them as nested UPIR skills. | `src/autoharness/skills/extractor.py:20` |
| **Pattern** | A detected repeated pattern in a trace — a sequence of node IDs with an occurrence count. | `src/autoharness/skills/extractor.py:12` |
| **Phi** | A merge node that combines values from multiple source nodes into a single state. | `src/autoharness/ir/nodes.py` |

## Runtime

| Term | Definition | Code |
|------|------------|------|
| **VM** | The execution engine. Interprets a UPIR graph step-by-step, dispatching on node `kind`. Returns a trace (list of trace events). | `src/autoharness/runtime/vm.py` |
| **State** | Per-node namespaced key-value store. Each node writes to its own namespace (`node_id.key`). | `src/autoharness/runtime/state.py` |
| **StepResult** | Return value from a single node execution. Contains `next` node ID, `state_delta`, `outputs`, `reward_signal`, `trace_event`. | `src/autoharness/runtime/step.py` |
| **SeedStream** | Deterministic random number stream. Same seed → same execution sequence. | `src/autoharness/runtime/seed.py` |

## Environments

| Term | Definition | Code |
|------|------------|------|
| **Environment Protocol** | Abstract base class defining the contract all environments must satisfy: `reset()`, `step()`, `legal_actions()`, `tools()`. | `src/autoharness/environment/protocol.py` |
| **ToolEnvironment** | Open action space environment. File operations with workspace sandbox validation. Actions are unrestricted. | `src/autoharness/environment/tool_env.py` |
| **GameEnvironment** | Legal-action-constrained environment. Wraps turn-based games (Tic-Tac-Toe). Tracks illegal moves and enforces legal action lists. | `src/autoharness/environment/game_env.py` |

## Search & Intelligence

| Term | Definition | Code |
|------|------------|------|
| **Thompson Tree Search** | Primary search strategy. Maintains Beta(alpha, beta) posteriors per branch. Thompson sampling picks which branch to expand next, balancing exploration/exploitation. | `PLAN.md` (Slice 5) |
| **value()** | Unified scalar reward function. Converts a Reward vector to a single float in [0, 1] for bandit-style search. Weights vary by environment kind (game vs tool). | `PLAN.md` (Slice 4) |
| **Refiner** | LLM-driven code rewriter. Takes current Harness/Policy + trace + Critic feedback → outputs rewritten IR, validated via Pydantic. | `PLAN.md` (Slice 6) |
| **Critic** | Consolidates sampled failures into structured feedback: failure clusters, legality violations, inefficiency patterns. Feeds into Refiner. | `PLAN.md` (Slice 6) |

## Safety

| Term | Definition | Code |
|------|------------|------|
| **Workspace** | Sandboxed filesystem boundary. All file operations validated via `os.path.realpath()` to prevent path traversal outside the workspace. | `src/autoharness/sandbox/workspace.py` |
| **Guardrails** | AST-based code safety checks. Enforces: no `try/except`, effect boundaries (filesystem, network, environment.step, state mutation). | `src/autoharness/sandbox/guardrails.py` |
| **Sandbox** | Restricted execution environment for harness code. Uses `exec()` with filtered builtins, tool timeouts, and exception propagation. | `src/autoharness/sandbox/harness_runner.py` |
| **Effects** | Declared capabilities of a harness: `filesystem`, `network`, `llm_calls`. Enforced by guardrails at compile time. | `src/autoharness/ir/harness.py` |
