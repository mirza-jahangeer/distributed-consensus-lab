"""Reproducible, documented distributed-systems experiments."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .simulator import Simulation

@dataclass
class Experiment:
    scenario: str
    mode: str
    sim: Simulation
    phases: dict[str, bool]

    def record(self) -> dict[str, Any]:
        return {"schema_version": 1, "scenario": self.scenario, "mode": self.mode,
                "phases": self.phases, "final_state": self.sim.state(),
                "violations": self.sim.violations, "trace": self.sim.trace}

def stale_candidate(mode: str = "correct") -> Experiment:
    """Show the stale-leader danger by changing one RequestVote safety rule."""
    sim = Simulation(mode=mode)
    sim.partition([["A", "B", "C"], ["D", "E"]])
    initial_election = sim.elect("A")
    if not initial_election or not sim.propose("A", "X"):
        raise AssertionError("A/B/C should commit X")
    if sim.nodes["C"].commit_index != 1:
        raise AssertionError("C must commit X before repartition")
    if sim.elect("D"):
        raise AssertionError("D/E minority cannot elect leader")
    sim.partition([["A", "B"], ["C", "D", "E"]])
    stale_election = sim.elect("D")
    fresh_election = False
    if stale_election:
        second_commit = sim.propose("D", "Y")
    else:
        fresh_election = sim.elect("C")
        if not fresh_election:
            raise AssertionError("fresh C should win term 3")
        second_commit = sim.propose("C", "Y")
    return Experiment("stale_candidate", mode, sim,
                      {"initial_election": initial_election, "initial_commit": True,
                       "stale_election": stale_election,
                       "fresh_election": fresh_election,
                       "second_commit": second_commit})

def run_scenario(name: str, mode: str) -> Experiment:
    if name == "stale_candidate":
        return stale_candidate(mode)
    raise ValueError(f"unknown scenario: {name}")
