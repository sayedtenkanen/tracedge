"""Validate UPIR graph invariants.

This module is deprecated. Use ``UPIR`` directly — Pydantic's
``@model_validator(mode="after")`` enforces the same invariants on
construction.
"""

from autoharness.ir.upir import UPIR


def validate_upir(upir: UPIR) -> bool:
    """Validate UPIR graph invariants (delegates to Pydantic validator).

    .. deprecated::
        UPIR's ``@model_validator`` already checks these invariants at
        construction time.  Prefer constructing UPIR directly; this
        function is retained for backward compatibility.
    """
    # Re-trigger the model validator by re-building from dict.
    # This is a no-op if the UPIR was already validated, but catches
    # any post-construction mutation.
    UPIR.model_validate(upir.model_dump())
    return True
