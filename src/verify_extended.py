#!/usr/bin/env python3
"""Recompute the paper's conclusions beyond the fixed-panel table and compare them.

Covers the fixed-pool asymptote (Section 4.2 and Appendix C), the analytic
calibration and its agreement with the Monte-Carlo curves (Section 3.3), the CC-1000
external check (Section 4.9), the panel selection results (Section 4.10, Tables 7-8,
Appendix A.7) with their error decomposition, and the selection rerun on the
placeholder-free items (Appendix D.5). Each quantity is checked
twice: against the saved unrounded value in reference/extended_reference.json (and
reference/panel_selection.csv) within --atol, and against the number printed in the
paper within half a unit of its last printed digit.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

if __package__:
    from . import civil_comments as CC
    from .formulas import closed_form_delta, nu_closed_form, panel_metrics, pool_asymptote, \
        solve_human_equivalent
    from .selection import Pool, select
    from .votes_io import load_panel, load_saved_calibration
else:
    import civil_comments as CC
    from formulas import closed_form_delta, nu_closed_form, panel_metrics, pool_asymptote, \
        solve_human_equivalent
    from selection import Pool, select
    from votes_io import load_panel, load_saved_calibration

CHAOSNLI = {"mnli_m": "chaosnli-mnli-m-1000", "snli": "chaosnli-snli-1000",
            "alphanli": "chaosnli-alphanli-1000"}
CELLS = [(ds, k) for ds in (*CHAOSNLI.values(), CC.DATASET) for k in (5, 7)]

# Values as printed in the paper; each is compared within half a unit of its last digit.
PRINTED = {
    "asymptote": {"nu_MSE_inf_centered": ([2.392, 3.990, 3.655], 3),
                  "observed_share_of_centered_pct": ([96.3, 94.0, 94.2], 1),
                  "nu_MSE_gain_at_k_project": ([0.043, 0.117, 0.102], 3),
                  "nu_MSE_inf_uncentered": ([2.397, 4.003, 3.656], 3)},
    "delta": [7.80e-4, 1.02e-3, 1.93e-3, 1.15e-3],
    "civil_comments": {"nu_H": (2.838, 3), "nu_MSE": (1.490, 3), "nu_MSE_finite_annotation": (1.549, 3),
                       "n_eff": (1.677, 3), "gamma_co_all": (0.571, 3), "human_votes_total": (176251, 0),
                       "annotators_median": (67, 0), "annotators_min": (50, 0),
                       "annotators_max": (2196, 0), "n_eff_tied_items_excluded": (10, 0)},
    # Table 7: S0 acc, S0 nu_H, A dacc (pp), A dnu_H (%), D dacc (pp), D dnu_H (%)
    "table7": [[0.7325, 2.732, 0.80, 27.6, 1.00, 10.8], [0.7215, 3.085, 0.20, 24.8, 2.35, 18.7],
               [0.8685, 2.495, 0.25, 56.0, 1.50, 40.6], [0.8590, 2.759, 1.10, 52.3, 2.70, 34.5],
               [0.9380, 2.651, 0.20, 43.9, 0.80, 23.8], [0.9390, 2.890, 0.10, 43.0, 0.70, 38.2],
               [0.6850, 1.724, 0.30, 51.6, 1.40, 32.6], [0.6860, 1.843, 0.10, 41.9, 0.80, 26.0]],
    "table7_decimals": [4, 3, 2, 1, 2, 1],
    # Table 8: S0 E, S0 nu_MSE, dnu_MSE (%) for A, D, E, domega_bar under A (%)
    "table8": [[0.2135, 2.125, 19.9, 7.5, 19.9, 5.7], [0.2066, 2.196, 13.4, 14.6, 15.4, 4.4],
               [0.1367, 2.487, 31.0, 29.6, 31.2, 26.6], [0.1317, 2.581, 33.2, 22.9, 34.4, 18.9],
               [0.0600, 2.768, 11.3, 10.6, 15.9, 32.2], [0.0588, 2.825, 17.2, 16.1, 18.6, 22.7],
               [0.2971, 1.184, 28.3, 19.0, 28.3, 4.1], [0.2890, 1.217, 23.7, 15.6, 23.7, 2.8]],
    "table8_decimals": [4, 3, 1, 1, 1, 1],
    "feasible": [85, 908, 282, 4311, 773, 981, 576, 449],
    "candidates_in_D_S0": [85, 906, 282, 4258, 756, 981, 555, 439],
    "one_swap_in_D_S0": [13, 43, 14, 118, 79, 60, 39, 25],
    # Appendix A.7 error decomposition under rule A: ranges of d(omega_bar/k) and -dB, and MNLI-m k=5
    "decomposition": {"d_omega_over_k": (0.0016, 0.0121), "minus_d_B": (0.0121, 0.0687),
                      "mnli_k5": (0.0044, -0.0398, -0.0354)},
    # Appendix D.5 clean-view rerun: max change of accuracy gains (pp), nu_H gains (points), S0 percentile ceiling
    "clean_view": {"dacc_pp": 0.004, "dnu_points": 0.34, "percentile_ceiling": (47.1, 47.4)},
}


class Checks:
    def __init__(self, atol):
        self.atol, self.rows = atol, []

    def add(self, group, name, value, expected, tol, kind):
        value = value.item() if isinstance(value, np.generic) else value
        if isinstance(expected, (bool, str, list)) or value is None:
            ok = value == expected
        else:
            ok = math.isfinite(value) and abs(value - expected) <= tol
        self.rows.append({"group": group, "check": name, "kind": kind, "recomputed": value,
                          "expected": expected, "tol": tol, "pass": bool(ok)})

    def saved(self, group, name, value, expected):
        exact = isinstance(expected, (int, bool, str, list)) and not isinstance(expected, float)
        self.add(group, name, value, expected, 0 if exact else self.atol, "saved_unrounded")

    def printed(self, group, name, value, printed, decimals):
        self.add(group, name, value, printed, 0.5 * 10 ** -decimals + 1e-9, "printed_in_paper")

    def tree(self, group, prefix, value, expected):
        """Compare every leaf of the saved reference with the recomputed structure."""
        if isinstance(expected, dict):
            for key, sub in expected.items():
                self.tree(group, f"{prefix}.{key}", value.get(key) if isinstance(value, dict) else None, sub)
        else:
            self.saved(group, prefix, value, expected)


def pct(new, old):
    return (new / old - 1.) * 100.


def selection_claims(checks, cells):
    group = "selection_printed"
    get = lambda f: [f(c) for c in cells]
    p = lambda c, r: c["panels"][r]
    for row, (cell, printed) in enumerate(zip(cells, PRINTED["table7"])):
        values = [p(cell, "S0")["acc"], p(cell, "S0")["nu_H"],
                  (p(cell, "A")["acc"] - p(cell, "S0")["acc"]) * 100, pct(p(cell, "A")["nu_H"], p(cell, "S0")["nu_H"]),
                  (p(cell, "D")["acc"] - p(cell, "S0")["acc"]) * 100, pct(p(cell, "D")["nu_H"], p(cell, "S0")["nu_H"])]
        for col, (v, e, d) in enumerate(zip(values, printed, PRINTED["table7_decimals"])):
            checks.printed(group, f"Table 7 row {row + 1} col {col + 3}", v, e, d)
    for row, (cell, printed) in enumerate(zip(cells, PRINTED["table8"])):
        s0 = p(cell, "S0")
        values = [s0["E"], s0["nu_MSE"], *(pct(p(cell, r)["nu_MSE"], s0["nu_MSE"]) for r in "ADE"),
                  pct(p(cell, "A")["omega_bar"], s0["omega_bar"])]
        for col, (v, e, d) in enumerate(zip(values, printed, PRINTED["table8_decimals"])):
            checks.printed(group, f"Table 8 row {row + 1} col {col + 3}", v, e, d)

    def span(name, values, low, high, decimals):
        checks.printed(group, f"{name} (min)", min(values), low, decimals[0])
        checks.printed(group, f"{name} (max)", max(values), high, decimals[1])

    enum = lambda c: c["enumeration"]
    span("Result 1: panels more accurate than S0", get(lambda c: enum(c)["n_acc_gt_S0"]), 109, 577093, (0, 0))
    span("Result 1: share of those with larger nu_H, %",
         get(lambda c: 100 * enum(c)["n_acc_gt_and_nu_H_gt_S0"] / enum(c)["n_acc_gt_S0"]), 98.55, 100.0, (2, 2))
    span("Result 1: extreme dominating panel, dacc pp",
         get(lambda c: (enum(c)["max_nu_H_in_D_S0"]["acc"] - p(c, "S0")["acc"]) * 100), 0.10, 0.90, (2, 2))
    span("Result 1: extreme dominating panel, dnu_H %",
         get(lambda c: pct(enum(c)["max_nu_H_in_D_S0"]["nu_H"], p(c, "S0")["nu_H"])), 33.6, 91.4, (1, 1))
    span("Result 1: S0 nu_H percentile", get(lambda c: enum(c)["S0_nu_H_percentile_pct"]), 0.00, 47.1, (2, 1))
    checks.add(group, "Result 1: S0 on the Pareto front (cases)", sum(get(lambda c: enum(c)["S0_on_pareto_front"])),
               0, 0, "printed_in_paper")
    span("Result 2: rule A dacc pp", get(lambda c: (p(c, "A")["acc"] - p(c, "S0")["acc"]) * 100), 0.10, 1.10, (2, 2))
    span("Result 2: rule A dnu_H %", get(lambda c: pct(p(c, "A")["nu_H"], p(c, "S0")["nu_H"])), 24.8, 56.0, (1, 1))
    span("Result 2: rule D dacc pp", get(lambda c: (p(c, "D")["acc"] - p(c, "S0")["acc"]) * 100), 0.70, 2.70, (2, 2))
    span("Result 2: rule D dnu_H %", get(lambda c: pct(p(c, "D")["nu_H"], p(c, "S0")["nu_H"])), 10.8, 40.6, (1, 1))
    reaches = [abs(p(c, "D")["acc"] - enum(c)["max_acc"]) < 1e-12 for c in cells]
    checks.add(group, "Result 2: rule D attains the enumeration-maximal accuracy (cases)", sum(reaches), 4, 0,
               "printed_in_paper")
    span("Result 2: rule D shortfall from maximal accuracy, pp",
         [(enum(c)["max_acc"] - p(c, "D")["acc"]) * 100 for c, r in zip(cells, reaches) if not r], 0.10, 0.50, (2, 2))
    span("Result 2: rule A share of the largest nu_H at that size, %",
         get(lambda c: 100 * p(c, "A")["nu_H"] / enum(c)["max_nu_H"]), 77.0, 92.0, (1, 1))
    span("Result 2: one-swap panels in D(S0)", get(lambda c: c["candidates"]["n_one_swap_in_D_S0"]), 13, 118, (0, 0))
    span("Result 2: one-swap panels in D(S0), % of N1",
         get(lambda c: 100 * c["candidates"]["n_one_swap_in_D_S0"] / c["candidates"]["n_one_swap"]), 9.6, 67.4, (1, 1))
    span("Result 2: rule A on N1, dnu_H %", get(lambda c: pct(c["rule_A_one_swap"]["nu_H"], p(c, "S0")["nu_H"])),
         11.9, 29.5, (1, 1))
    span("Result 2: rule A on N1, dacc pp", get(lambda c: (c["rule_A_one_swap"]["acc"] - p(c, "S0")["acc"]) * 100),
         0.10, 0.85, (2, 2))
    checks.add(group, "Result 2: one-swap panels on the candidate front (all cases)",
               sum(get(lambda c: c["candidates"]["n_one_swap_on_candidate_front"])), 0, 0, "printed_in_paper")
    ranks = lambda rules, side: [r for c in cells for rule in rules for r in p(c, rule)[side]]
    span("Result 2: rule A swapped-in ranks", ranks("A", "swapped_in_ranks"), 15, 32, (0, 0))
    span("Result 2: rule A swapped-out ranks", ranks("A", "swapped_out_ranks"), 1, 6, (0, 0))
    span("Result 2: rules A and D swapped-in ranks", ranks("AD", "swapped_in_ranks"), 11, 32, (0, 0))
    span("Result 2: rules A and D swapped-out ranks", ranks("AD", "swapped_out_ranks"), 1, 7, (0, 0))
    span("Result 2: q_bar fall under rule A, %", get(lambda c: -pct(p(c, "A")["q_bar"], p(c, "S0")["q_bar"])),
         35.4, 71.4, (1, 1))
    span("Result 2/3: omega_bar rise under rule A, %",
         get(lambda c: pct(p(c, "A")["omega_bar"], p(c, "S0")["omega_bar"])), 2.8, 32.2, (1, 1))
    span("Result 3: E fall under rule A, %", get(lambda c: -pct(p(c, "A")["E"], p(c, "S0")["E"])), 10.1, 24.9, (1, 1))
    for rule, low, high in (("A", 11.3, 33.2), ("D", 7.5, 29.6), ("E", 15.4, 34.4)):
        span(f"Result 3: rule {rule} dnu_MSE %", get(lambda c: pct(p(c, rule)["nu_MSE"], p(c, "S0")["nu_MSE"])),
             low, high, (1, 1))
    checks.add(group, "Result 3: rule D beats rule A on nu_MSE (cases)",
               sum(get(lambda c: p(c, "D")["nu_MSE"] > p(c, "A")["nu_MSE"])), 1, 0, "printed_in_paper")
    span("Result 3: rule A share of the feasible nu_MSE optimum, %",
         get(lambda c: 100 * p(c, "A")["nu_MSE"] / p(c, "E")["nu_MSE"]), 96.0, 100.0, (1, 1))
    gain = get(lambda c: 100 * (p(c, "A")["nu_MSE"] - p(c, "S0")["nu_MSE"])
               / (p(c, "E")["nu_MSE"] - p(c, "S0")["nu_MSE"]))
    span("Result 3: rule A share of the available nu_MSE improvement, %", gain, 70.6, 100.0, (1, 1))
    worst = CELLS[gain.index(min(gain))]
    checks.add(group, "Result 3: worst case for the indirect objective", list(worst),
               ["chaosnli-alphanli-1000", 5], 0, "printed_in_paper")
    checks.printed(group, "Result 3: nu_MSE gain forgone in the worst case, %", 100 - min(gain), 29.4, 1)
    checks.add(group, "Result 3: rules A and E return the same panel (cases)",
               sum(get(lambda c: p(c, "A")["members"] == p(c, "E")["members"])), 3, 0, "printed_in_paper")
    span("Result 3: rule E share of the largest feasible nu_H, %",
         get(lambda c: 100 * p(c, "E")["nu_H"] / c["candidates"]["max_nu_H_feasible"]), 92.2, 100.0, (1, 1))
    checks.add(group, "Result 3: rule E inside D(S0) (cases)", sum(get(lambda c: p(c, "E")["in_D_S0"])), 8, 0,
               "printed_in_paper")
    for key, name in (("feasible", "n_feasible"), ("candidates_in_D_S0", "n_in_D_S0"),
                      ("one_swap_in_D_S0", "n_one_swap_in_D_S0")):
        checks.add(group, f"Appendix A.7: {name} per case", get(lambda c: c["candidates"][name]),
                   PRINTED[key], 0, "printed_in_paper")
    for k, share in ((5, 1.81), (7, 0.19)):
        n = next(c["candidates"]["n_candidates"] for c in cells if c["k"] == k)
        checks.printed(group, f"Section 4.10: candidate share of all panels at k={k}, %",
                       100 * n / math.comb(32, k), share, 2)
    for cell, printed in zip(cells[6:], (1.724, 1.843)):
        checks.printed(group, f"Section 4.10: CC-1000 baseline nu_H at k={cell['k']}", p(cell, "S0")["nu_H"], printed, 3)


def calibration_claims(checks, curves, cells):
    """Section 3.3: PR_delta against the Monte-Carlo means on the grid and at the selected panels."""
    group = "calibration_printed"
    grid = []
    for dsid, (ms, prs) in curves.items():
        delta = next(c["delta"] for c in cells if c["dataset_id"] == dsid)
        grid += [abs(m / (1. + (m - 1.) * delta) / pr - 1.) * 100. for m, pr in zip(ms, prs)]
    checks.printed(group, "PR_delta vs Monte-Carlo PR_0, max over every grid point, %", max(grid), 0.18, 2)
    selected = []
    for cell in cells:
        for rule in ("S0", "A", "D", "E"):
            panel = cell["panels"][rule]
            nu_mc, status = solve_human_equivalent(*curves[cell["dataset_id"]], panel["PR"])
            if status == "ok":
                selected.append(abs(panel["nu_H"] / nu_mc - 1.) * 100.)
    checks.add(group, "selected panels covered by the Monte-Carlo grid", len(selected), 30, 0, "printed_in_paper")
    checks.printed(group, "closed form vs Monte Carlo nu_H, selected panels, max %", max(selected), 0.15, 2)


def decomposition_claims(checks, pools, cells):
    """Appendix A.7: E = omega_bar/k + B under rule A relative to S0."""
    group = "decomposition_printed"
    rows = []
    for cell in cells:
        k, gram = cell["k"], pools[cell["dataset_id"]].gram
        parts = {}
        for rule in ("S0", "A"):
            sub = gram[np.ix_(cell["panels"][rule]["members"], cell["panels"][rule]["members"])]
            parts[rule] = (np.trace(sub) / k ** 2, (sub.sum() - np.trace(sub)) / k ** 2)
        rows.append((parts["A"][0] - parts["S0"][0], parts["A"][1] - parts["S0"][1]))
    d_w, d_b = [r[0] for r in rows], [r[1] for r in rows]
    checks.add(group, "d(omega_bar/k) > 0 and dB < -d(omega_bar/k) (cases)",
               sum(w > 0 and b < -w for w, b in rows), 8, 0, "printed_in_paper")
    for name, values, (low, high) in (("d(omega_bar/k)", d_w, PRINTED["decomposition"]["d_omega_over_k"]),
                                      ("-dB", [-b for b in d_b], PRINTED["decomposition"]["minus_d_B"])):
        checks.printed(group, f"{name} (min)", min(values), low, 4)
        checks.printed(group, f"{name} (max)", max(values), high, 4)
    w, b, e = PRINTED["decomposition"]["mnli_k5"]
    checks.printed(group, "MNLI-m k=5 d(omega_bar/k)", d_w[0], w, 4)
    checks.printed(group, "MNLI-m k=5 dB", d_b[0], b, 4)
    checks.printed(group, "MNLI-m k=5 dE", d_w[0] + d_b[0], e, 4)


def clean_view_claims(checks, args, cells):
    """Appendix D.5: rerun the selection with every placeholder-touched item dropped."""
    group = "clean_view_printed"
    retained = {(c["dataset_id"], c["k"]): c for c in cells}
    dacc, dnu, same, ceiling = [], [], 0, []
    for key, dsid in CHAOSNLI.items():
        panel = load_panel(args.repo_root, key, args.chaosnli / f"chaosNLI_{key}.jsonl", "drop-items")
        pool = Pool(panel.idx, panel.human, panel.gold, panel.judges)
        for k in (5, 7):
            t0 = time.time()
            clean, old = select(pool, k), retained[(dsid, k)]
            same += all(clean["panels"][r]["judge_keys"] == old["panels"][r]["judge_keys"] for r in ("S0", "A", "D", "E"))
            same += all(clean["enumeration"][f] == old["enumeration"][f]
                        for f in ("n_panels", "n_acc_gt_S0", "n_acc_gt_and_nu_H_gt_S0", "S0_on_pareto_front"))
            for r in "ADE":
                gain = lambda c, f: c["panels"][r][f] - c["panels"]["S0"][f]
                dacc.append(abs(gain(clean, "acc") - gain(old, "acc")) * 100)
                dnu.append(abs(pct(clean["panels"][r]["nu_H"], clean["panels"]["S0"]["nu_H"])
                               - pct(old["panels"][r]["nu_H"], old["panels"]["S0"]["nu_H"])))
            ceiling.append((old["enumeration"]["S0_nu_H_percentile_pct"], clean["enumeration"]["S0_nu_H_percentile_pct"]))
            print(f"  clean view {dsid} k={k}: {time.time() - t0:.1f}s", flush=True)
    checks.add(group, "S0, A/D/E members and enumeration counts unchanged (2 per case)", same, 12, 0,
               "printed_in_paper")
    checks.printed(group, "max change of accuracy gains, pp", max(dacc), PRINTED["clean_view"]["dacc_pp"], 3)
    checks.printed(group, "max change of nu_H gains, points", max(dnu), PRINTED["clean_view"]["dnu_points"], 2)
    old_top, new_top = PRINTED["clean_view"]["percentile_ceiling"]
    checks.printed(group, "S0 percentile ceiling, retained", max(c[0] for c in ceiling), old_top, 1)
    checks.printed(group, "S0 percentile ceiling, clean view", max(c[1] for c in ceiling), new_top, 1)


def compare_panel_csv(checks, cells, path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    checks.add("selection_panel_csv", "row count", len(rows), 4 * len(cells), 0, "saved_unrounded")
    by_cell = {(c["dataset_id"], c["k"]): c for c in cells}
    for row in rows:
        panel = by_cell[(row["dataset_id"], int(row["k"]))]["panels"][row["rule"]]
        name = f"{row['dataset_id']} k={row['k']} {row['rule']}"
        checks.saved("selection_panel_csv", f"{name} judge_keys", " ".join(panel["judge_keys"]), row["judge_keys"])
        checks.saved("selection_panel_csv", f"{name} acc_int_sum_lut6", panel["acc_int_sum_lut6"],
                     int(row["acc_int_sum_lut6"]))
        for column, field in (("acc", "acc"), ("q_bar", "q_bar"), ("PR", "PR"), ("nu_H_closed_form", "nu_H"),
                              ("E", "E"), ("nu_MSE", "nu_MSE"), ("omega_bar", "omega_bar")):
            checks.add("selection_panel_csv", f"{name} {column}", panel[field], float(row[column]), 1e-9,
                       "saved_csv_rounded_to_1e-11")
        if row["in_joint_improvement_set"]:
            checks.saved("selection_panel_csv", f"{name} in D(S0)", panel["in_D_S0"],
                         row["in_joint_improvement_set"] == "1")


def main(argv=None):
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--chaosnli", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-10)
    args = parser.parse_args(argv)
    reference_dir = args.repo_root / "reference"
    ref = json.loads((reference_dir / "extended_reference.json").read_text(encoding="utf-8"))
    checks, started = Checks(args.atol), time.time()

    pools, closed, curves = {}, {}, {}
    for key, dsid in CHAOSNLI.items():
        panel = load_panel(args.repo_root, key, args.chaosnli / f"chaosNLI_{key}.jsonl", "paper-retained")
        pools[dsid] = Pool(panel.idx, panel.human, panel.gold, panel.judges)
        asym = pool_asymptote(panel.idx, panel.human)
        checks.tree("asymptote_saved", dsid, asym, ref["pool_asymptote"][dsid])
        metrics = panel_metrics(panel.idx, panel.human, panel.gold)
        curve, _ = load_saved_calibration(reference_dir, key, panel.provenance)
        curves[dsid] = curve
        delta = closed_form_delta(panel.human)
        closed[dsid] = {"delta": delta, "PR": metrics["PR"], "nu_H_closed_form": nu_closed_form(metrics["PR"], delta),
                        "nu_H_monte_carlo": solve_human_equivalent(*curve, metrics["PR"])[0]}
        for name, (values, decimals) in PRINTED["asymptote"].items():
            checks.printed("asymptote_printed", f"{dsid} {name}", asym[name], values[list(CHAOSNLI).index(key)],
                           decimals)
        checks.add("asymptote_printed", f"{dsid} uncentered minus centered nu_MSE_inf below 0.4%",
                   pct(asym["nu_MSE_inf_uncentered"], asym["nu_MSE_inf_centered"]) < 0.4, True, 0, "printed_in_paper")

    cal = ref["civil_comments_calibration"]
    curve = CC.load_curve(reference_dir, cal["sha256"])
    curves[CC.DATASET] = curve
    civil = CC.fixed_panel(args.repo_root, curve)
    checks.tree("civil_comments_saved", CC.DATASET, civil, ref["civil_comments_fixed_panel"])
    for name, (value, decimals) in PRINTED["civil_comments"].items():
        checks.printed("civil_comments_printed", name, civil[name], value, decimals)
    idx, human, gold, judges, _, _ = CC.load(args.repo_root)
    pools[CC.DATASET] = Pool(idx, human, gold, judges)
    pr_cc = panel_metrics(idx, human, gold)["PR"]
    closed[CC.DATASET] = {"delta": pools[CC.DATASET].delta, "PR": pr_cc,
                          "nu_H_closed_form": nu_closed_form(pr_cc, pools[CC.DATASET].delta),
                          "nu_H_monte_carlo": civil["nu_H"]}
    for dsid, value in closed.items():
        checks.tree("calibration_saved", dsid, value, ref["closed_form_calibration"][dsid])
    for dsid, printed in zip(closed, PRINTED["delta"]):
        checks.printed("calibration_printed", f"{dsid} delta x1e3", closed[dsid]["delta"] * 1e3, printed * 1e3, 2)
    checks.add("calibration_printed", "min 1/delta > 517 (printed as 1/delta > 517)",
               min(1 / c["delta"] for c in closed.values()) > 517, True, 0, "printed_in_paper")
    gaps = [abs(c["nu_H_closed_form"] / c["nu_H_monte_carlo"] - 1) * 100 for c in closed.values()]
    checks.printed("calibration_printed", "closed form vs Monte Carlo, full panels, % (min)", min(gaps), 0.027, 3)
    checks.printed("calibration_printed", "closed form vs Monte Carlo, full panels, % (max)", max(gaps), 0.077, 3)

    cells = []
    saved = {(c["dataset_id"], c["k"]): c for c in ref["selection"]}
    for dsid, k in CELLS:
        t0 = time.time()
        cell = {"dataset_id": dsid, **select(pools[dsid], k)}
        cells.append(cell)
        checks.tree("selection_saved", f"{dsid} k={k}", cell, saved[(dsid, k)])
        print(f"  selection {dsid} k={k}: {time.time() - t0:.1f}s", flush=True)
    compare_panel_csv(checks, cells, reference_dir / "panel_selection.csv")
    selection_claims(checks, cells)
    calibration_claims(checks, curves, cells)
    decomposition_claims(checks, pools, cells)
    clean_view_claims(checks, args, cells)

    failed = [row for row in checks.rows if not row["pass"]]
    groups = {}
    for row in checks.rows:
        g = groups.setdefault(row["group"], {"n": 0, "failed": 0})
        g["n"] += 1
        g["failed"] += not row["pass"]
    result = {"schema_version": 1, "pass": not failed, "atol": args.atol,
              "elapsed_sec": round(time.time() - started, 1), "model_api_calls": 0,
              "groups": groups, "failed": failed, "checks": checks.rows,
              "recomputed": {"closed_form_calibration": closed, "civil_comments_fixed_panel": civil,
                             "selection": cells}}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "extended_comparison.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    for name, g in groups.items():
        print(f"  {name}: {g['n'] - g['failed']}/{g['n']} pass")
    for row in failed[:20]:
        print(f"  FAIL {row['group']} | {row['check']}: {row['recomputed']!r} vs {row['expected']!r}")
    print("PASS: extended paper conclusions reproduce" if not failed else "FAIL: inspect extended_comparison.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
