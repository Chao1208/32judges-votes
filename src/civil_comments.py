"""CC-1000 score-layer loading and the fixed 32-judge readout, Section 4.9 (MIT).

The score layer carries the human toxicity counts, so no external join is needed.
Items are ordered by id_sha256 and judges by key. The empirical reference is
h_i = (1 - p_i, p_i) with p_i = n_toxic / n_annotators; gold is argmax(h_i), with
the 10 items at p_i = 0.5 going to NON-TOXIC. n_eff excludes those tied items.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

if __package__:
    from .formulas import panel_metrics, solve_human_equivalent
    from .votes_io import sha256
else:
    from formulas import panel_metrics, solve_human_equivalent
    from votes_io import sha256

DATASET = "civil-comments-1000"
LABELS = ("NON-TOXIC", "TOXIC")
PANEL_KEY = "F15_32"


def load(repo_root):
    """Return (idx, human, gold, judges, n_annotators, item_ids) for the 32-judge panel."""
    root = Path(repo_root)
    path = root / "datasets" / DATASET / "votes" / "baseline" / "scores.json"
    manifest = json.loads((root / "datasets" / DATASET / "manifest.json").read_text(encoding="utf-8"))
    if sha256(path) != manifest["arms"]["baseline"]["files"]["scores.json"]["sha256"]:
        raise ValueError("scores.json does not match its manifest hash")
    doc = json.loads(path.read_text(encoding="utf-8"))
    judges = sorted(doc["panels"][PANEL_KEY]["judges"])
    items = sorted(doc["items"], key=lambda item: item["id_sha256"])
    idx = np.empty((len(judges), len(items)), int)
    for i, item in enumerate(items):
        labels = item["judge_labels"]
        missing = [j for j in judges if j not in labels]
        if missing:
            raise ValueError(f"item {item['id_sha256'][:12]} lacks labels from {missing}")
        idx[:, i] = [LABELS.index(labels[j]) for j in judges]
    n_toxic = np.asarray([item["n_toxic"] for item in items], float)
    n_annotators = np.asarray([item["n_annotators"] for item in items], float)
    p = n_toxic / n_annotators
    human = np.column_stack([1. - p, p])
    gold = (p > 0.5).astype(int)
    return idx, human, gold, judges, n_annotators, [item["id_sha256"] for item in items]


def load_curve(reference_dir, expected_sha256):
    path = Path(reference_dir) / "calibration_curve_civil_comments.csv"
    if sha256(path) != expected_sha256:
        raise ValueError("CC-1000 calibration CSV does not match its recorded hash")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = sorted(csv.DictReader(handle), key=lambda row: int(row["m"]))
    return [int(row["m"]) for row in rows], [float(row["PR_mean"]) for row in rows]


def fixed_panel(repo_root, curve):
    """Table 6 readings plus the finite-annotation sensitivity of the supplementary protocol."""
    idx, human, gold, judges, n_annotators, _ = load(repo_root)
    metrics = panel_metrics(idx, human, gold)
    untied = human[:, 1] != 0.5
    binary = panel_metrics(idx[:, untied], human[untied], gold[untied])
    nu_h, status = solve_human_equivalent(*curve, metrics["PR"])
    b = float(np.mean((1. - np.sum(human ** 2, axis=1)) / (n_annotators - 1.)))
    return {"k": len(judges), "n_items": idx.shape[1], "PR": metrics["PR"],
            "nu_H": nu_h, "nu_H_status": status,
            "nu_MSE": metrics["nu_MSE"], "J": metrics["J"], "E": metrics["E"],
            "annotation_noise_b": b,
            "nu_MSE_finite_annotation": (metrics["J"] + b) / (metrics["E"] - b),
            "n_eff": binary["n_eff"], "n_eff_items": int(untied.sum()),
            "n_eff_tied_items_excluded": int((~untied).sum()),
            "gamma_co_all": metrics["gamma_co_all"],
            "human_votes_total": int(n_annotators.sum()),
            "annotators_median": float(np.median(n_annotators)),
            "annotators_min": int(n_annotators.min()), "annotators_max": int(n_annotators.max())}
