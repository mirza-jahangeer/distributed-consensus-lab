# Implementation Plan — Distributed Consensus Failure Forensics Lab

**Version:** 1.0  
**Prepared:** 2026-11-04  
**Status:** Proposed implementation roadmap; this document is a plan, not evidence that the planned capabilities exist.  
**Repository:** https://github.com/mirza-jahangeer/distributed-consensus-lab  
**Proposed stack:** .NET 10/C#, React/TypeScript, TLA+ (TLC initially), Python 3.11+ reference MVP.  
**Planning assumption:** One primary developer working approximately 12–15 focused hours/week, 16 weeks (~192–240 hours). Schedule is an estimate, subject to test results and scope.

---

## 1. Product thesis and differentiation

Build a **deterministic consensus failure-forensics lab**, rather than another general-purpose Raft clone. Engineers should be able to define a bounded cluster, inject faults, search for a safety failure, reproduce it deterministically, reduce its execution to a shorter counterexample, and inspect the causal evidence in a browser.

**Differentiation hypothesis (to validate experimentally):** A workflow that joins (a) mutation-based correct-vs-buggy comparison, (b) explicit schedule search, (c) shrink-to-minimal reproduction, (d) invariant evidence, and (e) visually synchronized replay may reduce diagnosis time relative to conventional teaching demos. These individual techniques are not novel and project superiority is not established.

**Research questions:**
1. Can an automated bounded explorer find the known stale-candidate committed-overwrite bug without a hand-crafted script?
2. Can it reduce the generated witness while preserving the same invariant violation?
3. Does the evidence graph expose votes, leader changes, truncation and the violated committed prefix in an interpretable way?
4. Does the model agree with independent reference specifications and, eventually, a production implementation adapter on supported cases?

**Out-of-scope claims:** This will not be described as a novel consensus algorithm, a formally verified implementation, or a production consensus server merely because tests pass.

## 2. Verified starting point (2026-11-04)

The current GitHub main branch includes:

- Python package under src/consensus_lab: simulator.py, scenarios.py, cli.py, report.py.
- A five-node single-process Raft-inspired model with manual elections, proposals, partition/heal, targeted message drops, simulated crash/restart and an ordered virtual-time event queue.
- An explicit unsafe mode which skips RequestVote log-freshness verification, a fixed stale-candidate scenario, historical committed-entry checks and witness event IDs.
- CLI: run, compare, replay, report; JSON output with schema_version=1 and a standalone HTML comparison.
- Ten Python tests recorded as passing locally; a GitHub Actions matrix (3.11, 3.12, 3.13) is present but the latest progress document reports remote job failures before reported test steps.
- Architecture and research documents already committed.

**Important gaps:** No C# engine, no React application, no autonomous failure search or minimizer, no real persistent storage, no automatic timeouts, no external implementation adapter, no TLA+ model or model-checked results. Read docs/ARCHITECTURE.md and docs/LOW_LEVEL_DESIGN.md for current (Python) details.

**Migration rule:** Keep the Python MVP intact while building the .NET implementation. Do not rewrite the existing historical docs as if a proposed component already exists. Label future architecture explicitly as planned.

## 3. Scope by release

| Release | Target | Essential capabilities | Explicitly deferred |
| --- | --- | --- | --- |
| R0 / baseline | Week 1 | Reproducible Python baseline, CI diagnosis, contract fixtures, ADRs | New Raft features |
| R1 / C# parity | Weeks 2–6 | C# state machine, virtual scheduler, same stale-leader positive/negative demonstrations, parity fixtures | Production transport, automatic search |
| R2 / forensics MVP | Weeks 7–10 | Independent safety oracle, structured evidence, bounded seed-based schedule search, reproducible failing schedule and minimizer | General linearizability, formal proof |
| R3 / interactive lab | Weeks 11–12 | ASP.NET Core experiment API and browser timeline/cluster visualization, import/export, side-by-side replay | Public multi-user SaaS |
| R4 / research-grade prototype | Weeks 13–16 | Small TLA+ model checked with TLC, mutation experiments, benchmark/research report, release packaging, tightened CI | Full production Raft feature parity |

**Stretch only after R4:** Go sidecar adapter for etcd-io/raft, richer linearizability checker, persistence crash consistency, membership changes, snapshots, performance profiling and multi-user hosting.

## 4. Proposed architecture

~~~mermaid
flowchart TB
    User["Engineer / CI"] --> Web["React + TypeScript forensic UI"]
    User --> CLI[".NET CLI"]
    Web --> API["ASP.NET Core 10 Minimal API"]
    API --> Run["Experiment Orchestrator"]
    CLI --> Run
    Run --> Schema["Versioned Scenario Parser + Validator"]
    Schema --> Scheduler["Deterministic Scheduler / Virtual Clock"]
    Scheduler --> Network["Faultable Virtual Transport"]
    Network --> Raft["Raft-Inspired Transition Engine"]
    Raft --> Nodes["Immutable Node State + Outputs"]
    Raft --> Oracle["Independent Safety Oracles"]
    Scheduler --> Trace["Append-only Canonical Trace"]
    Oracle --> Trace
    Run --> Explorer["Bounded Schedule Explorer"]
    Explorer --> Shrink["Counterexample Minimizer"]
    Shrink --> Trace
    Trace --> Export["JSON and HTML Artifacts"]
    TLA["TLA+ / TLC (separate check)"] -.-> Oracle
    Python["Python Reference MVP"] -. "Golden / semantic parity" .-> Schema
    External["External implementation adapter (stretch)"] -.-> Run
~~~

**Architectural boundaries:**

- **Consensus.Core:** Pure, testable protocol transitions; no sockets, filesystem, wall-clock time, or web framework references.
- **Consensus.Simulation:** Owns deterministic time, queue, fault schedule and node lifecycle; executes transitions.
- **Consensus.Contracts:** Versioned scenarios, commands, messages, events, traces and violation records. Keep schemas framework-agnostic.
- **Consensus.Checkers:** Independent, read-only event/state analyzers; never modify a consensus node during checking.
- **Consensus.Exploration:** Bounded schedule generation, canonical state hashing, duplicate-state pruning, failure extraction and shrinking.
- **Consensus.Cli:** Script and report entry points; must work offline.
- **Consensus.Api:** Experiment execution/query endpoints; bounded resources, input validation and streaming of trace events.
- **web/:** React UI consumes API/trace schemas; no consensus rules embedded in the browser.
- **formal/:** Finite TLA+ model, TLC configs, expected failing mutant, and documented checking assumptions.
- **python-reference/:** Preserve or relocate existing Python source only after the package path and CI compatibility have been migrated with a separate change.

**Guiding principle:** Consensus rules and scheduler must be independent, so the lab can later swap its teaching implementation for an external library without rewriting the explorer.

## 5. Detailed design and contracts

### 5.1 Pure transition model

Prefer a transition shape equivalent to:

~~~csharp
public interface IConsensusNode
{
    TransitionResult Step(NodeState state, NodeInput input);
}
public sealed record TransitionResult(
    NodeState NextState,
    IReadOnlyList<OutboundMessage> Messages,
    IReadOnlyList<DurableWrite> Writes,
    IReadOnlyList<TraceEvent> Events);
~~~

All state is supplied explicitly; the same input/state must generate the same result. Keep persistence requests separate from actual writes, and do not send messages that depend on durable changes before the simulator acknowledges the writes. Begin with a narrow subset of RequestVote and AppendEntries semantics; expand protocol coverage only with tests.

Separate **correct rules** from **named mutation definitions** (e.g., SkipVoteLogFreshness). Never use a generic "buggy" branch throughout production-facing code. Mutation flags should be scoped to experiments, validated, watermarked in reports and disabled in any future real-network adapter.

### 5.2 Deterministic event engine

Use a priority queue ordered by (virtualTick, monotonicSequence). Avoid DateTime.UtcNow, Task.Delay and nondeterministic thread scheduling within the engine. Seeded PRNG controls choice generation; its algorithm and seed must be included in exported metadata.

Event types: DeliverMessage, TimerFired, CrashNode, RestartNode, Partition, Heal, InjectDrop, DelayMessage, DuplicateMessage, ReorderMessage, PersistWriteAck and ClientCommand. Use a deterministic tie-breaker even when scheduled ticks match.

Support execution controls: Step(), RunUntil(predicate, eventBudget), Pause(), SnapshotState(), RestoreCheckpoint(). Exhaustion must return a structured Inconclusive/BudgetExceeded result, never "safe".

**Durability semantics:** An in-memory node surviving restart is not equivalent to disk persistence. In later phases explicitly model stable (term, vote, log) versus volatile (role, quorum votes, indexes) state. Persistence acknowledgment order must be testable.

### 5.3 Scenario/trace format

Define a new versioned declarative scenario schema (v2), while retaining read-only support for the existing schema_version=1 outputs. Example:

~~~json
{
  "schemaVersion": 2,
  "scenarioId": "stale-leader-safety",
  "engine": "csharp-raft-teaching",
  "mutation": "SkipVoteLogFreshness",
  "nodeIds": ["A", "B", "C", "D", "E"],
  "seed": 42,
  "maxEvents": 10000,
  "actions": [
    { "type": "partition", "groups": [["A", "B", "C"], ["D", "E"]] },
    { "type": "elect", "node": "A" },
    { "type": "propose", "node": "A", "command": "X" }
  ]
}
~~~

Use JSON Schema and validate unknown/unsupported actions. Traces include scenario hash, engine version, run seed, virtual tick, event sequence, parent/correlation IDs, before/after state hashes, source/destination, payload digest, and violation evidence. Set limits on JSON sizes, number of nodes, commands, trace events, and recursion depth.

**Reproducibility contract:** Re-running the same engine version + seed + scenario + exploration decisions produces the same *semantic execution*. Compare stable fields and canonicalized snapshots; do not compare timestamps, machine paths, stack traces, or intentionally different implementation internals. Document cross-version compatibility; never promise byte-identical C# and Python traces before a shared canonical representation is defined.

### 5.4 Safety and liveness checks

Separate categories:

| Property | What to check | Oracle evidence |
| --- | --- | --- |
| Election safety | At most one elected leader for a given term in a fixed configuration | Term and quorum vote witnesses |
| Log matching | Same index+term implies matching prefix in compared logs | Conflicting prefix and Appendix entries |
| Leader completeness | An entry committed in an earlier term remains in future elected leaders' logs | Commit witness, election and candidate log |
| State machine safety | Committed/applied values at an index cannot conflict across nodes | Historical commit provenance |
| Monotonic terms/votes | Term never decreases; at most one vote per term per node | State transition sequence |
| Commit rule | Majority confirmation and correct current-term handling | Replication acknowledgments + term |
| Liveness (conditional) | Progress only under specified fairness, timing and majority-connectivity assumptions | Assumption log and bounded no-progress outcome |

An oracle with no observed violation gives **no violation found in the explored executions**, not a proof of correctness. Document the finite bounds and assumptions for every formal-model result.

### 5.5 Search, minimization and provenance

Explorer v1: deterministic seeded randomized selection from enabled message deliveries and fault actions, with fixed event/branch/timeout budgets. Run a regression corpus of known-safe and intentionally unsafe scenarios. Track seeds, explored distinct states, pruned states, explored schedules, detected violation types, time and resource use.

Explorer v2: bounded depth-first or breadth-first enumeration for small clusters with canonical state fingerprints and conservative partial-order reduction only after independence assumptions are tested.

Shrinker: delta-debug whole operations, then individual fault actions/message choices, preserving the *same violation classification* and replayability. Re-run from a fresh state for each candidate. Report whether a trace is merely reduced or **1-minimal under the chosen reduction operators**; never call it globally shortest without an exhaustive argument.

Construct a causality graph using explicit event parent/correlation relationships. Distinguish causal dependencies supported by the trace from heuristically associated events. Preserve an unmodified original trace alongside the minimized one.

## 6. Repository structure (target; not yet present)

~~~text
distributed-consensus-lab/
  .github/workflows/
    python-reference.yml
    dotnet-ci.yml
    web-ci.yml
    formal.yml
  src/consensus_lab/                 # current Python package (initially unchanged)
  tests/                             # current Python tests
  dotnet/
    ConsensusLab.sln
    src/
      Consensus.Contracts/
      Consensus.Core/
      Consensus.Simulation/
      Consensus.Checkers/
      Consensus.Exploration/
      Consensus.Cli/
      Consensus.Api/
    tests/
      Consensus.Core.Tests/
      Consensus.Simulation.Tests/
      Consensus.Integration.Tests/
      Consensus.Conformance.Tests/
  web/
    src/
      components/ClusterGraph/
      components/LogInspector/
      components/Timeline/
      components/ViolationInspector/
      pages/ExperimentLab/
      features/scenarios/
      lib/api/
    tests/
  scenarios/
    baseline/
    mutations/
    exploration/
  contracts/
    scenario-v2.schema.json
    trace-v2.schema.json
    golden/
  formal/
    RaftSafety.tla
    RaftSafety.cfg
    MutatedElection.tla
    README.md
  docs/
    IMPLEMENTATION_PLAN.md
    ADR/
    API.md
    THREAT_MODEL.md
    EXPERIMENTS.md
  scripts/
  README.md
  RESEARCH.md
  PROGRESS.md
~~~

Do not create empty placeholder projects purely to fill this tree. Add directories when features begin, and make commits small and independently testable.

## 7. Sixteen-week implementation roadmap

### Phase 0 — Week 1: baseline and build reliability (12–15 h)

**Work:** Clone and run Python locally; pin example traces from both correct/unsafe runs; inspect unresolved GitHub Actions failures and fix permissions/workflow/runner problems as evidence indicates; document local prerequisites; add contract design ADR-001 and migration ADR-002.

**Deliverables:** Passing baseline CI (Python matrix), immutable golden scenario fixtures, reproducible demo command and CI failure notes.

**Gate:** Both known scenarios pass locally and in GitHub Actions, and their golden semantics are checked in. If remote CI remains unavailable, mark the gate blocked and proceed only on a named development branch.

### Phase 1 — Week 2: shared contracts and .NET scaffold (12–15 h)

**Work:** Create .NET 10 solution and projects, editorconfig, warnings-as-errors rules, central package management, test projects and source generators only when justified. Define typed scenario/trace contracts, JSON Schema v2, deterministic equality tests. Create Python fixture export and C# fixture import.

**Deliverables:** Compiling solution, contract fixtures, serializer validation tests, command to load a legacy Python trace.

**Gate:** No undocumented schema drift; an invalid scenario fails clearly; Python v1 remains usable unchanged.

### Phase 2 — Weeks 3–5: .NET consensus + simulator parity (36–45 h)

**Week 3:** Pure node-state transitions, term/vote rules, RequestVote messages, manual elections, deterministic tick queue, state snapshots.
**Week 4:** AppendEntries, log conflict rules, next/match indexes, majority commits and current-term commit restriction, repeated/idempotent messages.
**Week 5:** Partition/heal, drops, crashes/restarts, durable-vs-volatile state model, port fixed stale-candidate demonstration and compare semantic outputs with Python.

**Deliverables:** CLI commands run, compare, replay; safe election keeps X then Y, named unsafe mutation causes committed overwrite in the known schedule.

**Gate:** Golden correct/unsafe behaviors match; 100 identical-seed reruns produce identical normalized traces; tests explicitly cover term changes, stale candidates, duplicate acknowledgments, partitions and recovery. Budget exhaustion returns Inconclusive.

### Phase 3 — Week 6: scenario DSL and diagnostic events (12–15 h)

**Work:** Validated declarative scenarios, stable event taxonomy, event correlation chain, export/import, replay, safe parsing limits, examples for 3/5 nodes.

**Deliverables:** At least three scenarios: stale candidate, transient partition with recovery, and failed minority election.

**Gate:** A scenario is executable from a checked-in JSON file; replay of an exported trace is equivalent under the documented contract; malformed inputs cannot crash the host with an unhandled exception.

### Phase 4 — Weeks 7–8: independent safety checker (24–30 h)

**Week 7:** Separate checkers for election safety, monotonic term/voting, committed-entry immutability, historical prefix consistency; independently maintained commit provenance.
**Week 8:** Leader-completeness checks, machine-readable violation schema, structured event witness IDs, negative mutation tests, human-readable forensics report.

**Deliverables:** Checkers do not share business-rule helper methods with Consensus.Core. At least two independently introduced safety defects produce the intended check failures; expected-safe fixtures remain unflagged.

**Gate:** For each violation: type, affected node/index/term, witnesses, first observed tick, and reproduction command available. No known false positives in a small curated corpus.

### Phase 5 — Weeks 9–10: automated exploration and shrinking (24–30 h)

**Week 9:** Seeded run generator, fault budgets, enabled-event scheduling, coverage statistics, bounded schedule search, duplicate-state tracking.
**Week 10:** Delta-debugging minimizer, deterministic replay regression, preservation of violation type, evidence provenance and exploration report.

**Deliverables:** Explorer discovers a known unsafe mutation from at least one checked-in seed without a handcrafted complete schedule; it emits a reduced, replayable witness.

**Gate:** Seed reproducibility test; reduced trace is no longer than original; if the minimizer reports 1-minimality, removing any one supported removable unit fails to preserve the target violation. Track explored state count and budget as metrics; do not claim exhaustive search if it was sampled.

### Phase 6 — Weeks 11–12: API and interactive UI (24–30 h)

**Week 11:** Minimal API for create/run/step/resume/pause/cancel and trace download; bounded concurrency and cancellation; local-origin CORS; OpenAPI; server-side persistence of artifacts in sandboxed paths only.
**Week 12:** React+TypeScript experiment designer, network graph, per-node log inspector, virtual-time timeline, synchronized safe/unsafe compare, violation evidence jump links, scenario import/export, accessible keyboard controls.

**Deliverables:** A visitor can run the included failing experiment through the browser, pause and step, select a node and inspect the exact vote/append/overwrite events.

**Gate:** End-to-end UI tests, invalid-file rejection, cancellation behavior, run quotas, no API requirement for unsafe code execution. A local demo works from a documented startup command.

### Phase 7 — Weeks 13–14: bounded formal-model verification (24–30 h)

**Week 13:** Build a small TLA+ model of terms, voting, logs, commits and fixed membership; document abstraction mapping to implementation state; define election-safety and leader-completeness/state-machine safety invariants.
**Week 14:** Run TLC for a finite 3-node model with bounded terms/logs; create a named mutated voting model to obtain a counterexample; compare relevant behaviors to simulator fixtures. Investigate inconclusive/time-limited checks.

**Deliverables:** Checked-in .tla/.cfg files, reproducible model-checking commands, logs or results summary, assumptions and limitations.

**Gate:** Correct bounded model finishes with no invariant violation for stated parameters; deliberately faulty model generates a counterexample or the experiment is transparently marked blocked. An absence of violations in the bounded model is never called a proof of the C# implementation.

### Phase 8 — Weeks 15–16: hardening, evaluation and release (24–30 h)

**Week 15:** Threat model, benchmark harness, performance budget checks, static/security scanning, dependency audit, CI matrix coverage, retention/limits for generated artifacts, 1–2 baseline comparisons with existing tools.
**Week 16:** Developer docs, architecture decision records, demo recording/script, README screenshots, sample reports, MIT/license checks, v1.0 release notes and public reproducibility instructions.

**Deliverables:** Tagged release candidate with source, test results, exact sample scenarios, downloadable reports and clear feature/limitation table.

**Gate:** All required CI checks green or published exception with severity and owner; documented demonstration can be reproduced from a clean machine; no unexplained failing safety fixture.

## 8. Public API contracts (planned)

| Route | Method | Behavior |
| --- | --- | --- |
| /api/v1/scenarios/validate | POST | Validate schema/semantics, return structured errors |
| /api/v1/experiments | POST | Start bounded experiment; return run ID |
| /api/v1/experiments/{id} | GET | Return state, status, budgets, aggregate metrics |
| /api/v1/experiments/{id}/step | POST | Execute one virtual event (when paused) |
| /api/v1/experiments/{id}/pause | POST | Request pause at safe step boundary |
| /api/v1/experiments/{id}/resume | POST | Resume |
| /api/v1/experiments/{id}/cancel | POST | Request cancellation |
| /api/v1/experiments/{id}/events | GET | Stream/paginate trace events with cursor |
| /api/v1/experiments/{id}/artifacts | GET | Export scenario, traces and violations |
| /api/v1/explore | POST | Start budget-constrained seeded exploration |
| /api/v1/explorations/{id} | GET | Status and discovered witnesses |

Start with simple REST + bounded polling. Add server-sent events or SignalR only if a step-by-step streaming UX needs it; don't introduce an asynchronous multi-worker infrastructure for a single-user local lab. The simulation stays single-threaded and deterministic even if the API handles multiple requests concurrently.

Error model: ValidationError (400), NotFound (404), Conflict/InvalidState (409), BudgetExceeded (422 or documented equivalent), Canceled, Inconclusive, and InternalError. Do not expose stack traces or local filesystem paths.

## 9. Browser UI — specific components

1. **Experiment Workspace:** Pick scenario, node count, mutation, seed, fault budget, max virtual events; validation before execution.
2. **Cluster Topology:** Nodes display role, term, commit index and connected partitions; edge animation represents delivered/dropped messages.
3. **Log Inspector:** Per-node rows show index, term, command, committed status and conflicting/historical entries.
4. **Timeline + Scrubber:** Step, play/pause, virtual tick, filtered event types, bookmark/replay links.
5. **Violation Inspector:** Invariant type, witness event IDs, exact conflicting values, reproduction command and original/minimized trace.
6. **Comparison View:** Align correct vs mutated runs by scenario phase and semantic event identity, not by wall-clock timestamp.
7. **Exploration Dashboard:** Seeds tried, unique states/schedules explored, failures discovered, shrinking outcome and resource use.
8. **Accessibility:** Keyboard controls, text descriptions of colors/icons, responsive layout, trace export and error states.

Suggested frontend implementation: Vite + React + TypeScript, React Flow (verify license/version before use) or accessible SVG for topology, TanStack Query for API state. Avoid a large charting library until timeline requirements justify it.

## 10. Testing and assurance strategy

| Layer | Test strategy | Minimum exit evidence |
| --- | --- | --- |
| Pure state machine | xUnit unit tests and property-based generators | Vote term monotonicity, freshness, append consistency |
| Scheduler | Identical seeds, order ties, replay after checkpoints | 100/100 identical deterministic semantic traces |
| Fault model | Partition/heal/drop/delay/restart/persist-ack ordering | No delivery across a blocked link; crash semantics documented |
| Checkers | Hand-constructed safe/unsafe histories, mutation tests | Expected violations reported and safe fixtures unflagged |
| Conformance | Python vs C# semantic fixture comparisons | All initial baseline scenario fixtures agree |
| Explorer | Fixed seeds, bounds, failure discovery, search budgets | Known mutation discovered with repeatable witness |
| Shrinker | Replay after reduction and 1-minimality validation | Preservation of same invariant under supported operators |
| API | Integration tests with in-process server | Validation, cancellation, 409 state conflicts, resource quotas |
| UI | Component and Playwright smoke/e2e tests | Run/pause/step/evidence navigation and file import |
| Formal | TLC bounded model + mutant | Finite-check result recorded with exact parameters |
| CI | Linux + Windows .NET build/test, Python matrix, web checks | Required checks green before tagging |
| Security | Dependency and secret scanning, input fuzz/property tests | No known critical issue without documented mitigation |

**Independent model caution:** The reference simulator itself can contain bugs. Review Raft claims against the original paper and test against separate oracles, not only Python parity.

**Performance targets (initial hypotheses; adjust after measurement):**
- Local default experiment: <=10,000 events with a hard event budget and responsive stop.
- Report/replay: 10,000-event trace renders/imports without browser freeze on a typical desktop.
- Search: show tested schedules/second, unique states, allocated memory and wall time; no initial universal speed guarantee.
- API: per-run memory/time limits configurable, default single-user local deployment.
- Observability: expose duration, event count, drop count, violation count, seed and engine version; avoid labeling virtual ticks as real latency.

## 11. CI/CD, supply chain and release discipline

**Initial priority:** Diagnose the preexisting GitHub Actions issue using run metadata, workflow syntax and runner messages; do not equate runner provisioning failure with a failed test.

**Workflows to add incrementally:** Python reference matrix (3.11–3.13), .NET 10 restore/build/test on Linux and Windows, frontend npm ci/typecheck/lint/test/build, formal-model checks, a bounded deterministic nightly seed corpus, dependency/secret scanning. Keep PR checks reasonably fast; heavier exploration belongs in a separate scheduled or manual workflow.

**Practices:** Least-privilege workflow permissions; pin action major revisions or immutable SHAs based on risk; use lockfiles; no credentials or real production tokens in scenarios; publish test and reproduction artifacts with retention limits; use conventional commit scopes and ADRs; protect main after first stable R1 (requires repository settings).

**Release prerequisites:** Clean checkout builds; documented commands work; checked-in stable example traces; no silently failing checks; changelog explains schema compatibility; MIT and all third-party license notices verified; warnings about deliberately unsafe mutations conspicuous.

## 12. Risk register and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep into full production Raft | High | Ship educational R1–R4, defer snapshots/joint consensus/production network |
| Simulated engine is incorrect | High | Independent oracle, original paper review, mutant tests, eventual external adapter |
| State-space explosion | High | Strict budgets, smaller finite models, seed corpus, state hashing and measured pruning |
| False causal attribution | High | Separate hard event dependencies from heuristic grouping; preserve original traces |
| Nondeterminism introduced by async/API | High | Pure, single-threaded engine; external async shell only |
| Persistence semantics misunderstood | High | Explicit stable/volatile states; never call in-memory restart "durable" |
| TLA model misses implementation behaviors | High | Document abstraction mapping, bounded assumptions and missing actions |
| CI infrastructure failures | Medium | Fix baseline first; maintain local reproducibility and CI diagnostics |
| Unsafe mutation exposed as production toggle | High | Experiment-only mutation namespace; no real-network deployment configuration |
| Security and resource exhaustion when hosted | High | Local-only first; authenticate and quota public deployments, validate files and cap work |
| Comparison claims exceed evidence | Medium | Publish reproducible scripts, baseline versions and measured outcomes |

## 13. Estimated work effort and sequencing

| Phase | Weeks | Hours estimate | Depends on |
| --- | ---: | ---: | --- |
| Baseline, CI, ADRs | 1 | 12–15 | Existing repo |
| Contracts and .NET scaffold | 2 | 12–15 | Baseline |
| Pure C# engine and parity | 3–5 | 36–45 | Contracts |
| Scenario DSL and traces | 6 | 12–15 | Engine |
| Safety oracle and witnesses | 7–8 | 24–30 | Engine and traces |
| Search and minimization | 9–10 | 24–30 | Independent oracle |
| API and React UI | 11–12 | 24–30 | Trace schema and simulator API |
| TLA+ bounded model checking | 13–14 | 24–30 | Invariant definitions |
| Hardening, evaluation, release | 15–16 | 24–30 | All critical paths |
| **Total** | **16** | **192–240** | A single part-time developer |

**Parallel opportunities:** UI sketches after trace schema stabilizes; initial TLA+ safety specification can be started once core invariants are documented, though final evidence is gated in Weeks 13–14. Contract/test work comes before frontend polish.

**Change-control rule:** If >20% off estimate, reduce scope rather than compromise safety evidence. The minimum publishable milestone is C# parity + reproducible correct/unsafe example + independent invariant checker + fully passing CI.

## 14. Backlog in delivery order

**P0 (must-do):**
- B01: Investigate current Python GitHub Actions failures.
- B02: Freeze both baseline golden semantic traces.
- B03: Define versioned JSON scenario/trace schemas.
- B04: Scaffold .NET 10 solution and deterministic state transition engine.
- B05: Implement elections, append, current-term commit and faultable queue.
- B06: Port stale-candidate positive/negative experiments.
- B07: Build independent violation oracles and structured witness records.
- B08: Guarantee deterministic replay and CI parity.

**P1 (core product):**
- B09: Declarative scenario DSL and validation.
- B10: Seeded bounded fault schedule explorer.
- B11: Counterexample shrinker with regression check.
- B12: API with pause/step/cancel and run budget enforcement.
- B13: React topology, log inspector, timeline and comparison viewer.
- B14: TLA+ bounded model and deliberately faulty counterexample.
- B15: Security, accessibility and artifact export.

**P2 (research extensions):**
- B16: 3-node exhaustive bounded explorer and conservative POR.
- B17: External production Raft adapter (e.g., a licensed Go-sidecar harness).
- B18: Client operation histories and independent linearizability checker.
- B19: Disk faults, snapshots, membership changes, automatic elections.
- B20: Controlled evaluation against existing visualizers (time-to-diagnosis, accuracy).
- B21: Hosted multi-user demo with authentication, quotas and data retention.

## 15. Exact first iteration to implement

**PR 1 — Baseline and contract freeze**
- Diagnose existing workflow; run existing 10 tests; capture golden correct/unsafe traces.
- Add ADR-001 (why .NET core + Python fixture reference) and ADR-002 (deterministic trace contract).
- Introduce schema contract design without breaking v1.

**PR 2 — .NET Core skeleton**
- Add solution, Consensus.Contracts/Core/Simulation and xUnit projects; compile under .NET 10.
- Define immutable NodeState, Message, Entry and TransitionResult.
- Implement deterministic queue and first vote tests.

**PR 3 — Election parity**
- Port RequestVote, election term handling and named SkipVoteLogFreshness mutation.
- Demonstrate safe rejection vs unsafe vote with reusable scenario actions.

**PR 4 — Replication parity**
- Port AppendEntries, retries, log conflict/truncation and commit checking.
- Reproduce the fixed five-node X/Y scenario and compare stable semantics to Python.

**PR 5 — Oracle boundary**
- Check history independently; emit structured violation and witness; add bounded replay tests.
- Make the first C#-powered HTML report or JSON output reproducible.

**PR exit policy:** No PR is marked complete until tests run and the newly committed files are verified on GitHub. Do not mark future checklist items complete simply because they appear in this plan.

## 16. Definition of done and demo script

**R1 done:** Both engines run the named scenario; safe run retains committed X and appends Y; unsafe mutation overwrites previously committed X and produces a diagnosable safety violation; deterministic replay; build/test green.

**R2 done:** Bounded search finds the known unsafe behavior without using the full hand-authored failure path, exports a replayable trace, and shrinks it with accurately labeled minimality; checker reports the same invariant on the original and reduced trace.

**R3 done:** From the browser, an engineer can select the scenario, run correct and unsafe modes, inspect nodes, pause/step, view event witnesses and export an artifact. Errors, cancellations and budgets are visible.

**R4 done:** Reproducible bounded TLA+ checks are published alongside exact model parameters, all CI gates pass (or release is explicitly blocked), and the repository has a comparison study with clearly bounded claims and a self-guided demo.

**Five-minute public demo:**
1. Show initial five-node topology and partition A/B/C vs D/E.
2. Run correct election path and show X survives the leadership change.
3. Enable named unsafe vote mutation, use identical scenario/seed and show D elected stale.
4. Highlight C's previously committed X replaced by Y; jump to vote/truncation witnesses.
5. Run bounded schedule explorer, inspect found seed, reduce witness and replay.
6. Open matching finite-model checking results; explain what is and is not proven.

## 17. References and rationale

The following are primary/official sources or original project repositories used to ground technical decisions. We have not independently benchmarked every competing tool.

- Original Raft paper (and §5.4 leader completeness): https://raft.github.io/raft.pdf
- Raft dissertation: https://github.com/ongardie/dissertation
- etcd-io/raft deterministic message-driven state machine: https://github.com/etcd-io/raft
- HashiCorp Raft: https://github.com/hashicorp/raft
- FoundationDB simulation: https://apple.github.io/foundationdb/client-testing
- Jepsen: https://github.com/jepsen-io/jepsen
- Porcupine: https://github.com/anishathalye/porcupine
- TLA+ learning/tools: https://docs.tlapl.us/
- Apalache bounded symbolic model checking: https://apalache-mc.org/docs/apalache/index.html
- Official .NET 10 LTS lifecycle: https://dotnet.microsoft.com/en-us/platform/support/policy
- Microsoft ASP.NET Core Minimal APIs: https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis?view=aspnetcore-10.0
- Existing repository assessment: https://github.com/mirza-jahangeer/distributed-consensus-lab/blob/main/RESEARCH.md

**Source-credibility guardrail:** Documentation and project READMEs establish what maintainers claim, not independently verified correctness or superiority. Any future comparative results must include methodology, versions, environment, sample sizes and raw artifacts.

---

**Next action:** Start PR 1 by diagnosing the existing GitHub Actions failure and freezing golden Python fixtures. No additional feature should displace this foundation.
