"""Centralized defaults for AutoHarness configuration.

These values are referenced across the codebase. Keeping them in one
place makes tuning and documentation easier.
"""

from __future__ import annotations

# VM defaults
VM_MAX_STEPS = 100

# Sandbox defaults
SANDBOX_MAX_RUNTIME_MS = 1000

# Search defaults
THOMPSON_MAX_SEARCH_ITERATIONS = 50
THOMPSON_MAX_TOTAL_FAILURES = 10
THOMPSON_PRIOR_ALPHA = 1.0
THOMPSON_PRIOR_BETA = 1.0

# Reward defaults
REWARD_WEIGHTS_TOOL = {
    "task_success": 0.6,
    "efficiency": 0.2,
    "safety": 0.2,
}
REWARD_WEIGHTS_GAME = {
    "task_success": 0.5,
    "legality": 0.3,
    "safety": 0.2,
}
