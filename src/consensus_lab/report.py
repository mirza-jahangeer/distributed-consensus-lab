"""Standalone HTML forensic report (no runtime dependencies or remote scripts)."""
from __future__ import annotations
from html import escape
import json
from typing import Any

def _e(value: Any) -> str:
    return escape(str(value), quote=True)

def render_html(correct: dict[str, Any], buggy: dict[str, Any]) -> str:
    important = {"partition_changed", "election_started", "vote_granted", "vote_rejected",
                 "leader_elected", "proposal_appended", "leader_commit_advanced",
                 "log_truncated", "entry_committed", "violation_detected"}
    def panel(run: dict[str, Any]) -> str:
        mode = run["mode"]
        problems = run["violations"]
        head = (f'<section class="panel"><h2>{_e(mode.upper())}</h2>'
                f'<p>{len(problems)} detected violations · {len(run["trace"])} events</p>')
        rows = []
        for event in run["trace"]:
            if event["event"] not in important:
                continue
            number = event["id"]
            kind = event["event"]
            details = {k: v for k, v in event.items() if k not in ("id", "time", "event")}
            highlight = ' class="danger"' if kind == "violation_detected" else ""
            rows.append(f'<tr id="{_e(mode)}-e{number}"{highlight}><td>{number}</td>'
                        f'<td>{event["time"]}</td><td>{_e(kind)}</td>'
                        f'<td><code>{_e(json.dumps(details, sort_keys=True))}</code></td></tr>')
        witnesses = []
        for violation in problems:
            refs = ", ".join(f'<a href="#{_e(mode)}-e{num}">#{num}</a>'
                             for num in violation.get("witness_event_ids", []))
            witnesses.append(f'<li><b>{_e(violation["invariant"])}</b> — evidence: {refs}</li>')
        return (head + '<h3>Violation witnesses</h3>'
                + ('<ol>' + "".join(witnesses) + '</ol>'
                   if witnesses else '<p>None detected in this schedule.</p>')
                + '<h3>Key events</h3><table><thead><tr><th>#</th><th>Tick</th>'
                  '<th>Event</th><th>Evidence</th></tr></thead><tbody>'
                + "".join(rows) + '</tbody></table></section>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Consensus Failure Forensics — Correct vs Buggy</title>'
            '<style>body{font:15px system-ui,sans-serif;margin:0;background:#0b1425;color:#edf3ff}'
            'main{max-width:1500px;margin:auto;padding:30px}p{color:#abbcda}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:20px}'
            '.panel{background:#14233b;border:1px solid #344563;border-radius:16px;padding:18px;min-width:0}'
            'table{border-collapse:collapse;width:100%;font-size:12px}'
            'td,th{border-bottom:1px solid #33425e;padding:9px;text-align:left;vertical-align:top}'
            'td:last-child{max-width:350px;overflow-wrap:anywhere}'
            'code{white-space:normal;color:#a4f4e0}.danger{background:#4c2637}'
            'a{color:#8fc9ff}ol{padding-left:22px}li{margin:8px 0}'
            'small{color:#aebddd}</style></head>'
            '<body><main><h1>Consensus Failure Forensics Lab</h1>'
            '<p>Deterministic five-node stale-candidate experiment. Compare protected Raft voting'
            ' against an intentionally unsafe mutation. Tick is virtual time.</p>'
            '<p><small>Educational model; not production Raft or an exhaustive proof.</small></p>'
            '<div class="grid">' + panel(correct) + panel(buggy) + '</div></main></body></html>')
