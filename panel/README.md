# `panel/` — the 32 judges

This repository is named after its panel, not after a corpus: **every dataset here is judged by 32
judges**. A collection round pins its roster in one file, so a dataset manifest can point at the
exact roster that produced it.

| file | round | datasets |
|---|---|---|
| `panel-chaosnli.json` | ChaosNLI collection | `chaosnli-mnli-m-1000`, `chaosnli-snli-1000`, `chaosnli-alphanli-1000` |
| `panel-civil-comments-1000.json` | Civil Comments collection | `civil-comments-1000` |

Each file lists, per judge, the `judge_key` used in every vote file, the exact requested
`model_id`, and the vendor `family`. These files are the only judge roster in the repository: the
manifests, `scripts/verify.py` and the analysis code all take the panel from here.

## Same size, different roster

The two rounds were collected about two and a half weeks apart and the panels are **not identical**:
six judges differ. Provider model aliases drifted — five endpoints had disappeared (404 or no
channel on both routes) and three Google models were unavailable on both routes — and replacements
were taken from a candidate order fixed before probing. `panel-civil-comments-1000.json` records
the exact difference under `differs_from_chaosnli_round`, including the per-family delta
(Google −3, Moonshot −1, OpenAI +2, Anthropic +1, Zhipu +1).

Two consequences for anyone using this data:

1. **Panel size is aligned across datasets; family composition is not.** A difference between a
   ChaosNLI reading and a Civil Comments reading mixes task, human reference and roster. It is not
   a controlled comparison of corpora.
2. **Same-family redundancy is one of the sources of correlated error**, so a roster with more
   same-family judges is not simply a "larger panel".

Model ids are the requested strings; backend identity and version are not independently
authenticated. `earlier_generation` in the ChaosNLI roster is retained as recorded metadata, not as
evidence of backend chronology or capability.

`scripts/build_manifests.py` fails if a roster file and the judges actually present in a dataset
disagree, so a stale panel file cannot slip through.
