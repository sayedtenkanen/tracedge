"""Conformance tests: Architecture boundary commitments from PLAN.md.

Each test verifies ONE concrete commitment. A failure means either the
code drifted or the plan is stale — investigate, don't just fix the test.
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path("src/autoharness")


def _import_graph() -> dict[str, set[str]]:
    """Build a module-level import graph from source files (including __init__.py)."""
    graph: dict[str, set[str]] = {}
    for py_file in SRC.rglob("*.py"):
        if py_file.name == "__init__.py":
            # Map __init__.py to its parent package name
            module = str(py_file.parent.relative_to(SRC.parent)).replace("/", ".")
        else:
            module = str(py_file.relative_to(SRC.parent)).replace("/", ".").removesuffix(".py")
        tree = ast.parse(py_file.read_text())
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("autoharness"):
                    imports.add(node.module.split(".")[1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("autoharness"):
                        imports.add(alias.name.split(".")[1])
        graph[module] = imports
    return graph


GRAPH = _import_graph()


class TestArchitectureBoundaries:
    """PLAN: modules follow a strict dependency DAG."""

    def test_environment_never_imports_sandbox(self) -> None:
        """PLAN: environment/ is independent of sandbox/."""
        env_mods = [m for m in GRAPH if m.startswith("environment")]
        for mod in env_mods:
            assert "sandbox" not in GRAPH[mod], f"{mod} imports sandbox"

    def test_environment_never_imports_intelligence(self) -> None:
        """PLAN: environment/ is independent of intelligence/."""
        env_mods = [m for m in GRAPH if m.startswith("environment")]
        for mod in env_mods:
            assert "intelligence" not in GRAPH[mod], f"{mod} imports intelligence"

    def test_environment_never_imports_search(self) -> None:
        """PLAN: environment/ is independent of search/."""
        env_mods = [m for m in GRAPH if m.startswith("environment")]
        for mod in env_mods:
            assert "search" not in GRAPH[mod], f"{mod} imports search"

    def test_sandbox_never_imports_intelligence(self) -> None:
        """PLAN: sandbox/ is independent of intelligence/."""
        sandbox_mods = [m for m in GRAPH if m.startswith("sandbox")]
        for mod in sandbox_mods:
            assert "intelligence" not in GRAPH[mod], f"{mod} imports intelligence"

    def test_sandbox_never_imports_search(self) -> None:
        """PLAN: sandbox/ is independent of search/."""
        sandbox_mods = [m for m in GRAPH if m.startswith("sandbox")]
        for mod in sandbox_mods:
            assert "search" not in GRAPH[mod], f"{mod} imports search"

    def test_reward_never_imports_runtime(self) -> None:
        """PLAN: reward/ is pure functions, no runtime dependency."""
        reward_mods = [m for m in GRAPH if m.startswith("reward")]
        for mod in reward_mods:
            assert "runtime" not in GRAPH[mod], f"{mod} imports runtime"

    def test_reward_never_imports_sandbox(self) -> None:
        """PLAN: reward/ is pure functions, no sandbox dependency."""
        reward_mods = [m for m in GRAPH if m.startswith("reward")]
        for mod in reward_mods:
            assert "sandbox" not in GRAPH[mod], f"{mod} imports sandbox"

    def test_reward_never_imports_environment(self) -> None:
        """PLAN: reward/ is pure functions, no environment dependency."""
        reward_mods = [m for m in GRAPH if m.startswith("reward")]
        for mod in reward_mods:
            assert "environment" not in GRAPH[mod], f"{mod} imports environment"

    def test_search_never_imports_sandbox(self) -> None:
        """PLAN: search/ does not depend on sandbox/."""
        search_mods = [m for m in GRAPH if m.startswith("search")]
        for mod in search_mods:
            assert "sandbox" not in GRAPH[mod], f"{mod} imports sandbox"

    def test_search_never_imports_intelligence(self) -> None:
        """PLAN: search/ does not depend on intelligence/."""
        search_mods = [m for m in GRAPH if m.startswith("search")]
        for mod in search_mods:
            assert "intelligence" not in GRAPH[mod], f"{mod} imports intelligence"

    def test_runtime_never_imports_intelligence(self) -> None:
        """PLAN: runtime/ does not depend on intelligence/."""
        runtime_mods = [m for m in GRAPH if m.startswith("runtime")]
        for mod in runtime_mods:
            assert "intelligence" not in GRAPH[mod], f"{mod} imports intelligence"

    def test_runtime_never_imports_search(self) -> None:
        """PLAN: runtime/ does not depend on search/."""
        runtime_mods = [m for m in GRAPH if m.startswith("runtime")]
        for mod in runtime_mods:
            assert "search" not in GRAPH[mod], f"{mod} imports search"

    def test_intelligence_never_imports_runtime(self) -> None:
        """PLAN: intelligence/ does not depend on runtime/."""
        intel_mods = [m for m in GRAPH if m.startswith("intelligence")]
        for mod in intel_mods:
            assert "runtime" not in GRAPH[mod], f"{mod} imports runtime"

    def test_intelligence_never_imports_search(self) -> None:
        """PLAN: intelligence/ does not depend on search/."""
        intel_mods = [m for m in GRAPH if m.startswith("intelligence")]
        for mod in intel_mods:
            assert "search" not in GRAPH[mod], f"{mod} imports search"
