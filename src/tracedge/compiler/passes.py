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
