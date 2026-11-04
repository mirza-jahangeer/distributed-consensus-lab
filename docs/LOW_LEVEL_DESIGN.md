# Low-level architecture · Distributed Consensus Failure Forensics Lab

**Implementation:** single-process Python 3.11+ educational MVP. All five nodes are virtual; there is no socket server or external database.

## Component diagram

```mermaid
flowchart TB
  USER["Engineer / CI"] --> CLI["cli.py · main()\nrun | compare | report | replay"]
  CLI --> SCENARIO["scenarios.py\nstale_candidate(mode)"]
  SCENARIO --> SIM["Simulation\npartition() · elect() · propose()\ncrash() · restart()"]

  subgraph CORE["simulator.py · deterministic event engine"]
    SIM --> QUEUE["Virtual time and heapq\n(time, sequence, Message)"]
    QUEUE --> NETWORK{"Network fault gate\nalive | partition | drop_next"}
    NETWORK -->|deliver| DISPATCH["RPC dispatcher"]
    NETWORK -->|drop| TRACE["Append-only trace\nid | tick | event | details"]
    DISPATCH --> VOTE["Election handlers\nrequest_vote / vote_reply"]
    DISPATCH --> APPEND["Replication handlers\nappend / append_reply"]
    VOTE <--> NODES["Node registry: A, B, C, D, E\nterm | voted_for | role | log\ncommit_index | next_index | match_index"]
    APPEND <--> NODES
    VOTE -->|send reply / append| QUEUE
    APPEND -->|send reply / retry| QUEUE
    DISPATCH -->|after each message| ORACLE["check_invariants()"]
    ORACLE <--> HISTORY["Historical committed entries\n_commit_events | _leaders"]
    ORACLE --> VIOLATION["Failure evidence\noverwrite | divergence | witness IDs"]
    VIOLATION --> TRACE
    VOTE --> TRACE
    APPEND --> TRACE
  end

  SCENARIO --> RECORD["Experiment.record()\nmode | phases | state | violations | trace"]
  TRACE --> RECORD
  RECORD --> JSON["JSON trace + deterministic replay\ncli.py"]
  RECORD --> HTML["Standalone forensic report\nreport.py"]
  JSON --> OUTPUT["Engineer / CI artifacts"]
  HTML --> OUTPUT
```

## Internal message paths

| Phase | Function | Effect |
|---|---|---|
| Scenario | `stale_candidate(mode)` | Scripts partitions, elections and proposals |
| Send | `Simulation._send()` | Enqueues `Message` at virtual time, preserving FIFO tie order |
| Delivery | `Simulation.run()` | Applies crash, partition and targeted message-drop rules |
| Voting | `_handle_vote_request()`, `_handle_vote_reply()` | Term checks; log-freshness restriction in correct mode; quorum election |
| Replication | `_handle_append()`, `_handle_append_reply()` | Consistency checks, conflict truncation, replication progress, commit advancement |
| Oracle | `check_invariants()` | Compares live logs against immutable historical committed entries; detects cross-node divergence |
| Evidence | `_record()`, `_violate()` | Structured trace events, violation witnesses |
| Output | `Experiment.record()`, `render_html()` | JSON traces, replay verification, local HTML comparison |

## Exact safety-mutation decision

```mermaid
flowchart TD
    REQ["RequestVote arrives"] --> TERM{"Candidate term valid?"}
    TERM -->|no| REJECT["Reject"]
    TERM -->|yes| FREE{"Voter available?"}
    FREE -->|no| REJECT
    FREE -->|yes| MODE{"mode"}
    MODE -->|correct| FRESH{"Candidate log sufficiently up-to-date?"}
    FRESH -->|no| REJECT
    FRESH -->|yes| GRANT["Grant"]
    MODE -->|"buggy: skip freshness predicate"| GRANT
    GRANT --> QUORUM{"Majority reached?"}
    QUORUM -->|yes| LEADER["Leader replicates entries"]
    QUORUM -->|no| WAIT["Await further replies"]
    LEADER --> CHECK["Check committed-entry history"]
    CHECK -->|conflict| FAILURE["Record violation + witness IDs"]
    CHECK -->|none observed| PASS["No violation detected in this run"]
```

In intentionally unsafe mode, **only** the RequestVote log-freshness predicate is disabled. The fixed scenario shows why electing a stale leader can overwrite previously committed data.

## Key data structures

- `Entry(term, command)`: immutable replicated-log entry.
- `Node`: role, term, previous vote, log, commit index, votes, per-peer matching and next indexes, alive flag.
- `Message(kind, src, dst, term, data)`: simulated RPC envelope.
- `_queue`: virtual delivery heap keyed by timestamp and insertion order.
- `_groups`/`_drops`: fault-injection state.
- `_committed`: historical snapshot of entries committed on each node; intentionally retained even if a live log is truncated.
- `trace`/`violations`: diagnostic events with monotonic event IDs and witness references.

**Scope:** scripted five-node demonstration, not production Raft; no real network, disk persistence, snapshots, automatic elections, model checking or exhaustive verification. The checker finding no failure does not prove consensus correctness. 
