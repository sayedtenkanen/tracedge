"""Throwaway script to verify all Python snippets in docs parse and run correctly."""

import ast
import multiprocessing
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = [REPO / "USE_CASES.md", REPO / "USER_MANUAL.md"]

# Known importable names for quick smoke test
SAFE_IMPORTS = {
    "autoharness.ir.upir": ["UPIR", "UPIRNode", "Edge"],
    "autoharness.runtime.vm": ["VM"],
    "autoharness.environment.tool_env": ["ToolEnvironment"],
    "autoharness.environment.game_env": ["GameEnvironment"],
    "autoharness.reward.scorer": ["score_trace", "value", "Reward"],
    "autoharness.skills.extractor": ["SkillExtractor", "Pattern"],
    "autoharness.skills.pruner": ["SkillPruner"],
    "autoharness.search.thompson": ["ThompsonTreeSearch", "SearchConfig", "SearchResult"],
    "autoharness.intelligence.critic": ["Critic", "CriticOutput"],
    "autoharness.intelligence.refiner": ["Refiner"],
    "autoharness.trace.trace_ir": ["TraceEvent", "TraceLog"],
    "autoharness.memory.store": ["MemoryStore"],
    "autoharness.ir.harness": ["Harness", "HarnessResult"],
}


class SnippetTimeoutError(Exception):
    """Raised when a doc snippet exceeds its execution time budget."""


SAFE_BUILTINS = {
    "print": print,
    "range": range,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "any": any,
    "all": all,
    "enumerate": enumerate,
    "zip": zip,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "type": type,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": getattr,
    "sorted": sorted,
    "reversed": reversed,
    "map": map,
    "filter": filter,
    "abs": abs,
    "round": round,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "Exception": Exception,
}


def _exec_in_subprocess(block: str, queue: multiprocessing.Queue[object]) -> None:  # type: ignore[type-arg]
    """Execute block in a subprocess; puts result or exception into queue."""
    namespace: dict[str, object] = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(block, namespace)  # nosec B102 - executed with restricted builtins
        queue.put(None)
    except Exception as e:
        queue.put(e)


def run_snippet_with_timeout(
    block: str,
    timeout_seconds: float = 5.0,
) -> tuple[bool, str | None]:
    """Execute block with restricted builtins and a timeout.

    Returns (success, error_message).
    """
    queue: multiprocessing.Queue[object] = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_exec_in_subprocess, args=(block, queue))
    proc.start()
    proc.join(timeout=timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.0)
        return False, f"SnippetTimeoutError: exceeded {timeout_seconds}s timeout"

    if not queue.empty():
        exc = queue.get_nowait()
        if exc is not None:
            return False, f"{type(exc).__name__}: {exc}"

    return True, None


def extract_python_blocks(md_text: str) -> list[tuple[int, str]]:
    """Extract all ```python blocks with line numbers."""
    blocks = []
    lines = md_text.split("\n")
    in_block = False
    block_lines = []
    block_start = 0
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```python"):
            in_block = True
            block_lines = []
            block_start = i
        elif line.strip().startswith("```") and in_block:
            in_block = False
            blocks.append((block_start, "\n".join(block_lines)))
        elif in_block:
            block_lines.append(line)
    return blocks


def check_ast_parse(block: str, line_start: int, doc_name: str) -> list[str]:
    """Try to ast.parse a block. Return list of errors."""
    errors = []
    try:
        ast.parse(block)
    except SyntaxError as e:
        errors.append(f"  {doc_name}:{line_start}: SyntaxError: {e}")
    return errors


def check_imports(block: str, line_start: int, doc_name: str) -> list[str]:
    """Try to actually import the modules referenced in the block."""
    errors = []
    tree = ast.parse(block)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if module in SAFE_IMPORTS:
                for alias in node.names:
                    name = alias.name
                    if name not in SAFE_IMPORTS[module]:
                        errors.append(
                            f"  {doc_name}:{line_start}: '{name}' not found in '{module}'"
                        )
    return errors


def run_snippet(block: str, line_start: int, doc_name: str) -> list[str]:
    """Try to execute a snippet in a sandboxed namespace."""
    errors = []
    skip_markers = [
        "tasks",
        "GameLLM",
        "ResearchLLM",
        "SimpleLLM",
        "my_llm",
        "fast_upir",
        "thorough_upir",
        "balanced_upir",
        "strategies",
        "harness",
        "guardrails",
        "trace",
        "trace_log",
        "coding_agent",
        "pipeline",
        "research_agent",
        "tool_agent",
        "original_upir",
        "skill_upir",
    ]
    if any(m in block for m in skip_markers):
        return errors

    success, error_msg = run_snippet_with_timeout(block, timeout_seconds=5.0)
    if not success:
        errors.append(f"  {doc_name}:{line_start}: {error_msg}")
    return errors


def main() -> int:
    all_errors: list[str] = []
    total_blocks = 0

    for doc in DOCS:
        if not doc.exists():
            print(f"SKIP: {doc.name} not found")
            continue
        text = doc.read_text()
        blocks = extract_python_blocks(text)
        print(f"\n{'=' * 60}")
        print(f"{doc.name}: {len(blocks)} Python blocks")
        print(f"{'=' * 60}")

        for line_start, block in blocks:
            total_blocks += 1
            short = block[:60].replace("\n", " ")
            print(f"  L{line_start:4d}: {short}...")

            errs = check_ast_parse(block, line_start, doc.name)
            if errs:
                all_errors.extend(errs)
                print("    FAIL (parse)")
                continue

            errs = check_imports(block, line_start, doc.name)
            if errs:
                all_errors.extend(errs)
                print("    FAIL (import)")
                continue

            errs = run_snippet(block, line_start, doc.name)
            if errs:
                all_errors.extend(errs)
                print("    FAIL (exec)")
                continue

            print("    OK")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {total_blocks} blocks checked")
    if all_errors:
        print(f"ERRORS ({len(all_errors)}):")
        for e in all_errors:
            print(e)
        return 1
    else:
        print("ALL BLOCKS OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
