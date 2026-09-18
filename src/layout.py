"""Where a dataset's files live — the one place that knows the layout.

The repository moved to `datasets/<dataset_id>/...` in v2.0. Anything that reads votes goes
through here, so a future layout change is one edit rather than a grep. Lookups accept either
the dataset id (`chaosnli-snli`) or the v1.0 key the paper uses (`snli`), and fall back to the
v1.0 paths when a checkout still has them (`v1.0-paper`, or after `scripts/link_v1_layout.py`).

MIT licensed (see LICENSE).
"""
from __future__ import annotations

import json
from pathlib import Path

# v1.0 dataset key -> v2.0 dataset id. New datasets have no v1.0 key.
LEGACY_TO_ID = {"mnli_m": "chaosnli-mnli-m", "snli": "chaosnli-snli",
                "alphanli": "chaosnli-alphanli"}
ARM_DIR = {"baseline": "baseline", "swap": "swap",
           "votes": "baseline", "votes_swap": "swap"}       # v1.0 arm names still accepted


def dataset_id(dataset: str) -> str:
    return LEGACY_TO_ID.get(dataset, dataset)


def legacy_key(dataset: str) -> str | None:
    if dataset in LEGACY_TO_ID:
        return dataset
    for key, dsid in LEGACY_TO_ID.items():
        if dsid == dataset:
            return key
    return None


def index(root: Path) -> dict:
    return json.loads((Path(root) / "datasets" / "index.json").read_text(encoding="utf-8"))


def manifest(root: Path, dataset: str) -> dict:
    p = Path(root) / "datasets" / dataset_id(dataset) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def items_file(root: Path, dataset: str) -> Path:
    """The item roster (uid per line). v2.0 location first, then the v1.0 location."""
    root = Path(root)
    new = root / "datasets" / dataset_id(dataset) / "items" / "uids.txt"
    if new.exists():
        return new
    key = legacy_key(dataset)
    old = root / "items" / f"{key}_uids.txt" if key else None
    if old is not None and old.exists():
        return old
    return new                                   # report the expected v2.0 path in the error


def votes_dir(root: Path, dataset: str, arm: str = "baseline") -> Path:
    """The directory of per-judge jsonl files for one arm."""
    root, sub = Path(root), ARM_DIR[arm]
    new = root / "datasets" / dataset_id(dataset) / "votes" / sub
    if new.is_dir():
        return new
    key = legacy_key(dataset)
    if key:
        old = root / ("votes" if sub == "baseline" else "votes_swap") / key
        if old.is_dir():
            return old
    return new


def judges_csv(root: Path) -> Path:
    """The judge roster table. Kept at its v1.0 path, which the paper cites."""
    return Path(root) / "meta" / "judges.csv"
