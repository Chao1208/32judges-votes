"""Portable, strict UID-aligned loading; no metrics, service calls or reparsing.

Adapts the original study's votes_io alignment contract to this public archive.
Human counts and gold remain user-supplied; no upstream text/counts are bundled.
MIT licensed (see LICENSE).
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:                                    # importable as a package or as a loose directory
    from . import layout as _layout
except ImportError:                     # pragma: no cover - script-style import
    import layout as _layout

LABELS = {"mnli_m": ("e", "n", "c"), "snli": ("e", "n", "c"), "alphanli": ("1", "2")}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value):
    """Hash canonical UTF-8 JSON, independent of input JSON spacing/key order."""
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def rows(path):
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{Path(path).name}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict) or "uid" not in row:
                raise ValueError(f"{Path(path).name}:{line_number}: object with uid required")
            if not isinstance(row["uid"], (str, int)) or isinstance(row["uid"], bool):
                raise ValueError("uid must be a string or integer")
            row["uid"] = str(row["uid"])
            yield row


def load_human(path, uids, labels, gold_field="majority_label"):
    """Return normalized counts, supplied gold, and content fingerprints.

    Full upstream JSONL or a sampled JSONL is accepted. Counts must total 100.
    Gold uses the upstream majority_label field by default, including its
    recorded tie resolution. It is never computed using argmax(counts).
    """
    wanted, seen, records = set(uids), set(), {}
    for row in rows(path):
        uid = row["uid"]
        if uid in seen:
            raise ValueError("duplicate human UID")
        seen.add(uid)
        if uid not in wanted:
            continue
        counter = row.get("label_counter")
        if not isinstance(counter, dict) or set(counter) - set(labels):
            raise ValueError("label_counter must use only the canonical label vocabulary")
        counts = [counter.get(label, 0) for label in labels]
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in counts):
            raise ValueError("human counts must be nonnegative integers")
        if sum(counts) != 100:
            raise ValueError("paper reference requires exactly 100 human labels per item")
        gold = str(row.get(gold_field, ""))
        if gold not in labels:
            raise ValueError(f"missing or invalid supplied gold field {gold_field!r}")
        records[uid] = (counts, gold)
    if set(records) != wanted:
        raise ValueError(f"human input missing {len(wanted - set(records))} sampled UIDs")
    canonical = [[uid, records[uid][0]] for uid in sorted(uids)]
    gold_canonical = [[uid, records[uid][1]] for uid in sorted(uids)]
    human = np.asarray([records[uid][0] for uid in uids], float) / 100.
    gold = np.asarray([labels.index(records[uid][1]) for uid in uids], int)
    return human, gold, {"human_reference_sha256": fingerprint(canonical),
                         "supplied_gold_sha256": fingerprint(gold_canonical)}


@dataclass
class Panel:
    idx: np.ndarray
    human: np.ndarray
    gold: np.ndarray
    judges: list
    uids: list
    labels: tuple
    provenance: dict


def load_panel(repo_root, dataset, human_path, failure_policy="drop-items", gold_field="majority_label"):
    """Load the complete baseline panel; silently intersecting UIDs is forbidden."""
    if dataset not in LABELS or failure_policy not in ("drop-items", "paper-retained"):
        raise ValueError("unsupported dataset or failure policy")
    root, human_path = Path(repo_root), Path(human_path)
    labels = LABELS[dataset]
    roster_path = _layout.items_file(root, dataset)
    uids = roster_path.read_text(encoding="utf-8").split()
    if not uids or len(uids) != len(set(uids)):
        raise ValueError("item roster must be nonempty and have unique UIDs")
    with _layout.judges_csv(root).open(newline="", encoding="utf-8") as handle:
        metadata_judges = [row["judge_key"] for row in csv.DictReader(handle)]
    if len(metadata_judges) != len(set(metadata_judges)):
        raise ValueError("duplicate judge key in metadata")
    files = sorted(_layout.votes_dir(root, dataset, "baseline").glob("*.jsonl"))
    judges = [path.stem for path in files]
    if len(judges) < 2 or set(judges) != set(metadata_judges):
        raise ValueError("baseline vote files must exactly match the judge metadata roster")
    uid_index, label_index = {u: i for i, u in enumerate(uids)}, {v: i for i, v in enumerate(labels)}
    idx = np.empty((len(judges), len(uids)), dtype=int)
    failed = np.zeros_like(idx, dtype=bool)
    input_hashes = {roster_path.relative_to(root).as_posix(): sha256(roster_path),
                    "meta/judges.csv": sha256(_layout.judges_csv(root))}
    for judge_number, path in enumerate(files):
        seen = set()
        for row in rows(path):
            uid = row["uid"]
            if uid not in uid_index or uid in seen:
                raise ValueError(f"{path.name}: duplicate or unexpected vote UID")
            if "variant" in row:
                raise ValueError("presentation snapshots cannot be used as baseline votes")
            label = str(row.get("label", ""))
            if label not in label_index or not isinstance(row.get("parse_fail"), bool):
                raise ValueError(f"{path.name}: invalid label or non-boolean parse_fail")
            seen.add(uid)
            idx[judge_number, uid_index[uid]] = label_index[label]
            failed[judge_number, uid_index[uid]] = row["parse_fail"]
        if seen != set(uids):
            raise ValueError(f"{path.name}: missing {len(set(uids) - seen)} sampled UIDs")
        input_hashes[path.relative_to(root).as_posix()] = sha256(path)
    human, gold, reference = load_human(human_path, uids, labels, gold_field)
    affected = failed.any(axis=0)
    keep = ~affected if failure_policy == "drop-items" else np.ones(len(uids), dtype=bool)
    if keep.sum() < 2:
        raise ValueError("fewer than two items remain after failure filtering")
    provenance = {"dataset": dataset, "labels": list(labels), "judges": judges,
                  "failure_policy": failure_policy, "gold_field": gold_field,
                  "n_original_items": len(uids), "n_retained_items": int(keep.sum()),
                  "parse_fail_cells": int(failed.sum()), "parse_fail_items": int(affected.sum()),
                  "dropped_items": int((~keep).sum()), "roster_sha256": fingerprint(sorted(uids)),
                  "human_input_file_sha256": sha256(human_path),
                  "repository_input_sha256": input_hashes, **reference}
    return Panel(idx[:, keep], human[keep], gold[keep], judges,
                 [u for u, selected in zip(uids, keep) if selected], labels, provenance)


def load_saved_calibration(directory, dataset, provenance):
    """Use the saved human-anchor curve only for its exact reference item set."""
    directory = Path(directory)
    manifest = json.loads((directory / "calibration_manifest.json").read_text(encoding="utf-8"))
    wanted = manifest["datasets"][dataset]
    curve_path = directory / "calibration_curves.csv"
    if sha256(curve_path) != manifest["calibration_curves_sha256"]:
        raise ValueError("saved calibration CSV does not match its manifest hash")
    if provenance["dropped_items"]:
        return None, "unavailable_changed_item_set"
    for key in ("roster_sha256", "human_reference_sha256"):
        if provenance[key] != wanted[key]:
            return None, "unavailable_reference_mismatch"
    with curve_path.open(newline="", encoding="utf-8") as handle:
        records = [row for row in csv.DictReader(handle)
                   if row["dataset"] == dataset and row["anchor"] == "h"]
    records.sort(key=lambda row: int(row["m"]))
    if len(records) < 2 or len({row["m"] for row in records}) != len(records):
        raise ValueError("missing or duplicate saved human calibration sizes")
    return ([int(row["m"]) for row in records], [float(row["PR_mean"]) for row in records]), "saved_curve"
