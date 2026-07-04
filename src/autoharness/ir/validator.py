from autoharness.ir.upir import UPIR


def validate_upir(upir: UPIR) -> bool:
    """Validate UPIR graph invariants beyond Pydantic model validation.

    Checks:
    - Nodes dict is not empty
    - Entry node exists in nodes
    - All edges reference existing nodes
    """
    if not upir.nodes:
        raise ValueError("nodes must not be empty")

    if upir.entry not in upir.nodes:
        raise ValueError(f"entry '{upir.entry}' not found in nodes")

    for edge in upir.edges:
        if edge.from_ not in upir.nodes:
            raise ValueError(f"edge source '{edge.from_}' not found in nodes")
        if edge.to not in upir.nodes:
            raise ValueError(f"edge target '{edge.to}' not found in nodes")

    return True
