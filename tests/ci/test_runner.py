#!/usr/bin/env python3
"""
Local CI orchestrator for PRD08-09

Covers:
- Lint/type gates
- Unit/Integration/System tests
- Performance/Chaos run and baseline gate
- Simple coverage summary trigger

Usage examples:
  python tests/ci/test_runner.py lint
  python tests/ci/test_runner.py type
  python tests/ci/test_runner.py test --labels "unit or security or system and not slow"
  python tests/ci/test_runner.py integration
  python tests/ci/test_runner.py perf
  python tests/ci/test_runner.py perf_gate --prev prev_baseline.json --tol 10 --mode soft
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def run(cmd: List[str], cwd: str | None = None, env: Dict[str, str] | None = None) -> int:
    print(f"$ {' '.join(shlex.quote(c) for c in cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cwd, env=env, check=False)
        return res.returncode
    except FileNotFoundError as e:
        print(f"❌ command not found: {cmd[0]} ({e})")
        return 127


def ensure_reports_dir() -> Path:
    out = Path("reports")
    out.mkdir(parents=True, exist_ok=True)
    return out


def cmd_lint(_args: argparse.Namespace) -> int:
    code = 0
    code |= run(["flake8", "."])
    code |= run(["black", "--check", "."])
    code |= run(["isort", "--check-only", "."])
    return code


def cmd_type(_args: argparse.Namespace) -> int:
    # Prefer project mypy.ini if present
    config = "backend/mypy.ini" if Path("backend/mypy.ini").exists() else None
    base_cmd = ["mypy", "--strict"]
    if config:
        base_cmd.extend(["--config-file", config])
    # Cover backend/app and tests (python parts)
    targets = []
    if Path("backend/app").exists():
        targets.append("backend/app")
    if Path("tests").exists():
        targets.append("tests")
    if not targets:
        print("⚠️ no python targets found for mypy")
        return 0
    return run(base_cmd + targets)


def cmd_test(args: argparse.Namespace) -> int:
    ensure_reports_dir()
    labels = args.labels or ""
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        "-m", labels if labels else "",
        "--junitxml=reports/junit.xml",
    ]
    pytest_cmd = [c for c in pytest_cmd if c]
    # Optional parallelism via pytest-xdist
    if os.environ.get("PYTEST_XDIST") == "1":
        pytest_cmd.extend(["-n", os.environ.get("PYTEST_XDIST_WORKERS", "auto")])
    # Disable auto-loading third-party pytest plugins to avoid env mismatches
    env = dict(os.environ)
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    return run(pytest_cmd, env=env)


def cmd_integration(_args: argparse.Namespace) -> int:
    ensure_reports_dir()
    labels = "integration or system"
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        "-m", labels,
        "--junitxml=reports/junit.xml",
    ]
    # Optional parallelism via pytest-xdist
    if os.environ.get("PYTEST_XDIST") == "1":
        pytest_cmd.extend(["-n", os.environ.get("PYTEST_XDIST_WORKERS", "auto")])
    env = dict(os.environ)
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    return run(pytest_cmd, env=env)


def cmd_perf(_args: argparse.Namespace) -> int:
    ensure_reports_dir()
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-k",
        "performance or chaos",
    ]
    rc = run(pytest_cmd)
    # Display where the baseline is
    preferred = Path("tests/reports/perf/chaos_baseline.json")
    fallback = Path("/tmp/chaos_baseline.json")
    if preferred.exists():
        print(f"📄 baseline: {preferred}")
    elif fallback.exists():
        print(f"📄 baseline: {fallback}")
    else:
        print("⚠️ baseline not found; ensure performance tests executed record().")
    return rc


def _load_baseline(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    records = payload.get("records", [])
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in records:
        cid = str(r.get("case_id"))
        if cid:
            by_id[cid] = r
    return by_id


def _compare(prev: Dict[str, Dict[str, Any]], cur: Dict[str, Dict[str, Any]], tol: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    for cid, c in cur.items():
        if cid not in prev:
            continue
        c_ms = c.get("duration_ms")
        p_ms = prev[cid].get("duration_ms")
        try:
            c_ms = float(c_ms)
            p_ms = float(p_ms)
        except Exception:
            continue
        if p_ms <= 0:
            continue
        change = ((c_ms - p_ms) / p_ms) * 100.0
        item = {
            "case_id": cid,
            "prev_ms": round(p_ms, 3),
            "curr_ms": round(c_ms, 3),
            "change_pct": round(change, 2),
        }
        if change > tol:
            regressions.append(item)
        elif change < -tol:
            improvements.append(item)
    return regressions, improvements


def cmd_perf_gate(args: argparse.Namespace) -> int:
    ensure_reports_dir()
    prev_path = Path(args.prev)
    if not prev_path.exists():
        print(f"❌ prev baseline not found: {prev_path}")
        return 2
    # locate current baseline
    cur_path = Path(args.current) if args.current else Path("tests/reports/perf/chaos_baseline.json")
    if not cur_path.exists():
        alt = Path("/tmp/chaos_baseline.json")
        if alt.exists():
            cur_path = alt
    if not cur_path.exists():
        print(f"❌ current baseline not found: {cur_path}")
        return 2

    prev = _load_baseline(prev_path)
    cur = _load_baseline(cur_path)

    regressions, improvements = _compare(prev, cur, tol=float(args.tol))
    summary = {
        "regressions": regressions,
        "improvements": improvements,
        "tolerance_pct": float(args.tol),
        "prev": str(prev_path),
        "current": str(cur_path),
    }
    out = Path("reports") / "perf_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.mode == "hard" and regressions:
        return 3
    return 0


def cmd_cov_summary(_args: argparse.Namespace) -> int:
    # Delegate to coverage_report if present
    script = Path("tests/reports/coverage_report.py")
    if not script.exists():
        print("⚠️ coverage_report.py not found")
        return 0
    return run([sys.executable, str(script)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Local CI runner for PRD08-09")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lint", help="Run flake8/black-check/isort-check")
    sub.add_parser("type", help="Run mypy --strict")

    p_test = sub.add_parser("test", help="Run pytest with labels")
    p_test.add_argument("--labels", help="Pytest -m expression", default="")

    sub.add_parser("integration", help="Run integration/system tests")
    sub.add_parser("perf", help="Run performance/chaos tests and produce baseline")

    p_gate = sub.add_parser("perf_gate", help="Compare baselines and gate")
    p_gate.add_argument("--prev", required=True, help="Path to previous baseline json")
    p_gate.add_argument("--current", help="Path to current baseline json (optional)")
    p_gate.add_argument("--tol", default=10, help="Tolerance percent (default 10)")
    p_gate.add_argument("--mode", choices=["soft", "hard"], default="soft")

    sub.add_parser("cov_summary", help="Print coverage summary markdown")

    args = parser.parse_args()

    if args.cmd == "lint":
        return cmd_lint(args)
    if args.cmd == "type":
        return cmd_type(args)
    if args.cmd == "test":
        return cmd_test(args)
    if args.cmd == "integration":
        return cmd_integration(args)
    if args.cmd == "perf":
        return cmd_perf(args)
    if args.cmd == "perf_gate":
        return cmd_perf_gate(args)
    if args.cmd == "cov_summary":
        return cmd_cov_summary(args)

    print(f"unknown command: {args.cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
