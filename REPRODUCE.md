# Reproduce the paper's public fixed-panel results

[中文](REPRODUCE.zh-CN.md)

This is the single entry point for the public reproduction accompanying *How
Many Humans Is a Judge Panel Worth?*. **The experiment starts from the released
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
1,000 released item IDs per dataset.

## Step 4 — Run the whole public reproduction

```bash
python reproduce.py \
  --chaosnli /absolute/path/to/chaosNLI_v1.0 \
  --output-dir results/paper-reproduction
```

The offline command makes **0 model/API calls** and runs, in order:

1. integrity checks for all 191 released vote files;
2. the 11 analysis unit tests;
3. fresh fixed-panel analysis for MNLI-m, SNLI, and alphaNLI, followed by an
   absolute-tolerance comparison against the paper's saved main-table values.

A successful run ends with `PASS` and writes:

```text
results/paper-reproduction/summary.json
results/paper-reproduction/step1_archive_integrity.log
results/paper-reproduction/step2_unit_tests.log
results/paper-reproduction/step3_paper_table.log
results/paper-reproduction/paper-table/paper_comparison.json
results/paper-reproduction/paper-table/*_paper-retained.json
```

`paper_comparison.json` records expected value, recomputed value, absolute error,
and pass/fail for every checked metric. The default absolute tolerance is
`1e-10`; change it only with an explicit `--atol` argument.
`summary.json` also records `model_api_calls: 0` and
`network_requests_during_run: 0`.

## Step 5 — Interpret the reproduced metrics

The workflow reproduces the fixed 32-judge baseline-panel values for PR, panel
distribution error `E`, human disagreement `J`, `nu_MSE`, `gamma_co_all`, binary
error effective votes `n_eff`, and `nu_H`. Votes and human counts are loaded and
aligned afresh. `nu_H` is obtained by inverting the released, hash-checked human
calibration curve; this package does not rerun its Monte Carlo generation.

The paper retained six explicitly flagged deterministic placeholder labels in
its historical primary table. The orchestrator therefore uses
`--failure-policy paper-retained` for exact comparison. For a new analysis, use
the safer default `drop-items`; see [ANALYSIS.md](ANALYSIS.md).

## Selection results (panel-selection section of the paper)

`reference/panel_selection.csv` releases the panels behind the paper's
panel-selection results so that their values can be checked without rerunning the
search. One row per (dataset, k, rule), with `rule` in `S0` (accuracy-top-k
baseline), `A` (maximize `nu_H` subject to higher accuracy than `S0`), `D`
(maximize accuracy), and `E` (minimize `E` under the same accuracy constraint as
`A`). `judge_keys` joins to `panel/*.json` and to the vote files.

Conventions behind the columns:

- `acc` never breaks a tie. The item score is `1[gold in M] / |M|` over the set
  `M` of modal labels, the expectation under uniform tie-breaking. Since
  `|M| <= 3`, scores scaled by `lcm(1,2,3) = 6` are integers, so
  `acc_int_sum_lut6` is an exact integer sum and `acc = acc_int_sum_lut6 / (6n)`.
  This differs from the deterministic-hash majority vote used for the
  fixed-panel table.
- `nu_H_closed_form` inverts the analytic reference `PR0(m) = m / (1 + (m-1)d)`
  rather than the Monte Carlo grid in `reference/calibration_curves.csv`; the two
  agree to 0.024-0.085 percent on the full 32-judge panels, and the analytic form
  stays exact below two independent draws, where some baselines fall.
- `E` is the panel distribution error and `nu_MSE = J / E`; `omega_bar` is the
  mean member residual energy; `q_bar` is the mean squared off-diagonal entry of
  the normalized residual Gram matrix, with `PR = k / (1 + (k-1) q_bar)`.
- `in_joint_improvement_set` marks whether the panel is strictly better than
  `S0` on both accuracy and `nu_H`; it is blank for `S0` itself.

The candidate set is the at-most-two-swap neighborhood of `S0`, of size
`k(32-k) + C(k,2)C(32-k,2)`, and every rule breaks ties by enumeration order,
which lists one-swap candidates first. `reproduce.py` does not run this
enumeration; the released votes plus these definitions are what a third party
needs to recompute it.

## Reproduction boundary

This public workflow verifies the fixed full baseline panel and the paper's saved
main-table values. It does not reproduce presentation-order analyses, the
panel-selection search itself (its resulting panels and readings are released in
`reference/panel_selection.csv`), provider-family decompositions, new calibration simulations, split
stability, member-addition diagnostics, later geometry/loss diagnostics, or
figure generation. Those boundaries are also written into `summary.json`; a
successful run must not be reported as an end-to-end reproduction of every paper
figure and experiment.
