# AutoHarness — Use Cases

Each use case shows a complete end-to-end run. Define variants, call `run_tracedge()`, get results.

---

## 1. Self-Improving Coding Agent

**Problem:** LLM coding agents are inconsistent — sometimes they nail the fix, sometimes they loop.

**Solution:** AutoHarness watches which strategies succeed, finds the best one, and extracts reusable fix patterns.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class CodingLLM:
    def chat(self, prompt: str) -> str:
        if "fix" in prompt.lower():
            return "Fixed by adding input validation"
        return "Writing solution..."

variants = {
    "direct": UPIR(
        entry="read_task",
        nodes={
            "read_task": UPIRNode(kind="observe", node_id="read_task", query="Read task"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
            "test": UPIRNode(kind="act", node_id="test", tool="run_tests"),
        },
        edges=[
            Edge(from_="read_task", to="write", kind="sequential"),
            Edge(from_="write", to="test", kind="sequential"),
        ],
    ),
    "with_fix": UPIR(
        entry="read_task",
        nodes={
            "read_task": UPIRNode(kind="observe", node_id="read_task", query="Read task"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
            "test": UPIRNode(kind="act", node_id="test", tool="run_tests"),
            "fix": UPIRNode(kind="think", node_id="fix", prompt="Fix the failing test"),
            "rewrite": UPIRNode(kind="act", node_id="rewrite", tool="write_file"),
        },
        edges=[
            Edge(from_="read_task", to="write", kind="sequential"),
            Edge(from_="write", to="test", kind="sequential"),
            Edge(from_="test", to="fix", kind="sequential"),
            Edge(from_="fix", to="rewrite", kind="sequential"),
        ],
    ),
}

result = run_tracedge(
    variants=variants,
    llm=CodingLLM(),
    seed=42,
    max_search_iterations=10,
    env_kind="tool",
)
```

**Output:**
```
Status:           converged
Best variant:     with_fix
Skills extracted: 8
Episodes saved:   10
```

**What happened:** AutoHarness discovered that the `with_fix` strategy (write → test → fix → rewrite) succeeds more often. It extracted the "test → fix → rewrite" pattern as a reusable skill.

---

## 2. Automated Data Pipeline

**Problem:** Data pipelines need trial-and-error to find the right transformation sequence.

**Solution:** Define pipeline variants, let AutoHarness find the best one and extract the working pattern.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class PipelineLLM:
    def chat(self, prompt: str) -> str:
        return "processed"

variants = {
    "simple": UPIR(
        entry="read",
        nodes={
            "read": UPIRNode(kind="act", node_id="read", tool="read_file"),
            "transform": UPIRNode(kind="harness_call", node_id="transform", harness_id="csv_transform"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
        },
        edges=[
            Edge(from_="read", to="transform", kind="sequential"),
            Edge(from_="transform", to="write", kind="sequential"),
        ],
        harness_table={"csv_transform": "result = [row.upper() for row in inputs.get('data', [])]"},
    ),
    "validated": UPIR(
        entry="read",
        nodes={
            "read": UPIRNode(kind="act", node_id="read", tool="read_file"),
            "transform": UPIRNode(kind="harness_call", node_id="transform", harness_id="csv_transform"),
            "validate": UPIRNode(kind="harness_call", node_id="validate", harness_id="schema_check"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
        },
        edges=[
            Edge(from_="read", to="transform", kind="sequential"),
            Edge(from_="transform", to="validate", kind="sequential"),
            Edge(from_="validate", to="write", kind="sequential"),
        ],
        harness_table={
            "csv_transform": "result = [row.upper() for row in inputs.get('data', [])]",
            "schema_check": "result = {'valid': True}",
        },
    ),
}

result = run_tracedge(
    variants=variants,
    llm=PipelineLLM(),
    seed=42,
    max_search_iterations=10,
    env_kind="tool",
)
```

**Output:**
```
Status:           converged
Best variant:     validated
Skills extracted: 6
Episodes saved:   10
```

**What happened:** The `validated` pipeline (read → transform → validate → write) scored higher on safety. AutoHarness extracted the full pipeline as a reusable skill.

---

## 3. Game Strategy Discovery

**Problem:** Finding winning game strategies by hand is slow and brittle.

**Solution:** Define strategy variants, let Thompson search find the winner, extract it as a skill.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class GameLLM:
    def chat(self, prompt: str) -> str:
        return "4"  # Always pick center

variants = {
    "center": UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="Board state"),
            "act": UPIRNode(kind="act", node_id="act", tool="place_move", args={"position": 4}),
        },
        edges=[Edge(from_="observe", to="act", kind="sequential")],
    ),
    "corner": UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="Board state"),
            "act": UPIRNode(kind="act", node_id="act", tool="place_move", args={"position": 0}),
        },
        edges=[Edge(from_="observe", to="act", kind="sequential")],
    ),
    "adaptive": UPIR(
        entry="observe",
        nodes={
            "observe": UPIRNode(kind="observe", node_id="observe", query="Board state"),
            "think": UPIRNode(kind="think", node_id="think", prompt="Choose best move"),
            "act": UPIRNode(kind="act", node_id="act", tool="place_move"),
        },
        edges=[
            Edge(from_="observe", to="think", kind="sequential"),
            Edge(from_="think", to="act", kind="sequential"),
        ],
    ),
}

result = run_tracedge(
    variants=variants,
    llm=GameLLM(),
    seed=42,
    max_search_iterations=20,
    env_kind="game",
)
```

**Output:**
```
Status:           converged
Best variant:     adaptive
Skills extracted: 5
Episodes saved:   20
```

**What happened:** Thompson search discovered that the `adaptive` strategy (observe → think → act) wins most often. The winning pattern was compiled into a reusable skill.

---

## 4. Multi-Step Research Assistant

**Problem:** Research tasks require multiple steps — search, summarize, format — and the right sequence matters.

**Solution:** Let AutoHarness search over research workflow variants and extract the best pipeline.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class ResearchLLM:
    def chat(self, prompt: str) -> str:
        return "Research findings: key insight discovered"

variants = {
    "linear": UPIR(
        entry="research",
        nodes={
            "research": UPIRNode(kind="observe", node_id="research", query="Research topic"),
            "summarize": UPIRNode(kind="think", node_id="summarize", prompt="Summarize findings"),
            "format": UPIRNode(kind="act", node_id="format", tool="write_file"),
        },
        edges=[
            Edge(from_="research", to="summarize", kind="sequential"),
            Edge(from_="summarize", to="format", kind="sequential"),
        ],
    ),
    "with_review": UPIR(
        entry="research",
        nodes={
            "research": UPIRNode(kind="observe", node_id="research", query="Research topic"),
            "summarize": UPIRNode(kind="think", node_id="summarize", prompt="Summarize findings"),
            "review": UPIRNode(kind="think", node_id="review", prompt="Review for accuracy"),
            "revise": UPIRNode(kind="think", node_id="revise", prompt="Revise based on review"),
            "format": UPIRNode(kind="act", node_id="format", tool="write_file"),
        },
        edges=[
            Edge(from_="research", to="summarize", kind="sequential"),
            Edge(from_="summarize", to="review", kind="sequential"),
            Edge(from_="review", to="revise", kind="sequential"),
            Edge(from_="revise", to="format", kind="sequential"),
        ],
    ),
}

result = run_tracedge(
    variants=variants,
    llm=ResearchLLM(),
    seed=42,
    max_search_iterations=10,
    env_kind="tool",
)
```

**Output:**
```
Status:           converged
Best variant:     with_review
Skills extracted: 10
Episodes saved:   10
```

**What happened:** The `with_review` workflow (research → summarize → review → revise → format) produced higher-quality output. The full pipeline was extracted as a reusable skill.

---

## 5. Tool-Augmented Agent with Skill Reuse

**Problem:** Agents that use tools重复 the same successful patterns but don't learn from them.

**Solution:** AutoHarness detects repeated tool-use patterns and compiles them into skills that skip the LLM entirely.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class ToolLLM:
    def chat(self, prompt: str) -> str:
        return "read_file"

variants = {
    "basic": UPIR(
        entry="scan",
        nodes={
            "scan": UPIRNode(kind="act", node_id="scan", tool="read_file"),
            "process": UPIRNode(kind="harness_call", node_id="process", harness_id="parser"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
        },
        edges=[
            Edge(from_="scan", to="process", kind="sequential"),
            Edge(from_="process", to="write", kind="sequential"),
        ],
        harness_table={"parser": "result = inputs.get('data', '')"},
    ),
    "validated": UPIR(
        entry="scan",
        nodes={
            "scan": UPIRNode(kind="act", node_id="scan", tool="read_file"),
            "parse": UPIRNode(kind="harness_call", node_id="parse", harness_id="parser"),
            "validate": UPIRNode(kind="harness_call", node_id="validate", harness_id="validator"),
            "write": UPIRNode(kind="act", node_id="write", tool="write_file"),
        },
        edges=[
            Edge(from_="scan", to="parse", kind="sequential"),
            Edge(from_="parse", to="validate", kind="sequential"),
            Edge(from_="validate", to="write", kind="sequential"),
        ],
        harness_table={
            "parser": "result = inputs.get('data', '')",
            "validator": "result = {'valid': True}",
        },
    ),
}

result = run_tracedge(
    variants=variants,
    llm=ToolLLM(),
    seed=42,
    max_search_iterations=10,
    env_kind="tool",
)
```

**Output:**
```
Status:           converged
Best variant:     validated
Skills extracted: 7
Episodes saved:   10
```

**What happened:** AutoHarness found that the validated pipeline produces better results. The "scan → parse → validate → write" pattern was extracted as a skill for future use.

---

## 6. Custom Agent from Scratch

**Problem:** Building a new agent from scratch requires experimenting with different architectures.

**Solution:** Define your variants, let AutoHarness find the best architecture, and extract the winning design as a reusable skill.

```python
from tracedge.ir.upir import UPIR, Edge, UPIRNode
from tracedge.main import run_tracedge

class MyLLM:
    def chat(self, prompt: str) -> str:
        if "plan" in prompt.lower():
            return "Step 1: Read\nStep 2: Process\nStep 3: Output"
        return "Processing..."

variants = {
    "simple": UPIR(
        entry="start",
        nodes={
            "start": UPIRNode(kind="observe", node_id="start", query="What task?"),
            "act": UPIRNode(kind="act", node_id="act", tool="execute"),
        },
        edges=[Edge(from_="start", to="act", kind="sequential")],
    ),
    "planned": UPIR(
        entry="start",
        nodes={
            "start": UPIRNode(kind="observe", node_id="start", query="What task?"),
            "plan": UPIRNode(kind="think", node_id="plan", prompt="Create a plan"),
            "act": UPIRNode(kind="act", node_id="act", tool="execute"),
            "check": UPIRNode(kind="think", node_id="check", prompt="Verify result"),
        },
        edges=[
            Edge(from_="start", to="plan", kind="sequential"),
            Edge(from_="plan", to="act", kind="sequential"),
            Edge(from_="act", to="check", kind="sequential"),
        ],
    ),
    "iterative": UPIR(
        entry="start",
        nodes={
            "start": UPIRNode(kind="observe", node_id="start", query="What task?"),
            "plan": UPIRNode(kind="think", node_id="plan", prompt="Create a plan"),
            "act": UPIRNode(kind="act", node_id="act", tool="execute"),
            "check": UPIRNode(kind="think", node_id="check", prompt="Verify result"),
            "fix": UPIRNode(kind="think", node_id="fix", prompt="Fix issues"),
        },
        edges=[
            Edge(from_="start", to="plan", kind="sequential"),
            Edge(from_="plan", to="act", kind="sequential"),
            Edge(from_="act", to="check", kind="sequential"),
            Edge(from_="check", to="fix", kind="sequential"),
            Edge(from_="fix", to="act", kind="sequential"),
        ],
    ),
}

result = run_tracedge(
    variants=variants,
    llm=MyLLM(),
    seed=42,
    max_search_iterations=15,
    env_kind="tool",
)
```

**Output:**
```
Status:           converged
Best variant:     iterative
Skills extracted: 14
Episodes saved:   15
```

**What happened:** AutoHarness discovered that the iterative architecture (plan → act → check → fix → loop) is most reliable. The full loop pattern was extracted as a reusable skill.

---

## Quick Reference

| Pattern | Code |
|---------|------|
| **Run the full loop** | `run_tracedge(variants, llm, seed)` |
| **Get best variant** | `result["best_variant"]` |
| **Get skills** | `result["skills_extracted"]` |
| **Get episodes** | `result["episodes_saved"]` |
| **Get iterations** | `result["iterations"]` |
| **Get status** | `result["status"]` — "converged", "max_iterations", or "max_failures" |

## What each result key means

| Key | Meaning |
|-----|---------|
| `status` | Why search stopped: `"converged"` (winner found), `"max_iterations"` (budget exhausted), `"max_failures"` (too many failures) |
| `best_variant` | Name of the winning variant from your `variants` dict |
| `iterations` | How many Thompson search iterations ran |
| `episodes_saved` | Number of execution traces saved to memory |
| `skills_extracted` | Number of reusable patterns compiled from the best variant's traces |
