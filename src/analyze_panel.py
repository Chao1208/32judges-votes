#!/usr/bin/env python3
"""Offline fixed-panel analysis. Run: python src/analyze_panel.py --help."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .formulas import panel_metrics, solve_human_equivalent
    from .votes_io import LABELS, load_panel, load_saved_calibration
else:
    from formulas import panel_metrics, solve_human_equivalent
    from votes_io import LABELS, load_panel, load_saved_calibration


def main(argv=None):
    package_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=sorted(LABELS))
    parser.add_argument("--repo-root", type=Path, default=package_root,
                        help="dataset repository containing votes/, items/ and meta/")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--chaosnli", type=Path, help="user-provided chaosNLI_v1.0 directory")
    source.add_argument("--human-data", type=Path, help="user-provided full or sampled JSONL")
    parser.add_argument("--gold-field", default="majority_label",
                        help="supplied gold field; default preserves upstream majority_label ties")
    parser.add_argument("--failure-policy", choices=("drop-items", "paper-retained"), default="drop-items",
                        help="default drops each item with any placeholder; paper-retained reproduces the main table")
    parser.add_argument("--calibration-dir", type=Path, default=package_root / "meta" / "analysis",
                        help="directory holding saved calibration CSV and manifest")
    parser.add_argument("--no-calibration", action="store_true", help="skip saved-curve nu_H")
    parser.add_argument("--output", type=Path, help="JSON output; otherwise print to stdout")
    args = parser.parse_args(argv)
    human_path = args.human_data or args.chaosnli / f"chaosNLI_{args.dataset}.jsonl"
    try:
        panel = load_panel(args.repo_root, args.dataset, human_path, args.failure_policy, args.gold_field)
        result = panel_metrics(panel.idx, panel.human, panel.gold)
        result.update({"nu_H": None, "nu_H_status": "not_requested", "nu_H_is_upper_bound": False,
                       "nu_H_over_nu_MSE": None})
        if not args.no_calibration:
            curve, status = load_saved_calibration(args.calibration_dir, args.dataset, panel.provenance)
            if curve is not None:
                result["nu_H"], status = solve_human_equivalent(*curve, result["PR"])
            result["nu_H_status"] = status
            result["nu_H_is_upper_bound"] = status == "nu_H_le_first_grid"
            if status == "ok" and result["nu_MSE"] is not None and result["nu_MSE"] > 0.:
                result["nu_H_over_nu_MSE"] = result["nu_H"] / result["nu_MSE"]
        output = {"schema_version": 1, "analysis": "fixed_baseline_panel",
                  "metrics": result, "provenance": panel.provenance,
                  "calibration": {"mode": "none" if args.no_calibration else "saved_paper_curve",
                                  "new_monte_carlo_run": False},
                  "interpretation": "Human-equivalent metrics are reference- and target-specific, not human labor replacement rates."}
        encoded = json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f"analysis failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
