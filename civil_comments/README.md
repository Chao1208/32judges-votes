# Civil Comments score-only release

This directory contains the public score layer for the F15 external validation in *How Many Humans Is a Judge Panel Worth?*

`f15_public_scores.json` contains 1,000 sampled Civil Comments items with:

- a SHA-256 identifier instead of the source comment ID;
- the human toxicity fraction and annotator count used as the empirical reference;
- the final labels from the six frozen panels (including the 32-judge panel);
- non-`ok` status fields where applicable.

The release contains no comment text, raw model responses, reasoning traces, worker identifiers, integer source IDs, provider payloads, API credentials, or request ledger. The source archive and item text are not redistributed. `f15_public_manifest.json` records the score-file hash and the public-release provenance hashes.

The score layer is sufficient to audit the released F15 aggregate calculations when combined with the paper's protocol and analysis code. It is not a release of the source Civil Comments corpus or the raw collection record.
