# Synthetic snapshot plate evaluation

This is a reproducible check of the **existing public demo snapshot**, not a new recording or a field trial. The original seeder processed generated scenes at one frame per second. The generated ground-truth file was already used in development; it is not a held-out test set.

A unit is one distinct `(camera, plate)` pair. A predicted pair matches if at least one stored prediction has that camera and exact plate **within** its generated truth time window. Multiple predictions for the same pair collapse into one. The script compares the 206 plate-bearing observation rows in the snapshot to the 231 distinct ground-truth pairs:

| Result | Pairs |
| --- | ---: |
| Labeled truth pairs | 231 |
| Distinct predicted pairs | 103 |
| Matched within truth window | 86 |
| Predicted pairs without a time-window match | 17 |
| Truth pairs without a match | 145 |

By this definition, pair precision is **86/103 (83.5%)** and pair recall is **86/231 (37.2%)**. Camera C-033 produced no plate predictions in the snapshot. These numbers reveal a substantial coverage gap on this synthetic example and should not be interpreted as production OCR accuracy. A matched pair can contain additional wrong-time rows that this pair-level measure does not separately penalize; it is not a frame-level precision score. The corpus is synthetic, sampled at one frame per second, and was available during development. Results cannot be generalized to real-world feeds.

Run from a fresh checkout with Python 3.9 or newer, with no additional packages:

```sh
python3 tools/verify/evaluate_snapshot_plates.py
```

The [machine-readable result](synthetic-plate-evaluation.json) includes per-camera counts and SHA-256 digests of the snapshot and labels. This is a descriptive retrospective check of stored results, with no independent control model or prospective baseline.

For a different, small **historical** comparison on 21 hand-read crops from recorded Mumbai traffic, the [original team report](https://github.com/khamirdesai/DAU-Daiict-submission-Sentinel-gujarat-Hackathone/blob/9b65247f0f23093ee7147f9c4f80a053a280a07f/var/reports/ocr_indian_eval.json) reports 17 exact Awiros matches versus 5 Apple Vision and 2 CCT-ONNX after typing. It also records two invented Awiros reads on crops a person could not read, below its stated single-frame publication threshold. The comparison has not been independently rerun; it does not establish field performance.
