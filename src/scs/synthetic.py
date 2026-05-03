"""generate synthetic alert and trace data for local testing.
what it generates:
- alert rows with `incident_id`, `service`, `timestamp`, `name`, and `severity`
- trace/span rows with `source_service`, `target_service`, `timestamp`, and
  `duration_ms`

how it works:
- define a few realistic service clusters as scenarios
- rotate the service order per incident so the same pair can appear in both
  directions across the dataset
- generate trace rows for every service pair inside a scenario so the trace
  side has a plausible dependency graph and latency distribution
- generate alert rows for the same incident so the alert side has a failure
  timeline to compare against the trace-derived timing window
- include a couple of shared upstream roots like `postgres` and `redis_cache`
  so the data also contains one-way root-cause style dependencies
- stream the generated rows out in dataframe chunks so the rest of the code
  can treat the synthetic path the same way it treats real inputs
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random

import pandas as pd

from .models import (
    ALERT_INCIDENT_COL,
    ALERT_NAME_COL,
    ALERT_SEVERITY_COL,
    ALERT_SERVICE_COL,
    ALERT_TIMESTAMP_COL,
    TRACE_LATENCY_COL,
    TRACE_SOURCE_SERVICE_COL,
    TRACE_TARGET_SERVICE_COL,
    TRACE_TIMESTAMP_COL,
)


@dataclass(frozen=True)
class SyntheticScenario:
    """describe one realistic coupled-service cluster"""

    name: str
    services: tuple[str, ...]
    trace_latency_ms: tuple[int, int]
    alert_step_seconds: tuple[float, float]
    root_services: tuple[str, ...] = ("postgres", "redis_cache")


SCENARIOS: tuple[SyntheticScenario, ...] = (
    SyntheticScenario(
        name="auth_session",
        services=("auth_service", "session_store"),
        trace_latency_ms=(800, 3500),
        alert_step_seconds=(2.0, 6.0),
    ),
    SyntheticScenario(
        name="billing_payments_webhooks",
        services=("billing_service", "payments_service", "webhook_processor"),
        trace_latency_ms=(1200, 7000),
        alert_step_seconds=(2.5, 8.0),
    ),
    SyntheticScenario(
        name="order_inventory_reservation",
        services=("order_service", "inventory_service", "reservation_service"),
        trace_latency_ms=(1000, 6000),
        alert_step_seconds=(2.0, 7.0),
    ),
    SyntheticScenario(
        name="search_indexing_cache",
        services=("search_api", "indexer", "cache_warmer", "query_router"),
        trace_latency_ms=(600, 4500),
        alert_step_seconds=(1.5, 5.0),
    ),
    SyntheticScenario(
        name="notifications_delivery",
        services=("notifications_service", "email_worker", "sms_gateway", "template_renderer"),
        trace_latency_ms=(700, 5000),
        alert_step_seconds=(1.5, 6.0),
    ),
    SyntheticScenario(
        name="analytics_pipeline",
        services=("event_collector", "stream_processor", "metrics_aggregator", "warehouse_loader"),
        trace_latency_ms=(900, 6500),
        alert_step_seconds=(2.0, 7.5),
    ),
    SyntheticScenario(
        name="gateway_routing",
        services=("api_gateway", "tenant_router", "feature_flag_service", "rate_limiter"),
        trace_latency_ms=(500, 3200),
        alert_step_seconds=(1.0, 4.5),
    ),
    SyntheticScenario(
        name="admin_compliance",
        services=("admin_console", "audit_service", "compliance_exporter", "report_scheduler"),
        trace_latency_ms=(650, 4800),
        alert_step_seconds=(1.5, 5.5),
    ),
)

ALERT_SEVERITIES = ("warning", "critical")


def _rotate(values: tuple[str, ...], shift: int) -> tuple[str, ...]:
    """rotate a tuple so each incident starts from a different service"""
    shift = shift % len(values)
    return values[shift:] + values[:shift]


def _scenario_for_incident(incident_index: int) -> SyntheticScenario:
    """pick a repeating scenario so the dataset stays balanced"""
    return SCENARIOS[incident_index % len(SCENARIOS)]


def _incident_start(incident_index: int) -> datetime:
    """space incidents apart so the timestamps stay readable"""
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=incident_index * 9)


def _chunk_rows(rows: list[dict[str, object]], chunk_size: int) -> Iterator[pd.DataFrame]:
    """yield dataframe chunks from a row buffer"""
    for start in range(0, len(rows), chunk_size):
        yield pd.DataFrame.from_records(rows[start : start + chunk_size])


def _build_incident_order(scenario: SyntheticScenario, incident_index: int) -> tuple[str, ...]:
    """rotate the coupled services so forward and reverse evidence both appear"""
    return _rotate(scenario.services, incident_index)


def _build_trace_rows(
    incident_id: str,
    scenario: SyntheticScenario,
    order: tuple[str, ...],
    base_time: datetime,
    rng: Random,
) -> list[dict[str, object]]:
    """build trace rows for one synthetic incident."""
    rows: list[dict[str, object]] = []
    low_ms, high_ms = scenario.trace_latency_ms

    # make the core services look mutually coupled by emitting full pair coverage
    for source in order:
        for target in order:
            if source == target:
                continue
            for sample_index in range(2):
                rows.append(
                    {
                        ALERT_INCIDENT_COL: incident_id,
                        "scenario": scenario.name,
                        TRACE_TIMESTAMP_COL: base_time + timedelta(seconds=sample_index),
                        TRACE_SOURCE_SERVICE_COL: source,
                        TRACE_TARGET_SERVICE_COL: target,
                        TRACE_LATENCY_COL: rng.randint(low_ms, high_ms),
                    }
                )

    # add a shared upstream dependency so the graph also sees realistic root causes
    for root_service in scenario.root_services:
        for target_index, target in enumerate(order[: max(1, min(2, len(order)))]):
            rows.append(
                {
                    ALERT_INCIDENT_COL: incident_id,
                    "scenario": scenario.name,
                    TRACE_TIMESTAMP_COL: base_time + timedelta(seconds=10 + target_index),
                    TRACE_SOURCE_SERVICE_COL: root_service,
                    TRACE_TARGET_SERVICE_COL: target,
                    TRACE_LATENCY_COL: rng.randint(150, 1200),
                }
            )

    return rows


def _build_alert_rows(
    incident_id: str,
    scenario: SyntheticScenario,
    order: tuple[str, ...],
    base_time: datetime,
    rng: Random,
) -> list[dict[str, object]]:
    """build alert rows for one synthetic incident."""
    rows: list[dict[str, object]] = []
    current_time = base_time

    for index, service in enumerate(order):
        rows.append(
            {
                ALERT_INCIDENT_COL: incident_id,
                "scenario": scenario.name,
                ALERT_TIMESTAMP_COL: current_time,
                ALERT_SERVICE_COL: service,
                ALERT_NAME_COL: f"{scenario.name}:{service}:failure",
                ALERT_SEVERITY_COL: ALERT_SEVERITIES[min(index, len(ALERT_SEVERITIES) - 1)],
            }
        )
        current_time += timedelta(seconds=rng.uniform(*scenario.alert_step_seconds))

    return rows


def iter_synthetic_traces_df(
    incident_count: int = 250,
    *,
    seed: int = 7,
    chunk_size: int = 50_000,
) -> Iterator[pd.DataFrame]:
    """yield synthetic trace dataframe chunks."""
    rng = Random(seed)
    rows: list[dict[str, object]] = []
    for incident_index in range(incident_count):
        scenario = _scenario_for_incident(incident_index)
        order = _build_incident_order(scenario, incident_index)
        incident_id = f"incident-{incident_index:05d}"
        base_time = _incident_start(incident_index)
        rows.extend(_build_trace_rows(incident_id, scenario, order, base_time, rng))
        if len(rows) >= chunk_size:
            yield from _chunk_rows(rows, chunk_size)
            rows = []
    if rows:
        yield from _chunk_rows(rows, chunk_size)


def iter_synthetic_alerts_df(
    incident_count: int = 250,
    *,
    seed: int = 7,
    chunk_size: int = 50_000,
) -> Iterator[pd.DataFrame]:
    """yield synthetic alert dataframe chunks."""
    rng = Random(seed)
    rows: list[dict[str, object]] = []
    for incident_index in range(incident_count):
        scenario = _scenario_for_incident(incident_index)
        order = _build_incident_order(scenario, incident_index)
        incident_id = f"incident-{incident_index:05d}"
        base_time = _incident_start(incident_index)
        rows.extend(_build_alert_rows(incident_id, scenario, order, base_time, rng))
        if len(rows) >= chunk_size:
            yield from _chunk_rows(rows, chunk_size)
            rows = []
    if rows:
        yield from _chunk_rows(rows, chunk_size)


def write_synthetic_dataset(
    output_dir: str | Path,
    *,
    incident_count: int = 250,
    seed: int = 7,
    chunk_size: int = 50_000,
) -> tuple[Path, Path]:
    """write synthetic alerts and traces to csv files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    alerts_path = output_path / "alerts.csv"
    traces_path = output_path / "traces.csv"

    alert_chunks = list(iter_synthetic_alerts_df(incident_count, seed=seed, chunk_size=chunk_size))
    trace_chunks = list(iter_synthetic_traces_df(incident_count, seed=seed, chunk_size=chunk_size))

    pd.concat(alert_chunks, ignore_index=True).to_csv(alerts_path, index=False)
    pd.concat(trace_chunks, ignore_index=True).to_csv(traces_path, index=False)
    return alerts_path, traces_path
