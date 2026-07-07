# AutoHarness — Marketing Plan

## Product Positioning

**AutoHarness** is an open-source probabilistic program compiler for AI agents. It automatically discovers, compiles, and reuses successful behavioral patterns from LLM execution traces — turning one-shot successes into reliable, reusable subprograms.

**Implements and extends:** [arXiv:2603.03329](https://arxiv.org/abs/2603.03329) (Lou et al., Google DeepMind, 2026). The paper synthesizes constraint harnesses (protective code wrappers); this project extends the idea toward compiling execution traces into reusable, LLM-free skills.

## One-Liner

> AutoHarness lets AI agents learn from their own success — automatically extracting, compiling, and reusing winning strategies.

## Elevator Pitch (30 seconds)

LLMs are powerful but inconsistent. AutoHarness solves this by watching LLM executions, detecting repeated successful patterns, and compiling them into reusable skills. Think of it as a compiler that learns from execution — it observes what works, packages it into a skill, and reuses it. The result: more reliable agents, lower cost, and continuous self-improvement without human intervention.

## Key Differentiators

| Feature | AutoHarness | Voyager | DSPy | ADAS | AWM |
|---------|------------|---------|------|------|-----|
| **Trace→skill extraction** | Yes — from execution traces | Yes — code library | No (optimizes prompts) | Yes — from demos | Yes — from traces |
| **Deterministic skill replay** | Yes — compiled UPIR, no LLM | Partial (code gen) | No | No | No |
| **Safety sandboxing** | AST-based, no network/filesystem | None | None | None | None |
| **Bayesian search** | Thompson-sampling tree | No | No | No | No |
| **Model-agnostic** | Yes — any chat interface | Yes (OpenAI) | Yes | Yes | Yes |
| **Zero human labeling** | Yes | Yes | Partial (signatures) | Yes | Yes |

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
- **328 tests** with full type coverage (mypy strict) and security scanning

## Use Cases

### 1. Self-Improving Coding Agent
Define coding strategy variants (direct, with-fix, iterative). AutoHarness searches over them with Thompson sampling, finds the best one, and extracts reusable fix patterns. **One call:** `run_tracedge(variants, llm)`.

### 2. Automated Data Pipeline
Define pipeline variants (simple, validated, multi-stage). AutoHarness discovers which transformation sequence works best and extracts it as a reusable skill. No manual prompt tuning required.

### 3. Game Strategy Discovery
Define game strategies (center-first, corner-first, adaptive). Thompson search finds the winning strategy through Bayesian exploration. Winning patterns are compiled into deterministic skills.

### 4. Multi-Step Research Assistant
Define research workflows (linear, with-review, iterative). AutoHarness finds which workflow produces the best output and extracts the full pipeline as a reusable skill.

### 5. Tool-Augmented Agent with Skill Reuse
Define tool-use patterns (basic, validated). AutoHarness detects successful tool-use sequences and compiles them into skills that skip the LLM entirely — reducing token cost.

### 6. Custom Agent from Scratch
Define architecture variants (simple, planned, iterative). AutoHarness discovers which architecture is most reliable and extracts the winning design as a reusable skill.

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
