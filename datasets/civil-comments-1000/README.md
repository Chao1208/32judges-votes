# `civil-comments-1000`

A 1,000-item toxicity sample from the Civil Comments (Jigsaw) corpus, judged by the 32-judge panel
pinned in [`../../panel/panel-civil-comments-1000.json`](../../panel/panel-civil-comments-1000.json).
This is the external validation reported in *How Many Humans Is a Judge Panel Worth?*

* **Task**: binary toxicity. Labels `TOXIC` / `NON-TOXIC`.
* **Release tier**: score-only. One file, `votes/baseline/scores.json`, with per item an
  irreversible `id_sha256`, the human toxicity fraction and annotator count, the toxicity stratum,
  and every judge's final label plus any non-`ok` status.
* **Human reference**: real annotators per item, 50 at minimum (`n_toxic / n_annotators`, verified
  equal to the corpus `toxicity` column on all 1,000 items). No join is needed.
* **Counts and hashes**: [`manifest.json`](manifest.json); the released hash record as published at
  v1.0 is [`manifest-source.json`](manifest-source.json). Verify with
  `python3 scripts/verify.py --dataset civil-comments-1000`.

**Panel keys.** The file stores several frozen panels; the paper reports the 32-judge panel under
the key `F15_32`. The other keys are supporting records, retained for data alignment — they are
historical collection keys, not experiment names.

**The sample is deliberately not representative.** Items were drawn only from comments with at
least 50 annotators — 70,772 of the 1,804,875 train rows, 3.92% — and then in equal parts from
five toxicity-fraction strata. Contested items are therefore heavily over-represented: the middle
three strata are 78.8% of the eligible pool against 19.2% of the train split. The sample buys
anchor precision and pays for it in representativeness, so **no prevalence or generality claim can
be read off it**.

**Not included**: comment text, raw model responses, reasoning traces, worker identifiers, integer
source ids, provider payloads, API credentials, request ledgers. The source corpus (CC0) is not
redistributed; obtain it from Jigsaw if you need the text.

Field prose inside `scores.json` is in Chinese, as archived at release time; the field meanings are
listed in `manifest.json` under `arms.baseline.record_fields`. The bytes are left untouched so the
published sha256 still matches.
