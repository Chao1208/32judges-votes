"""Where a dataset's files live — the one place that knows the layout.

Everything that reads votes goes through here, so a future layout change is one edit rather
than a grep. Lookups accept either the dataset id (`chaosnli-snli`) or the ChaosNLI subset key
the analysis CLI uses (`snli`).

MIT licensed (see LICENSE).
"""
from __future__ import annotations

import json
from pathlib import Path

# ChaosNLI subset key (used by the analysis CLI and the saved reference values) -> dataset id.
CHAOSNLI_KEY_TO_ID = {"mnli_m": "chaosnli-mnli-m", "snli": "chaosnli-snli",
                      "alphanli": "chaosnli-alphanli"}
ARM_DIR = {"baseline": "baseline", "swap": "swap"}


def dataset_id(dataset: str) -> str:
    return CHAOSNLI_KEY_TO_ID.get(dataset, dataset)


def chaosnli_key(dataset: str) -> str | None:
    """The CLI key for a dataset id, or None for datasets that are not ChaosNLI subsets."""
    if dataset in CHAOSNLI_KEY_TO_ID:
        return dataset
    for key, dsid in CHAOSNLI_KEY_TO_ID.items():
        if dsid == dataset:
            return key
    return None


def index(root: Path) -> dict:
    return json.loads((Path(root) / "datasets" / "index.json").read_text(encoding="utf-8"))


def manifest(root: Path, dataset: str) -> dict:
    p = Path(root) / "datasets" / dataset_id(dataset) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def dataset_dir(root: Path, dataset: str) -> Path:
    return Path(root) / "datasets" / dataset_id(dataset)


def items_file(root: Path, dataset: str) -> Path:
    """The item roster: one item id per line, in sampling order."""
    return dataset_dir(root, dataset) / "items" / "uids.txt"


def votes_dir(root: Path, dataset: str, arm: str = "baseline") -> Path:
    """The directory of per-judge jsonl files for one arm."""
    return dataset_dir(root, dataset) / "votes" / ARM_DIR[arm]


def panel_file(root: Path, dataset: str) -> Path:
    """The pinned 32-judge roster that produced this dataset."""
    return Path(root) / manifest(root, dataset)["panel"]["file"]


def panel_judges(root: Path, dataset: str) -> list[str]:
    """Judge keys of that roster, in file order."""
    doc = json.loads(panel_file(root, dataset).read_text(encoding="utf-8"))
    return [j["judge_key"] for j in doc["judges"]]
