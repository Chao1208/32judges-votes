# Moved: `civil_comments/` → `datasets/civil-comments-1000/`

The Civil Comments score-only release now lives with every other dataset, one directory per
dataset:

| what | where |
|---|---|
| final judge labels, human toxicity fractions and annotator counts | [`datasets/civil-comments-1000/votes/baseline/scores.json`](../datasets/civil-comments-1000/votes/baseline/scores.json) |
| dataset manifest (counts, panel, hashes) | [`datasets/civil-comments-1000/manifest.json`](../datasets/civil-comments-1000/manifest.json) |
| released hash record, as published at v1.0 | [`datasets/civil-comments-1000/manifest-source.json`](../datasets/civil-comments-1000/manifest-source.json) |
| what the release does and does not contain | [`datasets/civil-comments-1000/README.md`](../datasets/civil-comments-1000/README.md) |
| the 32-judge roster for this round | [`panel/panel-civil-comments-1000.json`](../panel/panel-civil-comments-1000.json) |

The file contents are unchanged — `scores.json` has the same sha256 (`040dba5c…`) as
`f15_public_scores.json` did at v1.0. The paper reports the panel stored under the key
`F15_32`; the other panel keys in the same file are supporting records.

This directory is kept because the paper deep-links to it. See
[`COMPATIBILITY.md`](../COMPATIBILITY.md) for the full old-path → new-path map, or check out the
`v1.0-paper` tag to get the exact tree the paper describes.
