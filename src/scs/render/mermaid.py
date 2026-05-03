"""Render a directed service graph as Mermaid flowchart text."""

from __future__ import annotations

import re


def _safe_node_id(name: str, index: int) -> str:
    """ensure we support arbitrary node names in the graph"""
    slug = re.sub(r"[^0-9A-Za-z_]", "_", name).strip("_")
    if not slug:
        slug = "node"
    if slug[0].isdigit():
        slug = f"node_{slug}"
    return f"{slug}_{index}"


def render_mermaid(graph: dict[str, set[str]], title: str = "Inferred Service Graph") -> str:
    """Render a Mermaid flowchart from an adjacency map."""
    nodes = sorted(set(graph) | {target for targets in graph.values() for target in targets})
    node_ids = {node: _safe_node_id(node, index) for index, node in enumerate(nodes)}

    lines = ["flowchart LR", f"  %% {title}"]
    for node in nodes:
        lines.append(f'  {node_ids[node]}["{node}"]')

    for source in sorted(graph):
        for target in sorted(graph[source]):
            lines.append(f"  {node_ids[source]} --> {node_ids[target]}")

    return "\n".join(lines)
