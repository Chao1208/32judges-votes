# Compatibility

This repository was renamed and its data layout changed after the paper was frozen. Nothing was
recollected, recomputed or edited: **every released file is byte-identical to v1.0**, so every
sha256 in the paper, in its supplement, and in `meta/integrity.json` still matches. Only
locations moved.

If you only want the layout the paper describes, stop here and use the frozen tag:

```bash
git clone https://github.com/Chao1208/32judges-votes
cd 32judges-votes && git checkout v1.0-paper
```

## 1. The rename

| | |
|---|---|
| old | `github.com/Chao1208/chaosnli-judge-votes` |
| new | `github.com/Chao1208/32judges-votes` |

GitHub redirects the old name permanently: web links, `git clone`, `git fetch` and `git push`
against the old URL all continue to work, as do existing forks, stars and issue links. The URL
printed in the paper therefore stays valid. The name changed because the repository is no longer
about one corpus: the panel is the constant, the datasets are not.

Deep links into a path are redirected too, but only as long as that path exists on the default
branch. The one path the paper deep-links, `/tree/main/civil_comments`, is kept as a directory
holding a pointer README for exactly this reason.

## 2. What the paper cites, and where it is now

"How Many Humans Is a Judge Panel Worth?" (EN0.3CH0.4) names these paths. Each row shows where
the same bytes live on `main` today; all of them also still exist unchanged under `v1.0-paper`.

| cited in the paper | on `main` today | note |
|---|---|---|
| `votes/<dataset>/<judge>.jsonl` | `datasets/chaosnli-<dataset>/votes/baseline/<judge>.jsonl` | `mnli_m` → `chaosnli-mnli-m`, `snli` → `chaosnli-snli`, `alphanli` → `chaosnli-alphanli` |
| `votes_swap/<dataset>/<judge>.jsonl` | `datasets/chaosnli-<dataset>/votes/swap/<judge>.jsonl` | same file names, same contents |
| `items/<dataset>_uids.txt` | `datasets/chaosnli-<dataset>/items/uids.txt` | same sampling order |
| `civil_comments/f15_public_scores.json` | `datasets/civil-comments-1000/votes/baseline/scores.json` | unchanged bytes; sha256 `040dba5c…` |
| `civil_comments/f15_public_manifest.json` | `datasets/civil-comments-1000/manifest-source.json` | the released hash record, kept verbatim |
| `/tree/main/civil_comments` | still resolves | directory kept, now holding a pointer README |
| `meta/judges.csv` | **unchanged** | still at `meta/judges.csv` |
| `meta/integrity.json` | **unchanged path**, regenerated content | now derived from the dataset manifests; the same per-file hashes, plus provenance fields |
| `meta/analysis/{reported_values,calibration_manifest}.json`, `meta/analysis/calibration_curves.csv` | **unchanged** | saved paper reference values |
| `scripts/verify.py` | **unchanged path**, rewritten | verifies against the dataset manifests; still exits non-zero on any mismatch |
| `src/analyze_panel.py`, `src/verify_paper.py`, `src/votes_io.py`, `src/formulas.py` | **unchanged** | `--dataset mnli_m` and the other v1.0 keys still work |
| `reproduce.py` | **unchanged** | still the single offline entry point, still 0 API calls |

`meta/prompts.md` is mentioned in the supplement but has never existed in this repository; exact
prompts and request code are not part of the public release. That was true at v1.0 as well.

## 3. Code frozen against the v1.0 layout

The paper's supplement ships **its own copy** of the analysis code. That copy looks for
`votes/<dataset>/…` and `items/<dataset>_uids.txt` under whatever `--repo-root` you give it, so
pointing it at a fresh `main` checkout would fail. Two ways out:

```bash
# option 1 — use the tree the paper describes
git checkout v1.0-paper

# option 2 — stay on main and recreate the v1.0 paths as symlinks (no file is copied)
python3 scripts/link_v1_layout.py            # 195 symlinks
python3 scripts/link_v1_layout.py --remove   # undo
```

The links are gitignored, so they never enter a commit. Windows needs developer mode for
symlinks; use option 1 there.

The code **in this repository** needs neither: `src/layout.py` resolves both layouts, accepts
either the dataset id (`chaosnli-snli`) or the v1.0 key (`snli`), and is covered by
`tests/test_analysis.py::InputContractTests::test_v1_layout_still_loads`.

## 4. Names that did *not* change

* **Judge keys** (`gpt56sol`, `glm52`, …) are the join keys in every vote file. Unchanged.
* **Dataset keys for the analysis CLI** (`mnli_m`, `snli`, `alphanli`) are unchanged. The new
  directory names are additional, not replacements.
* **Panel keys inside the Civil Comments score file** (`F15_10` … `F15_32`) are unchanged. The
  paper reports `F15_32`; the others are supporting records. These are historical collection
  keys retained for data alignment, exactly as the paper's protocol note states.
* **Label vocabularies**: `e` / `n` / `c`, `1` / `2`, `TOXIC` / `NON-TOXIC`. Unchanged.
* **`parse_fail` semantics**: still a flagged placeholder label, still not a model judgment.

## 5. Verifying for yourself that nothing changed

```bash
python3 scripts/verify.py        # 192 files against the dataset manifests
python3 reproduce.py --chaosnli /path/to/chaosNLI_v1.0
```

`reproduce.py` was run after the restructure: archive integrity OK, 12 unit tests OK, and every
fixed-panel value in the saved main table reproduced to within 1e-10, with 0 model/API calls.

To confirm the move changed no content, compare the per-file records with the frozen tag:

```bash
git show v1.0-paper:meta/integrity.json > /tmp/v1_integrity.json
python3 - <<'EOF'
import json
old = json.load(open("/tmp/v1_integrity.json"))["datasets"]
new = json.load(open("meta/integrity.json"))["datasets"]
bad = [(d, a, j) for d in old for a in ("baseline", "swap")
       for j, rec in old[d][a].items() if new[d][a].get(j) != rec]
print("differing file records:", len(bad))
EOF
```

This prints `0`.

## 6. Citing

Cite the repository by its new URL, and pin what you used:

* a specific release for the paper's layout: `v1.0-paper`;
* `v2.0` or later for the dataset-extensible layout;
* or a commit sha, which is layout-independent.

`CITATION.cff` carries the machine-readable form. The BibTeX entry in `README.md` was updated to
the new URL and keeps the old one as a `note`, so a reader who finds the old citation can tell
they point at the same archive.
