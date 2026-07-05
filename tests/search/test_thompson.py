"""Tests for Thompson Tree Search — Beta posteriors, sampling, convergence, search loop."""

from __future__ import annotations

import random

from autoharness.ir.harness import Harness
from autoharness.search.thompson import (
    Branch,
    SearchConfig,
    ThompsonTreeSearch,
    is_converged,
    thompson_sample,
    update_posterior,
)


def _make_harness(code: str = "return x", kind: str = "action_filter") -> Harness:
    return Harness(kind=kind, code=code)


class TestUpdatePosterior:
    """Posterior update: alpha += v, beta += (1-v)."""

    def test_perfect_reward(self) -> None:
        alpha, beta = 1.0, 1.0
        alpha, beta = update_posterior(alpha, beta, 1.0)
        assert alpha == 2.0
        assert beta == 1.0

    def test_zero_reward(self) -> None:
        alpha, beta = 1.0, 1.0
        alpha, beta = update_posterior(alpha, beta, 0.0)
        assert alpha == 1.0
        assert beta == 2.0

    def test_half_reward(self) -> None:
        alpha, beta = 1.0, 1.0
        alpha, beta = update_posterior(alpha, beta, 0.5)
        assert alpha == 1.5
        assert beta == 1.5

    def test_accumulates(self) -> None:
        alpha, beta = 1.0, 1.0
        alpha, beta = update_posterior(alpha, beta, 0.8)
        alpha, beta = update_posterior(alpha, beta, 0.6)
        assert alpha == 2.4
        assert beta == 1.6


class TestThompsonSample:
    """Thompson sampling selects the branch with highest sampled theta."""

    def test_picks_best_branch(self) -> None:
        rng = random.Random(42)
        branches = [
            Branch(harness=_make_harness("a"), alpha=10.0, beta=1.0),
            Branch(harness=_make_harness("b"), alpha=1.0, beta=10.0),
        ]
        selected = thompson_sample(branches, rng)
        assert selected is branches[0]

    def test_deterministic_with_seed(self) -> None:
        branches = [
            Branch(harness=_make_harness("a"), alpha=5.0, beta=5.0),
            Branch(harness=_make_harness("b"), alpha=5.0, beta=5.0),
        ]
        s1 = thompson_sample(branches, random.Random(123))
        s2 = thompson_sample(branches, random.Random(123))
        assert s1.harness.code == s2.harness.code

    def test_high_alpha_favored(self) -> None:
        rng = random.Random(0)
        branches = [
            Branch(harness=_make_harness("good"), alpha=100.0, beta=1.0),
            Branch(harness=_make_harness("bad"), alpha=1.0, beta=100.0),
        ]
        results = [thompson_sample(branches, rng).harness.code for _ in range(50)]
        assert results.count("good") > 40


class TestIsConverged:
    """Convergence check: mean > threshold for enough iterations."""

    def test_converged(self) -> None:
        branch = Branch(harness=_make_harness(), alpha=100.0, beta=1.0, update_count=10)
        assert is_converged(branch, threshold=0.8, min_iterations=10)

    def test_not_converged_low_mean(self) -> None:
        branch = Branch(harness=_make_harness(), alpha=1.0, beta=100.0)
        assert not is_converged(branch, threshold=0.8, min_iterations=10)

    def test_not_converged_insufficient_iterations(self) -> None:
        branch = Branch(harness=_make_harness(), alpha=100.0, beta=1.0)
        branch.update_count = 5
        assert not is_converged(branch, threshold=0.8, min_iterations=10)

    def test_converged_exact_threshold(self) -> None:
        branch = Branch(harness=_make_harness(), alpha=8.0, beta=2.0, update_count=1)
        assert is_converged(branch, threshold=0.8, min_iterations=1)


class TestBranchPriorInitialization:
    """Branch initialized with correct prior alpha/beta."""

    def test_default_prior(self) -> None:
        b = Branch(harness=_make_harness())
        assert b.alpha == 1.0
        assert b.beta == 1.0

    def test_custom_prior(self) -> None:
        b = Branch(harness=_make_harness(), alpha=2.0, beta=3.0)
        assert b.alpha == 2.0
        assert b.beta == 3.0


class TestSearchConfigDefaults:
    """SearchConfig has correct defaults from PLAN.md."""

    def test_defaults(self) -> None:
        cfg = SearchConfig()
        assert cfg.prior_alpha == 1.0
        assert cfg.prior_beta == 1.0
        assert cfg.convergence_threshold == 0.8
        assert cfg.max_search_iterations == 20
        assert cfg.max_total_failures == 5
        assert cfg.num_parallel_rollouts == 8


class TestThompsonTreeSearchConverges:
    """Search loop converges on a good harness."""

    def test_converges_on_good_harness(self) -> None:
        good = _make_harness("good_harness")
        bad = _make_harness("bad_harness")

        call_count = {"good": 0, "bad": 0}

        def mock_rollout(h: Harness, seed: int) -> tuple[float, bool]:
            if h.code == "good_harness":
                call_count["good"] += 1
                return 0.95, False
            call_count["bad"] += 1
            return 0.1, False

        search = ThompsonTreeSearch(
            config=SearchConfig(
                convergence_threshold=0.8,
                min_convergence_iterations=3,
                max_search_iterations=50,
            ),
            env_kind="tool",
        )
        search.add_branch(good)
        search.add_branch(bad)

        result = search.run(mock_rollout, rng_seed=42)
        assert result.status == "converged"
        assert result.total_failures == 0
        assert result.best_branch is not None
        assert result.best_branch.update_count >= 3
        assert result.best_branch.harness.code == "good_harness"
        assert call_count["good"] > call_count["bad"]


class TestThompsonTreeSearchFailureBudget:
    """Search respects max_total_failures."""

    def test_stops_on_failure_budget(self) -> None:
        h = _make_harness("failing_harness")

        def failing_rollout(h: Harness, seed: int) -> tuple[float, bool]:
            return 0.0, True  # always fails

        search = ThompsonTreeSearch(
            config=SearchConfig(
                max_search_iterations=100,
                max_total_failures=3,
                convergence_threshold=0.99,
            ),
            env_kind="tool",
        )
        search.add_branch(h)

        result = search.run(failing_rollout, rng_seed=42)
        assert result.status == "max_failures"
        assert result.total_failures == 3


class TestThompsonTreeSearchMaxIterations:
    """Search stops at max_search_iterations."""

    def test_stops_at_max(self) -> None:
        h = _make_harness("slow_harness")

        def slow_rollout(h: Harness, seed: int) -> tuple[float, bool]:
            return 0.5, False

        search = ThompsonTreeSearch(
            config=SearchConfig(
                max_search_iterations=5,
                convergence_threshold=0.99,
            ),
            env_kind="tool",
        )
        search.add_branch(h)

        result = search.run(slow_rollout, rng_seed=42)
        assert result.iterations <= 5
        assert result.status == "max_iterations"


class TestThompsonTreeSearchEmpty:
    """Search with no branches returns immediately."""

    def test_empty_branches(self) -> None:
        def noop_rollout(h: Harness, seed: int) -> tuple[float, bool]:
            return 0.0, False

        search = ThompsonTreeSearch(env_kind="tool")
        result = search.run(noop_rollout, rng_seed=42)
        assert result.best_branch is None
        assert result.iterations == 0
        assert result.total_failures == 0
        assert result.status == "no_branches"
