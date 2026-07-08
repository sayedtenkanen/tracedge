# AutoHarness v5 — Vertical Slices Plan

> **Versioning note:** "v5" refers to this project's own iteration count, not the paper's. The paper (arXiv:2603.03329, Lou et al., Google DeepMind, submitted Feb 2026) is a single v1 preprint — there is no v1–v4 lineage to inherit from. Where this plan borrows a technique, it's cited explicitly; everything else is this project's own extension.

## What changed from earlier plans

| Area | Before | Now |
|---|---|---|
| Environment | Implicit, tool-only (`read_file`/`write_file`) | Pluggable `Environment` protocol: **ToolEnvironment** (files/shell/APIs) and **GameEnvironment** (legal-action-constrained, TextArena-style), selectable per run |
| Search/mutation | Population + elite selection only | **Thompson-sampling tree search** (paper's core method) as primary strategy; population search available as alternative |
| Core artifact | Only `Policy IR` | Added **Harness IR** as a first-class artifact alongside Policy IR — this is what the paper is actually about |
| Scope | Flat 16 slices, uniform confidence | Three phases by evidence level: **Phase 1 MVP** (paper-grounded), **Phase 2 Extensions** (speculative, paper names it as future work), **Phase 3 Compiler Theory** (independent research bet, no paper support) |
| Formalization | Harness runtime semantics, search value function, and Policy/Harness relationship were all implicit | Three explicit formalization layers: **Harness Execution Contract** (type + effects), **Unified Value Function** (Thompson search), **UPIR** (single IR substrate unifying Policy/Harness/Skill) — with explicit edges, input/output schemas, effects dict, guard_policy, and CriticOutput type |

---

## Global Principle

> Well-typed IR → Deterministic VM semantics → Trace IR → Reward signal → (optional) learning/optimization

### Core invariant

```
Valid execution = pure function over (PolicyIR, State, Environment, RandomSeed)
```

No hidden state outside VM.

---

## Environment Protocol (pluggable)

```python
class Environment(Protocol):
    def reset(self, seed: int) -> State: ...
    def step(self, state: State, action: Action) -> tuple[State, float, bool, dict]: ...
    def legal_actions(self, state: State) -> list[Action] | None: ...
    # None => unconstrained (tool-use envs); a list => hard constraint (game envs)
    def tools(self) -> dict[str, Callable]: ...
    # only populated for ToolEnvironment; empty for GameEnvironment
```

Two concrete implementations ship in Phase 1:

- **ToolEnvironment** — wraps `read_file`, `write_file`, and future tool registrations. `legal_actions` returns `None` (no enumerable action space); success is task-completion-checked, not move-legality-checked.
- **GameEnvironment** — wraps a TextArena-style turn-based game. `legal_actions` returns the enumerable legal move set at the current state; reward is sparse (win/loss/draw), and illegal-move rate is tracked separately as the paper's core metric.

Both conform to the same `step`/`reset` interface so the VM, Trace IR, and Reward Engine don't need to know which one they're running against.

---

## Harness IR

```python
Harness := {
    "kind": "action_filter" | "action_verifier" | "policy",
    "code": str,                      # python source, sandboxed exec only
    "input_schema": dict,             # expected input types for the harness function
    "output_schema": dict,            # expected output types for the harness function
    "effects": {                      # declared side effects (for compiler optimization + safety)
        "filesystem": bool,
        "network": bool,
        "llm_calls": int,
    },
    "target_env_kind": "tool" | "game" | "both",
    "version": int,
    "legality_accuracy": float | None,  # tracked only for GameEnvironment
    "guard_policy": {
        "no_try_except": True,        # enforced — see Guardrail #5
        "max_runtime_ms": int,        # hard timeout for harness execution
    },
}
```

- **action_filter** — narrows/re-ranks the LLM's candidate actions before execution.
- **action_verifier** — checks a proposed action before committing it; on rejection, loops back to the proposer (this is the paper's primary focus and best-validated variant).
- **policy** — pure code, no LLM call at inference. This is the "harness-as-policy" result from the paper: once a policy-kind harness clears its reward threshold, the VM can execute it directly, skipping Think/LLM nodes entirely.

New node type: **`HarnessCall`** — invokes a Harness at inference time. If `kind == "policy"` and accuracy/reward is above `convergence_threshold`, the VM bypasses the LLM for that node going forward.

---

## Harness Execution Contract (type + effects)

Harness IR says *what* a harness is. This says *how* it's allowed to run — the piece that turns Guardrails #4/#5 from conventions into mechanically enforceable rules.

**Type signature per kind** — a Harness's `code` must define exactly one top-level function matching its `kind`; nothing else is callable by the VM:

```python
HarnessSignature = {
    "action_filter":   Callable[[State, List[Action]], List[Action]],
    "action_verifier": Callable[[State, Action], bool],
    "policy":          Callable[[State], Action],
}
```

**Effect boundary:**

| Allowed | Disallowed |
|---|---|
| Read-only access to a `state` snapshot | Direct calls to `environment.step()` |
| Read access to the candidate action list (filter/verifier only) | Filesystem/network I/O outside the sandbox |
| Pure computation, stdlib only | Mutating the `state` object in place |
| — | `try`/`except` (Guardrail #5) |
| — | Any hidden randomness (violates the seed-determinism invariant) |

**Execution result** — a Harness call returns a `HarnessResult`, the Harness-specific counterpart to `StepResult`:

```python
HarnessResult = {
    "verdict": Action | List[Action] | bool,   # shape depends on kind
    "raised": ExceptionInfo | None,             # populated if the harness's code raised — never swallowed
    "cost": float,
}
```

**On uncaught exception:** since `try`/`except` is banned inside harness code, any exception propagates to the VM, not the Refiner. The VM's fixed handling (not the harness author's choice) is: `action_verifier` treats a raise as `False` (reject), `action_filter` treats it as an empty list (block all), `policy` falls back to the LLM `Think` node for that step. This closes the gap where a harness could otherwise "fail open."

**Determinism:** given identical `(state, action_or_candidates, seed)`, a Harness call must be a pure function — replayable through the same Trace IR contract as every other node.

---

## Single IR Substrate (UPIR)

Policy IR and Harness IR have so far been two separate, loosely-linked schemas — a `HarnessCall` node references a `Harness` by ID, but the two don't share a substrate. This breaks in Phase 3: compiler passes (dead-branch elimination, Phi/SSA merging, causal ablation) need one uniform graph to operate on, not "policy nodes, plus a separate opaque code blob some nodes call out to." Formalizing this now avoids a rewrite later.

**UPIR (Unified Policy IR)** — every construct, whether control-flow node, Skill reference, or Harness reference, is a `UPIRNode` in one graph:

```python
UPIR := {
    "entry": NodeID,
    "nodes": Dict[NodeID, UPIRNode],
    "edges": List[Edge],                         # explicit edge list for graph traversal
    "harness_table": Dict[HarnessID, Harness],   # code artifacts referenced, never inlined into the graph
    "skill_table": Dict[SkillID, UPIR],          # Phase 2 — nested UPIR graphs
    "type_env": optional,
    "schema": "typed-executable-graph",
}

UPIRNode := Observe | Act | Think | Branch | SkillCall | HarnessCall | Phi

Edge := {"from": NodeID, "to": NodeID, "kind": "sequential" | "branch" | "fallthrough"}
```

**Edge consistency rule:** The `edges` list and node-level references (`Branch.branches[].next`, implicit sequential fallthrough) must be kept in sync. The VM validates this on load: every node-level reference must have a corresponding edge, and every edge must have a valid source/target node. Mismatches are rejected before execution.

**Key structural insight:** `SkillCall` and `HarnessCall` are shaped identically — both are "reference an external artifact by ID, bind inputs, execute isolated, get a StepResult/HarnessResult back." That's the same node pattern (call-by-reference to a compiled/validated external unit) showing up at two points in the roadmap: Phase 1 harnesses, Phase 2 skills. Modeling them as thin type-tagged variants of one underlying `ReferenceCall` node means Phase 3's compiler passes handle one case, not two.

**What this changes concretely:**
- "Policy IR" is now just "a UPIR whose `harness_table` and `skill_table` are empty" — no separate schema, no separate VM code path.
- Compiler passes (Slice 12) walk `UPIR.nodes` uniformly; a Harness's internal code stays opaque to the compiler (it's validated Python, not IR), but the *node that calls it* is a first-class graph citizen, subject to dead-code elimination, Phi merging, etc., same as any `Think` or `Branch` node.
- Credit assignment (Slice 15)'s counterfactual ablation removes a `HarnessCall` node exactly the way it removes a `Branch` node — no special-casing.

**Note:** `skill_table` is defined in Slice 1 but stays empty until Phase 2 (Slice 7). Introducing the field early avoids a schema migration later.

**Compilation rules:**

| Source | Target | How |
|--------|--------|-----|
| Policy IR | UPIR | Direct — Policy IR is a UPIR with empty `harness_table`/`skill_table` |
| Harness IR | UPIR | Wraps `code` as a `HarnessCall` node referencing the harness by ID |
| Skill IR | UPIR subgraph | Extracted subgraph stored in `skill_table`, referenced via `SkillCall` |
| Trace IR | UPIR (reverse-inferred) | Slice 15's Credit Assignment Compiler produces a causal UPIR from execution traces |

---

## Step Execution Contract

```python
StepResult = {
    "next": NodeID | None,
    "state_delta": dict,
    "outputs": dict,
    "reward_signal": dict,
    "trace_event": dict
}
```

---

## Reward Schema (dual-mode)

```python
Reward = {
    "task_success": float,
    "efficiency": float,
    "safety": float,
    "skill_gain": float,
    "legality": float | None   # populated only for GameEnvironment
}
```

- **Thompson tree search** collapses this to a scalar heuristic for the bandit value function — see Unified Value Function below.
- **Population search** (alternative strategy) ranks candidates on the full normalized vector.

---

## Unified Value Function (Thompson search)

Thompson sampling needs a single scalar in `[0,1]` to update Beta-Bernoulli posteriors. Formalizing:

```python
def value(reward: Reward, env_kind: str, weights: ThompsonWeights) -> float:
    if env_kind == "game" and reward.legality is not None:
        v = weights.legality * reward.legality + weights.task_success * reward.task_success
    else:  # tool env, or game env before legality is known
        v = weights.task_success * reward.task_success + weights.efficiency * reward.efficiency
    return clamp(v, 0.0, 1.0)
```

```python
ThompsonWeights = {
    "legality": 0.5,       # only used when env_kind == "game"
    "task_success": 0.5,
    "efficiency": 0.0,     # only used as fallback when legality is unavailable
}
```

**Posterior update rule** — every branch in the search tree maintains `Beta(alpha, beta)`; each rollout's scalar value updates it directly, no separate binarization step:

```
On rollout outcome with value v:
    alpha_branch += v
    beta_branch  += (1 - v)

Branch selection:
    theta_i ~ Beta(alpha_i, beta_i)  for each candidate branch i
    expand branch with highest sampled theta_i
```

This is the one value function every part of Phase 1 shares — Slice 4 produces the `Reward` vector, Slice 5's Thompson search calls `value()` to update posteriors, and Slice 6's Critic uses the same scalar to judge whether a Refiner rewrite is actually an improvement.

---

## Guardrails

| # | Risk | Mitigation |
|---|------|------------|
| 1 | LLM returns invalid JSON | Pydantic validation + 3 retries in planner/optimizer |
| 2 | Tool hangs (infinite loop) | `subprocess.run(timeout=N)` on all tools |
| 3 | State key collisions | Namespaced: `state[node_id]` not `state[key]` |
| 4 | Filesystem escape | All paths through `/tmp/workspace`, `realpath()` check — applies equally to sandboxed Harness code execution |
| 5 | Harness code silently swallows failures | Generated Harness code must not contain `try`/`except` — forces failures to surface as explicit signals back into the Critic/Refiner loop (paper constraint) |
| 6 | Unbounded search cost | Hard cap on tree-search iterations / population generations per compile cycle (`max_search_iterations` in config) |
| 7 | Harness code violates its effect boundary (direct `environment.step()` calls, in-place state mutation) | Sandboxed exec with restricted builtins/globals enforcing the Harness Execution Contract; violations surface as a `raised` `HarnessResult`, never silently pass |

---

## Configuration

```python
DEFAULT_CONFIG = {
    "planner_model": "gpt-4o",
    "optimizer_model": "gpt-4o",
    "think_model": "gpt-4o-mini",
    "refiner_model": "gpt-4o",          # for Harness refinement loop
    "critic_model": "gpt-4o-mini",      # consolidates failure feedback

    "env_kind": "tool",                 # "tool" | "game" | "both"
    "search_strategy": "thompson_tree", # "thompson_tree" | "population" | "both"

    "population_size": 5,
    "elite_fraction": 0.4,

    "thompson_tree_max_depth": 6,
    "thompson_prior_alpha": 1.0,
    "thompson_prior_beta": 1.0,
    "thompson_weights": {"legality": 0.5, "task_success": 0.5, "efficiency": 0.0},
    "num_parallel_rollouts": 8,
    "max_failures_per_round": 5,        # bounded sample of failures fed to Critic

    "max_steps": 50,
    "max_episodes": 100,
    "tool_timeout": 10,
    "optimizer_retries": 3,
    "max_search_iterations": 20,        # Guardrail #6

    "compile_every_n_episodes": 10,
    "min_pattern_occurrences": 3,
    "skill_prune_success_threshold": 0.3,
    "workspace_root": "/tmp/workspace",
    "convergence_threshold": 0.8,
}
```

---

# Phase 1 — MVP (paper-grounded core)

### Slice 1 — Typed Agent VM + Environment Protocol (FOUNDATION)

**Goal:** Execute a single UPIR graph against both environment kinds with strict semantics.

**Build:**
- UPIR substrate (typed nodes + explicit edges + `harness_table` + `skill_table`) — see Single IR Substrate section
- Edge consistency validation on load (node-level references must match edge list)
- `Environment` protocol with ToolEnvironment and GameEnvironment implementations
- VM (step function based)
- StepResult contract enforced
- Deterministic transition logic (no probability yet)
- 2 tools for ToolEnvironment: `read_file`, `write_file`
- One TextArena-style GameEnvironment wrapper for `legal_actions`-based testing
- Random seed threaded through all execution (not global random)

**Done when:**
- VM is deterministic against both environment kinds
- StepResult contract enforced
- Trace fully reproducible given same seed, in both environment kinds

---

### Slice 2 — Sandbox + Environment Isolation

**Goal:** Make execution — including generated Harness code — safe and reproducible.

**Build:**
- `/tmp/workspace` sandbox
- Path validator (`os.path.realpath()` check)
- Subprocess timeouts
- Harness code executed under the same sandbox + timeout guardrails as tools
- `no_try_except` static check on generated Harness code before execution
- Enforce the Harness Execution Contract's effect boundary (restricted builtins/globals; no direct `environment.step()`, no in-place state mutation) — Guardrail #7

**Done when:**
- No filesystem escape possible
- All tool calls and Harness executions are bounded
- Harness code containing `try`/`except`, or violating the effect boundary, is rejected before execution

---

### Slice 3 — Trace IR System (execution observability)

**Goal:** Make execution — including per-rollout failures — fully observable.

**Build:**
Each node emits via StepResult.trace_event:
```json
{
    "node_id": "...",
    "inputs": {...},
    "outputs": {...},
    "cost": 0.1,
    "legal": true
}
```
`legal` populated only when running against GameEnvironment. `HarnessCall` nodes additionally emit the `HarnessResult` fields (`verdict`, `raised`, `cost`) into `trace_event`.

**Done when:**
- Trace is deterministically replayable
- Illegal-action events are distinguishable from generic failures in the trace
- A harness's `raised` exceptions are visible in the trace, not swallowed

---

### Slice 4 — Reward Engine (dual-mode signal layer)

**Goal:** Convert traces → structured reward vector, with a scalar fallback for bandit-style search.

**Build:**
- Success detection
- Efficiency penalty (step count)
- Safety scoring (basic rules)
- Legality tracking (GameEnvironment only)
- Reward normalization to the dual-mode Reward schema
- Expose the `value()` function (Unified Value Function section) for Thompson search consumption

**Done when:**
- Harnesses/policies are comparable across runs under both Thompson tree and population search
- `value()` output is stable and replayable given the same trace

---

### Slice 5 — Thompson Tree Search Engine (primary search strategy)

**Goal:** Search over harnesses/policies using Thompson-sampling tree search (paper's core method).

**Build:**
- Maintain a tree of code hypotheses (Harness or Policy)
- Roll out each candidate across `num_parallel_rollouts` environment instances
- Sample up to `max_failures_per_round` failures per rollout batch
- Compute `value(reward, env_kind, thompson_weights)` per rollout outcome
- Update each branch's `Beta(alpha, beta)` posterior per the update rule in Unified Value Function
- Thompson sampling over the tree picks which branch to expand next, balancing exploration/exploitation
- Terminate a branch when `convergence_threshold` is met or `max_search_iterations` is exhausted

**Done when:**
- Converged harnesses consistently outperform unguided baseline
- A `policy`-kind Harness can reach `convergence_threshold` and be compiled out (LLM bypassed)

**Note:** Population search strategy (alternative) can be added as a second slice after this. Both strategies can also run independently feeding the same elite pool via `search_strategy: "both"`.

---

### Slice 6 — Refiner + Critic Loop (LLM-guided harness rewrite)

**Goal:** Introduce semantic improvement via LLM-driven code refinement, matching the paper's Refiner/Critic structure.

**Build:**
- **Critic**: consolidates sampled failures (from Slice 5's rollouts) into structured error-type feedback — not raw stack traces, but categorized causes, including any `HarnessResult.raised` events

```python
CriticOutput := {
    "failure_clusters": List[dict],        # grouped failure modes with root causes
    "legality_violations": List[dict],     # illegal actions detected (GameEnvironment only)
    "inefficiency_patterns": List[dict],   # redundant or suboptimal execution paths
}
```

- **Refiner** (LLM): input = current Harness/Policy IR + trace + Critic's consolidated feedback + reward; output = rewritten IR, validated via Pydantic + `optimizer_retries`
- Enforce `no_try_except` and the effect-boundary check on all Refiner output before it re-enters the sandbox

**Done when:**
- Refiner-driven rewrites improve legality accuracy (GameEnvironment) or task success (ToolEnvironment) vs. the previous round
- A `policy`-kind Harness can reach `convergence_threshold` and be compiled out

---

# Phase 2 — Extensions (speculative — not paper-validated, named as future work by the paper)

### Slice 7 — Skill Extraction
Detect repeated subgraphs in traces, compress into a `skill_table` entry (a nested UPIR). *(Paper explicitly lists a reusable-harness library as unexplored future work — this slice is one concrete way to build toward that, not something the paper demonstrates.)*

**Done when:** `SkillExtractor` detects repeated node-id subsequences in traces and extracts them as nested UPIR skills stored in `skill_table`. Configurable `min_occurrences` threshold. 4 tests passing.

### Slice 8 — Skill Execution (composition layer)
`SkillCall` node, nested VM execution, skill registry lookup — structurally the same `ReferenceCall` pattern as `HarnessCall` (see UPIR).

### Slice 9 — Skill Pruning System
Usage + success-rate tracking; delete skills with `usage == 0` or `success_rate < skill_prune_success_threshold`.

### Slice 10 — Persistent Memory Layer
Episodic trace store to disk, skill persistence, global stats, reload on startup.

**Phase 2 done when:** repeated workflows become reusable, self-pruning skills that survive restarts.

---

# Phase 3 — Compiler Theory Layer (independent research direction — no paper support)

### Slice 11 — Probabilistic Execution Layer (PES upgrade)
Branch nodes support probability sampling; seed-controlled stochastic replay.

### Slice 12 — Compiler Pass System
Dead branch elimination, constant condition folding, unreachable node pruning, skill extraction pass — all operating uniformly over `UPIR.nodes` (see UPIR).

### Slice 13 — Cost-Aware Scheduler
Cost model per node; reorder execution graph; prefer a compiled `policy`-kind Harness over a `Think`+LLM node wherever one is available and above threshold.

### Slice 14 — Phi Nodes (SSA-style merging)
Merge divergent execution paths; unify state variables from branches.

### Slice 15 — Credit Assignment Compiler
Trace → causal graph; counterfactual ablation scoring (removes any `UPIRNode`, including `HarnessCall`/`SkillCall`, uniformly); node-level failure attribution.

### Slice 16 — Full Agent Compiler Loop
```
compile → execute → trace → score → attribute → rewrite → repeat
```

---

## Summary Table

| Slice | Delivers | Phase | Paper support |
|---|---|---|---|
| 1 | Typed VM + pluggable Environment (UPIR substrate) | 1 (MVP) | Partial — VM/IR formalism is this project's own; Environment split reflects paper's game-env focus |
| 2 | Safe sandbox, incl. Harness code + effect-boundary enforcement | 1 (MVP) | Yes — no-try-except constraint is direct from paper |
| 3 | Deterministic trace IR w/ legality flag + HarnessResult | 1 (MVP) | Partial |
| 4 | Dual-mode reward (vector + scalar via `value()`) | 1 (MVP) | Yes — scalar heuristic mirrors paper's search objective |
| 5 | Thompson tree search | 1 (MVP) | Yes — Thompson-sampling tree search is the paper's core method |
| 6 | Refiner + Critic loop, harness-as-policy | 1 (MVP) | Yes — this is the paper's central contribution |
| 7 | Skill extraction | 2 (Extension) | No — named as future work only |
| 8 | Skill execution | 2 (Extension) | No |
| 9 | Skill pruning | 2 (Extension) | No |
| 10 | Persistent memory | 2 (Extension) | No |
| 11 | Probabilistic transitions | 3 (Research) | No |
| 12 | Compiler passes (UPIR-wide) | 3 (Research) | No |
| 13 | Cost-aware scheduling | 3 (Research) | Conceptually adjacent — paper's harness-as-policy already achieves the cost win this slice generalizes |
| 14 | Phi nodes (SSA) | 3 (Research) | No |
| 15 | Counterfactual credit assignment (UPIR-wide) | 3 (Research) | No |
| 16 | Full loop | 3 (Research) | No |

## Dependency Graph

```
1 → 2 → 3 → 4 → 5 → 6 ─────────────────────────────┐   Phase 1 (MVP)
                                                     │
3 → 7 → 8 → 9 ──────────────────────────────────────┤   Phase 2 (Extensions)
4 → 10 ─────────────────────────────────────────────┤
                                                     │
1 → 11 → 12 → 13 ───────────────────────────────────┤   Phase 3 (Research)
11 → 14 → 15 ───────────────────────────────────────┤
5,6,9,10,13,15 → 16 ────────────────────────────────┘
```

---

## Project Structure

```
tracedge/
├── pyproject.toml
├── .gitignore
├── BLUEPRINT.md
├── PLAN.md
├── src/
│   └── tracedge/
│       ├── __init__.py
│       ├── config.py                  # DEFAULT_CONFIG + Pydantic settings
│       │
│       ├── ir/                        # UPIR + Harness IR types
│       │   ├── __init__.py
│       │   ├── upir.py                # UPIR, UPIRNode, Edge
│       │   ├── harness.py             # Harness, HarnessSignature, HarnessResult
│       │   ├── nodes.py               # Observe, Act, Think, Branch, SkillCall, HarnessCall, Phi
│       │   └── validator.py           # Edge consistency, schema validation
│       │
│       ├── runtime/                   # VM execution engine
│       │   ├── __init__.py
│       │   ├── vm.py                  # PES interpreter — runs UPIR step-by-step
│       │   ├── state.py               # Namespaced state (state[node_id])
│       │   ├── step.py                # StepResult, StepExecutionContract
│       │   └── seed.py                # Deterministic seed management
│       │
│       ├── environment/               # Pluggable env protocol
│       │   ├── __init__.py
│       │   ├── protocol.py            # Environment Protocol (ABC)
│       │   ├── tool_env.py            # ToolEnvironment (read_file, write_file)
│       │   └── game_env.py            # GameEnvironment (TextArena-style)
│       │
│       ├── sandbox/                   # Safety + isolation
│       │   ├── __init__.py
│       │   ├── workspace.py           # /tmp/workspace lockdown
│       │   ├── harness_runner.py      # Sandboxed harness code execution
│       │   └── guardrails.py          # no_try_except, effect boundary, path validation
│       │
│       ├── trace/                     # Trace IR system
│       │   ├── __init__.py
│       │   ├── trace_ir.py            # TraceEvent, TraceLog
│       │   └── emitter.py             # Per-node trace emission
│       │
│       ├── reward/                    # Reward engine
│       │   ├── __init__.py
│       │   ├── reward.py              # Reward schema (dual-mode)
│       │   ├── scorer.py              # Success, efficiency, safety, legality
│       │   └── value.py               # Unified value function for Thompson
│       │
│       ├── search/                    # Thompson tree search
│       │   ├── __init__.py
│       │   ├── thompson.py            # Tree structure, Beta posteriors, selection
│       │   └── rollout.py             # Parallel rollout execution
│       │
│       ├── intelligence/              # LLM integration (offline)
│       │   ├── __init__.py
│       │   ├── llm_client.py          # OpenAI/Ollama wrapper
│       │   ├── critic.py              # Failure clustering → CriticOutput
│       │   ├── refiner.py             # LLM-driven UPIR rewrite
│       │   └── planner.py             # Initial UPIR generation (Phase 2)
│       │
│       ├── skills/                    # Skill system (Phase 2)
│       │   ├── __init__.py
│       │   ├── registry.py            # Skill storage + lookup
│       │   ├── extractor.py           # Pattern detection → skill compilation
│       │   └── pruner.py              # Usage/success tracking + cleanup
│       │
│       └── memory/                    # Persistence (Phase 2)
│           ├── __init__.py
│           └── store.py               # Episodic traces, skill stats, global stats
│
├── tests/
│   ├── conftest.py                    # Shared fixtures (llm_client, tmp_workspace, sample_upir)
│   ├── ir/
│   │   ├── test_upir.py
│   │   ├── test_harness.py
│   │   ├── test_nodes.py
│   │   └── test_validator.py
│   ├── runtime/
│   │   ├── test_vm.py
│   │   ├── test_state.py
│   │   └── test_seed.py
│   ├── environment/
│   │   ├── test_tool_env.py
│   │   └── test_game_env.py
│   ├── sandbox/
│   │   ├── test_workspace.py
│   │   ├── test_harness_runner.py
│   │   └── test_guardrails.py
│   ├── trace/
│   │   └── test_trace_ir.py
│   ├── reward/
│   │   ├── test_scorer.py
│   │   └── test_value.py
│   ├── search/
│   │   ├── test_thompson.py
│   │   └── test_rollout.py
│   ├── intelligence/
│   │   ├── test_llm_client.py
│   │   ├── test_critic.py
│   │   └── test_refiner.py
│   └── integration/
│       └── test_end_to_end.py
│
└── examples/
    ├── tic_tac_toe.py                # GameEnvironment demo
    └── code_task.py                  # ToolEnvironment demo
```

### Slice → File mapping

| Slice | New/Modified files |
|-------|-------------------|
| 1 | `ir/`, `runtime/`, `environment/`, `config.py` |
| 2 | `sandbox/` |
| 3 | `trace/` |
| 4 | `reward/` |
| 5 | `search/` |
| 6 | `intelligence/` (critic, refiner) |
| 7 | `skills/extractor.py` |
| 8 | `skills/registry.py` + `ir/nodes.py` (SkillCall) |
| 9 | `skills/pruner.py` |
| 10 | `memory/` |
| 11 | `runtime/vm.py` (add stochastic branching) |
| 12 | New `compiler/` dir |
| 13 | New `compiler/scheduler.py` |
| 14 | `ir/nodes.py` (add Phi) + `runtime/vm.py` |
| 15 | New `compiler/attribution.py` |
| 16 | `main.py` (orchestration loop) |

---

## Testing Strategy

### Framework
- **pytest** as the test runner
- **ruff** for linting (already installed)
- **mypy** for type checking (already installed)

### LLM in tests
- All tests hit **local Ollama** (`gemma4:12b-mlx`) — no mocking
- Tests are slower but validate real LLM behavior
- A `conftest.py` fixture provides the shared LLM client

```python
# tests/conftest.py
import pytest
from openai import OpenAI

@pytest.fixture
def llm_client():
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

### Test structure

```
tests/
├── conftest.py                    # Shared fixtures
├── ir/
│   ├── test_upir.py               # UPIR construction, edge consistency
│   ├── test_harness.py            # Harness IR, signature, guard_policy
│   ├── test_nodes.py              # Node type creation, field validation
│   └── test_validator.py          # Schema validation, edge-node sync
├── runtime/
│   ├── test_vm.py                 # End-to-end UPIR execution, StepResult
│   ├── test_state.py              # Namespaced state, no collisions
│   └── test_seed.py               # Deterministic replay
├── environment/
│   ├── test_tool_env.py           # read_file/write_file, success detection
│   └── test_game_env.py           # legal_actions, illegal-move tracking
├── sandbox/
│   ├── test_workspace.py          # Path traversal prevention
│   ├── test_harness_runner.py     # Harness execution, effect boundary
│   └── test_guardrails.py         # no_try_except, timeout enforcement
├── trace/
│   └── test_trace_ir.py           # Trace emission, replay, legality flag
├── reward/
│   ├── test_scorer.py             # Reward vector computation
│   └── test_value.py              # Scalar value function
├── search/
│   ├── test_thompson.py           # Beta posteriors, selection, convergence
│   └── test_rollout.py            # Parallel rollout execution
├── intelligence/
│   ├── test_llm_client.py         # Ollama connection, response parsing
│   ├── test_critic.py             # Failure clustering
│   └── test_refiner.py            # LLM rewrites UPIR
└── integration/
    └── test_end_to_end.py         # Full loop test
```

### Per-slice test coverage

#### Slice 1 — UPIR VM + Environment Protocol

| Test | What it validates | File |
|------|-------------------|------|
| `test_upir_construction` | UPIR with nodes, edges, empty harness_table/skill_table | `tests/ir/test_upir.py` |
| `test_upir_edge_consistency_valid` | Edges match node-level references (Branch.next, sequential fallthrough) | `tests/ir/test_upir.py` |
| `test_upir_edge_consistency_mismatch_rejected` | Edge points to nonexistent node → raises on load | `tests/ir/test_upir.py` |
| `test_upir_node_types` | All 6 node types (Observe/Act/Think/Branch/SkillCall/HarnessCall) constructable | `tests/ir/test_nodes.py` |
| `test_step_result_contract` | StepResult has required fields: next, state_delta, outputs, reward_signal, trace_event | `tests/runtime/test_step.py` |
| `test_vm_executes_observe_node` | Observe node calls env.observe(), stores result in state | `tests/runtime/test_vm.py` |
| `test_vm_executes_act_node` | Act node calls tool, stores result in state | `tests/runtime/test_vm.py` |
| `test_vm_executes_think_node` | Think node calls LLM, stores result in state | `tests/runtime/test_vm.py` |
| `test_vm_executes_branch_node` | Branch node evaluates condition, follows correct path | `tests/runtime/test_vm.py` |
| `test_vm_terminate_on_end` | VM stops when current_node is None | `tests/runtime/test_vm.py` |
| `test_vm_max_steps_limit` | VM stops after max_steps iterations | `tests/runtime/test_vm.py` |
| `test_vm_deterministic_replay` | Same UPIR + same seed → identical trace | `tests/runtime/test_vm.py` |
| `test_vm_deterministic_replay_different_seed` | Same UPIR + different seed → different trace | `tests/runtime/test_vm.py` |
| `test_state_namespacing` | State scoped per node_id, no key collisions | `tests/runtime/test_state.py` |
| `test_state_flatten` | State.flatten() merges all node outputs for condition evaluation | `tests/runtime/test_state.py` |
| `test_seed_threading` | Seed passed through all execution, not sampled from global random | `tests/runtime/test_seed.py` |
| `test_tool_env_observe` | ToolEnvironment.observe() returns file contents | `tests/environment/test_tool_env.py` |
| `test_tool_env_step` | ToolEnvironment.step() executes tool, returns new state | `tests/environment/test_tool_env.py` |
| `test_tool_env_legal_actions_none` | ToolEnvironment.legal_actions() returns None | `tests/environment/test_tool_env.py` |
| `test_tool_env_success_detection` | ToolEnvironment detects task completion | `tests/environment/test_tool_env.py` |
| `test_game_env_observe` | GameEnvironment.observe() returns game state | `tests/environment/test_game_env.py` |
| `test_game_env_legal_actions_list` | GameEnvironment.legal_actions() returns list of legal moves | `tests/environment/test_game_env.py` |
| `test_game_env_illegal_move_rejected` | GameEnvironment.step() rejects illegal moves | `tests/environment/test_game_env.py` |
| `test_game_env_illegal_move_tracking` | Illegal moves tracked in reward/info | `tests/environment/test_game_env.py` |
| `test_game_env_sparse_reward` | Reward is win/loss/draw | `tests/environment/test_game_env.py` |

#### Slice 2 — Sandbox + Environment Isolation

| Test | What it validates | File |
|------|-------------------|------|
| `test_path_traversal_blocked` | Attempting to read/write outside /tmp/workspace → rejected | `tests/sandbox/test_workspace.py` |
| `test_symlink_escape_blocked` | Symlink pointing outside workspace → rejected via realpath check | `tests/sandbox/test_workspace.py` |
| `test_path_within_workspace_allowed` | Reading/writing within /tmp/workspace → succeeds | `tests/sandbox/test_workspace.py` |
| `test_tool_timeout_enforced` | Tool that sleeps longer than timeout → returns ERROR: Timeout | `tests/sandbox/test_workspace.py` |
| `test_harness_no_try_except_rejected` | Harness code containing try/except → static check rejects before execution | `tests/sandbox/test_guardrails.py` |
| `test_harness_no_except_rejected` | Harness code containing bare except → rejected | `tests/sandbox/test_guardrails.py` |
| `test_harness_effect_boundary_no_step` | Harness code calling environment.step() → rejected at runtime | `tests/sandbox/test_guardrails.py` |
| `test_harness_effect_boundary_no_state_mutation` | Harness code mutating state in place → rejected at runtime | `tests/sandbox/test_guardrails.py` |
| `test_harness_effect_boundary_no_filesystem` | Harness code doing file I/O → rejected (filesystem: false in effects) | `tests/sandbox/test_guardrails.py` |
| `test_harness_effect_boundary_no_network` | Harness code doing network I/O → rejected (network: false in effects) | `tests/sandbox/test_guardrails.py` |
| `test_harness_timeout_enforced` | Harness code exceeding max_runtime_ms → killed, returns raised | `tests/sandbox/test_harness_runner.py` |
| `test_harness_pure_computation_allowed` | Harness code doing pure math → executes successfully | `tests/sandbox/test_harness_runner.py` |
| `test_harness_exception_propagates` | Harness code raising exception → VM handles per kind (False/empty/LLM fallback) | `tests/sandbox/test_harness_runner.py` |

#### Slice 3 — Trace IR System

| Test | What it validates | File |
|------|-------------------|------|
| `test_trace_event_emitted_per_node` | Every node execution produces a trace_event | `tests/trace/test_trace_ir.py` |
| `test_trace_event_fields` | trace_event has node_id, inputs, outputs, cost | `tests/trace/test_trace_ir.py` |
| `test_trace_legal_flag_game_env` | trace_event.legal is True for legal moves in GameEnvironment | `tests/trace/test_trace_ir.py` |
| `test_trace_legal_flag_illegal` | trace_event.legal is False for illegal moves in GameEnvironment | `tests/trace/test_trace_ir.py` |
| `test_trace_legal_flag_none_tool_env` | trace_event.legal is None for ToolEnvironment | `tests/trace/test_trace_ir.py` |
| `test_trace_harness_result_fields` | HarnessCall nodes emit verdict, raised, cost in trace_event | `tests/trace/test_trace_ir.py` |
| `test_trace_harness_raised_visible` | Harness exception appears in trace, not swallowed | `tests/trace/test_trace_ir.py` |
| `test_trace_deterministic_replay` | Same execution → identical trace | `tests/trace/test_trace_ir.py` |
| `test_trace_cost_accumulated` | trace_event.cost values are consistent | `tests/trace/test_trace_ir.py` |

#### Slice 4 — Reward Engine

| Test | What it validates | File |
|------|-------------------|------|
| `test_reward_vector_schema` | Reward has task_success, efficiency, safety, skill_gain, legality | `tests/reward/test_scorer.py` |
| `test_reward_success_detection` | Successful task completion → task_success=1.0 | `tests/reward/test_scorer.py` |
| `test_reward_efficiency_penalty` | More steps → lower efficiency | `tests/reward/test_scorer.py` |
| `test_reward_safety_score` | Unsafe actions → safety < 1.0 | `tests/reward/test_scorer.py` |
| `test_reward_legality_game_env` | GameEnvironment rewards legality | `tests/reward/test_scorer.py` |
| `test_reward_legality_none_tool_env` | ToolEnvironment → legality is None | `tests/reward/test_scorer.py` |
| `test_value_function_game_env` | value() uses legality + task_success weights | `tests/reward/test_value.py` |
| `test_value_function_tool_env` | value() uses task_success + efficiency weights | `tests/reward/test_value.py` |
| `test_value_clamped_0_1` | value() output always in [0, 1] | `tests/reward/test_value.py` |
| `test_value_deterministic` | Same reward + same weights → same value | `tests/reward/test_value.py` |
| `test_value_legality_none_fallback` | When legality is None, falls back to efficiency | `tests/reward/test_value.py` |

#### Slice 5 — Thompson Tree Search

| Test | What it validates | File |
|------|-------------------|------|
| `test_beta_posterior_initialization` | New branch starts with prior alpha/beta from config | `tests/search/test_thompson.py` |
| `test_beta_posterior_update_success` | High value rollout → alpha increases | `tests/search/test_thompson.py` |
| `test_beta_posterior_update_failure` | Low value rollout → beta increases | `tests/search/test_thompson.py` |
| `test_branch_selection_sampling` | Thompson sampling picks branch with highest sampled theta | `tests/search/test_thompson.py` |
| `test_branch_selection_exploration` | Low-data branches occasionally selected (exploration) | `tests/search/test_thompson.py` |
| `test_convergence_detection` | Branch with value >= convergence_threshold → terminated | `tests/search/test_thompson.py` |
| `test_max_iterations_exceeded` | Search stops after max_search_iterations | `tests/search/test_thompson.py` |
| `test_rollout_execution` | Rollout executes UPIR, produces trace + reward | `tests/search/test_rollout.py` |
| `test_parallel_rollouts` | Multiple rollouts run independently | `tests/search/test_rollout.py` |
| `test_failures_bounded` | max_failures_per_round limits failure samples | `tests/search/test_rollout.py` |

#### Slice 6 — Refiner + Critic Loop

| Test | What it validates | File |
|------|-------------------|------|
| `test_critic_clusters_failures` | Critic groups failures into failure_clusters | `tests/intelligence/test_critic.py` |
| `test_critic_identifies_legality_violations` | Critic extracts legality violations from GameEnvironment traces | `tests/intelligence/test_critic.py` |
| `test_critic_identifies_inefficiency` | Critic identifies redundant execution paths | `tests/intelligence/test_critic.py` |
| `test_critic_output_schema` | CriticOutput has failure_clusters, legality_violations, inefficiency_patterns | `tests/intelligence/test_critic.py` |
| `test_refiner_produces_valid_upir` | Refiner output passes Pydantic validation | `tests/intelligence/test_refiner.py` |
| `test_refiner_output_no_try_except` | Refiner-generated harness code has no try/except | `tests/intelligence/test_refiner.py` |
| `test_refiner_output_effect_boundary` | Refiner output respects effect boundary | `tests/intelligence/test_refiner.py` |
| `test_refiner_respects_optimizer_retries` | Refiner retries up to optimizer_retries times on invalid output | `tests/intelligence/test_refiner.py` |
| `test_refiner_improves_success_rate` | Refiner rewrites improve task success over previous round | `tests/intelligence/test_refiner.py` |

#### Slice 7 — Skill Extraction

| Test | What it validates | File |
|------|-------------------|------|
| `test_detect_repeated_subgraphs` | Extractor finds repeated trace patterns | `tests/intelligence/test_extractor.py` |
| `test_extract_skill_from_pattern` | Repeated pattern → Skill IR (nested UPIR) | `tests/intelligence/test_extractor.py` |
| `test_min_pattern_occurrences` | Pattern must appear >= min_pattern_occurrences to extract | `tests/intelligence/test_extractor.py` |
| `test_extracted_skill_stored` | Extracted skill added to skill_table | `tests/intelligence/test_extractor.py` |

#### Slice 8 — Skill Execution

| Test | What it validates | File |
|------|-------------------|------|
| `test_skill_call_node_executes` | SkillCall node runs nested UPIR | `tests/intelligence/test_skill_exec.py` |
| `test_skill_registry_lookup` | SkillCall resolves skill by ID from skill_table | `tests/intelligence/test_skill_exec.py` |
| `test_skill_nested_state` | Nested UPIR has its own namespaced state | `tests/intelligence/test_skill_exec.py` |

#### Slice 9 — Skill Pruning

| Test | What it validates | File |
|------|-------------------|------|
| `test_prune_zero_usage` | Skills with usage == 0 are deleted | `tests/intelligence/test_pruner.py` |
| `test_prune_low_success_rate` | Skills with success_rate < threshold are deleted | `tests/intelligence/test_pruner.py` |
| `test_prune_preserves_good_skills` | High-usage, high-success skills are kept | `tests/intelligence/test_pruner.py` |

#### Slice 10 — Persistent Memory

| Test | What it validates | File |
|------|-------------------|------|
| `test_store_episode` | Episode traces written to disk | `tests/intelligence/test_store.py` |
| `test_store_skill_stats` | Skill usage/success persisted | `tests/intelligence/test_store.py` |
| `test_store_global_stats` | Global success rate persisted | `tests/intelligence/test_store.py` |
| `test_reload_on_startup` | Data survives process restart | `tests/intelligence/test_store.py` |

#### Slice 11 — Probabilistic Execution

| Test | What it validates | File |
|------|-------------------|------|
| `test_branch_sampling_probability` | Branch node samples from distribution | `tests/runtime/test_vm.py` |
| `test_stochastic_replay_same_seed` | Same seed → same stochastic trace | `tests/runtime/test_vm.py` |
| `test_stochastic_replay_different_seed` | Different seed → different trace | `tests/runtime/test_vm.py` |

#### Slice 12 — Compiler Passes

| Test | What it validates | File |
|------|-------------------|------|
| `test_dead_branch_elimination` | Unreachable nodes removed | `tests/compiler/test_passes.py` |
| `test_constant_folding` | Always-true branches inlined | `tests/compiler/test_passes.py` |
| `test_unreachable_node_pruning` | Nodes with no incoming edges removed | `tests/compiler/test_passes.py` |
| `test_pass_preserves_behavior` | Optimized UPIR produces same execution result | `tests/compiler/test_passes.py` |

#### Slice 13 — Cost-Aware Scheduler

| Test | What it validates | File |
|------|-------------------|------|
| `test_cost_model_per_node` | Each node has latency/llm_calls cost | `tests/compiler/test_scheduler.py` |
| `test_reorder_reduces_cost` | Scheduler reorders nodes to reduce total cost | `tests/compiler/test_scheduler.py` |
| `test_prefer_compiled_harness_over_think` | Policy-kind harness preferred over Think+LLM node | `tests/compiler/test_scheduler.py` |
| `test_behavior_preserved` | Reordered UPIR produces same result | `tests/compiler/test_scheduler.py` |

#### Slice 14 — Phi Nodes

| Test | What it validates | File |
|------|-------------------|------|
| `test_phi_merges_two_paths` | Phi node receives outputs from both branches | `tests/runtime/test_vm.py` |
| `test_phi_state_unification` | Phi node unifies state variables from branches | `tests/runtime/test_vm.py` |
| `test_phi_deterministic` | Same execution path → same merged state | `tests/runtime/test_vm.py` |

#### Slice 15 — Credit Assignment Compiler

| Test | What it validates | File |
|------|-------------------|------|
| `test_causal_trace_graph` | Trace produces causal graph linking nodes to outcomes | `tests/compiler/test_attribution.py` |
| `test_counterfactual_ablation` | Removing a node and re-running measures its impact | `tests/compiler/test_attribution.py` |
| `test_node_level_attribution` | Each node gets a reward attribution score | `tests/compiler/test_attribution.py` |
| `test_identifies_failure_cause` | System can identify which node caused failure | `tests/compiler/test_attribution.py` |

#### Slice 16 — Full Loop

| Test | What it validates | File |
|------|-------------------|------|
| `test_end_to_end_loop` | Full loop: generate → execute → trace → score → refine → repeat | `tests/integration/test_end_to_end.py` |
| `test_loop_convergence` | System improves over multiple iterations | `tests/integration/test_end_to_end.py` |
| `test_loop_both_env_types` | Loop works with both ToolEnvironment and GameEnvironment | `tests/integration/test_end_to_end.py` |
| `test_harness_compilation` | Policy-kind harness reaches convergence and is compiled out | `tests/integration/test_end_to_end.py` |

### pyproject.toml test config

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-config --strict-markers"

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

### Test naming convention
- `test_<thing>_<scenario>` — e.g., `test_vm_deterministic_replay`, `test_harness_rejects_try_except`

### Coverage reporting
```bash
pytest --cov=tracedge --cov-report=term-missing
```

---

## TDD Strategy

### Workflow per slice

1. **Red:** Write a failing test that defines expected behavior
2. **Green:** Write minimum code to make the test pass
3. **Refactor:** Clean up while keeping tests green

### Test doubles

**`tests/conftest.py` fixtures:**

```python
import pytest
from openai import OpenAI

class FakeLLMClient:
    """Returns canned responses for Slices 1-5. Real LLM tests in Slice 6+."""
    def __init__(self, response: str = '{"action": "default_action"}'):
        self._response = response
    def generate(self, prompt: str) -> str:
        return self._response

@pytest.fixture
def fake_llm():
    return FakeLLMClient()

@pytest.fixture
def llm_client():
    """Real Ollama client for Slice 6+ tests."""
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

@pytest.fixture
def tmp_workspace(tmp_path):
    """Isolated workspace for sandbox tests."""
    return tmp_path / "workspace"

@pytest.fixture
def sample_upir():
    """Minimal UPIR for VM tests — observe → act → done."""
    # Constructed in tests/conftest.py with real UPIR types
    ...
```

### TDD test order within slices

#### Slice 1 — exact build order

| Step | Test file | Test first | Then implement |
|------|-----------|-----------|----------------|
| 1a | `tests/ir/test_upir.py` | `test_upir_construction` | `ir/upir.py` |
| 1b | `tests/ir/test_nodes.py` | `test_upir_node_types` | `ir/nodes.py` |
| 1c | `tests/ir/test_validator.py` | `test_upir_edge_consistency_valid` | `ir/validator.py` |
| 1d | `tests/runtime/test_step.py` | `test_step_result_contract` | `runtime/step.py` |
| 1e | `tests/runtime/test_state.py` | `test_state_namespacing` | `runtime/state.py` |
| 1f | `tests/runtime/test_seed.py` | `test_seed_threading` | `runtime/seed.py` |
| 1g | `tests/environment/test_tool_env.py` | `test_tool_env_observe` | `environment/tool_env.py` |
| 1h | `tests/runtime/test_vm.py` | `test_vm_executes_observe_node` | `runtime/vm.py` (Observe only) |
| 1i | `tests/runtime/test_vm.py` | `test_vm_executes_act_node` | `runtime/vm.py` (add Act) |
| 1j | `tests/runtime/test_vm.py` | `test_vm_executes_think_node` | `runtime/vm.py` (add Think with FakeLLM) |
| 1k | `tests/runtime/test_vm.py` | `test_vm_executes_branch_node` | `runtime/vm.py` (add Branch) |
| 1l | `tests/runtime/test_vm.py` | `test_vm_deterministic_replay` | `runtime/vm.py` (verify seed threading) |

#### Slices 2-5 — sequential TDD

Each slice: write all tests first (using FakeLLM), then implement until green.

#### Slice 6+ — Ollama required

Mark tests to skip if Ollama is not running:

```python
import pytest
import httpx

def ollama_available() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except httpx.ConnectError:
        return False

@pytest.mark.skipif(not ollama_available(), reason="Ollama not running")
def test_refiner_produces_valid_upir(llm_client):
    ...
```

### Cross-slice test dependencies

| Slice | Depends on (must be green first) |
|-------|--------------------------------|
| 1 | None |
| 2 | 1 (VM exists) |
| 3 | 1 (VM exists) |
| 4 | None (pure functions) |
| 5 | 1, 4 (VM + Reward) |
| 6 | 1, 3, 4 (VM + Trace + Reward) |
| 7-10 | 1, 3 (VM + Trace) |
| 11-16 | 1, 3, 4 (VM + Trace + Reward) |

### Integration tests

`tests/integration/test_end_to_end.py` is written **last**, after all unit tests pass. It validates the full loop across all components.

---

## SCM Strategy

### Git initialization

```bash
git init
git add .
git commit -m "Initial commit: PLAN.md + BLUEPRINT.md"
```

### Branching strategy

**Branch per slice:**

```
main
├── slice/1-ir-types
├── slice/1-vm
├── slice/1-environment
├── slice/1-vm-full
├── slice/2-sandbox
├── slice/3-trace
├── slice/4-reward
├── slice/5-thompson
├── slice/6-refiner
├── slice/7-skill-extraction
├── slice/8-skill-execution
├── slice/9-skill-pruning
├── slice/10-memory
├── slice/11-probabilistic
├── slice/12-compiler-passes
├── slice/13-cost-scheduler
├── slice/14-phi-nodes
├── slice/15-credit-assignment
└── slice/16-full-loop
```

**Merge rule:** Branch merges to main only when all tests in that slice are green. No partial merges.

### Commit convention

**Two commits per TDD cycle:**

```
<type>(<scope>): <description>
```

Types:
- `test(scope): add failing tests for X` — Red phase
- `feat(scope): implement X to pass tests` — Green phase
- `refactor(scope): clean up X` — Refactor phase

**Examples:**

```
test(ir): add UPIR construction and validation tests
feat(ir): implement UPIR Pydantic models
test(runtime): add VM observe node tests
feat(runtime): implement VM with Observe node support
refactor(runtime): clean up state namespacing
```

**Scope:** `ir`, `runtime`, `environment`, `sandbox`, `trace`, `reward`, `search`, `intelligence`, `skills`, `memory`, `compiler`

### Pre-commit hooks

Add `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]
```

Install hooks:
```bash
pip install pre-commit
pre-commit install
```

### Commit checklist

Before each commit:
- [ ] Tests pass: `pytest tests/`
- [ ] Lint clean: `ruff check src/ tests/`
- [ ] Types clean: `mypy src/`
- [ ] No secrets/keys in code

### Tagging

Tag completed slices:
```bash
git tag -a v0.1-slice1 -m "Slice 1: UPIR VM + Environment Protocol"
git tag -a v0.2-slice2 -m "Slice 2: Sandbox + Safety"
...
```

---

## Release Checklist (updated 2026-07-08 — GitHub-only distribution)

All build phases are implemented and merged (PRs #16–#23). **Decision
2026-07-08: PyPI is deferred — distribution is via GitHub only** (git-URL
installs + wheels attached to releases by `.github/workflows/publish.yml`).
Accepted risk, revisit post-launch: the free PyPI name `tracedge` is
unprotected — anyone can register it, and `pip install tracedge` would then
install *their* package. If launch gets traction, claiming the name becomes
urgent.

Note: the v0.2.0 release exists but has no artifacts (its publish run used the
old broken PyPI workflow). The next release picks up the artifact workflow.

- [ ] **1. Cut v0.2.1** from up-to-date `main` (after this change is merged):
      `git tag v0.2.1 && git push origin v0.2.1`, then create the GitHub
      release from that tag (API: POST /repos/sayedtenkanen/tracedge/releases,
      `generate_release_notes: true`). The artifact workflow triggers on
      *release published* — a tag alone does nothing. Verify the run attaches
      the sdist + wheel to the release.
- [ ] **2. Verify the install** from a clean venv:
      `python3 -m venv /tmp/t && /tmp/t/bin/pip install "git+https://github.com/sayedtenkanen/tracedge.git@v0.2.1" && /tmp/t/bin/tracedge --version && /tmp/t/bin/tracedge --demo`
- [ ] **3. Sync docs to v0.2.1**: README pinned-install line currently says
      `@v0.2.0` — bump to the released tag. LAUNCH_CONTENT.md install lines
      already say `@v0.2.1`; confirm they match the actual released tag.
- [ ] **4. Launch** — get user sign-off on `LAUNCH_CONTENT.md` copy (it must
      still match `BENCHMARKS.md` claims exactly), then post the Show HN and
      X thread, and follow the `MARKETING.md` content calendar.
- [ ] **5. Remove this section** once step 2 passes and step 4 is posted.

### Guardrails that still apply

- Do not post launch content before step 2 passes — the exact install command
  in the copy must work before it appears publicly.
- Any claim published externally must match the committed `BENCHMARKS.md`
  (honest scope: same-task replay, "verified cache" framing — no
  generalization claims; that is explicitly not yet measured).

### Post-launch (parked, do not build now)

PyPI publication (deferred 2026-07-08 — see name-squatting risk above; the
old trusted-publishing workflow is in git history at tag v0.2.0 if needed);
hosted skill registry / trace observability; enterprise constraint-harness
product; LangChain/CrewAI adapters. (The interim FIX_PLAN.md was never
committed; its findings are resolved and its history lives in PRs #16–#21.)
