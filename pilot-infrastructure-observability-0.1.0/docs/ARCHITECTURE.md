# Architecture decision: 0.1.0

Use a small ASP.NET Core application with a local web UI. Keep the domain independent of consensus protocols: Machine, Observation and Evidence are the current contracts. Later introduce Resource and Relationship abstractions when implementing application/process discovery.

Flow: Windows CIM collector → authenticated HTTP observation endpoint → validated latest machine state → serialized snapshot → query-time health assessment → machine dashboard / evidence timeline.

Persistence: one API process owns the JSON file. Updates are prepared in memory, written to a temporary file and renamed before the in-memory snapshot changes. Failed writes do not advance visible state. This is a development storage adapter; database transactions and retention jobs are planned.

Health is a versioned resource-pressure rule, not a diagnosis. Missing metrics yield unknown unless the available evidence already shows warning/critical. Old observations yield stale regardless of historical pressure. Partial results and unsupported components remain explicit.

The current browser screen is dependency-free to keep the first slice small. Preserve API contracts when migrating to React. Use a mature telemetry backend for future historical metrics; do not turn the snapshot store into a time-series database.

Raft lab remains separate. Its future role is a cluster adapter and reproducible failure corpus, not the operational platform's coordination implementation.
