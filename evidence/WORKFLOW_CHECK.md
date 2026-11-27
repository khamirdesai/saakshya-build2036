# Reproducible original-app workflow check

This check exercises the original application API on a temporary copy of the **synthetic** public demonstration snapshot. It does not connect to the Sentinel network or a government camera. The dated run and exact snapshot SHA-256 are in [workflow-integrity-check.json](workflow-integrity-check.json).

| Check | Observed result |
|---|---|
| Known synthetic plate search | 7 exact matches across 2 cameras; all 7 marked `REQUIRES_VERIFICATION` |
| Absent plate negative control | 0 candidates |
| Access and query boundaries | Anonymous 401; missing case/purpose 400; administrator search 403; unfiltered search 400 |
| Untouched evidence chain | 6 of 6 records verify |
| Isolated metadata tamper trials | Each of the 6 records had its `camera_id` changed in turn without updating its hash; fresh verification detected 6 of 6 changes. After each original value was restored, the chain verified again. |
| Audit chain | Verified after the checks |

All six tested evidence records are **metadata-only**. Their verification does not show that a still image or clip was retained. The six alterations cover one field and one simple attack pattern in one known test snapshot. They are not a universal integrity guarantee, an assessment of production security, an independent field trial, or a measure of OCR accuracy, live-camera performance or investigation time saved.

## Repeat it

From a fresh checkout, use Python 3.12+ and install the project and development dependencies (`python -m pip install -e '.[dev]'`). Then run:

```sh
python tools/verify/submission_workflow_check.py
```

The script copies the reviewed database into a temporary directory; it never modifies the distributed snapshot and does not print or store issued demo credentials. It exits with an error if a check fails and writes the results as JSON to standard output. To retain a local result, redirect the output to a file.
