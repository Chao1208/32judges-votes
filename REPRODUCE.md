# Reproduce the paper's public results

[中文](REPRODUCE.zh-CN.md)

This is the single entry point for the public reproduction accompanying *How
Many Humans Are 32 LLM Judges Worth?*. **The experiment starts from the released
per-item votes of 32 judges and makes exactly 0 model/API calls.** It is an
offline analysis: no API credentials are read, and `reproduce.py` makes no
network requests.

Creating the environment and obtaining the separately licensed ChaosNLI input
may involve downloads before the experiment. Once those local inputs exist,
Step 4 is fully offline and performs zero API calls.

## Step 1 — Clone this repository

```bash
git clone https://github.com/Chao1208/32judges-votes.git
cd 32judges-votes
```

## Step 2 — Create an environment

Python 3.9 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Step 3 — Obtain ChaosNLI separately

ChaosNLI is not redistributed here because it retains its CC BY-NC 4.0 terms.
Download ChaosNLI v1.0 from its official project and locate the directory that
contains these three files:

```text
chaosNLI_mnli_m.jsonl
chaosNLI_snli.jsonl
chaosNLI_alphanli.jsonl
```

The reproduction reads only `uid`, `label_counter`, and `majority_label` for the
1,000 released item IDs per dataset. CC-1000 needs no external input: its score
layer already carries the human toxicity counts.

## Step 4 — Run the whole public reproduction

```bash
python reproduce.py \
  --chaosnli /absolute/path/to/chaosNLI_v1.0 \
  --output-dir results/paper-reproduction
```

The offline command makes **0 model/API calls** and runs, in order:

1. integrity checks for every released vote file;
2. the 21 analysis unit tests;
3. fresh fixed-panel analysis for MNLI-m, SNLI, and alphaNLI, followed by an
   absolute-tolerance comparison against the paper's saved main-table values;
4. the fixed-pool asymptote, the analytic calibration and its agreement with the
   Monte Carlo curves, the CC-1000 fixed panel, the full panel-selection
   experiment with its error decomposition, and the same selection rerun without
   placeholder-touched items, each compared against saved unrounded values and
   against the numbers printed in the paper.

Step 4 enumerates all C(32,5) = 201,376 and C(32,7) = 3,365,856 panels on each
of the four datasets, and again on the three ChaosNLI item sets without
placeholders; it takes about 4.5 minutes on a laptop, and the other steps take
seconds. A successful run ends with `PASS` and writes:

```text
results/paper-reproduction/summary.json
results/paper-reproduction/step1_archive_integrity.log
results/paper-reproduction/step2_unit_tests.log
results/paper-reproduction/step3_paper_table.log
results/paper-reproduction/step4_extended.log
results/paper-reproduction/paper-table/paper_comparison.json
results/paper-reproduction/paper-table/*_paper-retained.json
results/paper-reproduction/extended/extended_comparison.json
```

`paper_comparison.json` records expected value, recomputed value, absolute error,
and pass/fail for every checked metric. The default absolute tolerance is
`1e-10`; change it only with an explicit `--atol` argument.
`extended_comparison.json` lists every check of Step 4 with its kind:
`saved_unrounded` (within `--atol`) or `printed_in_paper` (within half a unit
of the last printed digit).
`summary.json` also records `model_api_calls: 0` and
`network_requests_during_run: 0`.

## Step 5 — Interpret the reproduced metrics

**Fixed panel (Step 3).** The workflow reproduces the fixed 32-judge
baseline-panel values for PR, panel distribution error `E`, human disagreement
`J`, `nu_MSE`, `gamma_co_all`, binary error effective votes `n_eff`, and `nu_H`.
Votes and human counts are loaded and aligned afresh. `nu_H` is obtained by
inverting the released, hash-checked human calibration curve; this package does
not rerun its Monte Carlo generation.

The paper retained six explicitly flagged deterministic placeholder labels in
its historical primary table. The orchestrator therefore uses
`--failure-policy paper-retained` for exact comparison. For a new analysis, use
the safer default `drop-items`; see [ANALYSIS.md](ANALYSIS.md).

**Fixed-pool asymptote (Section 4.2, Appendix C).** `src/formulas.py:pool_asymptote`
holds `mu2 = ||mean residual||^2`, the mean member variance `v_bar`, and the mean
centered covariance `rho_bar` fixed, so `E(m) = mu2 + v_bar (1/m + (1-1/m) rho_bar)`.
It reports the centered and uncentered limits of `nu_MSE`, the observed share of
the centered limit, and the gain from 32 to 64 judges.

**Analytic calibration (Section 3.3).** `closed_form_delta` computes
`delta = <s2 - 2 s3 + s2^2> / (n <1 - s2>^2)` from the human distributions. It is
a moment approximation: a ratio of expectations, not the expected squared
normalized inner product between two human draws, and the two differ at small
`n`. `nu_closed_form` inverts the approximate reference
`PR_delta(m) = m / (1 + (m-1) delta)` exactly, not the Monte Carlo mean; it is NaN
at `PR >= 1/delta`. Step 4 checks the agreement the paper reports: over every grid
point on all four item sets the largest gap between `PR_delta(m)` and the Monte Carlo
mean is 0.18% (0.1845% unrounded), and on the 30 selected panels the grid covers the
largest `nu_H` difference is 0.15% (0.1502% unrounded).

**CC-1000 (Section 4.9).** `src/civil_comments.py` reads the hash-checked score
layer, orders items by `id_sha256` and judges by key, and uses
`h_i = (1 - p_i, p_i)` with `p_i` the toxic share of annotators; gold is
`1[p_i > 0.5]`, and `n_eff` excludes the 10 items at `p_i = 0.5`. The
finite-annotation correction is `(J + b) / (E - b)` with
`b = mean((1 - ||h_i||^2) / (M_i - 1))`. `nu_H` inverts the saved CC-1000 Monte
Carlo curve in `reference/calibration_curve_civil_comments.csv`.

**Panel selection (Section 4.10, Tables 7-8, Appendix A.7).** `src/selection.py`
recomputes every selected panel and every enumeration count; the definitions
follow.

- `acc` never breaks a tie. The item score is `1[gold in M] / |M|` over the set
  `M` of modal labels, the expectation under uniform tie-breaking. Since
  `|M| <= 3`, scores scaled by `lcm(1,2,3) = 6` are integers, so
  `acc_int_sum_lut6` is an exact integer sum and `acc = acc_int_sum_lut6 / (6n)`.
  This differs from the deterministic-hash majority vote used for the
  fixed-panel table.
- `nu_H_closed_form` inverts the analytic approximation above rather than the
  Monte Carlo grid in `reference/calibration_curves.csv`; on the four full
  32-judge panels the two agree to 0.027-0.077 percent. Unlike the grid, the
  approximation is defined below two independent draws, where some baselines
  fall; a value there is a matched unit, not a count of draws.
- `E` is the panel distribution error and `nu_MSE = J / E`; `omega_bar` is the
  mean member residual energy; `q_bar` is the mean squared off-diagonal entry of
  the normalized residual Gram matrix, with `PR = k / (1 + (k-1) q_bar)`.
- `S0` is the `k` best single-judge accuracies, ties by judge key. The candidate
  set is the at-most-two-swap neighborhood of `S0`, of size
  `k(32-k) + C(k,2)C(32-k,2)`, listed one-swap first and, within each, by the
  judges swapped out, then those swapped in.
- Rule A maximizes `nu_H` over candidates with `acc > acc(S0)`; rule E minimizes
  `E` over the same set; rule D maximizes `acc`, then `nu_H`. Remaining ties go
  to the first candidate in the listed order. Accuracy is compared as an exact
  integer sum; `nu_H` and `E` are compared as double-precision values with no
  tolerance.
- Rule A's error change splits as `E = omega_bar/k + B` with the signed cross term
  `B = k^-2 sum_{a != b} K_ab`: in all eight cases `omega_bar/k` rises and `B` falls
  by more. `q_bar` squares the normalized inner products and drops their signs,
  so it is not the quantity that enters `E`.
- Dropping every item that a placeholder label touches (1 on MNLI-m, 5 on
  alphaNLI) and rerunning the whole selection leaves `S0`, the A/D/E panels and
  every enumeration count unchanged.
- `in_joint_improvement_set` marks whether the panel is strictly better than
  `S0` on both accuracy and `nu_H`; it is blank for `S0` itself.

`reference/panel_selection.csv` releases the resulting panels, one row per
(dataset, k, rule), so they can be checked without running Step 4.
`judge_keys` joins to `panel/*.json` and to the vote files.

## Reproduction boundary

This public workflow verifies the fixed full baseline panel, the paper's saved
main-table values, the fixed-pool asymptote, the analytic calibration, the
CC-1000 fixed panel, and the panel-selection experiment. It does not reproduce
presentation-order analyses, random subpanel curves, provider-family
decompositions, new calibration simulations (the Monte Carlo curves are read
from `reference/`), split stability, member-addition diagnostics, tie-rate
evidence, later geometry/loss diagnostics, or figure generation. Those
boundaries are also written into `summary.json`; a successful run must not be
reported as an end-to-end reproduction of every paper figure and experiment.
