"""score service coupling from dataframe-based alert evidence.
- timing windows decide what is plausible
- repeated bidirectional alert evidence decides what is coupled
"""

from __future__ import annotations

import math

import pandas as pd

from ..models import (
    ALERT_PAIR_INCIDENT_COL,
    ALERT_PAIR_PATH_EXISTS_COL,
    ALERT_PAIR_SOURCE_COL,
    ALERT_PAIR_WITHIN_WINDOW_COL,
    COUPLING_BALANCE_COL,
    COUPLING_COVERAGE_COL,
    COUPLING_FORWARD_HITS_COL,
    COUPLING_LEFT_COL,
    COUPLING_REVERSE_HITS_COL,
    COUPLING_RIGHT_COL,
    COUPLING_SCORE_COL,
    COUPLING_SUPPORT_COL,
    COUPLING_TOTAL_INCIDENTS_COL,
    required_columns,
)


def score_coupling(
    forward_hits: int,
    reverse_hits: int,
    incident_coverage: int,
    total_incidents: int,
) -> float:
    if total_incidents <= 0:
        return 0.0

    if incident_coverage <= 0:
        return 0.0

    # coverage says how often this pair appears across all incidents
    coverage = incident_coverage / total_incidents
    # a true coupled pair should show up in both directions, not just one
    balance = 1.0 - abs(forward_hits - reverse_hits) / max(forward_hits + reverse_hits, 1)
    score = math.sqrt(coverage * balance)

    # keep the score normalized so thresholds are easy to reason about
    return round(max(0.0, min(1.0, score)), 4)


def build_coupling_df(
    alert_pairs_df: pd.DataFrame,
    total_incidents: int | None = None,
    only_within_window: bool = True,
) -> pd.DataFrame:
    """aggregate alert pairs into a pairwise coupling score table"""
    frame = alert_pairs_df.copy()
    # the pair table already contains the candidate relationship and its window checks
    required_columns(
        frame,
        [
            ALERT_PAIR_INCIDENT_COL,
            ALERT_PAIR_SOURCE_COL,
            COUPLING_LEFT_COL,
            COUPLING_RIGHT_COL,
            ALERT_PAIR_PATH_EXISTS_COL,
            ALERT_PAIR_WITHIN_WINDOW_COL,
        ],
        name="alert_pairs",
    )

    if total_incidents is None:
        # use the full incident universe so coverage is comparable across pairs
        total_incidents = int(frame[ALERT_PAIR_INCIDENT_COL].nunique())

    # windowed pairs are the only ones we want to score by default
    if only_within_window:
        frame = frame[frame[ALERT_PAIR_WITHIN_WINDOW_COL]]
    else:
        frame = frame[frame[ALERT_PAIR_PATH_EXISTS_COL]]

    if frame.empty:
        # keep the expected output columns even when nothing survives filtering
        return pd.DataFrame(
            columns=[
                COUPLING_LEFT_COL,
                COUPLING_RIGHT_COL,
                COUPLING_FORWARD_HITS_COL,
                COUPLING_REVERSE_HITS_COL,
                COUPLING_SUPPORT_COL,
                COUPLING_BALANCE_COL,
                COUPLING_COVERAGE_COL,
                COUPLING_TOTAL_INCIDENTS_COL,
                COUPLING_SCORE_COL,
            ]
        )

    frame = frame.assign(
        # forward means the alert ordering matches the canonical pair ordering
        is_forward=frame[ALERT_PAIR_SOURCE_COL] == frame[COUPLING_LEFT_COL],
        # reverse means the incident observed the same pair in the opposite direction
        is_reverse=frame[ALERT_PAIR_SOURCE_COL] == frame[COUPLING_RIGHT_COL],
    )

    # count how often this pair appears in each direction across all incidents
    grouped = frame.groupby([COUPLING_LEFT_COL, COUPLING_RIGHT_COL], dropna=False)
    coupling_df = grouped.agg(
        forward_hits=("is_forward", "sum"),
        reverse_hits=("is_reverse", "sum"),
        incident_coverage=(ALERT_PAIR_INCIDENT_COL, "nunique"),
    ).reset_index()
    # support is the total amount of directional evidence for the pair
    coupling_df[COUPLING_SUPPORT_COL] = (
        coupling_df[COUPLING_FORWARD_HITS_COL] + coupling_df[COUPLING_REVERSE_HITS_COL]
    )
    # balance gets smaller when one direction dominates the other
    coupling_df[COUPLING_BALANCE_COL] = 1.0 - (
        (coupling_df[COUPLING_FORWARD_HITS_COL] - coupling_df[COUPLING_REVERSE_HITS_COL]).abs()
        / coupling_df[COUPLING_SUPPORT_COL].clip(lower=1)
    )
    coupling_df[COUPLING_TOTAL_INCIDENTS_COL] = total_incidents
    # score only the repeated bidirectional evidence, not the timing window itself
    coupling_df[COUPLING_SCORE_COL] = coupling_df.apply(
        lambda row: score_coupling(
            int(row[COUPLING_FORWARD_HITS_COL]),
            int(row[COUPLING_REVERSE_HITS_COL]),
            int(row["incident_coverage"]),
            int(row[COUPLING_TOTAL_INCIDENTS_COL]),
        ),
        axis=1,
    )
    return coupling_df.sort_values([COUPLING_SCORE_COL, COUPLING_SUPPORT_COL], ascending=[False, False]).reset_index(drop=True)
