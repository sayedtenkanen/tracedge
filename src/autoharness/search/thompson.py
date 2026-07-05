"""Thompson Tree Search — Beta posterior search over harness code hypotheses."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from autoharness.ir.harness import Harness


def thompson_sample(branches: list[Branch], rng: random.Random) -> Branch:
    """Sample theta from each branch's Beta posterior, return highest."""
    thetas = [rng.betavariate(b.alpha, b.beta) for b in branches]
    return branches[thetas.index(max(thetas))]


def update_posterior(alpha: float, beta: float, v: float) -> tuple[float, float]:
    """Update Beta posterior: alpha += v, beta += (1-v)."""
    return alpha + v, beta + (1.0 - v)


def is_converged(branch: Branch, threshold: float, min_iterations: int) -> bool:
    """True if branch mean >= threshold and enough updates have occurred."""
    return branch.mean >= threshold and branch.update_count >= min_iterations


@dataclass
class Branch:
    """A code hypothesis with Beta(alpha, beta) posterior."""

    harness: Harness
    alpha: float = 1.0
    beta: float = 1.0
    update_count: int = 0

    @property
    def mean(self) -> float:
        """Posterior mean of the Beta distribution."""
        total = self.alpha + self.beta
        return self.alpha / total if total > 0 else 0.0

    def update(self, v: float) -> None:
        """Update posterior with scalar value v in [0, 1]."""
        self.alpha, self.beta = update_posterior(self.alpha, self.beta, v)
        self.update_count += 1


@dataclass
class SearchConfig:
    """Configuration for Thompson tree search."""

    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    convergence_threshold: float = 0.8
    min_convergence_iterations: int = 3
    max_search_iterations: int = 20
    max_failures_per_round: int = 5
    num_parallel_rollouts: int = 8


@dataclass
class SearchResult:
    """Outcome of a Thompson tree search."""

    best_branch: Branch | None
    iterations: int
    total_failures: int
    status: str  # "converged", "max_iterations", "max_failures", "no_branches"


class ThompsonTreeSearch:
    """Thompson-sampling tree search over harness code hypotheses.

    Maintains a tree of Branch objects, each with a Beta posterior.
    Each iteration: sample branches, roll out the selected one,
    update its posterior, check convergence.
    """

    def __init__(
        self,
        config: SearchConfig | None = None,
        env_kind: str = "tool",
    ) -> None:
        self.config = config or SearchConfig()
        self.env_kind = env_kind
        self.branches: list[Branch] = []

    def add_branch(
        self,
        harness: Harness,
        alpha: float | None = None,
        beta: float | None = None,
    ) -> Branch:
        """Add a harness as a new branch with Beta prior."""
        a = alpha if alpha is not None else self.config.prior_alpha
        b = beta if beta is not None else self.config.prior_beta
        branch = Branch(harness=harness, alpha=a, beta=b)
        self.branches.append(branch)
        return branch

    def run(
        self,
        rollout_fn: Callable[[Harness, int], tuple[float, bool]],
        rng_seed: int = 42,
    ) -> SearchResult:
        """Run Thompson search until convergence or budget exhausted.

        Args:
            rollout_fn: Callable(harness, seed) -> (value, failed).
                Returns a scalar value in [0, 1] and whether this rollout failed.
            rng_seed: Seed for reproducible Thompson sampling.

        Returns:
            SearchResult with the best branch found.
        """
        rng = random.Random(rng_seed)
        total_failures = 0

        if not self.branches:
            return SearchResult(
                best_branch=None, iterations=0, total_failures=0, status="no_branches"
            )

        for iteration in range(1, self.config.max_search_iterations + 1):
            if not self.branches:
                break

            branch = thompson_sample(self.branches, rng)

            v, failed = rollout_fn(branch.harness, rng.randint(0, 2**31))

            if failed:
                total_failures += 1
                if total_failures >= self.config.max_failures_per_round:
                    return SearchResult(
                        best_branch=self._best_branch(),
                        iterations=iteration,
                        total_failures=total_failures,
                        status="max_failures",
                    )

            branch.update(v)

            if is_converged(
                branch, self.config.convergence_threshold, self.config.min_convergence_iterations
            ):
                return SearchResult(
                    best_branch=branch,
                    iterations=iteration,
                    total_failures=total_failures,
                    status="converged",
                )

        return SearchResult(
            best_branch=self._best_branch(),
            iterations=self.config.max_search_iterations,
            total_failures=total_failures,
            status="max_iterations",
        )

    def _best_branch(self) -> Branch | None:
        """Return the branch with the highest posterior mean."""
        if not self.branches:
            return None
        return max(self.branches, key=lambda b: b.mean)
