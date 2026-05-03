# strongly-connected-services

Find tightly coupled services from observability data - specifically whether or not services seem to fail together

Uses `pandas` dataframes to combine trace-derived service topology with alert-derived failure evidence, then collapses the strongest bidirectional relationships into strongly connected components

This isn't alert clustering
- Alert clustering says "these pages happened together, so they are related"
- Service coupling says "these services repeatedly fail each other, so they behave like one failure domain"

## Dataframe-first pipeline

Project is built around chunked dataframes:
- Traces are streamed into dataframe chunks
- Trace chunks are summarized into service-path timing statistics
- Those timings define a plausible alert propagation window (if an alert in service B follows an alert in service A, consider the coupling plausible if service B's alert lies within this window)
- Alerts are streamed into dataframe chunks
- Alert chunks are grouped by incident and turned into ordered service pairs
- Candidate pairs are filtered by the trace-derived window
- The remaining evidence is scored using repeated bidirectional failure behavior
- Strong pairs are turned into a graph and rendered as Mermaid

## How timing is derived

Traces do not directly contribute to the coupling score; they are used to estimate a plausible window for a service pair. Example:
- Service `A -> B` usually takes about `5s` at p95
- An alert gap around that size is a plausible candidate
- The pair still needs repeated bidirectional evidence to be considered truly coupled

So, the window is a filter and plausibility check

## How coupling is decided

Coupling becomes high confidence only when multiple signals agree:
- Repeated bidirectional failure propagation between the same services
- Stable timing that fits the trace-derived plausible window
- No stronger shared-root explanation, like the same cache, deploy, node, or upstream outage
- Enough repeated incidents to rule out coincidence

In other words:
- Traces define what is plausible
- Alerts show what actually happened
- Repeated bidirectional evidence is what makes two services coupled

# Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run with real data

```bash
scs --alerts ./data/alerts.csv --traces ./data/traces.csv --min-score 0.05 --output ./out/graph.mmd
```

## Synthetic mode

The repo includes a synthetic data generator so you can test the pipeline locally without exporting real observability data. It generates `alerts.csv` and `traces.csv`, then feeds them through the same pipeline.

```bash
mkdir -p out
scs --synthetic --synthetic-incidents 400 --synthetic-seed 7 --synthetic-output-dir ./data/synthetic --min-score 0.05 --output ./out/graph.mmd
```

## Output

The output is Mermaid flowchart that you can render into a visual graph. The graph is directional, and strong bidirectional relationships collapse into SCCs.

## Choosing `--min-score`

the coupling score is normalized from `0` to `1`, so the threshold is easy to tune:

- `0.00` to `0.02` = very permissive, usually noisy
- `0.02` to `0.05` = good starting range for small or synthetic datasets
- `0.05` to `0.10` = stricter, usually cleaner clusters
- `0.10+` = only the strongest pairs survive

a simple way to pick a threshold:

1. start at `0.05`
2. if the graph is empty or too sparse, lower to `0.02` or `0.01`
3. if the graph is too noisy, raise it toward `0.10`
4. keep the threshold where obvious coupled groups remain and unrelated edges fall away

for this repo, `0.05` is a reasonable default for both synthetic and real runs, but real incident density may push you a little higher or lower.