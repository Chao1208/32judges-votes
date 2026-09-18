# Changelog

All released files are byte-identical across these versions unless a row says otherwise. Data was
never recollected or recomputed; the changes are to layout, tooling and documentation.

## v2.0 — dataset-extensible layout

**Renamed** `chaosnli-judge-votes` → `32judges-votes`. GitHub redirects the old URL permanently
(web, clone, fetch, push), so citations printed before the rename keep working. The repository is
named after the panel because the panel is the invariant: 32 judges, more than one corpus, and
more corpora to come.

**Datasets are now peers.** Each one owns a directory:

```
datasets/<dataset_id>/{manifest.json, README.md, items/uids.txt, votes/<arm>/*.jsonl}
```

* `votes/<dataset>/` → `datasets/chaosnli-<dataset>-1000/votes/baseline/`
* `votes_swap/<dataset>/` → `datasets/chaosnli-<dataset>-1000/votes/swap/`
* `items/<dataset>_uids.txt` → `datasets/chaosnli-<dataset>-1000/items/uids.txt`
* `civil_comments/f15_public_scores.json` → `datasets/civil-comments-1000/votes/baseline/scores.json`
* `civil_comments/f15_public_manifest.json` → `datasets/civil-comments-1000/manifest-source.json`
* `meta/analysis/` → `reference/`

**Added**

* `datasets/index.json` — the dataset registry; records each manifest's own sha256, never a copy
  of the per-file hashes, so adding a dataset edits only its own directory plus one index entry.
* `datasets/<id>/manifest.json` — the authoritative per-dataset record (task, labels, items, arms,
  panel, per-file sha256/rows/ids/parse_fail), generated from the files themselves.
* `panel/panel-chaosnli.json`, `panel/panel-civil-comments-1000.json` — the 32-judge roster pinned
  per collection round, with the six-judge difference between rounds and why it exists. These
  replace `meta/judges.csv`, which held the ChaosNLI roster only.
* `schema/` — JSON Schema for vote records, dataset manifests and the index.
* `scripts/build_manifests.py` — regenerates every manifest and the index; `--check` fails if
  anything on disk is stale. Replaces `scripts/strip_raw_and_rebuild_integrity.py`.
* `src/layout.py` — the single place that knows where a dataset's files live.
* `CHANGELOG.md`, `CITATION.cff`.

**Changed**

* Dataset ids carry the sample size: `chaosnli-mnli-m-1000`, `chaosnli-snli-1000`,
  `chaosnli-alphanli-1000`, `civil-comments-1000`. Each released directory is one frozen sample of
  a corpus, so the size belongs in the id; the analysis CLI keys (`mnli_m` / `snli` / `alphanli`)
  are unchanged.
* `scripts/verify.py` now verifies against the per-dataset manifests, covers the Civil Comments
  score file as well (192 files), and checks the pinned panel roster.
* `scripts/join_chaosnli.py --arm` takes `baseline` / `swap` (was `votes` / `votes_swap`).
* `tests/` builds its fixture in the new layout; the judge roster now comes from the pinned panel
  file, and an extra vote file is an error.

**Removed**

* `meta/` — `judges.csv` (superseded by `panel/`), `integrity.json` (superseded by the per-dataset
  manifests) and `analysis/` (moved to `reference/`).
* `civil_comments/` — the score file moved under `datasets/`; nothing was left behind, so the
  paper's `/tree/main/civil_comments` deep links no longer resolve.
* `scripts/strip_raw_and_rebuild_integrity.py`.

No compatibility shims are shipped: the repository had no external users at the time of the
restructure, so old paths were deleted rather than aliased.

**Unchanged**: every vote file's bytes and sha256; `src/analyze_panel.py`, `src/verify_paper.py`,
`src/votes_io.py`, `src/formulas.py`; `reproduce.py`; judge keys; dataset keys `mnli_m` / `snli` /
`alphanli`; panel keys `F15_10` … `F15_32` inside the Civil Comments score file; label
vocabularies; `parse_fail` semantics.

**Verified after the restructure**: `scripts/verify.py` OK on 192 files; 12 unit tests OK;
`reproduce.py` reproduces every fixed-panel value in the saved main table to within 1e-10 with 0
model/API calls; a tampered vote file is still caught (rows, ids, roster membership and sha256 all
flag it).

## v1.0-paper — the layout the paper cites

The frozen tree behind *How Many Humans Is a Judge Panel Worth?* (EN0.3CH0.4): ChaosNLI baseline
and presentation-order votes at `votes/` and `votes_swap/`, rosters at `items/`, the Civil
Comments score-only release at `civil_comments/`. Tagged `v1.0-paper` so every path the paper
prints resolves exactly as printed, indefinitely.
