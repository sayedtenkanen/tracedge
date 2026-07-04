"""Guardrails — static analysis and effect boundary enforcement for harness code."""

from __future__ import annotations

import ast

# Modules that imply filesystem access.
_FS_MODULES = {"os", "os.path", "pathlib", "shutil", "io"}

# Modules that imply network access.
_NET_MODULES = {
    "urllib",
    "urllib.request",
    "urllib.parse",
    "http",
    "http.client",
    "socket",
    "requests",
}

# Attribute patterns that imply state mutation.
_STATE_MUTATION_ATTRS = {"__setitem__", "__delitem__"}


def check_harness_code(code: str, effects: dict[str, bool] | None = None) -> None:
    """Validate harness code against safety constraints.

    Raises ``ValueError`` if any constraint is violated.
    Constraints checked:
    - No ``try``/``except`` blocks.
    - Effect boundary: ``filesystem``, ``network``, and ``environment`` access.
    - No in-place state mutation.
    """
    tree = ast.parse(code)

    # --- try/except check ---
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            raise ValueError("Harness code must not contain try/except blocks")

    if effects is None:
        return

    # --- effect boundary checks ---
    allow_fs = effects.get("filesystem", True)
    allow_net = effects.get("network", True)

    for node in ast.walk(tree):
        # filesystem access via import
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if not allow_fs:
                _check_fs_import(node)
            if not allow_net:
                _check_net_import(node)

        # environment.step() call
        if isinstance(node, ast.Call):
            _check_env_call(node)

        # state mutation: subscript assignment or deletion
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "state"
                ):
                    raise ValueError("Harness code must not mutate state in place")

        if isinstance(node, ast.Delete):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "state"
                ):
                    raise ValueError("Harness code must not mutate state in place")

    # --- filesystem access via open() ---
    if not allow_fs:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
            ):
                raise ValueError("Harness code must not perform filesystem access")


def _check_fs_import(node: ast.Import | ast.ImportFrom) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in _FS_MODULES or alias.name.split(".")[0] in _FS_MODULES:
                raise ValueError("Harness code must not perform filesystem access")
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module in _FS_MODULES or module.split(".")[0] in _FS_MODULES:
            raise ValueError("Harness code must not perform filesystem access")


def _check_net_import(node: ast.Import | ast.ImportFrom) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in _NET_MODULES or alias.name.split(".")[0] in _NET_MODULES:
                raise ValueError("Harness code must not perform network access")
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module in _NET_MODULES or module.split(".")[0] in _NET_MODULES:
            raise ValueError("Harness code must not perform network access")


def _check_env_call(node: ast.Call) -> None:
    """Reject calls to environment.step() or environment.<attr>."""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "environment"
    ):
        raise ValueError("Harness code must not call environment methods directly")
