"""summarize trace edges into pairwise latency statistics

aggregates trace chunks into per-service-path timing data, giving observed latency distribution between service A and service B.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from ..ingest.traces import normalize_traces_df
from ..models import (
    SERVICE_PATH_CONFIDENCE_COL,
    SERVICE_PATH_COUNT_COL,
    SERVICE_PATH_FIRST_SEEN_COL,
    SERVICE_PATH_LAST_SEEN_COL,
    SERVICE_PATH_MEAN_COL,
    SERVICE_PATH_P50_COL,
    SERVICE_PATH_P95_COL,
    SERVICE_PATH_P99_COL,
    SERVICE_PATH_STD_COL,
    TRACE_LATENCY_COL,
    TRACE_LATENCY_S_COL,
    TRACE_SOURCE_SERVICE_COL,
    TRACE_TARGET_SERVICE_COL,
    TRACE_TIMESTAMP_COL,
)


def build_service_paths_df(trace_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """summarize trace chunks into pairwise latency statistics"""
    stats: dict[tuple[str, str], dict[str, object]] = {}
    total_spans = 0

    for chunk in trace_frames:
        frame = normalize_traces_df(chunk)
        if frame.empty:
            continue

        # convert milliseconds to seconds because the coupling window works in seconds
        frame[TRACE_LATENCY_S_COL] = frame[TRACE_LATENCY_COL].astype(float) / 1000.0
        total_spans += len(frame)

        # group by direct service path and collect timing distribution info
        grouped = frame.groupby([TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL], dropna=False)
        for (source, target), group in grouped:
            key = (str(source), str(target))    # key by service pair
            bucket = stats.setdefault(
                key,
                {
                    "count": 0,
                    "durations": [],
                    "first_seen": None,
                    "last_seen": None,
                },
            )

            # update count and durations
            bucket["count"] = int(bucket["count"]) + len(group)
            bucket["durations"].extend(group[TRACE_LATENCY_S_COL].astype(float).tolist())

            # update first and last seen timestamps
            first_seen = group[TRACE_TIMESTAMP_COL].min()
            last_seen = group[TRACE_TIMESTAMP_COL].max()
            if bucket["first_seen"] is None or first_seen < bucket["first_seen"]:
                bucket["first_seen"] = first_seen
            if bucket["last_seen"] is None or last_seen > bucket["last_seen"]:
                bucket["last_seen"] = last_seen

    if not stats:
        return pd.DataFrame(
            columns=[
                TRACE_SOURCE_SERVICE_COL,
                TRACE_TARGET_SERVICE_COL,
                SERVICE_PATH_COUNT_COL,
                SERVICE_PATH_P50_COL,
                SERVICE_PATH_P95_COL,
                SERVICE_PATH_P99_COL,
                SERVICE_PATH_MEAN_COL,
                SERVICE_PATH_STD_COL,
                SERVICE_PATH_FIRST_SEEN_COL,
                SERVICE_PATH_LAST_SEEN_COL,
                SERVICE_PATH_CONFIDENCE_COL,
            ]
        )

    rows = []
    for (source, target), bucket in stats.items():
        durations = pd.Series(bucket["durations"], dtype="float64")
        rows.append(
            {
                # canonical path metadata for later filtering and scoring
                TRACE_SOURCE_SERVICE_COL: source,
                TRACE_TARGET_SERVICE_COL: target,
                SERVICE_PATH_COUNT_COL: int(bucket["count"]),
                SERVICE_PATH_P50_COL: float(durations.quantile(0.50)),
                SERVICE_PATH_P95_COL: float(durations.quantile(0.95)),
                SERVICE_PATH_P99_COL: float(durations.quantile(0.99)),
                SERVICE_PATH_MEAN_COL: float(durations.mean()),
                SERVICE_PATH_STD_COL: float(durations.std()),
                SERVICE_PATH_FIRST_SEEN_COL: bucket["first_seen"],
                SERVICE_PATH_LAST_SEEN_COL: bucket["last_seen"],
                SERVICE_PATH_CONFIDENCE_COL: int(bucket["count"]) / max(total_spans, 1),
            }
        )

    return pd.DataFrame.from_records(rows).sort_values(
        [TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL]  # sort by service pair
    ).reset_index(drop=True)
