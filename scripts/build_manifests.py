#!/usr/bin/env python3
"""Rebuild every dataset manifest and the dataset index.

Run from the repository root after adding or changing a dataset:

    python3 scripts/build_manifests.py            # rewrite every generated file
    python3 scripts/build_manifests.py --check    # fail instead of writing (CI use)

Single source of truth: file records are computed from the files themselves. Each dataset
owns `datasets/<id>/manifest.json`; `datasets/index.json` records only each manifest's own
sha256, never a copy of the per-file hashes. Nothing else stores a per-file hash.

Adding a dataset means: create `datasets/<id>/`, describe it in `DATASETS[<id>]`, run this.

MIT licensed (see LICENSE-CODE).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "schema/dataset.manifest.schema.json"

CHAOSNLI_LICENSE = {"votes": "CC BY 4.0", "items": "CC BY 4.0",
                    "human_reference": "CC BY-NC 4.0 (ChaosNLI, not redistributed here)"}

# One entry per dataset. Everything that cannot be computed from the files lives here.
DATASETS: dict[str, dict] = {
    "chaosnli-mnli-m": {
        "legacy_key": "mnli_m", "family": "chaosnli",
        "title": "ChaosNLI MNLI-matched — 32 judges, baseline and presentation-order arms",
        "swap_panel_drop": {"dsv32": "channel died; only variant 0 was ever collected "
                                     "(500 rows), so the arm's panel analysis uses 31 judges"},
        "task": {"type": "nli-3way", "labels": ["e", "n", "c"],
                 "label_meaning": {"e": "entailment", "n": "neutral", "c": "contradiction"}},
        "arms": {"baseline": "votes/baseline", "swap": "votes/swap"},
        "panel": "panel/panel-chaosnli.json",
        "human_reference": {"source": "ChaosNLI", "redistributed": False,
                            "join_key": "uid", "annotators_per_item": 100,
                            "how_to_join": "scripts/join_chaosnli.py"},
        "license": CHAOSNLI_LICENSE,
    },
    "chaosnli-snli": {        "legacy_key": "snli", "family": "chaosnli",
        "title": "ChaosNLI SNLI — 32 judges, baseline and presentation-order arms",
        "swap_panel_drop": {"dsv32": "complete here, but excluded so that one panel is used "
                                     "across datasets (same rule as the baseline arm)"},
        "task": {"type": "nli-3way", "labels": ["e", "n", "c"],
                 "label_meaning": {"e": "entailment", "n": "neutral", "c": "contradiction"}},
        "arms": {"baseline": "votes/baseline", "swap": "votes/swap"},
        "panel": "panel/panel-chaosnli.json",
        "human_reference": {"source": "ChaosNLI", "redistributed": False,
                            "join_key": "uid", "annotators_per_item": 100,
                            "how_to_join": "scripts/join_chaosnli.py"},
        "license": CHAOSNLI_LICENSE,
    },
    "chaosnli-alphanli": {
        "legacy_key": "alphanli", "family": "chaosnli",
        "title": "ChaosNLI alphaNLI — 32 judges, baseline and presentation-order arms",
        "swap_panel_drop": {
            "dsv32": "channel died; no presentation-order file at all",
            "glm52": "dropped from the baseline panel for this dataset; variant 1 never collected",
            "kimik3": "channel died mid-collection; variant 1 is missing 26 cells and cannot be "
                      "re-collected — keeping it would silently shrink the uid intersection by 26 items"},
        "task": {"type": "abductive-2way", "labels": ["1", "2"],
                 "label_meaning": {"1": "hypothesis 1", "2": "hypothesis 2"}},
        "arms": {"baseline": "votes/baseline", "swap": "votes/swap"},
        "panel": "panel/panel-chaosnli.json",
        "human_reference": {"source": "ChaosNLI", "redistributed": False,
                            "join_key": "uid", "annotators_per_item": 100,
                            "how_to_join": "scripts/join_chaosnli.py"},
        "license": CHAOSNLI_LICENSE,
    },
    "civil-comments-1000": {
        "legacy_key": None, "family": "civil-comments",
        "title": "Civil Comments 1,000-item toxicity sample — 32 judges, score-only release",
        "task": {"type": "binary-toxicity", "labels": ["NON-TOXIC", "TOXIC"]},
        "arms": {"baseline": "votes/baseline"},
        "panel": "panel/panel-civil-comments-1000.json",
        "human_reference": {"source": "Civil Comments (Jigsaw), CC0", "redistributed": False,
                            "join_key": "id_sha256 (irreversible)",
                            "annotators_per_item": "50-2196 real annotators, carried in the file",
                            "how_to_join": "not needed: fractions and counts ship inside scores.json"},
        "license": {"votes": "CC BY 4.0",
                    "human_reference": "CC0 (source corpus, not redistributed here)"},
        "release_tier": "score_only",
    },
}

ARM_FIELDS = {"baseline": ["uid", "label", "parse_fail"],
              "swap": ["uid", "variant", "perm", "label", "parse_fail"]}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def vote_file_record(path: Path, arm: str) -> dict:
    """Per-file record computed from the file: rows, unique uids, parse_fail, sha256."""
    uids, rows, fails, per_variant = set(), 0, 0, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        extra = set(r) - set(ARM_FIELDS[arm])
        if extra:
            raise ValueError(f"{path}: unexpected field(s) {sorted(extra)} for arm {arm}")
        rows += 1
        uids.add(r["uid"])
        fails += bool(r.get("parse_fail"))
        if arm == "swap":
            per_variant[str(r["variant"])] = per_variant.get(str(r["variant"]), 0) + 1
    rec = {"rows": rows, "uids": len(uids), "parse_fail": fails, "sha256": sha256(path)}
    if arm == "swap":
        rec["rows_per_variant"] = dict(sorted(per_variant.items()))
    return rec


def panel_keys(spec: dict) -> list[str]:
    """The roster pinned in panel/, used to catch a panel file that drifted from the data."""
    doc = json.loads((ROOT / spec["panel"]).read_text(encoding="utf-8"))
    keys = [j["judge_key"] for j in doc["judges"]]
    if len(keys) != len(set(keys)) or len(keys) != doc["k"]:
        raise ValueError(f"{spec['panel']}: duplicate or miscounted judge_key")
    return keys


def chaosnli_manifest(dsid: str, spec: dict) -> dict:
    """A ChaosNLI dataset: uid roster + one jsonl per judge per arm."""
    d = ROOT / "datasets" / dsid
    roster = d / "items" / "uids.txt"
    uids = roster.read_text(encoding="utf-8").split()
    if len(uids) != len(set(uids)):
        raise ValueError(f"{roster}: duplicate uid")
    arms = {}
    roster_keys = set(panel_keys(spec))
    for arm, rel in spec["arms"].items():
        files = sorted((d / rel).glob("*.jsonl"))
        recs = {p.stem: vote_file_record(p, arm) for p in files}
        if arm == "baseline" and set(recs) != roster_keys:
            raise ValueError(f"{dsid}/baseline: vote files {sorted(set(recs) ^ roster_keys)} "
                             f"do not match the roster in {spec['panel']}")
        if not set(recs) <= roster_keys:
            raise ValueError(f"{dsid}/{arm}: {sorted(set(recs) - roster_keys)} not in the roster")
        for judge, rec in recs.items():
            outside = arm == "baseline" and rec["uids"] != len(uids)
            if outside:
                raise ValueError(f"{dsid}/{arm}/{judge}: covers {rec['uids']} of {len(uids)} uids")
        arms[arm] = {"path": f"datasets/{dsid}/{rel}", "record_fields": ARM_FIELDS[arm],
                     "n_files": len(recs),
                     "n_records": sum(r["rows"] for r in recs.values()),
                     "parse_fail_cells": sum(r["parse_fail"] for r in recs.values()),
                     "files": dict(sorted(recs.items()))}
        drop = spec.get("swap_panel_drop") if arm == "swap" else None
        if drop:
            arms[arm]["panel_excluded_from_arm_analysis"] = drop
    return {"schema": SCHEMA, "dataset_id": dsid, "family": spec["family"],
            "title": spec["title"], "legacy_key": spec["legacy_key"],
            "task": spec["task"], "n_items": len(uids),
            "panel": {"file": spec["panel"], "k": 32},
            "human_reference": spec["human_reference"],
            "items": {"path": f"datasets/{dsid}/items/uids.txt", "n": len(uids),
                      "sha256": sha256(roster), "order": "sampling order"},
            "arms": arms, "license": spec["license"]}


def score_only_manifest(dsid: str, spec: dict) -> dict:
    """A score-only dataset: one JSON carrying items, human fractions and final labels."""
    d = ROOT / "datasets" / dsid
    scores = d / "votes" / "baseline" / "scores.json"
    doc = json.loads(scores.read_text(encoding="utf-8"))
    src = json.loads((d / "manifest-source.json").read_text(encoding="utf-8"))
    if src["sha256"] != sha256(scores):
        raise ValueError(f"{dsid}: scores.json sha256 differs from the released record "
                         "— the restructure must not alter file contents")
    panels = {k: v["k"] for k, v in doc["panels"].items()}
    paper_key = "F15_32"
    roster = panel_keys(spec)
    in_file = doc["panels"][paper_key]["judges"]
    if sorted(in_file) != sorted(roster):
        raise ValueError(f"{dsid}: {spec['panel']} roster differs from the {paper_key} panel "
                         f"inside scores.json ({sorted(set(in_file) ^ set(roster))})")
    return {"schema": SCHEMA, "dataset_id": dsid, "family": spec["family"],
            "title": spec["title"], "legacy_key": spec["legacy_key"],
            "task": spec["task"], "n_items": doc["n_items"],
            "release_tier": spec["release_tier"],
            "panel": {"file": spec["panel"], "k": doc["n_judges"]},
            "human_reference": spec["human_reference"],
            "arms": {"baseline": {
                "path": f"datasets/{dsid}/votes/baseline",
                "record_fields": ["id_sha256", "stratum", "toxicity", "n_annotators",
                                  "n_toxic", "judge_labels", "judge_status"],
                "n_files": 1, "n_records": doc["n_items"] * doc["n_judges"],
                "files": {"scores.json": {"items": doc["n_items"],
                                          "judges": doc["n_judges"],
                                          "bytes": scores.stat().st_size,
                                          "sha256": src["sha256"]}}}},
            "panel_keys_in_file": panels,
            "paper_panel_key": paper_key,
            "excludes": doc["excludes"],
            "provenance": {k: v for k, v in src.items() if k != "file"},
            "license": spec["license"]}


def build() -> dict:
    manifests = {}
    for dsid, spec in DATASETS.items():
        manifests[dsid] = (score_only_manifest(dsid, spec) if spec.get("release_tier")
                           else chaosnli_manifest(dsid, spec))
    return manifests


def index_of(manifests: dict, written: dict) -> dict:
    return {"schema": "schema/index.schema.json",
            "repository": "32judges-votes",
            "what": "Per-item votes from a fixed 32-judge LLM panel, one directory per dataset.",
            "panel_invariant": "Every dataset in this repository is judged by 32 judges. "
                               "The roster of a given collection round is pinned in panel/.",
            "panel_files": sorted({m["panel"]["file"] for m in manifests.values()}),
            "datasets": [{"dataset_id": dsid, "family": m["family"], "title": m["title"],
                          "task_type": m["task"]["type"], "n_items": m["n_items"],
                          "panel_k": m["panel"]["k"], "arms": sorted(m["arms"]),
                          "release_tier": m.get("release_tier", "per_item_votes"),
                          "legacy_key": m["legacy_key"],
                          "manifest": f"datasets/{dsid}/manifest.json",
                          "manifest_sha256": written[dsid]}
                         for dsid, m in manifests.items()],
            "generated_by": "scripts/build_manifests.py",
            "note": "This index records each manifest's own sha256 only. Per-file hashes live "
                    "in the dataset manifests, so adding a dataset never edits another one."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if any generated file differs from what is on disk")
    args = ap.parse_args()
    manifests = build()
    targets: dict[Path, str] = {}
    written = {}
    for dsid, m in manifests.items():
        p = ROOT / "datasets" / dsid / "manifest.json"
        text = jdump(m)
        targets[p] = text
        written[dsid] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    targets[ROOT / "datasets" / "index.json"] = jdump(index_of(manifests, written))

    stale = [p for p, text in targets.items()
             if not p.exists() or p.read_text(encoding="utf-8") != text]
    if args.check:
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}", file=sys.stderr)
        print(f"{'FAIL' if stale else 'OK'}: {len(targets)} generated files, "
              f"{len(stale)} stale")
        return 1 if stale else 0
    for p, text in targets.items():
        p.write_text(text, encoding="utf-8")
    for dsid, m in manifests.items():
        arms = ", ".join(f"{a} {v['n_records']:,} records" for a, v in m["arms"].items())
        print(f"  {dsid:22} k={m['panel']['k']} items={m['n_items']:,}  {arms}")
    print(f"wrote {len(targets)} files ({len(stale)} changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
