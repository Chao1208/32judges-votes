#!/usr/bin/env python3
"""Re-verify this release against the per-dataset manifests.

For every dataset listed in `datasets/index.json`:

  * each manifest's own sha256 matches what the index records;
  * every released file matches its manifest record — sha256, rows, unique ids,
    parse_fail count and (presentation-order arm) rows per variant;
  * no vote record carries a field outside the arm's declared `record_fields`;
  * every uid in a vote file is in that dataset's item roster;
  * the pinned panel roster in `panel/` matches the judges actually present;
  * `meta/integrity.json` (the v1.0-shaped compatibility view) agrees with the manifests,
    so the two can never drift apart silently.

    python3 scripts/verify.py              # from the repository root
    python3 scripts/verify.py --dataset chaosnli-snli

Exits non-zero if anything mismatches. MIT licensed (see LICENSE-CODE).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(cond: bool, msg: str, bad: list) -> None:
    if not cond:
        bad.append(msg)


def verify_vote_file(path: Path, want: dict, fields: set, roster: set, bad: list) -> None:
    rel = path.relative_to(ROOT)
    rows, uids, pf, per_v = 0, set(), 0, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        check(set(r) <= fields, f"{rel}: field(s) outside record_fields: {sorted(set(r) - fields)}",
              bad)
        rows += 1
        uids.add(r["uid"])
        pf += bool(r.get("parse_fail"))
        if "variant" in r:
            per_v[str(r["variant"])] = per_v.get(str(r["variant"]), 0) + 1
    check(rows == want["rows"], f"{rel}: rows {rows} != {want['rows']}", bad)
    check(len(uids) == want["uids"], f"{rel}: uids {len(uids)} != {want['uids']}", bad)
    check(pf == want["parse_fail"], f"{rel}: parse_fail {pf} != {want['parse_fail']}", bad)
    check(uids <= roster, f"{rel}: uid outside the dataset item roster", bad)
    check(sha256(path) == want["sha256"], f"{rel}: sha256", bad)
    if "rows_per_variant" in want:
        check(per_v == want["rows_per_variant"], f"{rel}: rows per variant", bad)


def verify_dataset(entry: dict, bad: list) -> int:
    """→ number of released files checked for this dataset."""
    dsid = entry["dataset_id"]
    mpath = ROOT / entry["manifest"]
    if not mpath.exists():
        bad.append(f"{dsid}: missing {entry['manifest']}")
        return 0
    check(sha256(mpath) == entry["manifest_sha256"],
          f"{entry['manifest']}: sha256 differs from datasets/index.json "
          "(run scripts/build_manifests.py)", bad)
    m = json.loads(mpath.read_text(encoding="utf-8"))
    check(m["dataset_id"] == dsid, f"{entry['manifest']}: dataset_id mismatch", bad)
    check(m["panel"]["k"] == 32, f"{dsid}: panel k must be 32 (repository invariant)", bad)

    panel = json.loads((ROOT / m["panel"]["file"]).read_text(encoding="utf-8"))
    roster_keys = {j["judge_key"] for j in panel["judges"]}
    check(len(panel["judges"]) == panel["k"] == 32,
          f"{m['panel']['file']}: must pin exactly 32 judges", bad)

    uids: set[str] = set()
    if "items" in m:
        ipath = ROOT / m["items"]["path"]
        if ipath.exists():
            uids = set(ipath.read_text(encoding="utf-8").split())
            check(len(uids) == m["items"]["n"], f"{dsid}: item count", bad)
            check(sha256(ipath) == m["items"]["sha256"], f"{m['items']['path']}: sha256", bad)
        else:
            bad.append(f"{dsid}: missing {m['items']['path']}")

    n = 0
    for arm, a in sorted(m["arms"].items()):
        fields = set(a["record_fields"])
        for name, want in sorted(a["files"].items()):
            if m.get("release_tier") == "score_only":
                path = ROOT / a["path"] / name
                if not path.exists():
                    bad.append(f"missing file {path.relative_to(ROOT)}")
                    continue
                n += 1
                check(sha256(path) == want["sha256"], f"{path.relative_to(ROOT)}: sha256", bad)
                check(path.stat().st_size == want["bytes"],
                      f"{path.relative_to(ROOT)}: bytes", bad)
                continue
            check(name in roster_keys, f"{dsid}/{arm}: {name} is not in {m['panel']['file']}", bad)
            path = ROOT / a["path"] / f"{name}.jsonl"
            if not path.exists():
                bad.append(f"missing file {path.relative_to(ROOT)}")
                continue
            n += 1
            verify_vote_file(path, want, fields, uids, bad)
        check(a["n_files"] == len(a["files"]), f"{dsid}/{arm}: n_files", bad)
        if m.get("release_tier") != "score_only":
            check(a["n_records"] == sum(r["rows"] for r in a["files"].values()),
                  f"{dsid}/{arm}: n_records", bad)
    return n


def verify_derived_integrity(bad: list) -> None:
    """meta/integrity.json is generated from the manifests; prove it still agrees with them."""
    path = ROOT / "meta" / "integrity.json"
    if not path.exists():
        bad.append("missing meta/integrity.json (the v1.0 compatibility view)")
        return
    view = json.loads(path.read_text(encoding="utf-8"))
    check(view.get("raw_responses_included") is False,
          "meta/integrity.json must state raw_responses_included=false", bad)
    check(sha256(ROOT / "meta" / "judges.csv") == view["meta"]["judges.csv"],
          "meta/judges.csv: sha256 differs from meta/integrity.json", bad)
    index = json.loads((ROOT / "datasets" / "index.json").read_text(encoding="utf-8"))
    by_legacy = {e["legacy_key"]: e for e in index["datasets"] if e.get("legacy_key")}
    check(set(view["datasets"]) == set(by_legacy),
          f"meta/integrity.json covers {sorted(view['datasets'])}, index has "
          f"{sorted(by_legacy)}", bad)
    for key, node in view["datasets"].items():
        if key not in by_legacy:
            continue
        m = json.loads((ROOT / by_legacy[key]["manifest"]).read_text(encoding="utf-8"))
        check(node["items"] == {"n": m["items"]["n"], "sha256": m["items"]["sha256"]},
              f"integrity view {key}: items record differs from the manifest", bad)
        check(node["labels"] == m["task"]["labels"],
              f"integrity view {key}: labels differ from the manifest", bad)
        for arm in ("baseline", "swap"):
            check(node.get(arm) == m["arms"][arm]["files"],
                  f"integrity view {key}/{arm}: per-file records differ from the manifest "
                  "(run scripts/build_manifests.py)", bad)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", action="append", metavar="DATASET_ID",
                    help="verify only these datasets (default: every dataset in the index)")
    args = ap.parse_args()
    index = json.loads((ROOT / "datasets" / "index.json").read_text(encoding="utf-8"))
    wanted = [e for e in index["datasets"]
              if not args.dataset or e["dataset_id"] in args.dataset]
    if args.dataset and len(wanted) != len(args.dataset):
        print(f"unknown dataset id; the index has "
              f"{[e['dataset_id'] for e in index['datasets']]}", file=sys.stderr)
        return 2
    bad: list[str] = []
    total = 0
    for entry in wanted:
        n = verify_dataset(entry, bad)
        total += n
        print(f"  {entry['dataset_id']:22} {n:>4} files  k={entry['panel_k']}  "
              f"items={entry['n_items']:,}  arms={'+'.join(entry['arms'])}")
    if not args.dataset:
        verify_derived_integrity(bad)
    if bad:
        print(f"FAILED ({len(bad)} problems):")
        for m in bad[:40]:
            print("  -", m)
        return 1
    print(f"OK: {total} released files verified against {len(wanted)} dataset manifest(s) "
          "(sha256, rows, ids, parse_fail, variants, panel roster, integrity view)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
