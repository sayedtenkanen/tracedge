"""Compiler passes — operate uniformly over UPIR graphs."""

from __future__ import annotations

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

    For each convergence point, finds the nearest branch ancestor and inserts
    a phi node that can merge values from the divergent paths.
    """
    # Count incoming edges per node
    incoming: dict[str, list[str]] = {}
    for edge in upir.edges:
        incoming.setdefault(edge.to, []).append(edge.from_)

    # Find convergence points (more than one incoming edge)
    convergence = {nid: sources for nid, sources in incoming.items() if len(sources) > 1}

    if not convergence:
        return upir

    # Build a reverse adjacency for ancestor lookup
    children: dict[str, list[str]] = {}
    for edge in upir.edges:
        children.setdefault(edge.from_, []).append(edge.to)

    def _find_branch_ancestor(start: str) -> str:
        """BFS backward to find the nearest branch node."""
        from collections import deque

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
            # Walk backward via incoming edges
            for src in incoming.get(current, []):
                if src not in visited:
                    queue.append(src)
        return ""

    nodes = dict(upir.nodes.items())
    edges = list(upir.edges)

    for target_id in convergence:
        branch_source = _find_branch_ancestor(target_id)
        phi_id = f"phi_{target_id}"
        nodes[phi_id] = UPIRNode(
            node_id=phi_id,
            kind="phi",
            branch_source=branch_source,
            values={},
        )
        # Rewire: predecessors → phi → target
        for src_id in list(convergence[target_id]):
            # Remove old edge src → target
            edges = [e for e in edges if not (e.from_ == src_id and e.to == target_id)]
            # Add edge src → phi
            edges.append(Edge(from_=src_id, to=phi_id, kind="sequential"))
        # Add edge phi → target
        edges.append(Edge(from_=phi_id, to=target_id, kind="sequential"))

    return upir.model_copy(update={"nodes": nodes, "edges": edges})
