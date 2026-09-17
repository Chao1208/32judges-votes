# ChaosNLI judge votes — 32 LLM judges, per-item, with a presentation-order arm

Per-item votes from **32 LLM judges** (10 vendor families) on **1,000 items from each of the
three ChaosNLI sets** (MNLI-m, SNLI, alphaNLI), plus a **presentation-order arm** that re-asks a
500-item subset with the answer options in a different order. 221,474 judged cells in total,
released with high-level collection settings and a per-file integrity manifest.

This is the dataset behind *How Many Humans Is a Judge Panel Worth?* (see
[Citing](#citing) — the paper cites this repository, and this repository cites the paper).
It exists because work on judge-panel correlation currently re-collects per-item votes from
scratch every time: the votes are cheap to consume and expensive to produce. Reuse them.

ChaosNLI itself is **not** redistributed here (it is CC BY-NC 4.0). We ship our votes keyed by
ChaosNLI `uid`, the sampled id lists, and a join script. Offline fixed-panel analysis
code is provided under `src/`; see [ANALYSIS.md](ANALYSIS.md) for installation,
human-data requirements, failure policies, supported metrics, and reproduction limits.
To run the supported paper results from Step 1 through the final comparison, use
the single-entry [reproduction guide](REPRODUCE.md) and `python reproduce.py`.
The reproduction starts from saved 32-judge votes, runs offline, and makes
**0 model/API calls**.

## Layout

```
votes/<dataset>/<judge>.jsonl        baseline arm: 32 judges × 1,000 items × 3 datasets
votes_swap/<dataset>/<judge>.jsonl   presentation-order arm: same judges, 500-item subset
items/<dataset>_uids.txt             the 1,000 sampled ChaosNLI uids, in sampling order
meta/judges.csv                      judge key → model id, vendor family, generation flag
meta/integrity.json                  per-file sha256, rows, unique uids, parse_fail, variants
scripts/verify.py                    re-checks every file against meta/integrity.json
scripts/join_chaosnli.py             joins the votes with ChaosNLI's 100-annotator counts
src/analyze_panel.py                 portable fixed-panel analysis CLI
src/verify_paper.py                  compare actual outputs with the saved main table
meta/analysis/                      saved calibration, reference summaries, and manifest
ANALYSIS.md                         offline analysis instructions and scope
REPRODUCE.md                       Step 1--N guide and single reproduction entry point
reproduce.py                       integrity → tests → paper-table verification
```

`<dataset>` is one of `mnli_m`, `snli`, `alphanli`.

## Record format

Baseline arm (`votes/`), one JSON object per line:

| field | meaning |
|---|---|
| `uid` | ChaosNLI item id — the join key |
| `label` | the judge's label: `e` / `n` / `c` for the NLI sets, `1` / `2` for alphaNLI |
| `parse_fail` | `true` if no legal label could be read from the reply, **see the caveat below** |

Presentation-order arm (`votes_swap/`) adds `variant` (0 = baseline option order) and `perm`
(the permutation actually presented). One line per (item, variant).

Raw model responses, reasoning traces, prompts, and internal collection bookkeeping are **not**
included. Public records keep only `uid`, the final `label`, and `parse_fail`, plus `variant` and
`perm` for the presentation-order arm. The released `label` is the final score used by the paper.

## Panel

32 judges from 10 families (OpenAI 5, Alibaba 4, Google 4, Moonshot 4, Zhipu 4, Anthropic 3,
DeepSeek 3, ByteDance 2, xAI 2, MiniMax 1). The historical `earlier_generation` metadata flag
is retained as recorded, not as independent evidence of backend chronology or capability.

Model ids are the exact requested model strings; backend identity/version is not independently
authenticated. The collection used a single user message, no system message, temperature 0,
and a constrained answer format. Exact prompts and request code are not part of this public
repository. A released row should be read as an archived judgment record, not as evidence of a
fresh service call.

## Items and sampling

1,000 items per dataset, drawn from the full ChaosNLI set stratified into equal thirds by the
entropy of the 100-annotator label distribution (seed 42). `items/<dataset>_uids.txt` lists them
in sampling order; every `uid` in a vote file is guaranteed to be in that list (checked by
`scripts/verify.py`).

To get the human label distributions, clone ChaosNLI and join by `uid`:

```bash
git clone https://github.com/easonnie/chaos_nli
python3 scripts/join_chaosnli.py --chaosnli path/to/chaosNLI_v1.0 --dataset mnli_m | head -1
```

## Presentation-order arm

The same judges answer a 500-item subset again with the options presented in a different order:
three orders (`variant` 0/1/2) for the three-label sets, two for alphaNLI, which has two options.
The permutation is recorded per record and the answer is mapped back, so labels are directly
comparable in label semantics to the baseline arm. Baseline and presentation `variant=0`
are separately stored response snapshots; they must not be silently merged or substituted.

Coverage is not complete, and the gaps are the reason our analysis of this arm uses a **31 / 31 /
29** judge panel rather than 32:

| dataset | files | judges excluded from the arm's panel | why |
|---|---|---|---|
| `mnli_m` | 32 | `dsv32` | only `variant` 0 was ever collected (500 rows) |
| `snli` | 32 | `dsv32` | complete here, but excluded to keep one panel across datasets |
| `alphanli` | 31 | `dsv32`, `glm52`, `kimik3` | no file; only `variant` 0; 26 rows missing |

The files are shipped as they are, including the partial ones — a study that wants a different
panel should be able to see what was there.

## Caveats worth reading before use

**`parse_fail` labels are placeholders, not judgments.** When a reply contained no legal label
(or the call kept failing), the pipeline still emits a `label`, computed as a deterministic hash
of `uid:judge_key`. They are flagged placeholders, not model judgments. The new analysis
CLI defaults to removing every item affected by a placeholder. The paper's historical primary
table retained them; exact reproduction requires explicit `--failure-policy paper-retained`. There are 6 such
cells in the baseline arm (1 / 0 / 5 for MNLI-m / SNLI / alphaNLI) and 27 in the
presentation-order arm (11 / 8 / 8).

**Only final scores are released.** The dataset contains no raw model responses or reasoning
traces. Downstream analysis uses `label`; there is no public raw-text field to reparse.

**Temperature 0 is not determinism.** Re-asking the same question at temperature 0 does not
always return the same word. This archive does not separately identify a same-prompt
repeated-call noise floor. Order differences can include snapshot/cache and service variation;
they are not an isolated causal measurement of answer-option order alone.

**Nothing here is a benchmark ranking.** Agreement with the 100-annotator majority varies with
the dataset, and a judge's rank moves across datasets. These are votes, not a leaderboard.

## Integrity

```bash
python3 scripts/verify.py
```

checks sha256, row count, unique uid count, `parse_fail` count and rows-per-variant for all 191
vote files against `meta/integrity.json`, and that no vote file mentions an item outside the
sampled id list.

## Licensing

Data (`votes/`, `votes_swap/`, `items/`, `meta/`): **CC BY 4.0** — see `LICENSE`.
Existing code (`scripts/`): **MIT** — see unchanged `LICENSE-CODE`.
New analysis code (`src/`, `tests/`) and documentation: **MIT** — see `src/LICENSE`.
ChaosNLI is not included and stays under its own **CC BY-NC 4.0** terms; a join of our votes with
ChaosNLI inherits those terms.

## Citing

If you use these votes, please cite both the paper and this repository.

```bibtex
@misc{humans-per-panel-2026,
  title  = {How Many Humans Is a Judge Panel Worth? Anchoring Effective Panel Size on Human
            Label Distributions, and What the Shared Error Is Made Of},
  author = {Li, Chao and Yu, Yingying and Li, Yunfeng},
  year   = {2026},
  note   = {Preprint. arXiv identifier to be added once the preprint is posted;
            this repository is the paper's data release.}
}

@misc{chaosnli-judge-votes-2026,
  title        = {ChaosNLI judge votes: 32 LLM judges, per-item, with a presentation-order arm},
  year         = {2026},
  version      = {1.0},
  howpublished = {\url{https://github.com/Chao1208/chaosnli-judge-votes}},
  note         = {Data release of the paper above. CC BY 4.0}
}
```

And cite ChaosNLI, which supplies the items and the human label distributions:

```bibtex
@inproceedings{nie2020chaosnli,
  title     = {What Can We Learn from Collective Human Opinions on Natural Language
               Inference Data?},
  author    = {Nie, Yixin and Zhou, Xiang and Bansal, Mohit},
  booktitle = {Proceedings of the 2020 Conference on Empirical Methods in Natural Language
               Processing (EMNLP)},
  year      = {2020}
}
```
