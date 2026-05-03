"""load alert event data as pandas dataframes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from ..models import ALERT_INCIDENT_COL, ALERT_SERVICE_COL, ALERT_TIMESTAMP_COL, required_columns
from .shared import iter_dataframe_chunks


def normalize_alerts_df(df: pd.DataFrame) -> pd.DataFrame:
    """normalize the alert dataframe into the canonical schema"""
    frame = df.copy()
    required_columns(frame, [ALERT_INCIDENT_COL, ALERT_SERVICE_COL, ALERT_TIMESTAMP_COL], name="alerts")
    frame[ALERT_TIMESTAMP_COL] = pd.to_datetime(frame[ALERT_TIMESTAMP_COL], errors="coerce", utc=True)
    frame = frame.dropna(subset=[ALERT_INCIDENT_COL, ALERT_SERVICE_COL, ALERT_TIMESTAMP_COL])
    return frame.sort_values([ALERT_INCIDENT_COL, ALERT_TIMESTAMP_COL]).reset_index(drop=True)


def iter_alerts_df(path: str | Path, chunk_size: int = 50_000) -> Iterator[pd.DataFrame]:
    """yield normalized alert dataframe chunks."""
    for chunk in iter_dataframe_chunks(path, chunk_size=chunk_size):
        yield normalize_alerts_df(chunk)
