"""command-line entrypoint for building and rendering service coupling graphs."""

from __future__ import annotations

import argparse
from pathlib import Path

from .coupling import build_alert_pairs_df, build_coupling_df, build_plausible_windows_df, build_service_paths_df
from .graph.build import build_graph
from .ingest.alerts import iter_alerts_df
from .ingest.traces import iter_spans_df
from .render.mermaid import render_mermaid
from .synthetic import iter_synthetic_alerts_df, iter_synthetic_traces_df, write_synthetic_dataset


def build_parser() -> argparse.ArgumentParser:
    """build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="scs")
    parser.add_argument("--version", action="version", version="0.1.0")
    parser.add_argument("--alerts", help="path to alerts data (jsonl/csv/parquet)")
    parser.add_argument("--traces", help="path to traces data (jsonl/csv/parquet)")
    parser.add_argument("--synthetic", action="store_true", help="generate synthetic data instead of reading files")
    parser.add_argument("--synthetic-incidents", type=int, default=250, help="number of synthetic incidents to generate")
    parser.add_argument("--synthetic-seed", type=int, default=7, help="random seed for synthetic data")
    parser.add_argument("--synthetic-chunk-size", type=int, default=50_000, help="chunk size for synthetic generation")
    parser.add_argument("--synthetic-output-dir", type=Path, help="optional directory to write synthetic csv files")
    parser.add_argument("--min-score", type=float, default=0.05, help="minimum coupling score to render")
    parser.add_argument(
        "--alert-lag-seconds",
        type=float,
        default=0.0,
        help="extra allowance added to trace p95 latency when building plausible windows",
    )
    parser.add_argument("--window-floor-seconds", type=float, default=5.0, help="lower bound for plausible windows")
    parser.add_argument("--window-ceiling-seconds", type=float, default=300.0, help="upper bound for plausible windows")
    parser.add_argument("--output", type=Path, help="optional path to write the mermaid graph")
    parser.add_argument("--title", default="Inferred Service Coupling Graph", help="mermaid graph title")
    return parser


def _validate_inputs(args: argparse.Namespace) -> None:
    """check that the user gave either synthetic mode or real inputs."""
    if args.synthetic:
        return
    if not args.alerts or not args.traces:
        raise SystemExit("either pass --synthetic or provide both --alerts and --traces")


def main(argv: list[str] | None = None) -> int:
    """run the CLI."""
    args = build_parser().parse_args(argv)
    _validate_inputs(args)

    if args.synthetic:
        if args.synthetic_output_dir is not None:
            write_synthetic_dataset(
                args.synthetic_output_dir,
                incident_count=args.synthetic_incidents,
                seed=args.synthetic_seed,
                chunk_size=args.synthetic_chunk_size,
            )
        trace_frames = iter_synthetic_traces_df(
            incident_count=args.synthetic_incidents,
            seed=args.synthetic_seed,
            chunk_size=args.synthetic_chunk_size,
        )
        alert_frames = iter_synthetic_alerts_df(
            incident_count=args.synthetic_incidents,
            seed=args.synthetic_seed,
            chunk_size=args.synthetic_chunk_size,
        )
    else:
        trace_frames = iter_spans_df(args.traces)
        alert_frames = iter_alerts_df(args.alerts)

    service_paths_df = build_service_paths_df(trace_frames)
    windows_df = build_plausible_windows_df(
        service_paths_df,
        alert_lag_seconds=args.alert_lag_seconds,
        floor_seconds=args.window_floor_seconds,
        ceiling_seconds=args.window_ceiling_seconds,
    )
    alert_pairs_df, total_incidents = build_alert_pairs_df(alert_frames, windows_df)
    coupling_df = build_coupling_df(
        alert_pairs_df,
        total_incidents=total_incidents,
    )
    graph = build_graph(service_paths_df, coupling_df, min_score=args.min_score)
    mermaid = render_mermaid(graph, title=args.title)

    if args.output is not None:
        args.output.write_text(mermaid, encoding="utf-8")
    else:
        print(mermaid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
