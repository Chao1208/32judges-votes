#!/usr/bin/env python3
"""Keep only analysis fields in vote JSONL and rebuild integrity hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEEP = {
    "votes": ("uid", "label", "parse_fail"),
    "votes_swap": ("uid", "variant", "perm", "label", "parse_fail"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_path = ROOT / "meta/integrity.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed, removed = 0, {}
    for arm, fields in KEEP.items():
        manifest_key = "baseline" if arm == "votes" else "swap"
        for path in sorted((ROOT / arm).glob("*/*.jsonl")):
            cleaned = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                missing = [field for field in fields if field not in record]
                if missing:
                    raise ValueError(f"{path}: missing fields {missing}")
                for field in set(record) - set(fields):
                    removed[field] = removed.get(field, 0) + 1
                cleaned.append({field: record[field] for field in fields})
            content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                              for row in cleaned)
            path.write_text(content, encoding="utf-8")
            dataset, judge = path.parent.name, path.stem
            manifest["datasets"][dataset][manifest_key][judge]["sha256"] = sha256(path)
            changed += 1
    manifest["public_vote_fields"] = {arm: list(fields) for arm, fields in KEEP.items()}
    manifest["raw_responses_included"] = False
    manifest["generated_by"] = "scripts/strip_raw_and_rebuild_integrity.py"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Updated {changed} vote files; removed fields: {json.dumps(removed, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
