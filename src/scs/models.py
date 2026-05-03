"""Shared dataframe column names and validation helpers."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

ALERT_TIMESTAMP_COL = "timestamp"
ALERT_SERVICE_COL = "service"
ALERT_INCIDENT_COL = "incident_id"
ALERT_NAME_COL = "name"
ALERT_SEVERITY_COL = "severity"

TRACE_TIMESTAMP_COL = "timestamp"
TRACE_SOURCE_SERVICE_COL = "source_service"
TRACE_TARGET_SERVICE_COL = "target_service"
TRACE_LATENCY_COL = "duration_ms"
TRACE_LATENCY_S_COL = "duration_s"

SERVICE_PATH_COUNT_COL = "count"
SERVICE_PATH_P50_COL = "p50_latency_s"
SERVICE_PATH_P95_COL = "p95_latency_s"
SERVICE_PATH_P99_COL = "p99_latency_s"
SERVICE_PATH_MEAN_COL = "mean_latency_s"
SERVICE_PATH_STD_COL = "std_latency_s"
SERVICE_PATH_FIRST_SEEN_COL = "first_seen"
SERVICE_PATH_LAST_SEEN_COL = "last_seen"
SERVICE_PATH_CONFIDENCE_COL = "confidence"
SERVICE_PATH_WINDOW_COL = "plausible_window_s"

ALERT_PAIR_INCIDENT_COL = ALERT_INCIDENT_COL
ALERT_PAIR_SOURCE_COL = "ordered_source"
ALERT_PAIR_TARGET_COL = "ordered_target"
ALERT_PAIR_DELTA_COL = "delta_s"
ALERT_PAIR_WITHIN_WINDOW_COL = "within_window"
ALERT_PAIR_PATH_EXISTS_COL = "path_exists"

COUPLING_LEFT_COL = "service_a"
COUPLING_RIGHT_COL = "service_b"
COUPLING_FORWARD_HITS_COL = "forward_hits"
COUPLING_REVERSE_HITS_COL = "reverse_hits"
COUPLING_SUPPORT_COL = "support"
COUPLING_BALANCE_COL = "balance"
COUPLING_SCORE_COL = "score"
COUPLING_TOTAL_INCIDENTS_COL = "total_incidents"
COUPLING_COVERAGE_COL = "incident_coverage"


def required_columns(df: pd.DataFrame, columns: Iterable[str], *, name: str = "dataframe") -> None:
    """raise error if a dataframe is missing required columns."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")


def canonical_pair(left: str, right: str) -> tuple[str, str]:
    """ensure stable ordering for a service pair (simple sort)"""
    return (left, right) if left <= right else (right, left)
