"""Integration tests for the deliberately scoped consensus counterexample."""
import json
import tempfile
import unittest
from pathlib import Path
from consensus_lab.cli import main
from consensus_lab.scenarios import stale_candidate
from consensus_lab.simulator import Simulation

class ConsensusTests(unittest.TestCase):
    def test_correct_election_preserves_committed_x(self):
        exp = stale_candidate("correct")
        self.assertFalse(exp.phases["stale_election"])
        self.assertTrue(exp.phases["fresh_election"])
        self.assertTrue(exp.phases["second_commit"])
        self.assertEqual([], exp.sim.violations)
        for node in ("C", "D"):
            self.assertEqual(["X", "Y"], [e.command for e in exp.sim.nodes[node].log])
        self.assertEqual(2, exp.sim.nodes["C"].commit_index)
        self.assertTrue(any(e["event"] == "vote_rejected" and e["reason"] == "stale_log"
                            for e in exp.sim.trace))

    def test_buggy_election_detects_committed_overwrite(self):
        exp = stale_candidate("buggy")
        self.assertTrue(exp.phases["stale_election"])
        self.assertTrue(exp.phases["second_commit"])
        self.assertEqual("X", exp.sim.nodes["A"].log[0].command)
        self.assertEqual("Y", exp.sim.nodes["C"].log[0].command)
        self.assertTrue(any(v["invariant"] == "committed_entry_overwritten"
                            and v["node"] == "C" for v in exp.sim.violations))
        self.assertTrue(any(v["invariant"] == "committed_prefix_divergence"
                            for v in exp.sim.violations))
        self.assertTrue(all(v["witness_event_ids"] for v in exp.sim.violations))

    def test_same_scenario_produces_identical_trace(self):
        for mode in ("correct", "buggy"):
            self.assertEqual(stale_candidate(mode).record(), stale_candidate(mode).record())

    def test_replay_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "trace.json"
            self.assertEqual(0, main(["run", "--mode", "buggy", "--trace", str(target)]))
            self.assertEqual(0, main(["replay", str(target)]))
            record = json.loads(target.read_text())
            record["phases"]["stale_election"] = False
            target.write_text(json.dumps(record))
            self.assertEqual(1, main(["replay", str(target)]))

    def test_partition_blocks_quorum(self):
        sim = Simulation()
        sim.partition([["A", "B"], ["C", "D", "E"]])
        self.assertFalse(sim.elect("A"))
        self.assertFalse(any(n.role == "leader" for n in sim.nodes.values()))
        self.assertTrue(any(e["event"] == "message_dropped" and
                            e["cause"] == "network_partition" for e in sim.trace))

    def test_restart_retains_simulated_persistent_state(self):
        sim = Simulation()
        sim.partition([["A", "B", "C"], ["D", "E"]])
        self.assertTrue(sim.elect("A"))
        self.assertTrue(sim.propose("A", "X"))
        b = sim.nodes["B"]
        before = (b.term, b.voted_for, list(b.log), b.commit_index)
        sim.crash("B")
        sim.restart("B")
        self.assertEqual(before, (b.term, b.voted_for, b.log, b.commit_index))
        self.assertEqual("follower", b.role)

    def test_drop_rule_blocks_then_allows_election(self):
        sim = Simulation()
        sim.partition([["A", "B", "C"], ["D", "E"]])
        sim.drop_next(kind="request_vote", src="A", dst="C")
        self.assertFalse(sim.elect("A"))
        self.assertTrue(sim.elect("A"))

    def test_partition_healing_catches_up(self):
        sim = Simulation()
        sim.partition([["A", "B", "C"], ["D", "E"]])
        self.assertTrue(sim.elect("A"))
        self.assertTrue(sim.propose("A", "X"))
        sim.heal()
        self.assertTrue(sim.elect("C"))
        self.assertTrue(sim.propose("C", "Y"))
        for node in sim.nodes.values():
            self.assertEqual(["X", "Y"], [e.command for e in node.log])
        self.assertEqual([], sim.violations)

    def test_report_contains_both_modes_and_witnesses(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "comparison.html"
            self.assertEqual(0, main(["report", "--output", str(target)]))
            html = target.read_text()
            self.assertIn("CORRECT", html)
            self.assertIn("BUGGY", html)
            self.assertIn("committed_entry_overwritten", html)
            self.assertIn('href="#buggy-e', html)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            Simulation(mode="invalid")
        with self.assertRaises(ValueError):
            Simulation().partition([["A", "B"], ["B", "C", "D", "E"]])

if __name__ == "__main__":
    unittest.main()
