"""Compiler passes — operate uniformly over UPIR graphs."""

from __future__ import annotations

from collections import deque

from tracedge.ir.upir import UPIR, Edge, UPIRNode


def dead_branch_eliminate(upir: UPIR) -> UPIR:
    """Remove branches where one target node doesn't exist.

    Replaces the branch with a direct sequential edge to the surviving target.
    """
    nodes = dict(upir.nodes.items())
    edges = list(upir.edges)

    for node_id, raw_node in list(nodes.items()):
        node = raw_node if isinstance(raw_node, UPIRNode) else UPIRNode.model_validate(raw_node)
        if node.kind != "branch":
            continue
        true_next = getattr(node, "true_next", "")
        false_next = getattr(node, "false_next", "")

        true_alive = true_next in nodes
        false_alive = false_next in nodes

        if true_alive and not false_alive:
            nodes[node_id] = node.model_copy(update={"true_next": true_next, "false_next": ""})
            edges.append(Edge(from_=node_id, to=true_next, kind="sequential"))
        elif false_alive and not true_alive:
            nodes[node_id] = node.model_copy(update={"true_next": "", "false_next": false_next})
            edges.append(Edge(from_=node_id, to=false_next, kind="sequential"))

    return upir.model_copy(update={"nodes": nodes, "edges": edges})


def constant_fold(upir: UPIR) -> UPIR:
    """Fold branches with constant True/False conditions into sequential edges."""
    nodes = dict(upir.nodes.items())
    edges = list(upir.edges)

    for node_id, raw_node in list(nodes.items()):
        node = raw_node if isinstance(raw_node, UPIRNode) else UPIRNode.model_validate(raw_node)
        if node.kind != "branch":
            continue
        condition = getattr(node, "condition", "").strip()

        if condition == "True":
            true_next = getattr(node, "true_next", "")
            nodes[node_id] = node.model_copy(
                update={"kind": "act", "condition": "", "true_next": "", "false_next": ""}
            )
            if true_next:
                edges.append(Edge(from_=node_id, to=true_next, kind="sequential"))
        elif condition == "False":
            false_next = getattr(node, "false_next", "")
            nodes[node_id] = node.model_copy(
                update={"kind": "act", "condition": "", "true_next": "", "false_next": ""}
            )
            if false_next:
                edges.append(Edge(from_=node_id, to=false_next, kind="sequential"))

    return upir.model_copy(update={"nodes": nodes, "edges": edges})


def unreachable_prune(upir: UPIR) -> UPIR:
    """Remove nodes with no incoming edges (except the entry node)."""
    targets = {edge.to for edge in upir.edges}
    targets.add(upir.entry)

    pruned = {nid: node for nid, node in upir.nodes.items() if nid in targets}
    pruned_edges = [e for e in upir.edges if e.from_ in pruned and e.to in pruned]

    return upir.model_copy(update={"nodes": pruned, "edges": pruned_edges})


def insert_phi_nodes(upir: UPIR) -> UPIR:
    """Insert phi nodes at convergence points (nodes with multiple incoming edges).

    For each convergence point, finds the nearest branch ancestor via BFS and
    inserts a phi node.  The phi's ``values`` dict maps ``"true"`` → the
    branch's ``true_next`` and ``"false"`` → the branch's ``false_next``, so
    downstream nodes can read ``{phi_<id>.selected}`` via template resolution.

    Important: this pass also updates any predecessor branch node whose
    ``true_next``/````false_next`` attribute points at the convergence target,
    rerouting it to the inserted phi.  Without this, the VM would bypass the
    phi via attribute-based control flow (``_step_branch`` reads attributes,
    not edges).

    The ``sources`` field on ``Phi`` is a legacy artifact and is not used by
    the VM — see the ``Phi`` model docstring and ``VM._step_phi`` for the
    current branch-value selection semantics.
    """
    # Count incoming edges per node
    incoming: dict[str, list[str]] = {}
    for edge in upir.edges:
        incoming.setdefault(edge.to, []).append(edge.from_)

    # Find convergence points (more than one incoming edge)
    convergence = {nid: sources for nid, sources in incoming.items() if len(sources) > 1}

    if not convergence:
        return upir

    def _find_branch_ancestor(start: str) -> str:
        """BFS backward to find the nearest branch node."""
        visited: set[str] = set()
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            raw = upir.nodes.get(current)
            if raw is not None:
                node = raw if isinstance(raw, UPIRNode) else UPIRNode.model_validate(raw)
                if node.kind == "branch":
                    return current
            for src in incoming.get(current, []):
                if src not in visited:
                    queue.append(src)
        return ""

    nodes = dict(upir.nodes.items())
    edges = list(upir.edges)

    for target_id in convergence:
        branch_source = _find_branch_ancestor(target_id)
        phi_id = f"phi_{target_id}"

        # F2: populate values from the branch node's true_next/false_next
        values: dict[str, str] = {}
        if branch_source:
            branch_raw = upir.nodes.get(branch_source)
            if branch_raw is not None:
                branch_node = (
                    branch_raw
                    if isinstance(branch_raw, UPIRNode)
                    else UPIRNode.model_validate(branch_raw)
                )
                true_next = getattr(branch_node, "true_next", "")
                false_next = getattr(branch_node, "false_next", "")
                if true_next:
                    values["true"] = true_next
                if false_next:
                    values["false"] = false_next

        nodes[phi_id] = UPIRNode(
            node_id=phi_id,
            kind="phi",
            branch_source=branch_source,
            values=values,
        )

        # F1: update branch predecessors' true_next/false_next to point at phi
        if branch_source:
            branch_raw = nodes.get(branch_source)
            if branch_raw is not None:
                bn = (
                    branch_raw
                    if isinstance(branch_raw, UPIRNode)
                    else UPIRNode.model_validate(branch_raw)
                )
                updates: dict[str, str] = {}
                if getattr(bn, "true_next", "") == target_id:
                    updates["true_next"] = phi_id
                if getattr(bn, "false_next", "") == target_id:
                    updates["false_next"] = phi_id
                if updates:
                    nodes[branch_source] = bn.model_copy(update=updates)

        # Rewire: predecessors → phi → target
        for src_id in list(convergence[target_id]):
            edges = [e for e in edges if not (e.from_ == src_id and e.to == target_id)]
            edges.append(Edge(from_=src_id, to=phi_id, kind="sequential"))
        edges.append(Edge(from_=phi_id, to=target_id, kind="sequential"))

    return upir.model_copy(update={"nodes": nodes, "edges": edges})
