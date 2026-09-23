#!/usr/bin/env python3
"""Run the public paper reproduction offline with zero API calls."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(step: str, command: list[str], log_path: Path) -> None:
    print(f"[{step}] {' '.join(command)}", flush=True)
    result = subprocess.run(command, text=True, capture_output=True)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise SystemExit(f"{step} failed; inspect {log_path}")


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chaosnli", type=Path, required=True,
                        help="directory containing the three chaosNLI_*.jsonl files")
    parser.add_argument("--output-dir", type=Path, default=root / "results" / "paper-reproduction")
    parser.add_argument("--atol", type=float, default=1e-10)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    python = sys.executable

    run("Step 1/4: archive integrity", [python, str(root / "scripts/verify.py")],
        args.output_dir / "step1_archive_integrity.log")
    run("Step 2/4: analysis unit tests",
        [python, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"],
        args.output_dir / "step2_unit_tests.log")
    run("Step 3/4: paper-table recomputation",
        [python, str(root / "src/verify_paper.py"), "--repo-root", str(root),
         "--chaosnli", str(args.chaosnli), "--output-dir", str(args.output_dir / "paper-table"),
         "--atol", str(args.atol)],
        args.output_dir / "step3_paper_table.log")
    run("Step 4/4: asymptote, calibration, CC-1000 and panel selection",
        [python, str(root / "src/verify_extended.py"), "--repo-root", str(root),
         "--chaosnli", str(args.chaosnli), "--output-dir", str(args.output_dir / "extended"),
         "--atol", str(args.atol)],
        args.output_dir / "step4_extended.log")

    comparison = json.loads((args.output_dir / "paper-table/paper_comparison.json").read_text())
    comparison["archive_integrity_verified"] = True
    comparison["archive_integrity_verification_step"] = "Step 1/4"
    (args.output_dir / "paper-table/paper_comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    extended = json.loads((args.output_dir / "extended/extended_comparison.json").read_text())
    summary = {
        "status": "PASS" if comparison["pass"] and extended["pass"] else "FAIL",
        "scope": ["fixed 32-judge baseline panel and saved main-table values",
                  "fixed-pool asymptote (Section 4.2, Appendix C)",
                  "analytic calibration delta and its agreement with the Monte-Carlo curve (Section 3.3)",
                  "CC-1000 fixed panel (Section 4.9)",
                  "panel selection: rules A/D/E, full enumeration, Tables 7-8 (Section 4.10)"],
        "model_api_calls": 0,
        "network_requests_during_run": 0,
        "input_start": "released per-item votes from 32 judges",
        "archive_integrity": "PASS",
        "unit_tests": "PASS",
        "paper_table": comparison,
        "extended": {"pass": extended["pass"], "groups": extended["groups"],
                     "failed": extended["failed"], "errata": extended["errata"]},
        "not_reproduced": [
            "presentation-order analyses", "random subpanel curves",
            "provider-family decompositions", "new Monte Carlo calibration",
            "split/member-addition diagnostics", "geometry/loss diagnostics",
            "tie-rate evidence", "figure generation",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if summary["status"] != "PASS":
        raise SystemExit(f"FAIL: inspect {args.output_dir / 'summary.json'}")
    print("PASS: offline reproduction completed with 0 model/API calls")
    print(f"Summary: {args.output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
