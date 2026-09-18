#!/usr/bin/env python3
"""Recreate the v1.0 paths as symlinks, for code frozen against the old layout.

The paper's supplement ships its own copy of the analysis code, and that copy looks for
`votes/<dataset>/<judge>.jsonl`, `votes_swap/...` and `items/<dataset>_uids.txt`. Those paths
moved in v2.0. Two ways to run such code against this repository:

  1. `git checkout v1.0-paper` — the tree the paper cites, byte for byte; or
  2. run this script once in a v2.0 checkout:

         python3 scripts/link_v1_layout.py           # create the v1.0 paths as symlinks
         python3 scripts/link_v1_layout.py --remove  # take them back out

No file is copied: each v1.0 path becomes a symlink to the file that now holds the data, so
there is exactly one copy of every byte. The links are ignored by git (see .gitignore).
Symlinks need developer mode on Windows; use option 1 there.

MIT licensed (see LICENSE-CODE).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import layout                                                        # noqa: E402

CIVIL = ("civil_comments/f15_public_scores.json",
         "datasets/civil-comments-1000/votes/baseline/scores.json")


def pairs() -> list[tuple[Path, Path]]:
    """[(v1.0 path, current path)] for everything the v1.0 layout exposed."""
    out: list[tuple[Path, Path]] = []
    for key in layout.LEGACY_TO_ID:
        out.append((ROOT / "items" / f"{key}_uids.txt", layout.items_file(ROOT, key)))
        for v1_dir, arm in (("votes", "baseline"), ("votes_swap", "swap")):
            src = layout.votes_dir(ROOT, key, arm)
            for path in sorted(src.glob("*.jsonl")):
                out.append((ROOT / v1_dir / key / path.name, path))
    out.append((ROOT / CIVIL[0], ROOT / CIVIL[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--remove", action="store_true", help="remove the links again")
    args = ap.parse_args()
    made = removed = skipped = 0
    for old, new in pairs():
        if args.remove:
            if old.is_symlink():
                old.unlink()
                removed += 1
            continue
        if old.exists() and not old.is_symlink():
            skipped += 1                      # a real v1.0 file (this is a v1.0 checkout)
            continue
        if not new.exists():
            print(f"missing target: {new.relative_to(ROOT)}", file=sys.stderr)
            return 1
        old.parent.mkdir(parents=True, exist_ok=True)
        if old.is_symlink():
            old.unlink()
        old.symlink_to(Path(os.path.relpath(new, old.parent)))
        made += 1
    if args.remove:
        for d in ("votes", "votes_swap", "items"):          # civil_comments/ holds a real README
            top = ROOT / d
            for sub in sorted(top.glob("*"), reverse=True) if top.is_dir() else []:
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
            if top.is_dir() and not any(top.iterdir()):
                top.rmdir()
        print(f"removed {removed} v1.0 symlinks")
        return 0
    print(f"created {made} v1.0 symlinks" + (f", skipped {skipped} real files" if skipped else "")
          + "\nv1.0-shaped paths now resolve: votes/<dataset>/<judge>.jsonl, "
            "votes_swap/..., items/<dataset>_uids.txt, civil_comments/f15_public_scores.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
