# AutoHarness v4 — Complete Blueprint

## 1. Overview

**What it is:** A probabilistic skill compiler that searches over structured stochastic policy graphs, executes them in a sandbox, and compiles reusable behavioral modules from execution traces.

**Core idea:** Use an LLM to generate and evolve a population of policy graphs (JSON IR). Execute each policy in a sandboxed environment. Score them with a multi-objective critic. Select elites, mutate them (LLM + random), and compile successful sub-patterns into reusable skills.

**Inspired by:** [AutoHarness paper](https://arxiv.org/abs/2603.03329) (Lou et al., 2026) — auto-synthesizing code harnesses to prevent illegal LLM agent actions.

## 2. Architecture

```
                    ┌──────────────────────────┐
                    │   Task / Environment     │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  Planner (LLM)           │
                    │  Generates N policies    │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │     Policy Population (JSON IR)  │
                └────────────────┬────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
  PES Interpreter          Trace Logger            Skill Registry
  (runtime)                (node-level)            (memory)
        │
        ▼
   Environment Execution (/tmp/workspace sandbox)
        │
        ▼
   Multi-objective Critic
        │
        ▼
   Optimizer (LLM mutation + random mutation)
        │
        ▼
   Skill Compiler (frequent subgraph detection)
        │
        ▼
   Updated Policy Population
```

## 3. Policy IR (JSON Graph)

### 3.1 Top-level structure

```json
{
  "start": "n1",
  "nodes": {
    "n1": { ... },
    "n2": { ... }
  }
}
```

### 3.2 Node types (4 only)

**OBSERVE** — reads from environment:
```json
{
  "type": "observe",
  "out": "obs"
}
```

**ACT** — executes a tool or skill:
```json
{
  "type": "act",
  "tool": "run_tests",
  "args": { "path": "repo" },
  "out": "result"
}
```

**THINK** — runtime LLM call (gpt-4o-mini):
```json
{
  "type": "think",
  "in": ["obs", "memory"],
  "out": "plan"
}
```

**TRANSITION** — probabilistic routing:
```json
{
  "type": "transition",
  "branches": [
    { "if": "result.success == true", "next": "n_success", "p": 0.8 },
    { "if": "true", "next": "n_retry", "p": 1.0 }
  ]
}
```

### 3.3 Example policy (code task)

```json
{
  "start": "n1",
  "nodes": {
    "n1": { "type": "observe", "out": "code" },
    "n2": { "type": "think", "in": ["code"], "out": "plan" },
    "n3": { "type": "act", "tool": "write_file", "args": {"path": "solution.py", "content": "plan"}, "out": "write_result" },
    "n4": { "type": "act", "tool": "run_tests", "args": {"path": "tests/"}, "out": "test_result" },
    "n5": {
      "type": "transition",
      "branches": [
        { "if": "test_result.success == true", "next": "n_done", "p": 1.0 },
        { "if": "true", "next": "n2", "p": 1.0 }
      ]
    },
    "n_done": { "type": "observe", "out": "final" }
  }
}
```

## 4. Runtime

### 4.1 PES Interpreter (`runtime/interpreter.py`)

- Executes the JSON graph step-by-step
- Maintains `state` (namespaced per node ID)
- Logs node-level trace: `{node_id, type, action, output_value, latency}`
- `think` nodes call gpt-4o-mini at runtime
- `transition` nodes sample from valid branches based on conditions + probabilities
- Max steps limit (default 50) to prevent infinite loops

### 4.2 State (`runtime/state.py`)

```python
class State:
    def __init__(self):
        self.data = {}  # {node_id: {key: value}}

    def set(self, node_id, key, value):
        self.data.setdefault(node_id, {})[key] = value

    def get(self, node_id, key):
        return self.data.get(node_id, {}).get(key)

    def flatten(self):
        """For condition evaluation: merge all node outputs"""
        flat = {}
        for node_data in self.data.values():
            flat.update(node_data)
        return flat
```

No key collisions — variables scoped to the node that produced them.

### 4.3 Environment (`runtime/environment.py`)

- All file operations locked to `/tmp/workspace`
- Path traversal prevention: `os.path.realpath(path).startswith(workspace_root)`
- Methods: `observe()`, `get_reward()`, `reset()`

## 5. Registry

### 5.1 Tools (`registry/tools.py`)

| Tool | Description | Timeout |
|------|-------------|---------|
| `run_tests(path)` | Runs pytest, returns structured result | 10s |
| `read_file(path)` | Reads file contents | 2s |
| `write_file(path, content)` | Writes to file | 2s |
| `list_files(path)` | Lists directory | 2s |

All tools:
- Validate paths against workspace root
- Wrapped in `subprocess.run(timeout=N)`
- Return `"ERROR: Timeout"` or `"ERROR: {message}"` on failure

### 5.2 Skills (`registry/skills.py`)

Skills are compiled sub-policies:

```json
{
  "name": "fix_test_failure",
  "policy": { ... },
  "stats": {
    "success_rate": 0.72,
    "usage": 31
  }
}
```

- Execution: nested interpreter call on the skill's policy
- Pruning: delete if `usage == 0` or `success_rate < 0.3`

## 6. Intelligence Layer

### 6.1 Critic (`intelligence/critic.py`)

Multi-objective scoring:

```python
def evaluate(trace, env_result):
    return {
        "reward": env_result.reward,
        "efficiency": -len(trace),
        "safety": env_result.safety_score,
        "success": float(env_result.success)
    }
```

### 6.2 Planner (`intelligence/planner.py`)

- LLM generates initial population of N policies from task description
- Uses JSON mode / Pydantic validation with retry (3 attempts)
- Returns list of valid policy IRs

### 6.3 Optimizer (`intelligence/optimizer.py`)

Two mutation strategies:

**LLM mutation:**
- Sends failing policy + blame map to LLM
- LLM rewrites the JSON
- Pydantic validation + retry (3 attempts)

**Random mutation:**
- Swap a node's tool
- Change branch probabilities
- Add or remove a node
- Mutate tool arguments

### 6.4 Skill Compiler (`intelligence/compiler.py`)

Runs every N episodes:

1. **Detect patterns:** Find frequent subgraphs in recent traces
2. **Compress:** Convert repeated subgraph into a skill policy
3. **Name:** Auto-generate descriptive name
4. **Store:** Add to skill registry with initial stats

## 7. Memory (`memory/store.py`)

```python
{
  "episodic": [...],       # Recent traces + scores
  "skills": [...],         # Compiled skill references
  "stats": {
    "global_success_rate": 0.61,
    "generations": 42
  }
}
```

## 8. Outer Loop (`main.py`)

```python
def run_autoharness(task_description, config):
    skill_registry = SkillRegistry()
    memory = MemoryStore()

    population = planner.generate_population(task_description, config.population_size)

    for generation in range(config.max_episodes):
        results = []

        for policy in population:
            env = CodeTaskEnvironment(config.workspace_root)
            trace, state = PESInterpreter(policy, env, skill_registry, config).run()
            scores = critic.evaluate(trace, env.get_reward())
            results.append((policy, scores, trace))
            memory.store_episode(policy, trace, scores)

        elites = select_top(results, config.elite_fraction)

        population = []
        for policy, scores, trace in elites:
            population.append(policy)
            population.append(optimizer.llm_mutate(policy, scores))
            population.append(optimizer.random_mutate(policy))

        if generation % config.compile_every_n_episodes == 0:
            new_skills = compiler.compile_from_traces(memory.get_recent_traces())
            skill_registry.add_many(new_skills)
            skill_registry.prune(config.skill_prune_success_threshold)

        best = max(s["reward"] for _, s, _ in results)
        if best >= config.convergence_threshold:
            break
```

## 9. Configuration (`config.py`)

```python
DEFAULT_CONFIG = {
    "planner_model": "gpt-4o",
    "optimizer_model": "gpt-4o",
    "think_model": "gpt-4o-mini",
    "population_size": 5,
    "elite_fraction": 0.4,
    "max_steps": 50,
    "max_episodes": 100,
    "tool_timeout": 10,
    "optimizer_retries": 3,
    "compile_every_n_episodes": 10,
    "min_pattern_occurrences": 3,
    "skill_prune_success_threshold": 0.3,
    "workspace_root": "/tmp/workspace",
    "convergence_threshold": 0.8,
}
```

## 10. Guardrails

| # | Risk | Mitigation |
|---|------|------------|
| 1 | LLM returns invalid JSON | Pydantic validation + 3 retries in planner/optimizer |
| 2 | Tool hangs (infinite loop) | `subprocess.run(timeout=10)` on all tools |
| 3 | State key collisions | Namespaced: `state[node_id][key]` |
| 4 | Filesystem escape | All paths through `/tmp/workspace`, `realpath()` check |

## 11. Dependencies

```
openai>=1.0
pydantic>=2.0
```

Dev tools: `ruff`, `mypy` (already installed globally).

## 12. Implementation Order

| # | Task | Files |
|---|------|-------|
| 1 | Scaffolding | `pyproject.toml`, `config.py`, `schema.json` |
| 2 | Policy IR models | `runtime/ir.py` |
| 3 | State | `runtime/state.py` |
| 4 | Environment + safety | `runtime/environment.py` |
| 5 | Tool registry + timeouts | `registry/tools.py` |
| 6 | Interpreter | `runtime/interpreter.py` |
| 7 | Memory store | `memory/store.py` |
| 8 | Critic | `intelligence/critic.py` |
| 9 | Planner | `intelligence/planner.py` |
| 10 | Optimizer | `intelligence/optimizer.py` |
| 11 | Skill compiler | `intelligence/compiler.py` |
| 12 | Skill registry + pruning | `registry/skills.py` |
| 13 | main.py | `main.py` |
| 14 | Code task example | `examples/code_task.py` |
| 15 | Tests | `tests/` |
