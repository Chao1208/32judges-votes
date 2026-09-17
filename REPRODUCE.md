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
git clone https://github.com/Chao1208/chaosnli-judge-votes.git
cd chaosnli-judge-votes
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

## Reproduction boundary

This public workflow verifies the fixed full baseline panel and the paper's saved
main-table values. It does not reproduce presentation-order analyses, selected
subpanels, provider-family decompositions, new calibration simulations, split
stability, member-addition diagnostics, later geometry/loss diagnostics, or
figure generation. Those boundaries are also written into `summary.json`; a
successful run must not be reported as an end-to-end reproduction of every paper
figure and experiment.
