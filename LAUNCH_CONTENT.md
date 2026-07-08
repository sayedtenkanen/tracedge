# Launch Content

## Show HN Post

**Title:** tracedge — compile winning agent traces into skills that skip the LLM

**Body:**

Hey HN — I've been working on a problem that bugs me about LLM agents: they keep calling the same model for the same task, paying tokens every time even when the solution is already known.

tracedge is a probabilistic program compiler that watches your agent succeed, extracts the winning pattern as a deterministic skill, and replays it next time — no LLM call needed.

**How it works:**

1. You define strategy variants as UPIR (Unified Policy IR) graphs
2. Thompson tree search explores them, allocating more trials to promising ones
3. On success, SkillExtractor mines the trace for reusable subgraphs
4. Skills are persisted and loaded on future runs — the VM executes them directly, skipping think nodes entirely

**The result:** same output, zero tokens on reuse.

```
Baseline (no reuse): 8 LLM calls per run
With skill reuse:    0 LLM calls per run
Success rate:        100% → 100% (no degradation)
```

**Scope:** This is same-task replay — skills are extracted from and replayed on identical task instances. It's a verified cache for agent behavior, not generalization to new tasks. Generalization to held-out variants is not yet measured.

This is built on ideas from the AutoHarness paper (arXiv:2603.03329, Lou et al., Google DeepMind) — which synthesizes constraint harnesses for agent safety — but extends it toward compiling traces into reusable, LLM-free skills.

**Tech stack:** Python 3.12+, OpenAI-compatible API, Thompson sampling, AST-based sandbox. 381 tests, mypy strict, full CI.

Would love feedback on the approach. Is trace→skill compilation a viable path to cheaper agents, or are we better off just using faster/cheaper models?

Try it (GitHub-distributed, not on PyPI):

```
pip install git+https://github.com/sayedtenkanen/tracedge.git@v0.2.1
tracedge --demo
```

GitHub: https://github.com/sayedtenkanen/tracedge

---

## X/Twitter Thread

**Tweet 1 (hook):**
We built a compiler that watches your AI agent succeed once — then replays it forever without calling the LLM.

Same output. Zero tokens.

100% fewer LLM calls on identical task patterns.

🧵👇

**Tweet 2 (problem):**
LLM agents are powerful but expensive.

Every run pays for the same reasoning tokens, even when the solution is identical.

What if the agent could learn from its own wins and skip the LLM next time?

**Tweet 3 (how):**
tracedge works in 3 steps:

1️⃣ Execute → watch the agent solve the task
2️⃣ Extract → mine the winning trace for reusable patterns
3️⃣ Replay → execute the skill directly, no LLM needed

**Tweet 4 (evidence):**
Benchmark results on 20 tasks:

• Baseline: 8 LLM calls per run
• With skill reuse: 0 LLM calls
• Success rate: unchanged (100%)

The skill contains the deterministic subgraph — act → harness_call — without think nodes.

**Scope:** Same-task replay — skills are extracted from and replayed on identical task instances. Generalization to held-out variants is not yet measured.

**Tweet 5 (tech):**
Under the hood:
• UPIR (Unified Policy IR) for representing strategies
• Thompson tree search for Bayesian exploration
• AST-based sandbox for safe execution
• SkillExtractor mines successful traces
• MemoryStore persists and loads skills across runs

**Tweet 6 (paper):**
Built on ideas from the AutoHarness paper (arXiv:2603.03329, Lou et al.) — which auto-synthesizes constraint harnesses for agent safety.

We extend it: instead of just safety wrappers, we compile execution traces into reusable, LLM-free skills.

**Tweet 7 (CTA):**
Open source, MIT licensed. 381 tests, mypy strict, full CI.

If you're building LLM agents and want to cut token costs on repeated tasks, give it a try:

pip install git+https://github.com/sayedtenkanen/tracedge.git@v0.2.1

https://github.com/sayedtenkanen/tracedge

Feedback welcome 🙏
