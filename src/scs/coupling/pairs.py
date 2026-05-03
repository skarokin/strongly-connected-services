"""build ordered alert pairs and window filters from alert dataframes.

convert incident-level alerts into candidate service pairs.
it keeps only pairs that look plausible against the trace-derived windows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from itertools import combinations

import pandas as pd

from ..ingest.alerts import normalize_alerts_df
from ..models import (
    ALERT_INCIDENT_COL,
    ALERT_PAIR_DELTA_COL,
    ALERT_PAIR_INCIDENT_COL,
    ALERT_PAIR_PATH_EXISTS_COL,
    ALERT_PAIR_SOURCE_COL,
    ALERT_PAIR_TARGET_COL,
    ALERT_PAIR_WITHIN_WINDOW_COL,
    ALERT_SERVICE_COL,
    ALERT_TIMESTAMP_COL,
    COUPLING_LEFT_COL,
    COUPLING_RIGHT_COL,
    SERVICE_PATH_P95_COL,
    SERVICE_PATH_WINDOW_COL,
    TRACE_SOURCE_SERVICE_COL,
    TRACE_TARGET_SERVICE_COL,
    canonical_pair,
    required_columns,
)


def build_alert_pairs_df(
    alert_frames: Iterable[pd.DataFrame],
    service_windows_df: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """create ordered alert pairs and mark which ones fit the trace-derived windows"""
    incident_buckets: dict[str, list[dict[str, object]]] = defaultdict(list)

    # stream each alert chunk into an incident bucket so we can pair alerts per incident
    for chunk in alert_frames:
        frame = normalize_alerts_df(chunk)
        if frame.empty:
            continue

        for incident_id, service, timestamp in frame[
            [ALERT_INCIDENT_COL, ALERT_SERVICE_COL, ALERT_TIMESTAMP_COL]
        ].itertuples(index=False, name=None):
            incident_buckets[str(incident_id)].append(
                {
                    ALERT_SERVICE_COL: str(service),
                    ALERT_TIMESTAMP_COL: timestamp,
                }
            )

    records: list[dict[str, object]] = []
    # compare alerts inside each incident to find co-failure sequences
    for incident_id, alerts in incident_buckets.items():
        alerts.sort(key=lambda item: item[ALERT_TIMESTAMP_COL])
        # compare each alert pair
        for left, right in combinations(alerts, 2):
            if left[ALERT_SERVICE_COL] == right[ALERT_SERVICE_COL]:
                continue

            source, target = left, right    # source is the earlier alert

            delta_s = (target[ALERT_TIMESTAMP_COL] - source[ALERT_TIMESTAMP_COL]).total_seconds()
            service_a, service_b = canonical_pair(str(source[ALERT_SERVICE_COL]), str(target[ALERT_SERVICE_COL]))
            records.append(
                {
                    ALERT_PAIR_INCIDENT_COL: incident_id,
                    ALERT_PAIR_SOURCE_COL: source[ALERT_SERVICE_COL],
                    ALERT_PAIR_TARGET_COL: target[ALERT_SERVICE_COL],
                    ALERT_PAIR_DELTA_COL: delta_s,
                    COUPLING_LEFT_COL: service_a,
                    COUPLING_RIGHT_COL: service_b,
                }
            )

    pairs_df = pd.DataFrame.from_records(records)
    total_incidents = len(incident_buckets)
    if pairs_df.empty:
        return (
            pd.DataFrame(
                columns=[
                    ALERT_PAIR_INCIDENT_COL,
                    ALERT_PAIR_SOURCE_COL,
                    ALERT_PAIR_TARGET_COL,
                    ALERT_PAIR_DELTA_COL,
                    COUPLING_LEFT_COL,
                    COUPLING_RIGHT_COL,
                    TRACE_SOURCE_SERVICE_COL,
                    TRACE_TARGET_SERVICE_COL,
                    SERVICE_PATH_P95_COL,
                    SERVICE_PATH_WINDOW_COL,
                    ALERT_PAIR_PATH_EXISTS_COL,
                    ALERT_PAIR_WITHIN_WINDOW_COL,
                ]
            ),
            total_incidents,
        )

    windows = service_windows_df.copy()
    # only pairs with an actual traced path can be judged against the plausible window
    required_columns(
        windows,
        [TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL, SERVICE_PATH_P95_COL, SERVICE_PATH_WINDOW_COL],
        name="service_windows",
    )

    # merge the alert pairs with their trace-derived timing window
    merged = pairs_df.merge(
        windows,
        left_on=[ALERT_PAIR_SOURCE_COL, ALERT_PAIR_TARGET_COL],
        right_on=[TRACE_SOURCE_SERVICE_COL, TRACE_TARGET_SERVICE_COL],
        how="left",
        suffixes=("", "_trace"),
    )
    merged[ALERT_PAIR_PATH_EXISTS_COL] = merged[SERVICE_PATH_WINDOW_COL].notna()
    # only keep the pair if the alert gap fits inside the plausible trace window
    merged[ALERT_PAIR_WITHIN_WINDOW_COL] = merged[ALERT_PAIR_PATH_EXISTS_COL] & (
        merged[ALERT_PAIR_DELTA_COL] <= merged[SERVICE_PATH_WINDOW_COL]
    )
    return (
        merged.sort_values([ALERT_PAIR_INCIDENT_COL, ALERT_PAIR_SOURCE_COL, ALERT_PAIR_TARGET_COL]).reset_index(drop=True),
        total_incidents,
    )
