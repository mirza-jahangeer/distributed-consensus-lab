"""Distributed Consensus Failure Forensics Lab (educational, non-production)."""
from .scenarios import Experiment, stale_candidate
from .simulator import Entry, Node, Simulation
__all__ = ["Entry", "Node", "Simulation", "Experiment", "stale_candidate"]
