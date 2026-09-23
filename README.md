# 32judges-votes — per-item votes from a fixed 32-judge LLM panel

The same **32 LLM judges**, released per item, on more than one corpus. 32 judges is the
constant here; the datasets are not, and more will be added. Today:

| dataset | task | items | arms | panel | release |
|---|---|---|---|---|---|
| [`chaosnli-mnli-m-1000`](datasets/chaosnli-mnli-m-1000) | 3-way NLI (`e`/`n`/`c`) | 1,000 | baseline + presentation-order | 32 | per-item votes |
| [`chaosnli-snli-1000`](datasets/chaosnli-snli-1000) | 3-way NLI (`e`/`n`/`c`) | 1,000 | baseline + presentation-order | 32 | per-item votes |
| [`chaosnli-alphanli-1000`](datasets/chaosnli-alphanli-1000) | abductive 2-way (`1`/`2`) | 1,000 | baseline + presentation-order | 32 | per-item votes |
| [`civil-comments-1000`](datasets/civil-comments-1000) | binary toxicity (`TOXIC`/`NON-TOXIC`) | 1,000 | baseline | 32 | score-only |

221,474 judged ChaosNLI cells plus 32,000 Civil Comments cells. [`datasets/index.json`](datasets/index.json)
is the machine-readable registry; each dataset's own `manifest.json` holds its per-file hashes.

This is the data release behind *How Many Humans Is a Judge Panel Worth?* (see
[Citing](#citing)). It exists because work on judge-panel correlation currently re-collects
per-item votes from scratch every time: the votes are cheap to consume and expensive to produce.
Reuse them.

## Layout

```
datasets/index.json                          registry: one line per dataset + its manifest hash
datasets/<dataset_id>/manifest.json          items, arms, panel, per-file sha256 (authoritative)
datasets/<dataset_id>/README.md              what the dataset is and what it is not
datasets/<dataset_id>/items/uids.txt         item roster, in sampling order
datasets/<dataset_id>/votes/baseline/*.jsonl one file per judge, one JSON object per line
datasets/<dataset_id>/votes/swap/*.jsonl     presentation-order arm, where collected
panel/panel-<round>.json                     the 32-judge roster pinned per collection round
                                             (judge key -> model id, vendor family)
reference/                                   saved calibration curves and paper reference values
schema/                                      JSON Schema for vote records, manifests, the index
scripts/verify.py                            re-check every released file against the manifests
scripts/build_manifests.py                   regenerate the manifests and the index
scripts/join_chaosnli.py                     join ChaosNLI's human counts onto the votes
src/                                         portable analysis code (fixed panel, asymptote,
                                             calibration, CC-1000, panel selection)
reproduce.py                                 integrity -> tests -> paper-table -> extended checks
ANALYSIS.md / REPRODUCE.md                   analysis scope; single-entry reproduction guide
CHANGELOG.md                                 what changed between releases
```

A dataset id names the corpus **and the sample size** (`chaosnli-snli-1000`,
`civil-comments-1000`), because a corpus can be sampled more than once and each sample is judged
by its own panel round. Adding a dataset means adding one directory under `datasets/` and one entry
in `scripts/build_manifests.py`, then running it. No other dataset's files are touched.

## Record format

Per-item vote datasets ship one JSONL per judge. Baseline arm, one object per line:

| field | meaning |
|---|---|
| `uid` | item id in the source dataset — the join key |
| `label` | the judge's final label, from the dataset's `task.labels` |
| `parse_fail` | `true` if no legal label could be read from the reply — **see the caveat below** |

The presentation-order arm adds `variant` (0 = baseline option order) and `perm` (the permutation
actually presented), one line per (item, variant). The contract is machine-readable in
[`schema/votes.record.schema.json`](schema/votes.record.schema.json); `scripts/verify.py` rejects
any field outside it.

Score-only datasets (`release_tier: score_only`) ship a single JSON instead: per item a hashed
identifier, the human reference values, and every judge's final label. Their fields are listed in
the dataset manifest under `arms.baseline.record_fields`.

Raw model responses, reasoning traces, prompts, and internal collection bookkeeping are **not**
included anywhere. A released row is an archived judgment record, not evidence of a fresh
service call.

## The panel

32 judges, pinned per collection round in `panel/`:

| round | file | families |
|---|---|---|
| ChaosNLI | [`panel/panel-chaosnli.json`](panel/panel-chaosnli.json) | OpenAI 5, Alibaba 4, Google 4, Moonshot 4, Zhipu 4, Anthropic 3, DeepSeek 3, ByteDance 2, xAI 2, MiniMax 1 |
| Civil Comments | [`panel/panel-civil-comments-1000.json`](panel/panel-civil-comments-1000.json) | OpenAI 7, Zhipu 5, Alibaba 4, Anthropic 4, DeepSeek 3, Moonshot 3, ByteDance 2, xAI 2, Google 1, MiniMax 1 |

**Same size, not the same roster.** Between the two rounds, provider model aliases drifted: five
endpoints had disappeared (404 / no channel on both routes) and three Google models were
unavailable on both. Replacements came from a candidate order fixed before probing. Six judges
differ; the family deltas are recorded in the Civil Comments panel file. Consequence for readers:
cross-dataset differences in this repository are **not** a controlled comparison of corpora.

Model ids are the exact requested model strings; backend identity and version are not
independently authenticated. `earlier_generation` in the ChaosNLI roster is retained as recorded
metadata, not as evidence of backend chronology or capability. Collection used a single user
message, no system message, temperature 0, and a constrained answer format.

## Human reference values

* **ChaosNLI** is *not* redistributed here (CC BY-NC 4.0). Clone it and join by `uid`:

  ```bash
  git clone https://github.com/easonnie/chaos_nli
  python3 scripts/join_chaosnli.py --chaosnli path/to/chaosNLI_v1.0 --dataset mnli_m | head -1
  ```

  `--arm swap` and `--variant N` select the presentation-order arm.

* **Civil Comments** human values (toxicity fraction and annotator count per item) ship inside
  the score file, so no join is needed. The source corpus and comment text are not
  redistributed; item ids are irreversible hashes.

## Integrity

```bash
python3 scripts/verify.py                          # all datasets
python3 scripts/verify.py --dataset chaosnli-snli-1000   # one dataset
```

For every dataset this checks each manifest against the hash recorded in `datasets/index.json`,
then every released file against its manifest record — sha256, rows, unique ids, `parse_fail`
count, rows per variant — that no vote record carries an undeclared field, that every uid is in
the item roster, and that the judges present match the pinned 32-judge roster. 192 files are
covered today. `scripts/build_manifests.py --check` fails if any manifest is stale.

## Reproducing the paper

```bash
python3 reproduce.py --chaosnli /path/to/chaosNLI_v1.0
```

Four steps, offline, **0 model/API calls**: archive integrity, analysis unit tests, the saved
main-table comparison, then the fixed-pool asymptote, the analytic calibration, the CC-1000 panel
and the full panel-selection experiment (about 2.5 minutes). See [REPRODUCE.md](REPRODUCE.md) for the step-by-step guide and
[ANALYSIS.md](ANALYSIS.md) for what the portable CLI does and does not cover. The CLI takes the
v1.0 dataset keys (`mnli_m`, `snli`, `alphanli`), which still work.

## Caveats worth reading before use

**`parse_fail` labels are placeholders, not judgments.** When a reply contained no legal label (or
the call kept failing), the pipeline still emitted a `label`, computed as a deterministic hash of
`uid:judge_key`. The analysis CLI drops every item touched by a placeholder by default; the
paper's historical primary table retained them, so exact reproduction needs
`--failure-policy paper-retained`. There are 6 such cells in the ChaosNLI baseline arm
(1 / 0 / 5 for MNLI-m / SNLI / alphaNLI) and 27 in the presentation-order arm (11 / 8 / 8).

**Only final scores are released.** No raw model responses or reasoning traces, so there is no
public text field to reparse.

**Temperature 0 is not determinism.** Re-asking the same question at temperature 0 does not
always return the same word. This archive does not separately identify a same-prompt
repeated-call noise floor. Order differences can include snapshot, cache and service variation;
they are not an isolated causal measurement of answer-option order alone.

**The presentation-order arm is not complete**, and the gaps are why analyses of that arm use a
31 / 31 / 29 judge panel rather than 32. Each dataset manifest lists the excluded judges and the
reason under `arms.swap.panel_excluded_from_arm_analysis`. The partial files are shipped as they
are, so a study that wants a different panel can see what was there.

**Nothing here is a benchmark ranking.** Agreement with the human majority varies by dataset and
a judge's rank moves across datasets. These are votes, not a leaderboard.

**Sampling is not representative of a corpus.** Each dataset's README states its sampling rule;
the Civil Comments sample in particular is deliberately skewed toward contested items, so no
prevalence claim can be read off it.

## Licensing

Data (`datasets/*/votes/`, `datasets/*/items/`, `panel/`, `reference/`): **CC BY 4.0** — see `LICENSE`.
Existing collection scripts (`scripts/`): **MIT** — see `LICENSE-CODE`. Analysis code (`src/`,
`tests/`) and documentation: **MIT** — see `src/LICENSE`.

Source corpora are not redistributed and keep their own terms: ChaosNLI is **CC BY-NC 4.0** (a
join of our votes with ChaosNLI inherits those terms); Civil Comments is **CC0**, and only
irreversible item hashes plus aggregate human values appear here.

## Citing

Please cite the paper and this repository; and cite the source corpus of whichever dataset you
use.

```bibtex
@misc{humans-per-panel-2026,
  title  = {How Many Humans Is a Judge Panel Worth? Anchoring Effective Panel Size on Human
            Label Distributions, and What the Shared Error Is Made Of},
  author = {Li, Chao and Yu, Yingying and Li, Yunfeng},
  year   = {2026},
  note   = {Preprint. arXiv identifier to be added once the preprint is posted;
            this repository is the paper's data release.}
}

@misc{32judges-votes-2026,
  title        = {32judges-votes: per-item votes from a fixed 32-judge LLM panel},
  year         = {2026},
  version      = {2.0},
  howpublished = {\url{https://github.com/Chao1208/32judges-votes}},
  note         = {Data release of the paper above. CC BY 4.0}
}

@inproceedings{nie2020chaosnli,
  title     = {What Can We Learn from Collective Human Opinions on Natural Language
               Inference Data?},
  author    = {Nie, Yixin and Zhou, Xiang and Bansal, Mohit},
  booktitle = {Proceedings of the 2020 Conference on Empirical Methods in Natural Language
               Processing (EMNLP)},
  year      = {2020}
}
```

Civil Comments comes from the Jigsaw Unintended Bias in Toxicity Classification data (CC0); cite
it as that competition's dataset.

[`CITATION.cff`](CITATION.cff) carries the machine-readable form. Pin a release tag or a commit
sha for whatever you used.

## History

This repository was published as `chaosnli-judge-votes` and renamed once Civil Comments was added;
GitHub redirects the old URL. The pre-restructure tree is tagged `v1.0-paper`. Release-to-release
changes are in [CHANGELOG.md](CHANGELOG.md).
