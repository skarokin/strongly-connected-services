"""derive trace-informed timing windows for candidate alert pairs.

use trace p95 latency to derive a plausible alert-pair window.
the window is only a filter, not the final coupling score.
"""

from __future__ import annotations

import pandas as pd

from ..models import (
    SERVICE_PATH_P95_COL,
    SERVICE_PATH_WINDOW_COL,
    TRACE_SOURCE_SERVICE_COL,
    TRACE_TARGET_SERVICE_COL,
    required_columns,
)


def build_plausible_windows_df(
    service_paths_df: pd.DataFrame,
    alert_lag_seconds: float = 0.0,
    floor_seconds: float = 5.0,
    ceiling_seconds: float = 300.0,
) -> pd.DataFrame:
    """convert trace latency stats into a bounded plausible window"""
    frame = service_paths_df.copy()
    # we only need the traced path and its p95 latency to build the filter window
    required_columns(
        frame,
        [TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL, SERVICE_PATH_P95_COL],
        name="service_paths",
    )

    if frame.empty:
        # keep the expected shape even when there is no trace data
        frame[SERVICE_PATH_WINDOW_COL] = pd.Series(dtype="float64")
        return frame

    # the alert lag expands the trace-derived path timing into a practical window
    # for now, alert lag is a fixed, human-assumed value. in the future this maybe can be learned (from alert metadata) 
    frame[SERVICE_PATH_WINDOW_COL] = (
        frame[SERVICE_PATH_P95_COL].astype(float) + float(alert_lag_seconds)
    ).clip(lower=floor_seconds, upper=ceiling_seconds)

    return frame.sort_values([TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL]).reset_index(drop=True)
