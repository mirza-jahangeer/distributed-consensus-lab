"""Deterministic Raft-inspired failure forensics (educational, not production Raft)."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import heapq
from typing import Any


@dataclass(frozen=True)
class Entry:
    term: int
    command: str


@dataclass
class Node:
    id: str
    term: int = 0
    voted_for: str | None = None
    log: list[Entry] = field(default_factory=list)
    commit_index: int = 0
    role: str = "follower"
    alive: bool = True
    votes: set[str] = field(default_factory=set)
    next_index: dict[str, int] = field(default_factory=dict)
    match_index: dict[str, int] = field(default_factory=dict)

    def last_term(self) -> int:
        return self.log[-1].term if self.log else 0


@dataclass(frozen=True)
class Message:
    kind: str
    src: str
    dst: str
    term: int
    data: dict[str, Any]


class Simulation:
    """Discrete-event teaching model. Buggy mode skips only the vote log-freshness rule."""

    def __init__(self, ids: tuple[str, ...] = ("A", "B", "C", "D", "E"),
                 *, mode: str = "correct", latency: int = 1) -> None:
        if mode not in ("correct", "buggy"):
            raise ValueError("mode must be correct or buggy")
        if len(ids) < 3 or len(set(ids)) != len(ids) or latency < 1:
            raise ValueError("need >=3 unique nodes and latency >=1")
        self.ids = tuple(ids)
        self.nodes = {name: Node(name) for name in ids}
        self.mode = mode
        self.latency = latency
        self.time = 0
        self._order = 0
        self._queue: list[tuple[int, int, Message]] = []
        self._groups = {name: 0 for name in ids}
        self._drops: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []
        self.violations: list[dict[str, Any]] = []
        self._violation_keys: set[tuple[Any, ...]] = set()
        self._committed: dict[tuple[str, int], Entry] = {}
        self._commit_events: dict[tuple[str, int], int] = {}
        self._leaders: dict[int, str] = {}

    @property
    def quorum(self) -> int:
        return len(self.ids) // 2 + 1

    def _record(self, event: str, **details: Any) -> int:
        event_id = len(self.trace) + 1
        self.trace.append({"id": event_id, "time": self.time, "event": event, **details})
        return event_id

    def partition(self, groups: list[list[str]]) -> None:
        if sorted(n for group in groups for n in group) != sorted(self.ids):
            raise ValueError("groups must partition all configured nodes")
        self._groups = {n: group_id for group_id, group in enumerate(groups) for n in group}
        self._record("partition_changed", groups=groups)

    def heal(self) -> None:
        self.partition([list(self.ids)])

    def drop_next(self, *, kind: str | None = None, src: str | None = None,
                  dst: str | None = None, count: int = 1) -> None:
        if count < 1 or any(n is not None and n not in self.nodes for n in (src, dst)):
            raise ValueError("invalid message drop")
        self._drops.append({"kind": kind, "src": src, "dst": dst, "remaining": count})
        self._record("drop_rule_added", kind=kind, src=src, dst=dst, count=count)

    def crash(self, name: str) -> None:
        node = self.nodes[name]
        node.alive = False
        node.role = "follower"
        node.votes.clear()
        node.next_index.clear()
        node.match_index.clear()
        self._record("node_crashed", node=name)

    def restart(self, name: str) -> None:
        node = self.nodes[name]
        node.alive = True
        node.role = "follower"
        node.votes.clear()
        node.next_index.clear()
        node.match_index.clear()
        self._record("node_restarted", node=name, term=node.term,
                     retained_entries=len(node.log), retained_commit=node.commit_index)
        self.check_invariants()

    def _send(self, msg: Message) -> None:
        if not self.nodes[msg.src].alive:
            self._record("message_not_sent", kind=msg.kind, src=msg.src,
                         dst=msg.dst, cause="source_crashed")
            return
        self._order += 1
        heapq.heappush(self._queue, (self.time + self.latency, self._order, msg))
        self._record("message_sent", kind=msg.kind, src=msg.src, dst=msg.dst, term=msg.term)

    def _step_down(self, node: Node, term: int) -> None:
        if term > node.term:
            node.term = term
            node.voted_for = None
        node.role = "follower"
        node.votes.clear()
        node.next_index.clear()
        node.match_index.clear()

    def elect(self, name: str) -> bool:
        candidate = self.nodes[name]
        if not candidate.alive:
            raise ValueError("crashed node cannot start election")
        candidate.term += 1
        candidate.role = "candidate"
        candidate.voted_for = name
        candidate.votes = {name}
        candidate.next_index.clear()
        candidate.match_index.clear()
        self._record("election_started", candidate=name, term=candidate.term,
                     last_index=len(candidate.log), last_term=candidate.last_term())
        for peer in self.ids:
            if peer != name:
                self._send(Message("request_vote", name, peer, candidate.term,
                                   {"last_index": len(candidate.log),
                                    "last_term": candidate.last_term()}))
        self.run()
        return candidate.role == "leader"

    def propose(self, leader_name: str, command: str) -> bool:
        leader = self.nodes[leader_name]
        if not leader.alive or leader.role != "leader":
            raise ValueError("only an active leader can propose")
        if not command:
            raise ValueError("command must be nonempty")
        leader.log.append(Entry(leader.term, command))
        self._record("proposal_appended", leader=leader_name, index=len(leader.log),
                     term=leader.term, command=command)
        for peer in self.ids:
            if peer != leader_name:
                self._send_append(leader, peer)
        self.run()
        return leader.commit_index >= len(leader.log)

    def _send_append(self, leader: Node, peer: str) -> None:
        if not leader.alive or leader.role != "leader":
            return
        next_idx = leader.next_index.get(peer, len(leader.log) + 1)
        prev = next_idx - 1
        data = {"prev_index": prev,
                "prev_term": leader.log[prev - 1].term if prev else 0,
                "entries": [asdict(entry) for entry in leader.log[prev:]],
                "leader_commit": leader.commit_index}
        self._send(Message("append", leader.id, peer, leader.term, data))

    def run(self, *, max_events: int = 10_000) -> int:
        processed = 0
        while self._queue:
            if processed >= max_events:
                raise RuntimeError("event budget exceeded")
            when, _, msg = heapq.heappop(self._queue)
            self.time = when
            processed += 1
            if not self.nodes[msg.src].alive or not self.nodes[msg.dst].alive:
                self._record("message_dropped", kind=msg.kind, src=msg.src,
                             dst=msg.dst, cause="crashed_node")
                continue
            if self._groups[msg.src] != self._groups[msg.dst]:
                self._record("message_dropped", kind=msg.kind, src=msg.src,
                             dst=msg.dst, cause="network_partition")
                continue
            discard = False
            for rule in self._drops:
                if rule["remaining"] and all(rule[k] is None or rule[k] == val for k, val in
                                             (("kind", msg.kind), ("src", msg.src), ("dst", msg.dst))):
                    rule["remaining"] -= 1
                    discard = True
                    self._record("message_dropped", kind=msg.kind, src=msg.src,
                                 dst=msg.dst, cause="injected_drop")
                    break
            if discard:
                continue
            self._record("message_delivered", kind=msg.kind, src=msg.src,
                         dst=msg.dst, term=msg.term)
            handlers = {
                "request_vote": self._handle_vote_request,
                "vote_reply": self._handle_vote_reply,
                "append": self._handle_append,
                "append_reply": self._handle_append_reply,
            }
            handlers[msg.kind](msg)
            self.check_invariants()
        return processed

    def _handle_vote_request(self, msg: Message) -> None:
        voter = self.nodes[msg.dst]
        if msg.term > voter.term:
            self._step_down(voter, msg.term)
        fresh_enough = (msg.data["last_term"], msg.data["last_index"]) >= (
            voter.last_term(), len(voter.log))
        free_to_vote = voter.voted_for in (None, msg.src)
        grant = msg.term >= voter.term and free_to_vote and (
            fresh_enough or self.mode == "buggy")
        if grant:
            voter.voted_for = msg.src
        reason = ("unsafe_log_check_disabled" if grant and not fresh_enough else
                  "up_to_date" if grant else
                  "stale_log" if not fresh_enough and msg.term >= voter.term else
                  "already_voted_or_old_term")
        self._record("vote_granted" if grant else "vote_rejected",
                     voter=voter.id, candidate=msg.src, term=msg.term,
                     reason=reason, voter_last_index=len(voter.log),
                     candidate_last_index=msg.data["last_index"])
        self._send(Message("vote_reply", voter.id, msg.src, voter.term,
                           {"granted": grant, "election_term": msg.term}))

    def _handle_vote_reply(self, msg: Message) -> None:
        candidate = self.nodes[msg.dst]
        if msg.term > candidate.term:
            self._step_down(candidate, msg.term)
            return
        if candidate.role != "candidate" or candidate.term != msg.data["election_term"]:
            return
        if not msg.data["granted"]:
            return
        candidate.votes.add(msg.src)
        if len(candidate.votes) < self.quorum:
            return
        candidate.role = "leader"
        event_id = self._record("leader_elected", leader=candidate.id,
                                term=candidate.term, voters=sorted(candidate.votes))
        prior = self._leaders.get(candidate.term)
        if prior is not None and prior != candidate.id:
            self._violate(("election_safety", candidate.term), "election_safety",
                          leaders=[prior, candidate.id], term=candidate.term,
                          witness_event_ids=[event_id])
        self._leaders[candidate.term] = candidate.id
        candidate.next_index = {p: len(candidate.log) + 1 for p in self.ids if p != candidate.id}
        candidate.match_index = {p: 0 for p in self.ids if p != candidate.id}
        for peer in self.ids:
            if peer != candidate.id:
                self._send_append(candidate, peer)

    def _handle_append(self, msg: Message) -> None:
        follower = self.nodes[msg.dst]
        if msg.term < follower.term:
            self._reply_append(msg, False, 0)
            return
        if msg.term > follower.term or follower.role != "follower":
            self._step_down(follower, msg.term)
        prev = msg.data["prev_index"]
        if prev > len(follower.log) or (
            prev and follower.log[prev - 1].term != msg.data["prev_term"]
        ):
            self._reply_append(msg, False, 0)
            return
        for index, data in enumerate(msg.data["entries"], start=prev + 1):
            incoming = Entry(**data)
            if index <= len(follower.log) and follower.log[index - 1] != incoming:
                removed = [asdict(x) for x in follower.log[index - 1:]]
                follower.log = follower.log[:index - 1]
                if follower.commit_index > len(follower.log):
                    follower.commit_index = len(follower.log)
                self._record("log_truncated", node=follower.id, index=index,
                             removed=removed, incoming=asdict(incoming))
            if index > len(follower.log):
                follower.log.append(incoming)
        if msg.data["leader_commit"] > follower.commit_index:
            follower.commit_index = min(msg.data["leader_commit"], len(follower.log))
        self._reply_append(msg, True, prev + len(msg.data["entries"]))

    def _reply_append(self, request: Message, success: bool, match: int) -> None:
        follower = self.nodes[request.dst]
        self._send(Message("append_reply", follower.id, request.src, follower.term,
                           {"success": success, "match": match}))

    def _handle_append_reply(self, msg: Message) -> None:
        leader = self.nodes[msg.dst]
        if msg.term > leader.term:
            self._step_down(leader, msg.term)
            return
        if leader.role != "leader" or msg.term != leader.term:
            return
        if not msg.data["success"]:
            if leader.next_index[msg.src] > 1:
                leader.next_index[msg.src] -= 1
                self._send_append(leader, msg.src)
            return
        leader.match_index[msg.src] = max(leader.match_index[msg.src], msg.data["match"])
        leader.next_index[msg.src] = leader.match_index[msg.src] + 1
        old = leader.commit_index
        for index in range(len(leader.log), old, -1):
            if leader.log[index - 1].term != leader.term:
                continue
            replicas = 1 + sum(match >= index for match in leader.match_index.values())
            if replicas >= self.quorum:
                leader.commit_index = index
                break
        if leader.commit_index > old:
            self._record("leader_commit_advanced", leader=leader.id,
                         old_index=old, new_index=leader.commit_index)
            for peer in self.ids:
                if peer != leader.id:
                    self._send_append(leader, peer)

    def _violate(self, key: tuple[Any, ...], invariant: str, **details: Any) -> None:
        if key in self._violation_keys:
            return
        self._violation_keys.add(key)
        event_id = self._record("violation_detected", invariant=invariant, **details)
        self.violations.append({"event_id": event_id, "invariant": invariant, **details})

    def check_invariants(self) -> None:
        for name in self.ids:
            node = self.nodes[name]
            for index in range(1, node.commit_index + 1):
                key = (name, index)
                if key not in self._committed:
                    self._committed[key] = node.log[index - 1]
                    self._commit_events[key] = self._record("entry_committed", node=name,
                                                             index=index,
                                                             entry=asdict(node.log[index - 1]))
            for (owner, index), original in list(self._committed.items()):
                if owner != name:
                    continue
                actual = node.log[index - 1] if len(node.log) >= index else None
                if actual != original:
                    unsafe_votes = [e["id"] for e in self.trace if
                                    e["event"] == "vote_granted" and
                                    e["reason"] == "unsafe_log_check_disabled"]
                    truncations = [e["id"] for e in self.trace if
                                   e["event"] == "log_truncated" and e["node"] == name]
                    self._violate(("committed_entry_overwritten", name, index),
                                  "committed_entry_overwritten", node=name, index=index,
                                  original=asdict(original),
                                  actual=asdict(actual) if actual else None,
                                  witness_event_ids=[self._commit_events[(name, index)]]
                                  + unsafe_votes[-1:] + truncations[-1:])
        by_index: dict[int, dict[str, Entry]] = {}
        for (name, index), entry in self._committed.items():
            by_index.setdefault(index, {})[name] = entry
        for index, owners in by_index.items():
            for first in sorted(owners):
                for second in sorted(owners):
                    if first >= second or owners[first] == owners[second]:
                        continue
                    self._violate(("committed_prefix_divergence", index, first, second),
                                  "committed_prefix_divergence", index=index,
                                  nodes=[first, second],
                                  entries=[asdict(owners[first]), asdict(owners[second])],
                                  witness_event_ids=[self._commit_events[(first, index)],
                                                     self._commit_events[(second, index)]])

    def state(self) -> dict[str, dict[str, Any]]:
        return {name: {"term": node.term, "role": node.role, "alive": node.alive,
                       "voted_for": node.voted_for,
                       "log": [asdict(entry) for entry in node.log],
                       "commit_index": node.commit_index}
                for name, node in self.nodes.items()}
