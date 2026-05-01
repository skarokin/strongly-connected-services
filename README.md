# strongly-connected-services

Analysis tool that uses alerts to infer which services are tightly coupled by how often they fail together, with traces used to bootstrap topology and learn timing windows for propagation.

I'm not doing alert clustering. Rather, service clustering using alert behavior as evidence.
- Alert grouping would say "these alerts happened around the same time, so they're related."
- Service grouping says "these services appear to be operationally coupled because their failures repeatedly show up together in a causal pattern."

Alerts are used for:
- identifying real failures
- learning co-failure behavior
- grouping incidents by shared symptoms

Traces are used for:
- building the baseline service dependency graph
- learning timing windows for alert propagation
- explaining and validating suspected cascades

## Probable window

The tool uses traces to estimate a likely propagation window between services. If a traced path from service A to service B typically takes X time at p95, then alerts separated by roughly that amount plus a derived or pre-assumed alerting lag bufer are treated as plausible evidence of related failure behavior.

This window is simply a heuristic that says "this sequence is probably not random."

## High-confidence coupling signals

Coupling becomes high confidence only when multiple signals agree:

- repeated bidirectional failure propagation between the same services
- stable timing that fits the traced path and the probable window
- a real dependency mechanism in traces or architecture
- no stronger shared-root explanation, such as the same cache, deploy, node, or upstream outage
- enough repeated incidents to rule out coincidence

In other words, traces define what is plausible, alerts show what actually happened, and the repeated combination of both is what lets the tool say two services are effectively coupled.

The graph does not generate "these services share the same dependency", it generates "these services tend to form a failure loop"

So, the graph is DIRECTIONAL. An alert in Service A causing an alert in service B does not mean they are coupled. An alert in Service B ALSO causing an alert in service A now means they are coupled