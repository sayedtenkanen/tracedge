# AutoHarness — Marketing Plan

## Product Positioning

**AutoHarness** is an open-source probabilistic program compiler for AI agents. It automatically discovers, compiles, and reuses successful behavioral patterns from LLM execution traces — turning one-shot successes into reliable, reusable subprograms.

**Based on:** Inspired by [arXiv:2603.03329](https://arxiv.org/abs/2603.03329) (Lou et al., Google DeepMind, 2026)

## One-Liner

> AutoHarness lets AI agents learn from their own success — automatically extracting, compiling, and reusing winning strategies.

## Elevator Pitch (30 seconds)

LLMs are powerful but inconsistent. AutoHarness solves this by watching LLM executions, detecting repeated successful patterns, and compiling them into reusable skills. Think of it as a compiler that learns from execution — it observes what works, packages it into a skill, and reuses it. The result: more reliable agents, lower cost, and continuous self-improvement without human intervention.

## Key Differentiators

| Feature | AutoHarness | LangGraph | DSPy | AutoGen |
|---------|------------|-----------|------|---------|
| **Automatic skill extraction** | Yes — from execution traces | No | No | No |
| **Reusable subprograms** | Yes — compiled skills | No | Partial (modules) | No |
| **Safety sandboxing** | AST-based, no network/filesystem | None | None | None |
| **Zero human labeling** | Yes | Yes | Partial (signatures) | Yes |
| **Works with any LLM** | Yes — any chat interface; OpenAI adapter included | Yes | Yes | Yes |
| **Thompson search** | Yes — Bayesian exploration | No | No | No |

## Target Audience

### Primary
- **AI/ML Engineers** building LLM-powered agents
- **Researchers** in program synthesis, agent architectures, probabilistic programming
- **Developer tool companies** building coding assistants or autonomous agents

### Secondary
- **Data scientists** automating multi-step workflows
- **Academic labs** exploring agent self-improvement

## Core Value Propositions

### 1. Self-Improving Agents
AutoHarness watches your agent succeed, extracts the pattern, and makes it reusable. No human labeling, no manual prompt tuning — the agent learns from its own wins.

### 2. Safety by Design
Every skill execution runs in a sandboxed environment with AST-based guardrails. No network access, no filesystem writes, no try/except — just pure computation with enforced effect boundaries.

### 3. Bayesian Search Over Strategies
Instead of brute-force search, AutoHarness uses Thompson sampling to explore the strategy space — allocating more trials to promising approaches while still exploring alternatives.

### 4. Model-Agnostic
Works with any LLM exposing a chat interface — OpenAI adapter included. Swap models without changing your agent logic.

## Technical Highlights

- **UPIR (Unified Policy IR):** A single graph representation for policies, harnesses, and skills
- **Sandboxed execution:** Thread-based isolation with restricted builtins and AST-level static analysis
- **Dual-mode reward:** Vector rewards for population search, scalar rewards for Thompson bandit updates
- **Skill lifecycle:** Extract → Execute → Prune → Persist → Reuse
- **307 tests** with full type coverage (mypy strict) and security scanning

## Use Cases

### 1. Coding Assistants
An agent that writes code. AutoHarness detects that "write test → run test → fix error" is a repeated successful pattern, compiles it into a skill, and reuses it — reducing token costs and improving reliability.

### 2. Multi-Step Workflows
An agent that researches, summarizes, and formats. AutoHarness extracts the successful research→summarize pipeline as a reusable skill for future queries.

### 3. Game Playing
An agent that plays Tic-Tac-Toe. AutoHarness discovers winning strategies through Thompson search and compiles them into deterministic skill subroutines.

### 4. Tool-Augmented Agents
An agent that reads files, processes data, and writes outputs. AutoHarness captures the successful tool-use patterns and makes them available as skills.

## Go-to-Market Strategy

### Phase 1: Research Community (Months 1-3)
- **ArXiv paper** (companion to the original)
- **Conference talks:** NeurIPS, ICML, ICLR workshops on program synthesis
- **GitHub presence:** Strong README, examples, tests
- **Target:** 50-100 stars, 5-10 contributors

### Phase 2: Developer Community (Months 3-6)
- **Blog posts:** "How to make your AI agent self-improving"
- **Tutorials:** Step-by-step guide for common use cases
- **Integration guides:** LangChain, CrewAI, AutoGen compatibility
- **Target:** 500+ stars, 50+ adopters

### Phase 3: Production (Months 6-12)
- **Enterprise features:** Persistent skill libraries, team collaboration
- **Cloud hosted version** (managed service)
- **Partner integrations:** IDE plugins, CI/CD pipelines
- **Target:** 2000+ stars, production deployments

## Content Calendar (First Month)

| Week | Content | Channel |
|------|---------|---------|
| 1 | Launch announcement + README | GitHub, Twitter/X |
| 1 | "What is AutoHarness?" explainer | Blog post |
| 2 | Tutorial: Your first self-improving agent | Blog + YouTube |
| 2 | Tic-Tac-Toe demo walkthrough | Twitter thread |
| 3 | Deep dive: Thompson search for agents | Blog post |
| 3 | Comparison: AutoHarness vs LangGraph/DSPy | Twitter thread |
| 4 | "Building a coding agent with AutoHarness" | Tutorial series |

## Metrics to Track

- **GitHub:** Stars, forks, issues, PRs, contributors
- **Adoption:** PyPI downloads, unique users
- **Quality:** Test coverage, security scan results, CI pass rate
- **Community:** Discord/Slack members, blog comments, conference citations

## Pricing Model

- **Open source (MIT):** Core library
- **Premium (future):** Managed cloud service, enterprise support, skill marketplace

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| "It's just a wrapper" | Emphasize the compiler theory, Thompson search, and sandbox — these are non-trivial |
| "LLMs are good enough now" | Position as complementary — better reliability at lower cost |
| "Security concerns" | Lead with the AST-based sandbox and restricted builtins |
| "Too academic" | Lead with practical examples (coding agents, workflow automation) |

## Success Criteria (6 months)

- [ ] 500+ GitHub stars
- [ ] 50+ production users
- [ ] 3+ blog posts / tutorials published
- [ ] 1+ conference talk accepted
- [ ] Integration with 1+ agent framework (LangChain, CrewAI, etc.)
- [ ] 100% test coverage on core modules
