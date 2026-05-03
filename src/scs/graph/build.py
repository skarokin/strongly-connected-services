"""Build a directed coupling graph from scored service pairs."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from ..models import COUPLING_LEFT_COL, COUPLING_RIGHT_COL, COUPLING_SCORE_COL, required_columns


def build_graph(coupling_df: pd.DataFrame, *, min_score: float = 0.1) -> dict[str, set[str]]:
    """Construct an adjacency map from scored service pairs.

    The coupling score is pair-level evidence, so strong pairs are rendered as
    bidirectional edges to make SCCs visible in the final graph.
    """
    frame = coupling_df.copy()
    required_columns(frame, [COUPLING_LEFT_COL, COUPLING_RIGHT_COL, COUPLING_SCORE_COL], name="coupling")

    graph: dict[str, set[str]] = defaultdict(set)
    for row in frame.itertuples(index=False):
        if getattr(row, COUPLING_SCORE_COL) < min_score:
            continue
        left = getattr(row, COUPLING_LEFT_COL)
        right = getattr(row, COUPLING_RIGHT_COL)
        graph[left].add(right)
        graph[right].add(left)
    return dict(graph)
