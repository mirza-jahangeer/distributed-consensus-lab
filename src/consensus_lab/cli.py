"""Command-line interface for reproducible consensus experiments."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from .scenarios import run_scenario
from .report import render_html

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def brief(record: dict[str, Any]) -> str:
    phases = record["phases"]
    problems = record["violations"]
    kinds = sorted({item["invariant"] for item in problems})
    result = "UNSAFE (expected in deliberately buggy mode)" if problems else "NO VIOLATION DETECTED"
    return (f"Mode: {record['mode']} | {result}\n"
            f"Stale D elected: {phases['stale_election']} | "
            f"Fresh C elected: {phases['fresh_election']} | "
            f"Y committed: {phases['second_commit']}\n"
            f"Invariant failures: {len(problems)}"
            + (f" ({', '.join(kinds)})" if kinds else "")
            + f"\nTrace events: {len(record['trace'])}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="consensus-lab", description="Deterministic consensus forensics MVP")
    subs = parser.add_subparsers(dest="command", required=True)
    run = subs.add_parser("run", help="Run scenario and optionally export JSON trace")
    run.add_argument("--scenario", default="stale_candidate", choices=["stale_candidate"])
    run.add_argument("--mode", default="correct", choices=["correct", "buggy"])
    run.add_argument("--trace", type=Path)
    run.add_argument("--json", action="store_true")
    compare = subs.add_parser("compare", help="Compare correct and buggy voting")
    compare.add_argument("--trace-dir", type=Path)
    report = subs.add_parser("report", help="Generate standalone HTML comparison")
    report.add_argument("--output", type=Path, default=Path("consensus-report.html"))
    replay = subs.add_parser("replay", help="Recompute and verify JSON trace")
    replay.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        record = run_scenario(args.scenario, args.mode).record()
        if args.trace:
            save(args.trace, record)
        print(json.dumps(record, indent=2) if args.json else brief(record))
        return 0
    if args.command == "compare":
        for mode in ("correct", "buggy"):
            record = run_scenario("stale_candidate", mode).record()
            if args.trace_dir:
                save(args.trace_dir / f"stale-candidate-{mode}.json", record)
            print(brief(record) + "\n")
        return 0
    if args.command == "report":
        good = run_scenario("stale_candidate", "correct").record()
        bad = run_scenario("stale_candidate", "buggy").record()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_html(good, bad), encoding="utf-8")
        print(f"HTML report written: {args.output}")
        return 0
    try:
        expected = json.loads(args.path.read_text(encoding="utf-8"))
        if expected.get("schema_version") != 1:
            raise ValueError("unsupported trace schema version")
        actual = run_scenario(expected["scenario"], expected["mode"]).record()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"REPLAY FAILED: {exc}")
        return 2
    if canonical(actual) != canonical(expected):
        print("REPLAY MISMATCH: trace, state or violations differ from recomputed execution")
        return 1
    print(f"REPLAY VERIFIED: {args.path} ({len(actual['trace'])} identical events)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
