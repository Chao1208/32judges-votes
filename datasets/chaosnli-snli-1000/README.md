# `chaosnli-snli-1000`

1,000 items from ChaosNLI's SNLI set, judged by the 32-judge panel pinned in
[`../../panel/panel-chaosnli.json`](../../panel/panel-chaosnli.json).

* **Task**: 3-way NLI. Labels `e` (entailment), `n` (neutral), `c` (contradiction).
* **Arms**: `votes/baseline/` (every judge, every item) and `votes/swap/` (presentation-order
  arm, a 500-item subset re-asked with the options in a different order, `variant` 0/1/2).
* **Items**: `items/uids.txt`, in sampling order. Sampled from the full ChaosNLI set, stratified
  into equal thirds by the entropy of the 100-annotator label distribution, seed 42.
* **Counts and hashes**: [`manifest.json`](manifest.json) — rows, unique uids, `parse_fail` cells
  and sha256 per file. Verify with `python3 scripts/verify.py --dataset chaosnli-snli-1000`.

**Human label distributions are not redistributed here** (ChaosNLI is CC BY-NC 4.0). Join by
`uid`:

```bash
python3 scripts/join_chaosnli.py --chaosnli /path/to/chaosNLI_v1.0 --dataset snli
```

The analysis CLI still uses the v1.0 dataset key `snli`.

**Read before use**: `parse_fail` rows carry a placeholder label, not a judgment; the
presentation-order arm is incomplete, and `manifest.json` records which judges are excluded from
that arm's panel analysis and why. The repository-level caveats in
[`../../README.md`](../../README.md) apply.
