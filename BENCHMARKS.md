# Benchmarks

*Generated: 2026-07-07 21:58 UTC*

**Headline:** Skill reuse reduces LLM calls at equal or better success rate.

**Reproduce:** `python -m benchmarks --categories code_gen game tool`

---

## Overall

| Metric | Baseline (no reuse) | With Skill Reuse |
|---|---|---|
| Avg success rate | 75.0% | 75.0% |
| Mean LLM calls | 11.0 | 0.0 |
| Mean LLM calls saved | — | 11.0 |
| **LLM reduction** | — | **100.0%** |
| Tasks | 20 | 20 |

## Code Gen

| Task | Success (baseline) | Success (reuse) | LLM calls (baseline) | LLM calls (reuse) | Saved |
|---|---|---|---|---|---|
| double | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| add_one | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| factorial | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| is_even | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| reverse_string | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| sum_list | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| max_of_three | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| abs_value | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| count_vowels | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| fizzbuzz_check | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |

**Code Gen summary:** LLM reduction = **100.0%**, success rate: 100.0% → 100.0%

## Game

| Task | Success (baseline) | Success (reuse) | LLM calls (baseline) | LLM calls (reuse) | Saved |
|---|---|---|---|---|---|
| tic_tac_toe_game_1 | 0.0% | 0.0% | 20.0 | 0.0 | 20.0 |
| tic_tac_toe_game_2 | 0.0% | 0.0% | 20.0 | 0.0 | 20.0 |
| tic_tac_toe_game_3 | 0.0% | 0.0% | 20.0 | 0.0 | 20.0 |
| tic_tac_toe_game_4 | 0.0% | 0.0% | 20.0 | 0.0 | 20.0 |
| tic_tac_toe_game_5 | 0.0% | 0.0% | 20.0 | 0.0 | 20.0 |

**Game summary:** LLM reduction = **100.0%**, success rate: 0.0% → 0.0%

## Tool

| Task | Success (baseline) | Success (reuse) | LLM calls (baseline) | LLM calls (reuse) | Saved |
|---|---|---|---|---|---|
| write_hello | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| write_and_read | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| file_operations | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| nested_write | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |
| multi_step_tool | 100.0% | 100.0% | 8.0 | 0.0 | 8.0 |

**Tool summary:** LLM reduction = **100.0%**, success rate: 100.0% → 100.0%

---

## Reproduction

```bash
# Full benchmark suite
python -m benchmarks

# Code generation tasks only
python -m benchmarks --categories code_gen

# Game tasks only
python -m benchmarks --categories game

# Fewer seeds for faster iteration
python -m benchmarks --seeds 42 43 44
```

## Methodology

- **Phase 1 (Training):** Run baseline variants (think → harness_call) to extract and persist skills via `SkillExtractor`.
- **Phase 2a (Baseline):** Run baseline variants again without skill reuse — each rollout calls the LLM for think nodes.
- **Phase 2b (Reuse):** Run reuse variants (skill_call only) with persisted skills loaded — deterministic execution, no LLM calls.
- Each task runs across 5 random seeds.
- Success = Thompson search converges (posterior mean >= 0.8) on the best variant.
- LLM calls = count of think/branch events in the execution trace.
- LLM calls saved = difference between baseline and reuse LLM call counts.
