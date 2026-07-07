"""Benchmark task definitions — code generation, tic-tac-toe, tool tasks.

Design:
- Each task has a "baseline" variant (multi-step flow) and a "reuse" variant
  (skill_call that reuses a previously learned pattern).
- During training, we create skills from the known common patterns
  (observe→act for games, act→harness_call for code-gen).
- The test phase measures: baseline (no reuse) vs reuse (with persisted skills).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from autoharness.ir.upir import UPIR, UPIRNode


@dataclass
class Task:
    """A single benchmark task."""

    name: str
    category: str  # "code_gen", "game", "tool"
    baseline_variants: dict[str, UPIR]
    reuse_variants: dict[str, UPIR]
    # The skill to persist during training (skill_id → UPIR)
    training_skills: dict[str, UPIR]
    llm: Any
    env_kind: str  # "tool" or "game"
    env_factory: Callable[[int], Any] | None = None
    seeds: list[int] = field(default_factory=lambda: [42, 43, 44, 45, 46])
    max_total_failures: int = 10
    success_threshold: float = 0.8

    def passes(self, result: dict[str, Any]) -> bool:
        return (
            result["status"] == "converged"
            and result["best_variant"] is not None
            and result.get("per_variant_stats", {})
            .get(result["best_variant"], {})
            .get("posterior_mean", 0.0)
            >= self.success_threshold
        )


# ---------------------------------------------------------------------------
# Scripted LLMs
# ---------------------------------------------------------------------------


class PlanThenActLLM:
    """Returns a plan string on think prompts, 'ok' on branch prompts."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        if "true or false" in prompt.lower():
            return "true"
        return "I will implement this step."


class SmartTicTacToeLLM:
    """Picks center (4) if available, else first legal move."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return "4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_code_gen_task(
    name: str,
    harness_code: str,
    seeds: list[int] | None = None,
) -> Task:
    """Create a code-gen task.

    Baseline: think → act → think → harness_call (4 events, 2 LLM calls).
    Reuse: skill_call (act→harness_call) → no think nodes → 0 LLM calls.
    Training skill: act→harness_call subgraph extracted from the baseline.
    """
    # The "learned" skill: just the act→harness_call portion
    skill_upir = UPIR(
        entry="act1",
        nodes={
            "act1": UPIRNode(
                kind="act",
                node_id="act1",
                tool="write_file",
                args={"path": "/tmp/bench.txt", "content": "prepared"},  # nosec B108
            ),
            "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
        },
        edges=[{"from": "act1", "to": "h1", "kind": "sequential"}],
        harness_table={"h": harness_code},
    )

    baseline = UPIR(
        entry="think1",
        nodes={
            "think1": UPIRNode(
                kind="think",
                node_id="think1",
                prompt="Plan the approach for this task.",
            ),
            "act1": UPIRNode(
                kind="act",
                node_id="act1",
                tool="write_file",
                args={"path": "/tmp/bench.txt", "content": "{think1.response}"},  # nosec B108
            ),
            "think2": UPIRNode(
                kind="think",
                node_id="think2",
                prompt="Review the work: {act1.tool_output}",
            ),
            "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
        },
        edges=[
            {"from": "think1", "to": "act1", "kind": "sequential"},
            {"from": "act1", "to": "think2", "kind": "sequential"},
            {"from": "think2", "to": "h1", "kind": "sequential"},
        ],
        harness_table={"h": harness_code},
    )

    reuse = UPIR(
        entry="s1",
        nodes={
            "s1": UPIRNode(kind="skill_call", node_id="s1", skill_id="skill_1"),
        },
        edges=[],
        skill_table={},
    )

    return Task(
        name=name,
        category="code_gen",
        baseline_variants={"impl": baseline},
        reuse_variants={"impl_reuse": reuse},
        training_skills={"skill_1": skill_upir},
        llm=PlanThenActLLM(),
        env_kind="tool",
        seeds=seeds or [42, 43, 44, 45, 46],
    )


def _make_game_task(
    name: str,
    seeds: list[int] | None = None,
) -> Task:
    """Create a tic-tac-toe task.

    Baseline: think → observe → act → think → observe → act (6 events, 2 LLM calls).
    Reuse: skill_call (observe→act) → no think nodes → 0 LLM calls.
    """
    from autoharness.environment.game_env import GameEnvironment

    # The "learned" skill: observe→act (deterministic game play)
    skill_upir = UPIR(
        entry="obs1",
        nodes={
            "obs1": UPIRNode(kind="observe", node_id="obs1", query="Board"),
            "act1": UPIRNode(kind="act", node_id="act1", tool="place_move"),
        },
        edges=[{"from": "obs1", "to": "act1", "kind": "sequential"}],
    )

    baseline = UPIR(
        entry="think1",
        nodes={
            "think1": UPIRNode(
                kind="think",
                node_id="think1",
                prompt="What move should I make?",
            ),
            "obs1": UPIRNode(kind="observe", node_id="obs1", query="Board"),
            "act1": UPIRNode(kind="act", node_id="act1", tool="place_move"),
            "think2": UPIRNode(
                kind="think",
                node_id="think2",
                prompt="What move should I make next?",
            ),
            "obs2": UPIRNode(kind="observe", node_id="obs2", query="Board"),
            "act2": UPIRNode(kind="act", node_id="act2", tool="place_move"),
        },
        edges=[
            {"from": "think1", "to": "obs1", "kind": "sequential"},
            {"from": "obs1", "to": "act1", "kind": "sequential"},
            {"from": "act1", "to": "think2", "kind": "sequential"},
            {"from": "think2", "to": "obs2", "kind": "sequential"},
            {"from": "obs2", "to": "act2", "kind": "sequential"},
        ],
    )

    reuse = UPIR(
        entry="s1",
        nodes={
            "s1": UPIRNode(kind="skill_call", node_id="s1", skill_id="skill_1"),
        },
        edges=[],
        skill_table={},
    )

    return Task(
        name=name,
        category="game",
        baseline_variants={"player": baseline},
        reuse_variants={"player_reuse": reuse},
        training_skills={"skill_1": skill_upir},
        llm=SmartTicTacToeLLM(),
        env_kind="game",
        env_factory=lambda _seed: GameEnvironment(),
        seeds=seeds or [42, 43, 44, 45, 46],
    )


def _make_tool_task(
    name: str,
    harness_code: str,
    seeds: list[int] | None = None,
) -> Task:
    """Create a tool task.

    Baseline: think → act → think → harness_call (4 events, 2 LLM calls).
    Reuse: skill_call (act→harness_call) → 0 LLM calls.
    """
    skill_upir = UPIR(
        entry="act1",
        nodes={
            "act1": UPIRNode(
                kind="act",
                node_id="act1",
                tool="write_file",
                args={"path": "/tmp/bench_tool.txt", "content": "prepared"},  # nosec B108
            ),
            "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
        },
        edges=[{"from": "act1", "to": "h1", "kind": "sequential"}],
        harness_table={"h": harness_code},
    )

    baseline = UPIR(
        entry="think1",
        nodes={
            "think1": UPIRNode(
                kind="think",
                node_id="think1",
                prompt="What tool should I use?",
            ),
            "act1": UPIRNode(
                kind="act",
                node_id="act1",
                tool="write_file",
                args={"path": "/tmp/bench_tool.txt", "content": "{think1.response}"},  # nosec B108
            ),
            "think2": UPIRNode(
                kind="think",
                node_id="think2",
                prompt="Verify the result: {act1.tool_output}",
            ),
            "h1": UPIRNode(kind="harness_call", node_id="h1", harness_id="h"),
        },
        edges=[
            {"from": "think1", "to": "act1", "kind": "sequential"},
            {"from": "act1", "to": "think2", "kind": "sequential"},
            {"from": "think2", "to": "h1", "kind": "sequential"},
        ],
        harness_table={"h": harness_code},
    )

    reuse = UPIR(
        entry="s1",
        nodes={
            "s1": UPIRNode(kind="skill_call", node_id="s1", skill_id="skill_1"),
        },
        edges=[],
        skill_table={},
    )

    return Task(
        name=name,
        category="tool",
        baseline_variants={"tool_impl": baseline},
        reuse_variants={"tool_impl_reuse": reuse},
        training_skills={"skill_1": skill_upir},
        llm=PlanThenActLLM(),
        env_kind="tool",
        seeds=seeds or [42, 43, 44, 45, 46],
    )


# ---------------------------------------------------------------------------
# Code generation tasks (10)
# ---------------------------------------------------------------------------

CODE_GEN_TASKS: list[Task] = [
    _make_code_gen_task("double", "def double(x): return x * 2\nresult = double(5) == 10"),
    _make_code_gen_task("add_one", "def add_one(x): return x + 1\nresult = add_one(41) == 42"),
    _make_code_gen_task(
        "factorial",
        "def factorial(n):\n"
        "    return 1 if n <= 1 else n * factorial(n - 1)\n"
        "result = factorial(5) == 120",
    ),
    _make_code_gen_task(
        "is_even",
        "def is_even(n): return n % 2 == 0\nresult = is_even(4) and not is_even(7)",
    ),
    _make_code_gen_task(
        "reverse_string",
        "def reverse(s): return s[::-1]\nresult = reverse('hello') == 'olleh'",
    ),
    _make_code_gen_task(
        "sum_list",
        "def sum_list(lst): return sum(lst)\nresult = sum_list([1, 2, 3, 4]) == 10",
    ),
    _make_code_gen_task(
        "max_of_three",
        "def max3(a, b, c):\n"
        "    if a >= b and a >= c: return a\n"
        "    if b >= c: return b\n"
        "    return c\n"
        "result = max3(1, 3, 2) == 3",
    ),
    _make_code_gen_task(
        "abs_value",
        "def abs_val(n): return -n if n < 0 else n\nresult = abs_val(-5) == 5 and abs_val(3) == 3",
    ),
    _make_code_gen_task(
        "count_vowels",
        "def count_vowels(s):\n"
        "    return sum(1 for c in s.lower() if c in 'aeiou')\n"
        "result = count_vowels('hello world') == 3",
    ),
    _make_code_gen_task(
        "fizzbuzz_check",
        "def fizzbuzz(n):\n"
        "    if n % 15 == 0: return 'FizzBuzz'\n"
        "    if n % 3 == 0: return 'Fizz'\n"
        "    if n % 5 == 0: return 'Buzz'\n"
        "    return str(n)\n"
        "result = fizzbuzz(15) == 'FizzBuzz' and fizzbuzz(3) == 'Fizz'"
        " and fizzbuzz(5) == 'Buzz' and fizzbuzz(7) == '7'",
    ),
]


# ---------------------------------------------------------------------------
# Game tasks (5)
# ---------------------------------------------------------------------------

GAME_TASKS: list[Task] = [
    _make_game_task("tic_tac_toe_game_1"),
    _make_game_task("tic_tac_toe_game_2", seeds=[100, 101, 102, 103, 104]),
    _make_game_task("tic_tac_toe_game_3", seeds=[200, 201, 202, 203, 204]),
    _make_game_task("tic_tac_toe_game_4", seeds=[300, 301, 302, 303, 304]),
    _make_game_task("tic_tac_toe_game_5", seeds=[400, 401, 402, 403, 404]),
]


# ---------------------------------------------------------------------------
# Tool tasks (5)
# ---------------------------------------------------------------------------

TOOL_TASKS: list[Task] = [
    _make_tool_task("write_hello", "result = True"),
    _make_tool_task("write_and_read", "result = True"),
    _make_tool_task("file_operations", "result = True"),
    _make_tool_task("nested_write", "result = True"),
    _make_tool_task("multi_step_tool", "result = True"),
]


# ---------------------------------------------------------------------------
# All tasks
# ---------------------------------------------------------------------------

ALL_TASKS: list[Task] = CODE_GEN_TASKS + GAME_TASKS + TOOL_TASKS

TASKS_BY_CATEGORY: dict[str, list[Task]] = {
    "code_gen": CODE_GEN_TASKS,
    "game": GAME_TASKS,
    "tool": TOOL_TASKS,
}
