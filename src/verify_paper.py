#!/usr/bin/env python3
"""Compare actual CLI outputs with the saved paper table using your ChaosNLI copy."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--chaosnli", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-10)
    parser.add_argument("--verify-archive", action="store_true",
                        help="also run the data repository's integrity verifier")
    args = parser.parse_args()
    if args.atol <= 0.:
        parser.error("--atol must be positive")
    expected = json.loads((root / "reference/reported_values.json").read_text())["datasets"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.verify_archive:
        check = subprocess.run([sys.executable, str(args.repo_root / "scripts/verify.py")],
                               text=True, capture_output=True)
        (args.output_dir / "archive_integrity.log").write_text(check.stdout + check.stderr)
        check.check_returncode()
    comparisons = {}
    for dataset, reference in expected.items():
        output = args.output_dir / f"{dataset}_paper-retained.json"
        command = [sys.executable, str(root / "src/analyze_panel.py"), "--dataset", dataset,
                   "--repo-root", str(args.repo_root), "--chaosnli", str(args.chaosnli),
                   "--failure-policy", "paper-retained", "--output", str(output)]
        subprocess.run(command, check=True)
        actual = json.loads(output.read_text())["metrics"]
        checks = {}
        for metric, want in reference.items():
            got = actual.get(metric)
            difference = None if got is None else abs(got - want)
            checks[metric] = {"expected": want, "actual": got, "absolute_error": difference,
                              "pass": difference is not None and difference <= args.atol}
        comparisons[dataset] = checks
    result = {"tolerance_absolute": args.atol,
              "archive_integrity_verified": args.verify_archive,
              "note": "Votes and user-supplied human counts are loaded afresh; nu_H inverts a saved curve, not a new Monte Carlo calibration.",
              "datasets": comparisons,
              "pass": all(check["pass"] for checks in comparisons.values() for check in checks.values())}
    (args.output_dir / "paper_comparison.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("PASS: all fixed-panel paper values match" if result["pass"] else "FAIL: inspect paper_comparison.json")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
