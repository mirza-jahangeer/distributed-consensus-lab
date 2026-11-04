# Distributed Consensus Failure Forensics Lab

> **A deterministic Raft-inspired teaching MVP that turns a subtle consensus safety rule into a reproducible failure and a causal witness.** Not production Raft and not a novel consensus algorithm.

[![CI](https://github.com/mirza-jahangeer/distributed-consensus-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/mirza-jahangeer/distributed-consensus-lab/actions/workflows/ci.yml)

## Why this exists

Most Raft demos explain *how* a leader gets elected. This lab investigates **why an apparently minor election shortcut can lose committed data**. It runs the *same* five-node network schedule twice: with the paper's up-to-date voting restriction enabled and with that **single rule intentionally disabled**. The output provides event IDs that connect votes, leadership and overwrites to the safety failure.

It is a focused, controlled experiment and does **not** claim to replace etcd/raft, production fault simulators or Jepsen. See [competitive research](RESEARCH.md) and [architecture and limitations](docs/ARCHITECTURE.md).

## Run locally

Requires Python 3.11+. No third-party runtime dependencies.

```bash
python -m pip install -e .
consensus-lab compare
consensus-lab report --output consensus-report.html
consensus-lab run --mode correct --trace correct.json
consensus-lab run --mode buggy --trace buggy.json
consensus-lab replay buggy.json
python -m unittest discover -s tests -v
```

Open `consensus-report.html` in a browser to browse the paired timelines and jump to causal witness events. Use `python -m consensus_lab compare` if you prefer not to install the entry point (with `PYTHONPATH=src` from a source checkout).

### Expected behavior

| Observation | Correct voting | Intentionally buggy voting |
| --- | --- | --- |
| Stale candidate D elected? | **No** | **Yes** |
| Fresh candidate C elected? | Yes | No |
| Where does the next command `Y` land? | Index 2 (after committed `X`) | Index 1 (overwrites committed `X` on C) |
| Safety oracle | No violation found in this schedule | Detects committed overwrite and conflicting committed history |

**A run with no detected violations is not a proof of correctness.** The experiment checks a particular schedule and a small set of invariants.

## Low-level architecture diagram

The **[detailed low-level design](docs/LOW_LEVEL_DESIGN.md)** includes editable Mermaid diagrams, module/data contracts, fault-injection paths, safety-oracle dependencies and the exact unsafe-vote decision point. The GitHub document renders interactive Mermaid diagrams directly.

## The five-node experiment

1. Split connectivity into `[A,B,C]` and `[D,E]`.
2. A wins term 1 using A/B/C, replicates and commits `X` at log index 1.
3. D's election in the D/E minority fails but advances D's term.
4. Repartition into `[A,B]` and `[C,D,E]`.
5. D seeks election with an empty log. Correct C **rejects** it as stale. Buggy C **votes for** it.
6. In correct mode, C becomes leader and commits `Y` after `X`; in buggy mode, D overwrites C's committed `X` with `Y`.
7. The monitor records `committed_entry_overwritten` and `committed_prefix_divergence`, with references to supporting trace events.

For a formal discussion of why the log freshness restriction matters, see the [original Raft paper, §5.4](https://raft.github.io/raft.pdf).

## Run your own fault experiments

```python
from consensus_lab import Simulation

sim = Simulation(mode="correct")
sim.partition([["A", "B", "C"], ["D", "E"]])
assert sim.elect("A")
assert sim.propose("A", "SET order=paid")
sim.crash("B")
sim.restart("B")  # simulated persistent state is retained in memory
sim.drop_next(kind="request_vote", src="C", dst="D")
print(sim.state())
print(sim.violations)
```

Supported primitives: manual election, proposals, virtual-time message queue, fixed network latency, partitions/heal, single-message fault rules, crash/restart with persistent state retained in memory, JSON traces, deterministic replay, and invariant checking.

## Design choices and tradeoffs

The code is small and uses only Python's standard library so every transition is readable. The event loop is ordered by `(virtual_time, insertion_sequence)` and no randomness or system clock enters the simulation. `replay` recomputes the scenario and compares full canonicalized JSON; it is a deterministic equality check, not a cryptographic authenticity guarantee.

**Not implemented:** real network/storage, disk durability, snapshotting, automated election timers, membership changes, concurrent clients, leases, formal model checking, real-world linearizability, network reordering beyond the scripted scheduler, or exhaustive failure exploration. No production security or reliability properties are claimed. This lab illustrates an important Raft restriction, not a complete Raft specification.


## Planned real Raft integration and fault injection

The current code is a **virtual Python teaching simulator**. The next core milestone is integrating an **actual three-node etcd-io/raft test cluster**, controlled by a .NET adapter, then injecting bounded network partitions and latency through isolated test-only infrastructure. The lab will observe quorum, committed/applied writes, recovery and fault cleanup; it will never silently apply destructive tests to production or arbitrary external systems.

Read the [real Raft integration and fault-injection specification](docs/REAL_RAFT_INTEGRATION.md) and the [updated 20-week implementation roadmap](docs/IMPLEMENTATION_PLAN.md). **These real-cluster capabilities are planned, not yet working in the repository.**

## Next engineering iterations

- Define a reusable declarative scenario/fault DSL, with seed-based schedule exploration and shrinking of failing traces.
- Run real etcd/raft or HashiCorp Raft behind an adapter and reuse the same external checker.
- Check completed read/write histories for linearizability and compare with Porcupine/Jepsen.
- Add disk fault semantics, automatic elections, snapshots, and more of the Raft protocol.
- Publish a hosted interactive report (currently the CLI generates a standalone local HTML file).

Follow development in [PROGRESS.md](PROGRESS.md). Licensed MIT (see LICENSE).