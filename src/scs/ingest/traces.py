"""load trace/span data as pandas dataframes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from ..models import TRACE_LATENCY_COL, TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL, TRACE_TIMESTAMP_COL, required_columns
from .shared import iter_dataframe_chunks


def normalize_traces_df(df: pd.DataFrame) -> pd.DataFrame:
    """normalize the trace dataframe into the canonical schema"""
    frame = df.copy()
    required_columns(frame, [TRACE_TIMESTAMP_COL, TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL, TRACE_LATENCY_COL], name="traces")
    frame[TRACE_TIMESTAMP_COL] = pd.to_datetime(frame[TRACE_TIMESTAMP_COL], errors="coerce", utc=True)
    frame[TRACE_LATENCY_COL] = pd.to_numeric(frame[TRACE_LATENCY_COL], errors="coerce")
    frame = frame.dropna(subset=[TRACE_TIMESTAMP_COL, TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL, TRACE_LATENCY_COL])
    return frame.sort_values([TRACE_TIMESTAMP_COL, TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL]).reset_index(drop=True)


def iter_spans_df(path: str | Path, chunk_size: int = 50_000) -> Iterator[pd.DataFrame]:
    """yield normalized span dataframe chunks."""
    for chunk in iter_dataframe_chunks(path, chunk_size=chunk_size):
        yield normalize_traces_df(chunk)
