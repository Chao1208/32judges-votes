#!/usr/bin/env python3
"""Join the judge votes with the ChaosNLI human label distributions.

ChaosNLI is NOT redistributed here (it is CC BY-NC 4.0). Download it first:

    git clone https://github.com/easonnie/chaos_nli
    # or fetch the release archive it links to, then point --chaosnli at chaosNLI_v1.0/

Then, from the repository root:

    python3 scripts/join_chaosnli.py --chaosnli /path/to/chaosNLI_v1.0 --dataset mnli_m

For every sampled item it prints one JSON line with the item's 100-annotator label counts and
the panel's votes, which is the input shape our analysis starts from:

    {"uid": ..., "label_counter": {"e": 4, "n": 67, "c": 29},
     "votes": {"gpt56sol": "n", ...}, "parse_fail": ["sonnet46"]}

Cells listed under "parse_fail" carry a deterministic placeholder label, not a model judgment
(drop them). The public release contains final labels, not raw responses or reasoning traces.
MIT licensed (see LICENSE-CODE).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import layout                                                        # noqa: E402

CHAOS_FILE = {"mnli_m": "chaosNLI_mnli_m.jsonl", "snli": "chaosNLI_snli.jsonl",
              "alphanli": "chaosNLI_alphanli.jsonl"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chaosnli", required=True, type=Path, help="ChaosNLI v1.0 directory")
    ap.add_argument("--dataset", required=True, choices=sorted(CHAOS_FILE))
    ap.add_argument("--arm", default="baseline", choices=["baseline", "swap"])
    ap.add_argument("--variant", type=int, default=None,
                    help="presentation-order arm only: keep just this variant")
    args = ap.parse_args()

    uids = layout.items_file(ROOT, args.dataset).read_text().split()
    keep = set(uids)
    human = {}
    with open(args.chaosnli / CHAOS_FILE[args.dataset]) as f:
        for line in f:
            r = json.loads(line)
            if r["uid"] in keep:
                human[r["uid"]] = r["label_counter"]
    missing = keep - set(human)
    assert not missing, f"{len(missing)} sampled uids not found in ChaosNLI: {sorted(missing)[:3]}"

    votes: dict[str, dict[str, str]] = {u: {} for u in uids}
    failed: dict[str, list[str]] = {u: [] for u in uids}
    for path in sorted(layout.votes_dir(ROOT, args.dataset, args.arm).glob("*.jsonl")):
        judge = path.stem
        for line in open(path):
            r = json.loads(line)
            if args.variant is not None and r.get("variant") != args.variant:
                continue
            votes[r["uid"]][judge] = r["label"]
            if r["parse_fail"]:
                failed[r["uid"]].append(judge)

    for u in uids:
        if not votes[u]:
            continue  # the swap arm covers a 500-item subset
        print(json.dumps({"uid": u, "label_counter": human[u], "votes": votes[u],
                          "parse_fail": failed[u]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
