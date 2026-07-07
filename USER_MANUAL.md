# AutoHarness — User Manual

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Building a UPIR Graph](#building-a-upir-graph)
5. [Running the VM](#running-the-vm)
6. [Using Environments](#using-environments)
7. [Working with Harnesses](#working-with-harnesses)
8. [Skills System](#skills-system)
9. [Reward Scoring](#reward-scoring)
10. [Thompson Search](#thompson-search)
11. [Refiner + Critic](#refiner--critic)
12. [Persistent Memory](#persistent-memory)
13. [Configuration](#configuration)
14. [Examples](#examples)
15. [API Reference](#api-reference)

---

## Installation

### Requirements
- Python 3.12+
- pip

### Install from source

```bash
git clone git@github.com:sayedtenkanen/auto-harnessessing.git
cd auto-harnessessing

python3.12 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### Verify installation

```bash
pytest tests/ -q
# 297 passed
```

---

## Quick Start

```python
from autoharness.ir.upir import UPIR, UPIRNode, Edge
from autoharness.runtime.vm import VM

# 1. Define a policy graph
upir = UPIR(
    entry="observe",
    nodes={
        "observe": UPIRNode(kind="observe", node_id="observe", query="What is 2+2?"),
        "think": UPIRNode(kind="think", node_id="think", prompt="Answer: 4"),
        "act": UPIRNode(kind="act", node_id="act", tool="respond"),
    },
    edges=[
        Edge(from_="observe", to="think", kind="sequential"),
        Edge(from_="think", to="act", kind="sequential"),
    ],
)

# 2. Provide an LLM
class SimpleLLM:
    def chat(self, prompt: str) -> str:
        return "4"

# 3. Execute
vm = VM(upir=upir, llm=SimpleLLM())
trace = vm.run()

# 4. Inspect results
for event in trace:
    print(f"{event['kind']}: {event.get('outputs', {})}")
```

---

## Full Loop

The `run_autoharness()` function wires together the entire pipeline — search, execution, scoring, skill extraction, and memory persistence — in a single call.

```python
from autoharness.ir.upir import UPIR, Edge, UPIRNode
from autoharness.main import run_autoharness

# 1. Define strategy variants
variants = {
    "fast": UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="What is 2+2?"),
            "answer": UPIRNode(kind="act", node_id="answer", tool="respond"),
        },
        edges=[Edge(from_="observe", to="answer", kind="sequential")],
    ),
    "thorough": UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="What is 2+2?"),
            "think": UPIRNode(kind="think", node_id="think", prompt="Think step by step"),
            "answer": UPIRNode(kind="act", node_id="answer", tool="respond"),
        },
        edges=[
            Edge(from_="observe", to="think", kind="sequential"),
            Edge(from_="think", to="answer", kind="sequential"),
        ],
    ),
}

# 2. Any object with chat(prompt) -> str works as the LLM
class MyLLM:
    def chat(self, prompt: str) -> str:
        return "4"

# 3. Run the full loop
result = run_autoharness(
    variants=variants,
    llm=MyLLM(),
    seed=42,
    max_search_iterations=10,
    max_total_failures=5,
    env_kind="tool",       # or "game" for game environments
    data_dir="./memory",   # None for temp directory
)

# 4. Inspect results
print(result["status"])            # "converged" | "max_iterations" | "max_failures"
print(result["best_variant"])      # Name of the winning variant
print(result["iterations"])        # How many search iterations ran
print(result["episodes_saved"])    # Traces saved to memory
print(result["skills_extracted"])  # Reusable patterns compiled
```

### What happens inside

1. **Thompson search** — Each variant becomes a branch with a Beta(α, β) posterior. At each iteration, the branch with the highest sampled value is executed.
2. **VM execution** — The winning variant's UPIR graph is walked step by step, producing a trace.
3. **Reward scoring** — The trace is scored on task success, efficiency, and safety.
4. **Posterior update** — The branch's Beta distribution is updated: α += reward, β += (1 - reward).
5. **Skill extraction** — After search completes, repeated patterns in the best variant's traces are compiled into reusable skills.
6. **Memory persistence** — All episodes, skill stats, and global stats are saved to disk.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `variants` | required | `dict[str, UPIR]` — named strategies to search over |
| `llm` | required | Any object with `chat(prompt: str) -> str` |
| `seed` | `42` | Random seed for reproducibility |
| `max_search_iterations` | `10` | Budget for Thompson search |
| `max_total_failures` | `5` | Failure budget before early stopping |
| `env_kind` | `"tool"` | `"tool"` or `"game"` — affects reward weights |
| `data_dir` | `None` | Directory for MemoryStore. Temp dir if None. |

### Return value

```python
{
    "status": "converged",        # Why search stopped
    "best_variant": "thorough",   # Winning variant name
    "iterations": 8,              # Search iterations used
    "episodes_saved": 10,         # Traces saved
    "skills_extracted": 5,        # Skills compiled
}
```

### Using with real LLMs

```python
from autoharness.intelligence.llm_client import OpenAIChatClient

llm = OpenAIChatClient(model="gpt-4o")
result = run_autoharness(variants=variants, llm=llm, seed=42)
```

### Using with game environments

```python
result = run_autoharness(
    variants=game_variants,
    llm=my_llm,
    seed=42,
    env_kind="game",  # Uses game-specific reward weights
)
```

---

## Core Concepts

### UPIR (Unified Policy IR)
A directed graph where nodes represent computational steps and edges define execution order. UPIR unifies policies, harnesses, and skills into one representation.

### Node Types
| Node | Purpose | Key Fields |
|------|---------|------------|
| `observe` | Query the environment | `query` |
| `act` | Execute a tool/action | `tool`, `args` |
| `think` | Internal reasoning | `prompt` |
| `branch` | Conditional routing | `condition` |
| `harness_call` | Execute sandboxed code | `harness_id` |
| `skill_call` | Execute a reusable skill | `skill_id` |
| `phi` | Merge state from sources | `sources` |

### VM
Step-by-step interpreter that walks the UPIR graph, evaluates nodes, and produces trace events.

### Trace
Ordered list of execution events recording what happened at each step.

### Reward
Scalar score (0-1) measuring how successful and efficient an execution was.

### Skills
Reusable subprograms extracted from repeated successful patterns in traces.

---

## Building a UPIR Graph

### Basic graph

```python
from autoharness.ir.upir import UPIR, UPIRNode, Edge

upir = UPIR(
    entry="start",
    nodes={
        "start": UPIRNode(kind="observe", node_id="start", query="Hello"),
        "end": UPIRNode(kind="act", node_id="end", tool="respond"),
    },
    edges=[Edge(from_="start", to="end", kind="sequential")],
)
```

### Branching graph

```python
from autoharness.ir.upir import UPIR, UPIRNode, Edge

upir = UPIR(
    entry="start",
    nodes={
        "start": UPIRNode(kind="branch", node_id="start", condition="is_error"),
        "fix": UPIRNode(kind="act", node_id="fix", tool="fix_code"),
        "ok": UPIRNode(kind="act", node_id="ok", tool="respond"),
    },
    edges=[
        Edge(from_="start", to="fix", kind="branch_true"),
        Edge(from_="start", to="ok", kind="branch_false"),
    ],
)
```

### Validation

UPIR validates on construction:
- Entry node must exist in nodes
- All edges must reference existing nodes
- Edge `from_` field accepts both `"from"` and `"from_"` (Pydantic alias)

```python
from autoharness.ir.upir import UPIR, UPIRNode

# This raises ValidationError
UPIR(
    entry="missing",
    nodes={"a": UPIRNode(kind="observe", node_id="a")},
    edges=[],
)  # ValidationError: entry 'missing' not in nodes
```

---

## Running the VM

### Basic execution

```python
from autoharness.runtime.vm import VM

vm = VM(upir=upir, llm=my_llm, seed=42)
trace = vm.run()  # Returns list[dict]
```

### With environment

```python
from autoharness.environment.tool_env import ToolEnvironment

env = ToolEnvironment(workspace="/tmp/my_workspace")
vm = VM(upir=upir, llm=my_llm, seed=42, environment=env)
trace = vm.run()
```

### Deterministic replay

```python
vm1 = VM(upir=upir, llm=my_llm, seed=42)
vm2 = VM(upir=upir, llm=my_llm, seed=42)
assert vm1.run() == vm2.run()  # Same seed = same trace
```

### Configuration

```python
from autoharness.runtime.vm import VM

vm = VM(
    upir=upir,
    llm=my_llm,
    seed=42,
    max_steps=50,  # Default: 100
    environment=my_env,
)
```

### Trace events

Each trace event is a dict with:
```python
{
    "node_id": "observe",
    "kind": "observe",
    "inputs": {"query": "What is 2+2?"},
    "outputs": {"result": "4"},
    "cost": 0.01,  # optional
    "legal": True,  # optional
}
```

---

## Using Environments

### ToolEnvironment

File I/O with sandboxed path validation:

```python
from autoharness.environment.tool_env import ToolEnvironment

env = ToolEnvironment(workspace="/tmp/sandbox")

# Inside a harness, you can:
# env.read_file("data.txt")    → reads /tmp/sandbox/data.txt
# env.write_file("out.txt", data)  → writes to /tmp/sandbox/out.txt
# Path traversal outside workspace is blocked
```

### GameEnvironment

Tic-Tac-Toe with legal move enforcement:

```python
from autoharness.environment.game_env import GameEnvironment

env = GameEnvironment()
env.reset()
env.legal_actions()  # ['0', '1', ..., '8']
env.step('4')        # Place mark at center
```

### Custom environment

Implement the `Environment` protocol:

```python
from autoharness.environment.protocol import Environment

class MyEnv:
    def reset(self) -> None:
        self.state = {}

    def step(self, action: str) -> dict:
        return {"reward": 1.0, "done": True}

    def legal_actions(self) -> list[str]:
        return ["a", "b", "c"]

    def tools(self) -> dict:
        return {}

env = MyEnv()  # duck-typing works, no inheritance needed
```

---

## Working with Harnesses

Harnesses are sandboxed code snippets that run with restricted permissions.

### Defining a harness

```python
from autoharness.ir.harness import Harness

harness = Harness(
    kind="policy",
    code="result = inputs['x'] * 2",
)
```

### Adding to UPIR

```python
upir = UPIR(
    entry="start",
    nodes={
        "start": UPIRNode(kind="harness_call", node_id="start", harness_id="double"),
    },
    edges=[],
    harness_table={"double": harness},
)
```

### Guardrails (static analysis)

The sandbox performs AST-level analysis before execution:

| Rule | What it blocks |
|------|---------------|
| `no_try_except` | `try`/`except` blocks |
| `no_network` | `import socket`, `import requests`, `urllib` |
| `no_filesystem` | `import os`, `import shutil`, `open()` |
| `no_environment_step` | `env.step()` calls |
| `no_state_mutation` | `state[x] = y` assignments |

Errors are raised before execution, not at runtime.

### Restricted builtins

Harness code runs with a curated set of 60 safe builtins. Blocked:
- `eval`, `exec`, `compile`, `__import__`
- `open`, `getattr`, `hasattr`, `type`, `super`
- `globals`, `locals`, `vars`

---

## Skills System

Skills are reusable subprograms extracted from repeated patterns in execution traces.

### Extracting skills

```python
from autoharness.skills.extractor import SkillExtractor

extractor = SkillExtractor(min_occurrences=2)

# Build a trace log
from autoharness.trace.trace_ir import TraceEvent, TraceLog
trace = TraceLog()
for _ in range(3):
    trace.append(TraceEvent(node_id="n1", kind="observe"))
    trace.append(TraceEvent(node_id="n2", kind="act"))

# Detect patterns and extract
patterns = extractor.detect_patterns(trace)
for pattern in patterns:
    skill_node = extractor.extract_skill(pattern, original_upir)

# extractor.skill_table now contains the extracted skills
```

### Executing skills

Skills execute as nested VMs:

```python
# A skill_call node triggers nested execution
upir = UPIR(
    entry="call1",
    nodes={
        "call1": UPIRNode(kind="skill_call", node_id="call1", skill_id="my_skill"),
    },
    edges=[],
    skill_table={"my_skill": skill_upir},
)
```

Nested state is namespaced: `nested.<node_id>` under the calling node.

### Pruning skills

```python
from autoharness.skills.pruner import SkillPruner

pruner = SkillPruner(
    skill_table=extractor.skill_table,
    stats={"skill_1": {"usage": 10, "successes": 8}},
    min_success_rate=0.5,
)

pruned = pruner.prune()  # Returns filtered dict
```

Skills with `usage == 0` or `success_rate < min_success_rate` are removed.

---

## Reward Scoring

### Scoring a trace

```python
from autoharness.reward.scorer import score_trace, value

# Score a trace
reward = score_trace(trace, env_kind="tool")  # or env_kind="game"
print(reward.task_success)  # 1.0 if harness_call verdict='ok', else 0.0
print(reward.efficiency)    # decays with step count
print(reward.safety)        # 1.0 if no exceptions

# Get scalar value
v = value(reward)  # float in [0, 1]
```

### Reward modes

| Mode | Weight set | Use case |
|------|-----------|----------|
| `"tool"` | task_success=0.6, efficiency=0.2, safety=0.2 | File I/O, API calls |
| `"game"` | task_success=0.5, legality=0.3, safety=0.2 | Games, puzzles |

### Reward components

- **Success:** `1.0` if harness_call verdict is `"ok"`, else `0.0`
- **Efficiency:** `1.0 - (steps / max_steps)`, clamped to [0, 1]
- **Safety:** `1.0` if no raised exceptions, else `0.0`
- **Legality:** Fraction of events with `legal=True`

---

## Thompson Search

Bayesian exploration of strategy space using Thompson sampling.

```python
from autoharness.search.thompson import ThompsonTreeSearch, SearchConfig
from autoharness.ir.harness import Harness

config = SearchConfig(
    max_search_iterations=50,
    max_total_failures=10,
    prior_alpha=1.0,
    prior_beta=1.0,
    convergence_threshold=0.8,
)

search = ThompsonTreeSearch(config=config)

# Add branches (each wrapping a Harness)
search.add_branch(Harness(kind="policy", code="strategy_a"))
search.add_branch(Harness(kind="policy", code="strategy_b"))

# Define a rollout function: (Harness, seed) -> (value, failed)
def rollout(harness, seed):
    strategy_name = harness.code
    vm = VM(upir=strategies[strategy_name], llm=my_llm, seed=seed)
    trace = vm.run()
    reward = score_trace(trace, env_kind="tool")
    return value(reward), False

result = search.run(rollout_fn=rollout)
print(result.best_branch)   # Branch with highest posterior mean
print(result.iterations)    # How many iterations it took
```

### How it works

1. Each branch has a Beta(α, β) posterior
2. At each iteration, sample from each branch's posterior
3. Execute the branch with the highest sample
4. Update: `α += reward`, `β += (1 - reward)`
5. Stop when a branch exceeds `convergence_threshold` or budget is exhausted

---

## Refiner + Critic

LLM-guided improvement of harness code.

```python
from autoharness.intelligence.critic import Critic
from autoharness.intelligence.refiner import Refiner

# Analyze failures (takes a list of traces)
critic = Critic()
analysis = critic.analyze([trace])  # pass as list of traces
print(analysis.failure_clusters)     # [{"root_cause": "ValueError", "count": 3}]
print(analysis.legality_violations)  # [{"node_id": "act", "outputs": {}}]

# Refine the harness (llm is a Callable[[str], str])
refiner = Refiner(llm=my_llm.chat)
refined = refiner.refine(harness=harness, feedback=analysis)
print(refined.code)     # Improved code
print(refined.version)  # Incremented version number
```

### Critic analysis

- **Failure clustering:** Groups errors by type
- **Root cause extraction:** Parses error messages for actionable info
- **Legality detection:** Flags events with `legal=False`
- **Inefficiency detection:** Flags traces exceeding step threshold

---

## Persistent Memory

JSON-file-backed storage for episodes, skills, and global stats.

```python
from pathlib import Path
from autoharness.memory.store import MemoryStore

store = MemoryStore(data_dir=Path("./memory"))

# Episodes
store.save_episode("ep1", trace, reward=0.85)
episode = store.load_episode("ep1")  # dict or None

# Skill stats
store.save_skill_stats("skill_1", usage=10, successes=8)
stats = store.load_skill_stats("skill_1")  # {"usage": 10, "successes": 8}

# Global stats
store.save_global_stats(total_runs=100, success_rate=0.75)
stats = store.load_global_stats()  # {"total_runs": 100, "success_rate": 0.75}
```

### Directory structure

```
memory/
├── episodes/
│   ├── ep1.json
│   └── ep2.json
├── skills/
│   ├── skill_1.json
│   └── skill_2.json
└── global_stats.json
```

### Error handling

Corrupted files return defaults instead of raising:
- Missing/corrupted episode → `None`
- Missing/corrupted skill stats → `{"usage": 0, "successes": 0}`
- Missing/corrupted global stats → `{"total_runs": 0, "success_rate": 0.0}`

---

## Configuration

Default values in `src/autoharness/config.py`:

```python
VM_MAX_STEPS = 100
SANDBOX_MAX_RUNTIME_MS = 1000

THOMPSON_MAX_SEARCH_ITERATIONS = 50
THOMPSON_MAX_TOTAL_FAILURES = 10
THOMPSON_PRIOR_ALPHA = 1.0
THOMPSON_PRIOR_BETA = 1.0

REWARD_WEIGHTS_TOOL = {
    "success": 0.4,
    "efficiency": 0.3,
    "safety": 0.2,
    "legality": 0.1,
}

REWARD_WEIGHTS_GAME = {
    "success": 0.5,
    "efficiency": 0.2,
    "safety": 0.2,
    "legality": 0.1,
}
```

---

## Examples

Two runnable examples in `examples/`:

### Tic-Tac-Toe (`examples/tic_tac_toe.py`)

```bash
python examples/tic_tac_toe.py
```

Demonstrates GameEnvironment with observe→act loop, reward scoring, and game stats.

### Code Task (`examples/code_task.py`)

```bash
python examples/code_task.py
```

Demonstrates ToolEnvironment with observe→think→act pipeline and reward scoring.

---

## API Reference

### ir/upir.py
- `UPIR(entry, nodes, edges, harness_table, skill_table)` — Graph constructor
- `UPIRNode(kind, node_id, **kwargs)` — Node in the graph
- `Edge(from_, to, kind)` — Directed edge

### runtime/vm.py
- `VM(upir, llm, seed, max_steps, environment)` — Execute a UPIR
- `vm.run()` → `list[dict]` — Execute and return trace

### environment/protocol.py
- `Environment` — Protocol: `reset()`, `step(action)`, `legal_actions()`, `tools()`

### sandbox/guardrails.py
- `check_guardrails(code, guard_policy)` → `list[str]` — Static analysis errors

### sandbox/harness_runner.py
- `run_harness(code, inputs, timeout_ms, environment)` → `HarnessResult` — Sandboxed exec

### trace/trace_ir.py
- `TraceEvent(node_id, kind, **fields)` — Single trace event
- `TraceLog` — `list[TraceEvent]`

### reward/scorer.py
- `score_trace(trace, env_kind="tool")` → `Reward` — Score a trace
- `value(reward, env_kind="tool")` → `float` — Scalar reward value

### search/thompson.py
- `ThompsonTreeSearch(config, env_kind)` — Bayesian search
- `search.add_branch(harness)` → `Branch` — Add a strategy
- `search.run(rollout_fn, rng_seed)` → `SearchResult`

### intelligence/critic.py
- `Critic(inefficiency_threshold)` — Analyze failures
- `critic.analyze(traces)` → `CriticOutput` — takes list[list[dict]]

### intelligence/refiner.py
- `Refiner(llm, max_retries)` — llm is `Callable[[str], str]`
- `refiner.refine(harness, feedback)` → `Harness` — Improve code

### skills/extractor.py
- `SkillExtractor(min_occurrences)` — Extract skills from traces
- `extractor.detect_patterns(trace)` → `list[Pattern]`
- `extractor.extract_skill(pattern, upir)` → `UPIRNode`

### skills/pruner.py
- `SkillPruner(skill_table, stats, min_success_rate)` — Prune low-quality skills
- `pruner.prune()` → `dict[str, UPIR]`

### memory/store.py
- `MemoryStore(data_dir)` — Persistent storage
- `store.save_episode(id, trace, reward)`
- `store.load_episode(id)` → `dict | None`
- `store.save_skill_stats(id, usage, successes)`
- `store.load_skill_stats(id)` → `dict`
- `store.save_global_stats(total_runs, success_rate)`
- `store.load_global_stats()` → `dict`
