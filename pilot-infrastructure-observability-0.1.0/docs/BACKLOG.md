# Pilot backlog

Initial customer: B2B software teams operating .NET/IIS and SQL Server, with developers participating in production support.

## 0.1.0 first slice
- Machine observation ingestion, stable IDs and server validation.
- CPU, memory and system-volume disk percentages; fresh/stale/unknown health.
- Local dashboard, synthetic demo producer and Windows CIM collector.
- Bounded inventory, retained deduplication window and health-change evidence.
- Local snapshot persistence and black-box API regression checks.

## 0.2.0 collector reliability
- Validate Windows collector on supported Windows Server versions.
- Durable queue/retry, enrollment and per-agent identity; TLS deployment.
- Service/IIS app pool discovery; monitored machine → service relationships.
- Automatic stale/recovered transitions in timeline, notification routing.
- Retention and SQLite/PostgreSQL migration; repository CI after approval.

## 0.3.0 application investigation
- .NET OpenTelemetry traces and SQL Server observations.
- Deployment markers and application → process → machine relationships.
- Incident timeline and evidence bundles; no unsupported causal claims.

## Later
- Pilot onboarding with one application and 3–10 hosts.
- Cluster adapters (including Raft), sites, regions and global federation.
- Tenant isolation, roles, audited operations and hosted service.

Release policy: supported OS verification, meaningful tests, upgrade/rollback check, documented limits, customer feedback. No production-readiness claim for 0.1.0.
