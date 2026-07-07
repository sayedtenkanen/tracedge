"""Sandbox — correctness guardrails for harness execution.

This module provides runtime isolation for harness code via restricted
builtins and AST-based guardrails. It is NOT a full security sandbox —
it prevents accidental misuse (try/except, undeclared effects) but does
not block deliberate escape attempts via getattr/type/super chains.
Full subprocess isolation is deferred to Phase 2.
"""
