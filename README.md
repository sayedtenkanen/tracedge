# AutoHarness

Probabilistic program compiler that searches over a unified intermediate representation (UPIR), executes it in sandboxed environments, and compiles successful behaviors into reusable executable subprograms.

Based on [arXiv:2603.03329](https://arxiv.org/abs/2603.03329) (Lou et al., Google DeepMind, 2026).

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
| 8-10 | Skill Execution, Pruning, Memory | planned |
| 11-16 | Compiler layer | planned |

## Install

```bash
# Clone
git clone git@github.com:sayedtenkanen/auto-harnessessing.git
cd auto-harnessessing

# Create venv (Python 3.12+)
python3.12 -m venv .venv
source .venv/bin/activate

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Quick start

```python
from autoharness.ir.upir import UPIR, Edge
from autoharness.runtime.vm import VM

# Define a simple policy graph
upir = UPIR(
    entry="observe",
    nodes={
        "observe": {"kind": "observe", "node_id": "observe", "query": "What is 2+2?"},
        "think": {"kind": "think", "node_id": "think", "prompt": "Answer: 4"},
        "act": {"kind": "act", "node_id": "act", "tool": "respond"},
    },
    edges=[
        Edge(from_="observe", to="think", kind="sequential"),
        Edge(from_="think", to="act", kind="sequential"),
    ],
)

# Execute with an LLM
class SimpleLLM:
    def chat(self, prompt: str) -> str:
        return "4"

vm = VM(upir=upir, llm=SimpleLLM())
trace = vm.run()
```

## Architecture

```
UPIR (Unified Policy IR)
  └─ VM (step-by-step interpreter)
       ├─ Observe → Act → Think → Branch → HarnessCall → SkillCall → Phi
       ├─ Environment (ToolEnvironment | GameEnvironment)
       └─ Trace → Reward → Thompson Search → Refiner/Critic
```

**Core loop:** Execute → Trace → Score → Search → Refine → Compile

## Project structure

```
src/autoharness/
├── ir/              # UPIR, nodes, Harness IR types
├── runtime/         # VM, state, seed, StepResult
├── environment/     # Protocol, ToolEnvironment, GameEnvironment
├── sandbox/         # Workspace, guardrails, harness runner
├── trace/           # Trace IR
├── reward/          # Reward engine
├── search/          # Thompson tree search
├── intelligence/    # LLM client, critic, refiner
├── skills/          # Skill extraction
├── memory/          # (planned) Persistence
└── compiler/        # (planned) Compiler passes
```

## Development

```bash
# Tests
pytest tests/

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/

# Security scan
bash scripts/security-scan.sh

# CI status
bash scripts/ci-status.sh
```

## License

Research use only.
