#!/usr/bin/env python3
"""Re-verify this release against meta/integrity.json.

Checks, for every vote file: sha256, row count, unique uid count, parse_fail count, and
(for the presentation-order arm) rows per variant. Also checks that every uid appearing in a
vote file is in the corresponding items/<dataset>_uids.txt.

    python3 scripts/verify.py            # from the repository root

Exits non-zero on the first mismatch. MIT licensed (see LICENSE-CODE).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_FIELDS = {
    "votes": {"uid", "label", "parse_fail"},
    "votes_swap": {"uid", "variant", "perm", "label", "parse_fail"},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(cond: bool, msg: str, bad: list) -> None:
    if not cond:
        bad.append(msg)


def main() -> int:
    integrity = json.loads((ROOT / "meta" / "integrity.json").read_text())
    bad: list[str] = []
    n_files = 0
    for ds, d in sorted(integrity["datasets"].items()):
        allowed = set((ROOT / "items" / f"{ds}_uids.txt").read_text().split())
        check(len(allowed) == d["items"]["n"], f"{ds}: item count", bad)
        check(sha256(ROOT / "items" / f"{ds}_uids.txt") == d["items"]["sha256"],
              f"{ds}: items sha256", bad)
        for arm, sub in (("votes", "baseline"), ("votes_swap", "swap")):
            for judge, want in sorted(d[sub].items()):
                path = ROOT / arm / ds / f"{judge}.jsonl"
                if not path.exists():
                    bad.append(f"missing file {path.relative_to(ROOT)}")
                    continue
                n_files += 1
                rows, uids, pf, per_v = 0, set(), 0, {}
                for line in open(path):
                    r = json.loads(line)
                    check(set(r) == ALLOWED_FIELDS[arm],
                          f"{path.relative_to(ROOT)}: fields {sorted(r)}", bad)
                    rows += 1
                    uids.add(r["uid"])
                    pf += bool(r["parse_fail"])
                    if "variant" in r:
                        per_v[str(r["variant"])] = per_v.get(str(r["variant"]), 0) + 1
                rel = path.relative_to(ROOT)
                check(rows == want["rows"], f"{rel}: rows {rows} != {want['rows']}", bad)
                check(len(uids) == want["uids"], f"{rel}: uids {len(uids)} != {want['uids']}", bad)
                check(pf == want["parse_fail"], f"{rel}: parse_fail {pf} != {want['parse_fail']}", bad)
                check(uids <= allowed, f"{rel}: uid outside items/{ds}_uids.txt", bad)
                check(sha256(path) == want["sha256"], f"{rel}: sha256", bad)
                if "rows_per_variant" in want:
                    check(per_v == want["rows_per_variant"], f"{rel}: rows per variant", bad)
    for name, want in sorted(integrity["meta"].items()):
        check(sha256(ROOT / "meta" / name) == want, f"meta/{name}: sha256", bad)
    check(integrity.get("raw_responses_included") is False,
          "integrity manifest must state raw_responses_included=false", bad)
    check(integrity.get("public_vote_fields") ==
          {arm: list(fields) for arm, fields in {
              "votes": ("uid", "label", "parse_fail"),
              "votes_swap": ("uid", "variant", "perm", "label", "parse_fail"),
          }.items()}, "integrity manifest public_vote_fields mismatch", bad)
    if bad:
        print(f"FAILED ({len(bad)} problems):")
        for m in bad[:40]:
            print("  -", m)
        return 1
    print(f"OK: {n_files} vote files verified against meta/integrity.json "
          f"(sha256, rows, uids, parse_fail, variants)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
