# Real Raft Integration & Fault Injection

**Design status:** Planned core capability, not yet implemented.  
**Prepared:** 2026-11-04  
**Related:** [Implementation roadmap](IMPLEMENTATION_PLAN.md)

## 1. Product requirement

The lab must integrate with a real Raft-based distributed system. It must provision or attach to an explicitly authorized **isolated test cluster**, inject controlled faults, collect evidence of consensus and application behavior, and produce a replayable *experiment configuration* plus diagnostic traces.

Two integration tracks are required:

1. **Managed real-Raft harness:** Run 3 or 5 independent real Raft peer processes based on etcd-io/raft (Go), expose a small replicated key/value state machine, observe consensus data, and control test faults through our .NET API.
2. **Existing Raft application adapter:** Observe a pre-existing Raft-based application via supported public APIs and inject network faults *only if its test network is deliberately routed through a controlled proxy*. For Kubernetes, an opt-in Chaos Mesh provider can follow.

A third, separate possibility is to **add Raft to a .NET application** using an opt-in replicated command SDK backed by a Raft sidecar. This needs application-specific replicated state machine integration, durable storage, peer transport, bootstrap, and safe reads; it cannot be transparently injected into an arbitrary app.

## 2. Architectural boundaries

- **Consensus.Contracts:** Shared scenario and trace schemas, capability negotiation, semantic test intent.
- **Consensus.Core / Consensus.Simulation:** Deterministic .NET teaching-model implementation from the main roadmap.
- **Consensus.Integrations.Abstractions:** IClusterAdapter, IFaultProvider, IObservationCollector; explicit capabilities.
- **Consensus.Integrations.RaftHarness:** C# client of Go sidecar running actual etcd-io/raft.
- **harness/go-raft/:** Separate processes for actual Raft nodes, durable storage, peer network, applied state machine, instrumentation and test-only control endpoint.
- **Consensus.Integrations.Toxiproxy:** TCP fault provider for connections explicitly routed via Toxiproxy in a disposable Docker network.
- **Consensus.Integrations.Etcd:** Existing-cluster adapter for an owned test etcd deployment, initially observation and client operation history.
- **Consensus.Checkers:** Independent safety/history/recovery verification.
- **Consensus.Api + React:** Select execution mode, validate capabilities, run experiment, show nodes/faults and evidence.
- **Control policy and cleanup:** Plan validation, environment identity, explicit opt-in, TTL, emergency stop and out-of-band restore.

### Integration flow

~~~mermaid
flowchart TB
  User["Experiment UI / CLI"] --> API["ASP.NET Core 10 API"]
  API --> Policy["Auth + Scope + Budget + Dry Run"]
  Policy --> Orchestrator["Experiment Orchestrator"]
  Orchestrator --> Simulator["Virtual .NET Simulator"]
  Orchestrator --> Adapter["IClusterAdapter"]
  Adapter --> Go["Go: etcd-io/raft Peer Harness"]
  Adapter --> Etcd["Existing etcd Test Adapter"]
  Policy --> Fault["IFaultProvider"]
  Fault --> MessageHook["Raft-aware Message Hook"]
  Fault --> Proxy["Toxiproxy TCP Layer"]
  MessageHook --> Go
  Proxy --> Go
  Proxy --> Etcd
  Simulator --> Checker["Independent Invariant Checker"]
  Go --> Collector["Client + Cluster Observation Collector"]
  Etcd --> Collector
  Collector --> Checker
  Checker --> Evidence["Trace + Witness + Recovery Report"]
  Evidence --> User
  Policy --> Cleanup["TTL + Cleanup Reaper"]
  Cleanup --> Fault
~~~

## 3. Contracts and capabilities

Proposed C# interfaces (examples, subject to implementation review):

~~~csharp
public interface IClusterAdapter : IAsyncDisposable
{
    Task<ClusterCapabilities> GetCapabilitiesAsync(CancellationToken ct);
    Task<ClusterSnapshot> ObserveAsync(CancellationToken ct);
    Task<ClientOperationResult> SubmitAsync(ClientOperation operation, CancellationToken ct);
    IAsyncEnumerable<ClusterEvent> WatchAsync(CancellationToken ct);
}

public interface IFaultProvider
{
    Task<FaultReceipt> ApplyAsync(FaultPlan plan, CancellationToken ct);
    Task<FaultReceipt> RevertAsync(string faultId, CancellationToken ct);
}
~~~

Capabilities must be explicit (supports message-level faults, TCP partition, process restart, storage fault, leader observation, applied-index observation). Reject unsupported faults; do not silently approximate a Raft-message drop with a TCP chunk drop.

**Toxiproxy limitation:** It disrupts TCP streams and sockets, not named Raft RPCs. Precise drop/duplicate/reorder of one RequestVote or AppendEntries message requires a Raft-aware hook in the Go harness. The packet-loss toxic acts on chunks of TCP traffic; it is not equivalent to selectively dropping a logical RPC.

**Determinism boundary:** Our virtual simulator can give exact schedule replay with pinned engine/seed/decisions. A real cluster has OS scheduling, wall clock, peer transport and storage nondeterminism. Its artifacts support reproducible *fault configuration and outcome checks*, not guaranteed identical event ordering.

## 4. Actual Raft harness design

Use etcd-io/raft with separate peer processes/containers and an explicit test FSM (initially SET and GET on a single replicated map), not virtual nodes in one process. Each peer must implement:

1. Peer identity and bootstrap, Node.Tick, Node.Step and Node.Propose.
2. Correct processing of Ready; persist entries, HardState and snapshots in required order before dependent outgoing messages, apply committed entries and call Advance. Test crash/restart with retained volumes.
3. A peer transport with selectable test-only per-RPC message hook and optional proxy-routed TCP connections.
4. Client operation IDs and explicit semantics for committed/applied acknowledgments; no silent assumption that a proposed operation always commits.
5. Observation endpoint with node ID, term, role/leader, commit index, applied index, log state (test-only), lifecycle and storage incarnation.
6. Safe local process/container management and explicit cleanup; never wipe data as part of an ordinary restart.

The first managed implementation is based on a Go Raft engine; C# is the orchestration, checking and presentation language, not a rewrite of the production consensus library.

## 5. Fault matrix

| Fault | Virtual simulator | Go Raft harness | Attached test cluster |
| --- | --- | --- | --- |
| Bidirectional / directional partition | Yes, logical links | Yes, message hook or TCP proxy | Yes, if peer links are routed through proxy |
| Latency and jitter | Yes, virtual ticks | Yes | Yes, via TCP proxy |
| TCP packet/chunk loss | Simulated messages | Yes, via proxy | Yes, via proxy |
| Drop one RequestVote | Yes | Yes, Raft-aware message hook | No, without an instrumented adapter |
| Duplicate/reorder specific Raft RPC | Yes | Yes, Raft-aware hook | No, with generic TCP proxy |
| Crash / restart | Virtual lifecycle | Yes, owned test processes | Only managed disposable test containers |
| Disk write failure | Simulated storage fault (later) | Explicit storage shim (later) | No by default |
| Healing / catch-up | Yes | Yes | Yes, if network recovery observed |

**Recovery must be measured**: confirming a fault was removed does not prove a node recovered. Verify health, quorum, leadership, replication/applied state and workload success.

## 6. Safe operating boundaries

Only operate on clearly registered, isolated test deployments owned or controlled by the operator. Initial version should reject external production targets entirely.

- Endpoints and container namespaces must be explicitly allowlisted, not discovered as arbitrary reachable addresses.
- Provide dry-run preview of exact target links, processes, fault type, duration, cleanup method, estimated quorum impact and test artifacts.
- Distinguish control-plane connectivity from the faulted data plane; never route fault cleanup through a connection that is intentionally partitioned.
- Every fault has a TTL and automatic rollback on completion/cancellation/exception, plus an independent cleanup reaper. If cleanup cannot be confirmed, mark FAILED_CLEANUP and block further injections.
- Keep Toxiproxy's administrative endpoint on a trusted network. It is unauthenticated by default; where supported use an auth token and never expose it to the public internet.
- Limit node count, experiment duration, fault scope, restarts, concurrent runs, event counts, resource usage and artifact sizes.
- Require operator authorization, log all control actions, redact secrets; ensure any future hosted UI uses authentication and least privilege.
- No chaos experiments against production service dependencies or unowned systems.

## 7. Verification strategy and expected outcomes

Minimum live-system tests:

1. A healthy three-node cluster elects a leader and commits a value. Check that applied/read results agree on healthy replicas under appropriately consistent read modes.
2. Isolate a follower; remaining majority acknowledges subsequent writes, minority does not commit new writes.
3. Heal and confirm follower catches up to the committed state.
4. Crash/restart one follower preserving durable data; previously acknowledged writes survive.
5. Isolate the leader; remaining majority can elect another leader, while client operations on the isolated leader do not falsely claim successful majority commitment.
6. Add asymmetric delay/loss and verify behavior against documented timeouts; check recovery, not guaranteed exact timings.
7. Re-run same fault configuration and compare invariant outcomes and recovery distributions rather than byte-identical traces.

Independent checker evidence should capture client invocation/response intervals, any unknown/timeout outcome, operation IDs, leader term, committed/applied indices where exposed, and time-aligned transport fault activation. A timeout is an inconclusive operation, not a confirmed failed commit. Lack of observed violation does not imply formal correctness.

## 8. Planned real-cluster experiment

1. Start a **disposable** 3-node Go Raft test cluster under Docker Compose or Testcontainers with a Toxiproxy control network.
2. Confirm cluster healthy and send SET order-1=paid; wait for an applied/committed acknowledgment.
3. Partition one follower from the remaining peers; submit SET order-2=shipped through majority.
4. Demonstrate that the isolated minority cannot acknowledge fresh majority-committed writes.
5. Heal, observe replication catch-up and compare state machines.
6. Crash/restart the previously isolated follower using its persisted test volume.
7. Export a forensic bundle containing node states, fault timestamps, client operation history, consistency verdicts, health and cleanup receipt.
8. Run the same declared fault configuration again and show what can and cannot be deterministically reproduced.

## 9. Delivery, acceptance and ownership

The original plan was 16 weeks / 192–240 engineering hours at 12–15 hours/week. Making real-Raft integration a mandatory deliverable expands the **estimate to 20 weeks / 240–300 hours**, with integration preceding the UI.

| Sprint | Week | Acceptance gate |
| --- | --- | --- |
| INT-01: Contract & safety policy | 9 | Adapter and FaultProvider interfaces; dry-run rejects unsupported/unsafe fault |
| INT-02: Real Raft harness | 10 | 3 peers elect leader, replicate values, restart follower with persistent volume |
| INT-03: Transport fault integration | 11 | Real partition/latency test; majority continues, minority blocked, controlled healing |
| INT-04: Evidence/cleanup | 12 | Recovery verified; every fault reverted or explicit FAILED_CLEANUP; report exported |
| INT-05: Existing etcd test adapter | After core MVP | Attach to disposable etcd, capability negotiation and safe network tests |
| INT-06: .NET embedding SDK | Future option | Opt-in replicated commands to harness; explicit FSM and durability contract |

Updated overall sequence:

| Weeks | Work |
| --- | --- |
| 1 | Python baseline, CI fix, golden fixtures |
| 2 | Contracts, .NET scaffold |
| 3–5 | .NET Raft-inspired engine parity |
| 6 | Scenario DSL and replay |
| 7–8 | Independent invariant checks |
| **9–12** | **Real Raft harness, fault injectors, observation, rollback** |
| 13–14 | Schedule exploration and counterexample minimization |
| 15–16 | ASP.NET API and React UI |
| 17–18 | TLA+ bounded checks |
| 19–20 | Security, benchmark study, docs, release |

**Definition of done for real-Raft feature:** From one documented local command, a three-node actual Raft implementation runs, accepts test writes, suffers an injected network partition, maintains safe majority behavior, recovers after cleanup, and provides machine-readable verification evidence. The complete run is repeatable as a test *configuration*, not guaranteed as an identical event trace.

## 10. Research references

- etcd-io/raft: https://github.com/etcd-io/raft
- Raft library host duties and Ready/Advance usage: https://github.com/etcd-io/raft/blob/main/doc.go
- Shopfiy Toxiproxy official project: https://github.com/Shopify/toxiproxy
- Toxiproxy module for Testcontainers .NET: https://dotnet.testcontainers.org/modules/toxiproxy/
- Chaos Mesh NetworkChaos for possible future Kubernetes integration: https://chaos-mesh.org/docs/simulate-network-chaos-on-kubernetes/
- HashiCorp Raft, alternative library: https://github.com/hashicorp/raft
- Jepsen history-based system testing: https://github.com/jepsen-io/jepsen

**Claims scope:** Published docs establish supported features, not independent benchmark superiority; keep vendor/library versions pinned when implementation begins.
