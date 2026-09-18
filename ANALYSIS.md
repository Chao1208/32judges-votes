# Offline fixed-panel analysis

[中文](ANALYSIS.zh-CN.md)

This package recomputes the fixed 32-judge baseline panel statistics in
*How Many Humans Is a Judge Panel Worth?*, EN0.2CH0.4. It reads the released votes
and a user-supplied ChaosNLI copy. It never calls a model or downloads data. Raw
responses and reasoning traces are not released; analysis starts from final
`label` scores. Python 3.9+ and NumPy are sufficient.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 src/analyze_panel.py --dataset mnli_m \
  --chaosnli path/to/chaosNLI_v1.0 --output results/mnli_m_clean.json
```

Obtain ChaosNLI separately from <https://github.com/easonnie/chaos_nli> and its
linked data archive. `--chaosnli` points to the directory containing
`chaosNLI_mnli_m.jsonl`, `chaosNLI_snli.jsonl`, and `chaosNLI_alphanli.jsonl`.
Alternatively pass `--human-data path/to/file.jsonl` for one full or sampled file.
The required fields are `uid`, `label_counter` (nonnegative integer counts totaling
100), and `majority_label`. Missing count labels mean zero. The supplied majority
label, including its tie resolution, is preserved; the loader never recomputes
gold with `argmax`. `old_label` is a different target and is not the default.

When the analysis code is supplied separately from the data repository, add
`--repo-root path/to/32judges-votes`. This directory must contain `datasets/<dataset_id>/` and `panel/`;
it need not contain the analysis code. Run the
command from the analysis package directory, or invoke the script by its path.

## Failure policies and the paper table

The default `--failure-policy drop-items` removes the union of items with at
least one `parse_fail` placeholder, preserving a rectangular complete panel.
Baseline placeholder cells/items are 1/1, 0/0, and 5/5 for MNLI-m, SNLI, alphaNLI.
Thus the clean analyses retain 999, 1000, and 995 items. These placeholder labels
are not model judgments.

The paper's primary table retains the recorded deterministic placeholder labels.
Reproduce that table explicitly:

```bash
python3 src/analyze_panel.py --dataset mnli_m \
  --chaosnli path/to/chaosNLI_v1.0 --failure-policy paper-retained \
  --output results/mnli_m_paper-retained.json
python3 src/verify_paper.py --chaosnli path/to/chaosNLI_v1.0 \
  --output-dir results/paper-verification --verify-archive
```

`verify_paper.py` runs all three datasets with `paper-retained`, compares with
`reference/reported_values.json`, and writes each absolute error. Its default
tolerance is `1e-10`. Add `--repo-root` when using a separate data checkout.
These are the fixed main-table values, not every result in the paper.

## Metric definitions and calibration

With one-hot vote `Y[a,i]` and empirical human distribution `h[i]`, residuals are
`r[a,i] = Y[a,i] - h[i]`. The uncentered Gram matrix is
`K[a,b] = mean_i <r[a,i],r[b,i]>`; normalize it by its positive diagonal to get
`C[a,b] = K[a,b]/sqrt(K[a,a] K[b,b])`. `C` is not a Pearson matrix.

| Output | Definition |
|---|---|
| `PR` | `k² / sum(C²)`, evaluated through the equivalent PSD eigenspectrum |
| `E` | `mean_i ||mean_a r[a,i]||²` |
| `J` | `mean_i (1 - ||h[i]||²)` |
| `nu_MSE` | `J/E` when `J>0` and `E>0` |
| `gamma_co_all` | Center each judge's residual across items; `sum_i ||sum_a r_centered[a,i]||² / (k sum_ai ||r_centered[a,i]||²)` |
| `n_eff` | `k / (1+(k-1)*phi_bar)`; `phi_bar` is mean pairwise Pearson correlation of binary errors against the supplied gold |
| `nu_H` | Linear inverse of the saved conditional-independent human-reference mean-PR curve |

`gamma_co_all` is a centered variance share on the original residual scale. It
does not include all mean bias. Its full one-hot computation equals the
orthonormal zero-sum contrast calculation. The `n_eff` denominator uses a numerical positivity guard of `1e-14`; smaller values are treated as numerically degenerate. Undefined statistics have JSON `null`
and a reason, rather than silently replacing undefined correlations with zeros.

`reference/calibration_curves.csv` is the saved EN0.2CH0.4 derived
calibration output: sizes 2–12, 16, 24, 32, 48, 64, 96, 128; 12 replicates;
seed base 42. Only anchor `h` is used here. This release does **not** rerun those
Monte Carlo draws. The manifest verifies the CSV hash, canonical UID set, and
human-count reference fingerprint. Whitespace and extra task-text fields in an
upstream JSONL do not affect the semantic match.

A changed item set or human reference is not assigned the old curve. Therefore
default clean MNLI-m/alphaNLI output `nu_H=null` with
`unavailable_changed_item_set`; SNLI keeps the complete original item set. Use
`--no-calibration` to request only directly computed statistics. A changed
reference requires an independently calibrated new curve and provenance, which
is outside this release's supported reproduction scope. Targets below the first
grid value are reported as `nu_H=2`, `nu_H_status=nu_H_le_first_grid`: read this as
**nu_H ≤ 2**, never as an exact estimate. Values above the grid have no estimate.

Neither human-equivalent measure is a rate of replacing human labor. The
reference is the observed 100-person distribution, not an assertion of latent
truth. A new dataset, collection protocol, label encoding, item cohort, or reference requires
its own evaluation protocol.

## Coverage and checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify.py  # available in the data repository
```

Tests include independent balanced-panel examples, duplication versus
cancellation, centered versus uncentered behavior, degenerate metrics, gold
ties, duplicate/missing UIDs, invalid counts, placeholder filtering, and
calibration/reference mismatch. No upstream dataset is needed for unit tests.

Supported: fixed full baseline panels on MNLI-m, SNLI, alphaNLI; the metrics
above; clean-versus-paper placeholder policies; exact-input hashes; the paper
table comparison. JSON outputs contain metrics and hashes, not upstream counts
or task text, and do not embed absolute input paths.

Not covered: presentation-order analyses, random/selected subpanels, family
decompositions, calibration simulation, label-mode tests, split stability,
stable-addition/rank diagnostics, the later geometry/loss diagnostics, or figure generation.
The full 125,474-row presentation archive is preserved, but the paper's registered
122,000-row selection is not executed by this CLI. This code does not reproduce
the whole paper and does not close every reproducibility limitation.

Requested model identifiers are provenance strings, not independently verified
backend versions. Cached records and separate baseline/presentation-v0
snapshots must not be interpreted as one fresh service call per released row.
No separate same-prompt repeated-call noise floor is established by this archive.
For the EN0.2CH0.4 main table, the explicit `paper-retained` protocol in this
guide takes precedence; the new CLI defaults to `drop-items` for clean analysis.

The full upstream release version is not newly authenticated by this package.
It records actual input-file hashes and canonical selected-count/gold hashes,
and checks the selected human reference against the saved calibration manifest.

## Implementation and licenses

`src/formulas.py` adapts the study's verified pure-math module. `src/votes_io.py`
adapts its strict explicit-UID alignment contract without internal registry paths
or collection dependencies. Degenerate-domain checks are explicit in this
public interface. No API configuration or secret is needed.

Released votes, item rosters and metadata remain under the original `LICENSE` (CC BY 4.0).
Existing `scripts/` remain under the unchanged `LICENSE-CODE` (MIT).
New `src/`, `tests/`, and analysis documentation use `src/LICENSE` (MIT).
Saved derived calibration/reference summaries in `reference/` are CC BY 4.0.
ChaosNLI task text and human counts are not redistributed and retain the
upstream CC BY-NC 4.0 terms. Keep joined upstream data out of public bundles.
