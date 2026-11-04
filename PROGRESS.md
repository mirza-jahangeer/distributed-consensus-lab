# Development progress

**Last updated:** 2026-11-04. Checkmarks indicate committed code and local validation, not formal proof or production readiness.

- [x] Public GitHub repository confirmed and writable.
- [x] Research comparison with references to original Raft work, production libraries, simulations and testing frameworks.
- [x] Deterministic single-process event scheduler and virtual five-node Raft-inspired state machine.
- [x] Network partitions, targeted message drops, simulated crash/restart.
- [x] Correct and intentionally unsafe election modes plus stale-candidate scenario.
- [x] Historical committed-entry oracle, divergence detection and witness event IDs.
- [x] CLI commands, JSON export, canonical replay and standalone HTML report.
- [x] Ten tests passed locally on Python 3.13 during development.
- [x] Detailed low-level Mermaid architecture committed under docs/.
- [x] Core code, tests, documentation and GitHub Actions workflow committed to main.
- [ ] Confirm GitHub Actions matrix has passed on Python 3.11, 3.12 and 3.13.
- [ ] Build automatic schedule search and failing-trace minimization.
- [ ] Run comparisons with actual production consensus libraries.

**Scope:** Educational and non-production. A passed local test suite covers a small scenario set, not all Raft behaviors or all possible failure schedules.
