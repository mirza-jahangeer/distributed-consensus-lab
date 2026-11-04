# Competitive research and differentiation

**Reviewed:** 2026-11-04. A targeted primary-source review, not a claim to have crawled every page on the internet or proved the concept is novel.

## Foundational research

- [Ongaro & Ousterhout, In Search of an Understandable Consensus Algorithm (USENIX ATC 2014)](https://www.usenix.org/conference/atc14/technical-sessions/presentation/ongaro). The extended [Raft paper §5.4](https://raft.github.io/raft.pdf) explains why leaders must possess entries committed in earlier terms. This experiment disables the RequestVote log-freshness restriction in one branch and observes the resulting conflict.
- [etcd-io/raft](https://github.com/etcd-io/raft) documents its message-driven deterministic state-machine model. Our work does not introduce deterministic Raft state machines.
- [FoundationDB simulation documentation](https://apple.github.io/foundationdb/client-testing) describes deterministic seeded workload replays, simulated whole clusters, and induced network/disk failures. Simulation itself is not new.
- [Jepsen](https://github.com/jepsen-io/jepsen) describes generating operation histories, injecting faults and checking the results. This teaching MVP tests only its own simulated log history.

## Comparison with existing work

| Existing work | Publicly documented focus | How this MVP differs / where it overlaps |
| --- | --- | --- |
| [etcd-io/raft](https://github.com/etcd-io/raft) | Production Raft library, deterministic core, full consensus features | We demonstrate one wrong election rule in a small scripted model, not a production Raft replacement |
| [hashicorp/raft](https://github.com/hashicorp/raft) | Embeddable Go consensus, transport, snapshots and storage | No production transport, persistence, snapshots or configuration changes |
| [RaftScope](https://github.com/ongardie/raftscope) | Interactive leader election and log visualization | Our output centers on paired mutation runs plus machine-readable event witnesses |
| [Raminshiraz/raft-visualizer](https://github.com/Raminshiraz/raft-visualizer) | Browser visualizer with partitions, crash/recovery and safety investigations | Significant overlap; our MVP is narrower and emphasizes comparing the exact same scenario under one deliberate safety-rule defect |
| [Jepsen](https://github.com/jepsen-io/jepsen) | Testing real systems with fault injection and history checkers | We simulate virtual nodes rather than operating a real faulted cluster |
| [Porcupine](https://github.com/anishathalye/porcupine) | Linearizability checking for operation histories | Our checks are limited to committed-log immutability and cross-node agreement; no general linearizability proof |
| [FoundationDB](https://github.com/apple/foundationdb) | Sophisticated deterministic runtime and fault exploration | Our simulator is a tiny teaching implementation; no claim of similar scale |
| [TigerBeetle VOPR](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/internals/vopr.md) | Simulation-based testing and reproducible failure exploration | Inspired by reproducibility, but there is no seeded randomized exploration or production-code testing in v0.1 |

## Hypothesis and modest differentiator

A **paired single-rule mutation** makes one causal failure easier to investigate: compare *correct* versus *buggy* with an identical scripted environment; link election votes to later log truncation and committed-prefix conflicts by event ID; export a trace and inspect the two runs side by side in a standalone HTML report.

This is a demonstrable teaching and diagnostic pattern, **not** a newly discovered consensus algorithm or a substantiated superiority claim. Other tools already support deterministic simulation, invariants and visualization.

## Falsifiable next experiments

1. Compare diagnosis time and accuracy against existing teaching tools with participants new to Raft; predefine sample size and outcome measures.
2. Build seeded event-schedule search, reproduce discovered failures and shrink them to minimal traces. Report explored schedules, not only anecdotes.
3. Integrate external implementations through adapters and compare independently produced histories, avoiding self-validation of the same model.
4. Apply a separate client-history checker for linearizability once the simulator supports concurrent clients and real state-machine operations.

## Source limitations

Claims above describe what public project documentation states; they are not independent benchmarks. Repository functionality and licensing can change. A single passing scenario never proves the absence of consensus bugs.
