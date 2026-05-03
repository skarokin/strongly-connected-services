"""shared dataframe loading helpers for the ingest layer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd


def iter_dataframe_chunks(path: str | Path, chunk_size: int = 50_000) -> Iterator[pd.DataFrame]:
    """yield dataframe chunks from csv, tsv, jsonl, json, or parquet input."""
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()

    if suffix == ".csv":
        yield from pd.read_csv(path_obj, chunksize=chunk_size)
        return
    if suffix == ".tsv":
        yield from pd.read_csv(path_obj, chunksize=chunk_size, sep="	")
        return
    if suffix in {".jsonl", ".ndjson"}:
        yield from pd.read_json(path_obj, lines=True, chunksize=chunk_size)
        return
    if suffix == ".json":
        yield pd.read_json(path_obj)
        return
    if suffix == ".parquet":
        yield pd.read_parquet(path_obj)
        return
    raise ValueError(f"unsupported input format: {path_obj.suffix}")
