"""Render a directed service graph as Mermaid flowchart text."""

from __future__ import annotations

import re
from collections.abc import Iterable


def _safe_node_id(name: str, index: int) -> str:
    """ensure we support arbitrary node names in the graph"""
    slug = re.sub(r"[^0-9A-Za-z_]", "_", name).strip("_")
    if not slug:
        slug = "node"
    if slug[0].isdigit():
        slug = f"node_{slug}"
    return f"{slug}_{index}"


def render_mermaid(
    graph: dict[str, set[str]],
    components: Iterable[set[str]] | None = None,
    title: str = "Inferred Service Graph",
) -> str:
    """Render a Mermaid flowchart from an adjacency map.

    when scc components are supplied, multi-node components are grouped into subgraphs
    """
    nodes = sorted(set(graph) | {target for targets in graph.values() for target in targets})
    node_ids = {node: _safe_node_id(node, index) for index, node in enumerate(nodes)}
    component_list = [set(component) for component in components or []]
    clustered_nodes = set().union(*[component for component in component_list if len(component) > 1]) if component_list else set()

    lines = ["flowchart LR", f"  %% {title}"]

    if component_list:
        for component_index, component in enumerate(sorted(component_list, key=lambda item: (-len(item), sorted(item))), start=1):
            members = sorted(component)
            if len(members) <= 1:
                continue
            lines.append(f'  subgraph scc_{component_index}["SCC {component_index} ({len(members)} nodes)"]')
            for node in members:
                lines.append(f'    {node_ids[node]}["{node}"]')
            lines.append("  end")

    for node in nodes:
        if node not in clustered_nodes:
            lines.append(f'  {node_ids[node]}["{node}"]')

    for source in sorted(graph):
        for target in sorted(graph[source]):
            lines.append(f"  {node_ids[source]} --> {node_ids[target]}")

    return "\n".join(lines)
