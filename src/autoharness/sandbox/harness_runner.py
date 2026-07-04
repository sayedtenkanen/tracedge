"""Harness runner — sandboxed execution with timeout and guardrail enforcement."""

from __future__ import annotations

import threading
from typing import Any

from autoharness.sandbox.guardrails import check_harness_code

# Restricted builtins: only safe, common names are available.
_RESTRICTED_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "getattr": getattr,
    "hasattr": hasattr,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "property": property,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "super": super,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


def run_harness(
    code: str,
    max_runtime_ms: int = 1000,
    effects: dict[str, bool] | None = None,
    state: dict[str, Any] | None = None,
    environment: Any = None,
) -> dict[str, Any]:
    """Execute harness code in a sandboxed namespace.

    Returns:
        ``{"verdict": "ok", "outputs": <dict>, "raised": None}`` on success.
        ``{"verdict": "error", "outputs": {}, "raised": <exception>}`` on error.
        ``{"verdict": "timeout", "outputs": {}, "raised": "Timeout"}`` on timeout.
    """
    # Static guardrail check
    check_harness_code(code, effects=effects)

    outputs: dict[str, Any] = {}
    raised: Any = None

    # Restricted globals
    sandbox_globals: dict[str, Any] = {
        "__builtins__": _RESTRICTED_BUILTINS,
        "state": state or {},
        "environment": environment,
    }

    def _target() -> None:
        nonlocal raised
        try:
            exec(code, sandbox_globals)  # noqa: S102  # nosec B102
        except Exception as e:  # noqa: BLE001
            raised = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=max_runtime_ms / 1000.0)

    if thread.is_alive():
        return {"verdict": "timeout", "outputs": {}, "raised": "Timeout", "timed_out": True}

    if raised is not None:
        return {"verdict": "error", "outputs": {}, "raised": raised}

    # Collect non-builtin, non-dunder outputs
    for key, val in sandbox_globals.items():
        if key.startswith("_") or key in {"state", "environment"}:
            continue
        if callable(val) and val is _RESTRICTED_BUILTINS.get(key):
            continue
        outputs[key] = val

    return {"verdict": "ok", "outputs": outputs, "raised": None}
