"""Build a service dependency graph and overlay strong coupling edges."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from ..models import (
    COUPLING_LEFT_COL,
    COUPLING_RIGHT_COL,
    COUPLING_SCORE_COL,
    SERVICE_PATH_CONFIDENCE_COL,
    TRACE_SOURCE_SERVICE_COL,
    TRACE_TARGET_SERVICE_COL,
    required_columns,
)


def build_graph(
    service_paths_df: pd.DataFrame,
    coupling_df: pd.DataFrame | None = None,
    *,
    min_path_confidence: float = 0.0,
    min_score: float = 0.05,
) -> dict[str, set[str]]:
    """Construct a full service graph, then reinforce strong coupled pairs

    The trace-derived service paths provide the base dependency graph, so every
    service that appears in traces stays visible even if it is not part of an
    SCC. The coupling table then adds reverse edges for high-confidence pairs so
    the strongly connected clusters still stand out
    """
    trace_frame = service_paths_df.copy()
    required_columns(
        trace_frame,
        [TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL],
        name="service_paths",
    )

    graph: dict[str, set[str]] = defaultdict(set)
    has_path_confidence = SERVICE_PATH_CONFIDENCE_COL in trace_frame.columns
    for row in trace_frame.itertuples(index=False):
        if has_path_confidence and getattr(row, SERVICE_PATH_CONFIDENCE_COL) < min_path_confidence:
            continue

        source = getattr(row, TRACE_SOURCE_SERVICE_COL)
        target = getattr(row, TRACE_TARGET_SERVICE_COL)
        graph[source].add(target)
        graph.setdefault(target, set())

    if coupling_df is not None and not coupling_df.empty:
        coupling_frame = coupling_df.copy()
        required_columns(coupling_frame, [COUPLING_LEFT_COL, COUPLING_RIGHT_COL, COUPLING_SCORE_COL], name="coupling")
        for row in coupling_frame.itertuples(index=False):
            if getattr(row, COUPLING_SCORE_COL) < min_score:
                continue
            left = getattr(row, COUPLING_LEFT_COL)
            right = getattr(row, COUPLING_RIGHT_COL)
            graph[left].add(right)
            graph[right].add(left)

    return dict(graph)
