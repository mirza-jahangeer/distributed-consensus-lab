# Development progress

This file tracks published work in this repository. **A checked item means it has been completed and verified; an unchecked item is not complete.**

Last status update: 2026-11-02

## Milestones
- [x] Confirm GitHub repository is accessible and public
- [x] Define initial project direction: deterministic consensus fault-forensics lab
- [ ] Finish comparative research and document attributable sources in RESEARCH.md
- [ ] Implement deterministic Raft-inspired simulator (virtual clock and reproducible message scheduling)
- [ ] Implement fault injection (partitions, dropped messages, crash/restart)
- [ ] Implement invariant checks and an intentionally buggy election mode
- [ ] Write and run automated tests
- [ ] Publish runnable code, usage examples and architecture documentation
- [ ] Verify committed code and report results

## Scope and guardrails
The initial MVP is a teaching and fault-diagnosis simulator, not a production-ready Raft implementation. Its intentionally faulty mode must be clearly segregated and must never be advertised as safe to deploy.

## How to monitor
Browse **Commits** for new pushes. Check README.md for run instructions once it is available. This checklist is updated when each milestone is verified.

## Current state
The repo is set up for tracking. Research, implementation, testing and publication of the actual MVP are **still pending**.
