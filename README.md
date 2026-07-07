# AutoHarness

Probabilistic program compiler that discovers, compiles, and reuses successful behavioral patterns from LLM execution traces — turning one-shot successes into reliable, reusable subprograms.

Implements and extends [arXiv:2603.03329](https://arxiv.org/abs/2603.03329) (Lou et al., Google DeepMind, 2026) — the paper synthesizes constraint harnesses; this project compiles execution traces into reusable, LLM-free skills.

## Quick start

```python
# executable
from tracedge.ir.upir import UPIR, UPIRNode
from tracedge.main import run_tracedge

# Define strategy variants — one succeeds, one fails
variants = {
    "good": UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "result = True"},
    ),
    "bad": UPIR(
        entry="h1",
        nodes={"h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h")},
        edges=[],
        harness_table={"h": "raise ValueError('always fails')"},
    ),
}

# Any object with chat(prompt) -> str works as the LLM
class MyLLM:
    def chat(self, prompt: str) -> str:
        return "ok"

# Run the full loop: execute → score → search → extract → persist
result = run_tracedge(
    variants=variants,
    llm=MyLLM(),
    seed=42,
    max_search_iterations=15,
    env_kind="tool",
)

print(result["best_variant"])       # "good" — winner found by Thompson search
print(result["episodes_saved"])     # 3 — traces saved to memory
```

### What just happened?

In one call, AutoHarness:

1. **Searched** — ran each variant through Thompson sampling (Bayesian exploration), allocating more trials to promising strategies
2. **Scored** — evaluated each execution trace on task success, efficiency, and safety
3. **Extracted** — detected repeated successful patterns and compiled them into reusable skills
4. **Persisted** — saved all traces, skill stats, and search results to memory

No manual prompt tuning. No human labeling. The system learns from its own wins.

## Install

```bash
git clone git@github.com:sayedtenkanen/auto-harnessessing.git
cd auto-harnessessing

python3.12 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"

# Run the end-to-end demo
python examples/end_to_end.py
```

## Status

| Slice | Description | Status |
|-------|-------------|--------|
| 1 | UPIR VM + Environment Protocol | done |
| 2 | Sandbox + Safety | done |
| 3 | Trace IR | done |
| 4 | Reward Engine | done |
| 5 | Thompson Tree Search | done |
| 6 | Refiner + Critic Loop | done |
| 7 | Skill Extraction | done |
| 8-10 | Skill Execution, Pruning, Memory | done |
| 11-16 | Compiler layer | planned |

## Architecture

```
run_tracedge()
  ├─ ThompsonTreeSearch  — Bayesian exploration over strategy variants
  ├─ VM                  — step-by-step UPIR interpreter
  ├─ Score               — reward = f(task_success, efficiency, safety)
  ├─ SkillExtractor      — detect patterns → compile into reusable skills
  └─ MemoryStore         — persist episodes, skills, global stats
```

**Core loop:** Execute → Score → Search → Extract → Persist

## Run the examples

```bash
# Full end-to-end loop (no API key needed)
python examples/end_to_end.py

# Tic-Tac-Toe with game environment
python examples/tic_tac_toe.py

# Code task with tool environment
python examples/code_task.py

# Real OpenAI API call
export OPENAI_API_KEY="sk-..."
python examples/real_llm_task.py
```

## Development

```bash
pytest tests/
ruff check src/ tests/
ruff format src/ tests/
mypy src/
bash scripts/security-scan.sh
```

## License

MIT — see [LICENSE](LICENSE).
