# Architecture and correctness scope

See the rendered [low-level Mermaid diagrams](LOW_LEVEL_DESIGN.md).

## Code modules

- `simulator.py`: deterministic heap-based message scheduler, virtual network faults, five-node Raft-inspired election and replication, immutable historical commit registry and safety checker.
- `scenarios.py`: fixed five-node sequence that induces a committed-data overwrite only if the log-freshness vote restriction is bypassed.
- `cli.py`: run, compare, replay and report commands; canonical JSON comparison and exports.
- `report.py`: dependency-free standalone HTML report with per-event witness links.
- `tests/test_consensus.py`: ten integration tests for positive/negative election scenarios, loss, partition, recovery, report and replay.

## Safety properties observed

1. **Election safety:** monitor leaders elected in a single term.
2. **Committed-entry immutability:** record each first-seen committed entry and flag later truncation/replacement, even if the live node reduces its commit index.
3. **Committed-prefix agreement:** flag different historically committed entries at the same index on different nodes.
4. **Current-term commit constraint:** a leader only advances commit index directly for entries in its own term after majority replication.

Each violation includes diagnostic witness event IDs. These are **not** proven minimal causal explanations.

## Explicit simplifications

The model uses manually triggered elections, a predetermined scenario and a discrete-event heap ordered by (virtual time, insertion sequence). It does not implement real transport or disk IO, persisted commits, timeouts, background threads, snapshots, pre-vote, automatic elections, dynamic membership, general linearizability or exhaustive search. Crash/restart retains simulated state only in Python objects. The intentionally unsafe branch is solely for negative testing. Do not deploy this as a consensus service.
