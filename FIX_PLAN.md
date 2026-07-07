# FIX_PLAN.md — Handover Work Order: From Plumbing to Product

**Audience:** any agent (or human) picking up this work cold, with no access to the
conversation that produced this document. Everything you need is in this file, the
repo, and `AGENTS.md`. Read `AGENTS.md` first — it defines the mandatory workflow
(TDD red→green→refactor, branch per unit of work, PR-only merges, mypy strict,
ruff, pre-commit hooks, CI must pass).

**Mission:** AutoHarness's docs and marketing claim a self-improving agent loop
("the system learns from its own wins"). A code review on 2026-07-07 found the
core loop does not yet do this — the plumbing is real and well-tested, but the
learning signal is absent. This plan closes that gap, produces benchmark evidence,
and prepares launch. **Do not start Phase 5 (launch) until Phase 1's acceptance
test passes.**

**Progress tracking:** check the boxes in this file as you complete tasks, and
update it in the same PR as the work. Keep the Status table in `README.md` and
`AGENTS.md` consistent with reality.

---

## Part 1 — Findings (verify these yourself before coding)

Do not take this document's word for it. Each finding lists evidence and a
verification step. If a finding no longer reproduces (someone may have fixed it),
skip its tasks and note that in the PR.

### F1. `act` nodes never touch the environment
`VM._step_act` (`src/autoharness/runtime/vm.py`, `_step_act` method) records the
tool name and args into state and the trace, but never calls
`environment.step(...)` or any tool. `run_autoharness`
(`src/autoharness/main.py`, inside `rollout`) constructs `VM(..., environment=None)`.
**Verify:** read both functions; grep `environment` in `vm.py` — it is stored in
`__init__` and used only by `_step_harness_call`/`_step_skill_call`, never by `_step_act`.

### F2. LLM output cannot influence execution
`_step_think` stores `response` in state, but no node kind reads another node's
state to build its prompt/args (no templating/interpolation exists).
**Verify:** grep for `format(` / `{` interpolation over state in `src/autoharness/runtime/` — none.

### F3. Demo rewards are flat; the "winner" is sampling noise
`_score_success` (`src/autoharness/reward/scorer.py`) returns 1.0 only when a
`harness_call` event has verdict `"ok"`. The README quickstart and
`examples/end_to_end.py` variants contain **no** `harness_call` nodes, so
`task_success = 0` for every rollout and `value()` reduces to
`0.2*efficiency + 0.2*safety ≈ 0.39`, far below the 0.8 convergence threshold
(`SearchConfig.convergence_threshold`).
**Verify:** `python examples/end_to_end.py` — observed baseline (2026-07-07):
all episode rewards 0.388–0.396, `Status: max_iterations`, `Skills extracted: 17`
from 5 episodes. Note also: on pure efficiency the *fewer-steps* variant scores
higher, so the README's claimed output (`best_variant == "thorough"`) is not a
result the scoring can systematically produce.

### F4. Skill extraction is an artifact counter, and skills are discarded
`SkillExtractor.detect_patterns` (`src/autoharness/skills/extractor.py`) counts
repeated node-id windows over **concatenated reruns of the same graph**, so
patterns trivially repeat (hence 17 "skills" from 5 episodes). In
`run_autoharness`, `extractor.skill_table` is never injected into any
`upir.skill_table`, never saved to `MemoryStore`, and never reused. The
documented lifecycle "Extract → Persist → Reuse" stops at Extract.
**Verify:** grep `skill_table` in `src/autoharness/main.py` and
`src/autoharness/memory/store.py` — the store has `save_skill_stats` but no
`save_skill`, and `main.py` drops the extractor after counting.

### F5. No benchmark evidence
`MARKETING.md` claims "more reliable agents, lower cost" with no numbers anywhere
in the repo. There is no `benchmarks/` directory.

### F6. Competitor table is inaccurate
`MARKETING.md` "Key Differentiators" table claims DSPy has no automatic program
optimization — false (DSPy compiles/optimizes LM programs: MIPRO, GEPA). The
real prior art for trace→skill extraction — Voyager's skill library, Agent
Workflow Memory (AWM), ADAS — is not mentioned. Target audience (researchers,
AI engineers) will catch this immediately.

### F7. PyPI name collision (external fact — cannot be discovered from the repo)
The package name `autoharness` on PyPI is **taken and actively maintained**:
v1.4.7 released 2026-07-06, maintainer `softwaresalt`, an "agent harness
framework" for AI coding assistants — an adjacent space, which makes the
collision worse. PyPI normalizes names, so `auto-harness` / `auto_harness`
resolve to the same name. A rename is required before publishing.
**Verify:** fetch https://pypi.org/project/autoharness/

### F8. The arXiv citation is real but describes a narrower system (external fact)
arXiv:2603.03329 verified to exist (fetched 2026-07-07): "AutoHarness: improving
LLM agents by automatically synthesizing a code harness" — Xinghua Lou, Miguel
Lázaro-Gredilla, Antoine Dedieu, Carter Wendelken, Wolfgang Lehrach, Kevin P.
Murphy; submitted 2026-02-10. The paper is about auto-synthesizing **constraint
harnesses** (protective code wrappers) — not about compiling traces into
reusable skills. This repo's docs describe the broader ambition as if it were
the paper's. Positioning must say "implements and extends," not "based on."

---

## Part 2 — Non-negotiables (context for every decision below)

- **Headline claim to build toward** (frozen; every demo/doc must support it):
  *"Compiles winning agent traces into deterministic skills that skip the LLM —
  same output, fewer tokens."* Token-cost reduction is the sellable wedge.
- **Honesty is the launch strategy.** The repo's credibility asset is its
  engineering hygiene (309 tests, mypy strict, security scanning, CI). One
  reader discovering that a documented output is fabricated destroys that. When
  in doubt, under-claim.
- **Workflow:** per `AGENTS.md` — feature branch per phase or sub-task
  (suggested: `fix/phase1-real-loop`, `fix/phase2-skill-reuse`, ...), TDD with
  the two-commit pattern (`test(scope): ...` then `feat(scope): ...`), PR to
  `main`, CI green before merge. Never push to `main` directly. Start branches
  from up-to-date `main`, not from `docs/end-to-end-use-cases`.
- **Testing an LLM locally:** `AGENTS.md` documents a local Ollama endpoint;
  scripted/fake LLMs (objects with `chat(prompt) -> str`) are fine and preferred
  for deterministic tests — see existing test suite for the pattern.

---

## Part 3 — The plan

### Phase 0 — Blocking decisions (ASK THE USER — do not decide unilaterally)

- [ ] **0.1 New package name.** Required because of F7. Propose 3–5 candidates
      with PyPI-availability + GitHub + domain checks done (starting points:
      `skillforge`, `tracecompile`, `harnessc`, `skillc`, `replaykit`), then ask
      the user to choose. Everything in Phase 5 depends on this; Phases 1–4 can
      proceed under the current name.
- [ ] **0.2 Confirm scope.** The user's goal is revenue ("make a killing"). This
      plan's scope is: make the OSS library honest and demonstrably valuable,
      then launch. Hosted-service work is explicitly out of scope (see Deferred).

### Phase 1 — Make the loop actually learn (~1 week) — fixes F1, F2, F3

Branch: `fix/phase1-real-loop`.

- [ ] **1.1 Wire environment into `act` nodes.** `_step_act` calls the
      environment when present (follow the existing `Environment` protocol in
      `src/autoharness/environment/protocol.py`); record `result`, `legal`, and
      an outcome verdict in the trace event. Add
      `env_factory: Callable[[int], Any] | None` to `run_autoharness`; create/reset
      a fresh environment per rollout seeded with the rollout seed. Keep
      `environment=None` working (pure-LLM tasks).
- [ ] **1.2 State→node data flow (most important single fix).** Template
      interpolation for `think` prompts, `act` args, and `branch` conditions:
      `"{node_id.key}"` resolved from `State` at step time. Missing keys must
      surface as explicit trace errors, not silent empty strings. TDD: write
      failing tests for interpolation in think/act/branch first.
- [ ] **1.3 Real success signal.** Extend `score_trace` so `task_success` can
      come from environment-reported terminal outcomes (e.g. game won, tool
      verification passed) in addition to `harness_call` verdicts. The trace
      event schema for env outcomes is yours to design — document the verdict
      vocabulary in the docstring as the existing code does.
- [ ] **1.4 Convergence integration test.** Two variants with genuinely
      different success rates under a scripted LLM; assert the better one wins
      with `status == "converged"` for ≥3 fixed seeds
      (`tests/integration/test_main.py`).
- [ ] **1.5 Docs that cannot lie.** Replace the README quickstart with a task
      that has a verifiable success signal. Extend
      `scripts/verify_doc_snippets.py` to **execute** the quickstart and assert
      the documented outputs; wire it into `.github/workflows/ci.yml`.

**Acceptance (all must hold):** `python examples/end_to_end.py` shows a reward
spread of roughly 0.2→0.9 across variants, reaches `converged`, picks the same
(genuinely better) winner across seeds; `pytest tests/` green; doc-snippet check
green in CI.

#### Phase 1 punch list (added 2026-07-07 after review of in-progress work)

Tasks 1.1–1.4 are substantially implemented in the working tree (see Handover
Log entry of the same date) but NOT committed, NOT on the right branch, and
NOT complete. Finish these before opening the Phase 1 PR:

- [ ] **1.6 Move the work to the right branch.** The implementation currently
      sits uncommitted on `docs/end-to-end-uses-cases`. Create
      `fix/phase1-real-loop` off up-to-date `main`, bring the changes over
      (e.g. `git stash` → checkout new branch → `git stash pop`), and commit in
      reviewable units (tests and implementation per TDD convention as far as
      the existing work allows; do not rewrite working code just to fake a
      red/green history).
- [ ] **1.7 Surface missing template keys as trace errors.** In
      `VM._resolve_templates` (`src/autoharness/runtime/vm.py`), an unresolved
      `{node_id.key}` currently passes through silently as literal text. Plan
      task 1.2 requires missing references to produce an explicit error in the
      step's trace event (e.g. `"error": "unresolved template ref: {think.response}"`).
      TDD: failing test first in `tests/runtime/test_vm.py`.
- [ ] **1.8 Strengthen the convergence test.** `test_convergence_good_wins`
      (`tests/integration/test_main.py`) asserts only the winner; also assert
      `result["status"] == "converged"` per this phase's acceptance criteria.
- [ ] **1.9 Finish task 1.5 — executable doc verification.** Extend
      `scripts/verify_doc_snippets.py` to extract and *execute* the README
      quickstart and assert its documented outputs (`best_variant == "good"`,
      `episodes_saved` matches); add the script to `.github/workflows/ci.yml`.
- [ ] **1.10 Harden the scorer against non-dict `info`.** In
      `_score_success` (`src/autoharness/reward/scorer.py`),
      `env_result.get("info", {})` returns `None` when the key exists with a
      `None` value, and the chained `.get` crashes. Use
      `(env_result.get("info") or {})`. Failing test first.
- [ ] **1.11 (Optional, may defer to Phase 3.)** `ToolEnvironment.step` sets
      `info["success"] = True` for any successful `write_file`, which the
      scorer counts as full task success. Note this as a known-generous signal
      in the scorer docstring now; tighten when the benchmark suite defines
      real ground truth.

### Phase 2 — Make skills real (~1 week) — fixes F4

Branch: `fix/phase2-skill-reuse`. Depends on Phase 1.

- [ ] **2.1 Meaningful extraction.** Mine patterns per-episode from *successful*
      traces only; dedupe overlapping/nested windows (keep maximal patterns).
      Target: the end-to-end demo extracts 1–2 meaningful skills, not 17 artifacts.
- [ ] **2.2 Persist skills.** Add `MemoryStore.save_skill(skill_id, upir)` /
      `load_skills()` (JSON, consistent with existing store patterns); wire into
      `run_autoharness` alongside the existing `save_skill_stats`.
- [ ] **2.3 Close the reuse loop.** `run_autoharness(..., reuse_skills=True)`
      loads stored skills into `upir.skill_table` so `skill_call` nodes (already
      implemented in the VM) can fire; integrate `SkillPruner`
      (`src/autoharness/skills/pruner.py`) so low-performing skills are dropped.
- [ ] **2.4 LLM-free replay (the money feature).** When a skill's nodes have
      fully resolved args and no `think`/`branch` nodes requiring an LLM, replay
      it without calling `llm.chat`. Count LLM calls; return `llm_calls_saved`.
- [ ] **2.5 Richer result dict.** Add per-variant posterior means, total LLM
      calls, `llm_calls_saved`, and token usage when the adapter exposes it
      (`src/autoharness/intelligence/llm_client.py`).

**Acceptance:** an integration test proves: run 1 extracts and persists a skill;
run 2 with `reuse_skills=True` loads it and completes the same task family with
strictly fewer LLM calls at equal-or-better success rate.

### Phase 3 — Evidence (~1–2 weeks) — fixes F5. Parallel with Phase 4.

Branch: `fix/phase3-benchmarks`. Depends on Phase 2.

- [ ] **3.1 Eval suite.** `benchmarks/` with 30–50 tasks that have ground truth:
      code-generation tasks verified by unit tests via `harness_call`, plus
      tic-tac-toe winrate vs a random opponent using `GameEnvironment`.
- [ ] **3.2 Reproducible report.** One script → `BENCHMARKS.md`: success rate
      and LLM-call/token cost, with vs without skill reuse, 5 seeds, mean ± std,
      exact reproduction command at the top.
- [ ] **3.3 Real-LLM run.** Same suite via the OpenAI adapter against a cheap
      hosted model (needs `OPENAI_API_KEY` from the user) and/or the local
      Ollama endpoint from `AGENTS.md`. Publish the actual numbers, whatever
      they are.

**Acceptance:** one honest headline number of the form *"X% fewer LLM calls at
equal success rate on our N-task suite"* backed by a committed, reproducible script.

### Phase 4 — Docs honesty & positioning (~2–3 days) — fixes F6, F8. Parallel with Phase 3.

Branch: `fix/phase4-docs-honesty`.

- [ ] **4.1 Fix the competitor table** in `MARKETING.md`: correct the DSPy row;
      add Voyager (skill library), Agent Workflow Memory, ADAS as prior art with
      honest deltas. Reposition as complementary: "DSPy optimizes prompts; we
      compile execution traces into LLM-free skills."
- [ ] **4.2 Clarify the paper relationship** in `README.md` + `MARKETING.md` per
      F8: "implements the harness-synthesis idea and extends it toward
      trace-compiled skills."
- [ ] **4.3 Replace every illustrative number** in `README.md`, `USE_CASES.md`,
      `USER_MANUAL.md` with captured real output (enforced by 1.5's CI check —
      extend coverage to these files' runnable snippets).

### Phase 5 — Distribution & launch (~1 week) — fixes F7. Only after Phases 1–4.

Branch: `fix/phase5-launch`. **Hard gate: Phase 1 acceptance must be green.**

- [ ] **5.1 Rename** repo + package to the Phase 0.1 name: `pyproject.toml`,
      `src/` package dir, all imports, URLs, `AGENTS.md`, badges. Keep a GitHub
      repo redirect from the old name.
- [ ] **5.2 Publish to PyPI** at 0.2.0 via GitHub Actions trusted publishing
      (new workflow; tag-triggered).
- [ ] **5.3 Demo GIF** (vhs or asciinema): run 1 discovers a skill, run 2 reuses
      it, LLM-call counter visibly drops. Embed at the top of the README.
- [ ] **5.4 Launch content.** Lead with the Phase 3 benchmark writeup (Show HN +
      X thread), follow with a "we implemented and extended the AutoHarness
      paper" post. Then execute the content calendar already in `MARKETING.md`.
      Publishing posts is outward-facing — get user sign-off on final copy.
- [ ] **5.5 Track** stars, PyPI downloads, inbound per `MARKETING.md` metrics.

### Explicitly deferred (post-launch revenue experiments — do not build now)

- Hosted skill registry + trace/cost observability (LangSmith-style play)
- Enterprise guardrails product (the paper's actual pitch: synthesized
  constraint harnesses for agent reliability/compliance)
- Framework integrations (LangChain / CrewAI adapters)

---

## Part 4 — Sequencing, effort, and stop conditions

- Order: 0 → 1 → 2 → {3 ∥ 4} → 5. Roughly 4–6 weeks part-time.
- **Stop and ask the user when:** choosing the package name (0.1); anything
  requiring paid API keys (3.3); publishing anything outward-facing (5.2, 5.4);
  or if a Part 1 finding doesn't reproduce and it changes a phase's scope.
- **Definition of done for the whole plan:** all boxes checked, CI green on
  `main`, `BENCHMARKS.md` numbers reproducible from a clean clone, README
  quickstart executes verbatim in CI, package installable from PyPI under the
  new name.

---

## Part 5 — Execution protocol (how to complete this plan)

### Session startup (every working session)

1. Read `AGENTS.md`, then this file in full, including the Handover Log below.
2. `git checkout main && git pull`. Confirm a clean baseline **before** changing
   anything: `pytest tests/`, `ruff check src/ tests/`, `mypy src/`. If the
   baseline is already broken, fix or report that first — do not build on red.
3. Pick the first unchecked task whose dependencies are met (order in Part 3 is
   the dependency order). Re-verify its Part 1 finding before writing code.

### Working a task

- One branch per phase (names in Part 3); within a phase, do sub-tasks in order.
- Strict TDD per `AGENTS.md`: write failing tests, commit
  (`test(scope): add failing tests for X`); implement minimally, commit
  (`feat(scope): implement X to pass tests`); refactor while green.
- Never weaken, skip, or delete an existing test to get to green. If a test
  seems wrong, say so in the PR and change it in its own commit with reasoning.
- Never fabricate output. Anything this plan requires you to "capture" (demo
  output, benchmark numbers, README snippets) must come from actually running
  the command, and the command must be committed alongside the output.
- Before every push, run the full local gate:
  `pytest tests/ && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/`
  plus `bash scripts/security-scan.sh` when touching dependencies or sandbox code.

### PR process

- Push the branch and open a PR to `main` (e.g. `gh pr create`). Direct pushes
  to `main` are prohibited (see `AGENTS.md`).
- PR description must state: which task IDs it implements (e.g. "Implements
  1.1–1.3"), which findings it fixes (e.g. "Fixes F1, F3"), and — for a phase's
  final PR — the **pasted, real output** of that phase's acceptance commands.
- Check this file's boxes in the same PR as the work. A box may only be checked
  when the change is merged-quality: tests included, CI green.
- Merge via GitHub after CI passes, then delete the branch and return to `main`.

### When reality disagrees with the plan

- If a Part 1 finding doesn't reproduce: skip its tasks, note it in the PR and
  in the Handover Log.
- If a task's design turns out wrong in detail (e.g. a better templating syntax
  than `{node_id.key}`): improve it, document the deviation in the PR. Detail
  deviations are fine; **scope** changes (dropping a phase, adding a feature,
  changing the headline claim) require asking the user.
- If a task exceeds ~2× its effort estimate, stop, write down what's hard in
  the Handover Log, and surface it to the user rather than grinding.

### Session shutdown (every working session)

1. Leave the tree clean: work committed on its branch, nothing half-edited.
2. Update this file's checkboxes to match merged reality.
3. Append a dated entry to the Handover Log: what was completed (with PR
   links/numbers), current branch and its state, the exact next action, and any
   surprises or open questions for the user.

---

## Handover Log

Newest entry first. Every session appends one.

### 2026-07-07 (later) — Phase 1 in-progress work reviewed; punch list added

- **Done:** reviewed an uncommitted Phase 1 implementation found in the working
  tree (author unknown — not produced in the review session). Verified against
  the plan and the full local gate:
  - `pytest tests/` → 310 passed; `ruff check` clean; `mypy src/` strict clean.
  - `python examples/end_to_end.py` → `Status: converged`, `Best variant: good`,
    3 iterations, episode rewards 1.0 (baseline before: flat ~0.39,
    `max_iterations`, noise winner). Demo honestly reports `Skills extracted: 0`.
  - Environment wiring (1.1), templating (1.2), multi-signal scorer (1.3),
    convergence test (1.4), and an honest README quickstart (part of 1.5) are
    implemented. Call signatures verified against
    `src/autoharness/environment/protocol.py` and both built-in environments.
- **Not done / found in review:** see the Phase 1 punch list (tasks 1.6–1.11)
  added under Phase 1. Summary: work is on the wrong branch and uncommitted
  (1.6); missing template refs fail silently instead of erroring (1.7);
  convergence test doesn't assert `status == "converged"` (1.8); executable
  doc verification + CI wiring still missing (1.9); scorer crashes on
  `info=None` from third-party envs (1.10); write_file success signal is
  known-generous (1.11, may defer).
- **Branch state:** `docs/end-to-end-use-cases` checked out. Uncommitted
  modifications: `src/autoharness/runtime/vm.py`,
  `src/autoharness/reward/scorer.py`, `src/autoharness/main.py`,
  `examples/end_to_end.py`, `README.md`, `tests/integration/test_main.py`.
  Untracked: `FIX_PLAN.md`. **Do not discard or reset this tree** — it contains
  the Phase 1 implementation.
- **Next action:** task 1.6 first (move work to `fix/phase1-real-loop` off
  `main`, commit, include FIX_PLAN.md), then 1.7–1.10 via TDD, then open the
  Phase 1 PR with the acceptance-command outputs pasted in the description.
  Only check boxes 1.1–1.5 when that PR is merged.
- **Open questions for the user:** unchanged from the previous entry (package
  name for 0.1; API key availability for 3.3).

### 2026-07-07 — Plan created (review session)

- **Done:** full code/docs review; findings F1–F8 established and externally
  verified where applicable (PyPI collision, arXiv paper); this plan written.
  Baseline captured: `python examples/end_to_end.py` → rewards 0.388–0.396,
  `Status: max_iterations`, 17 skills from 5 episodes.
- **Branch state:** `docs/end-to-end-use-cases` checked out; this file is the
  only new/uncommitted change. Commit it (or move it to a fresh branch off
  `main`) before starting work.
- **Next action:** Phase 0.1 — check name candidates on PyPI/GitHub and ask the
  user to choose; in parallel, start Phase 1 on `fix/phase1-real-loop` (task
  1.1, re-verify F1 first).
- **Open questions for the user:** package name choice (0.1); whether an
  `OPENAI_API_KEY` will be available for task 3.3 or benchmarks should target
  the local Ollama endpoint only.
