#!/usr/bin/env python3
"""Evaluate stored synthetic leads against the same corpus's generated truth.

Pair-level, time-window-matched accounting; this is not a held-out or field
benchmark. Multiple observations of a camera/plate pair collapse to one pair.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'deployment/snapshot/demo.sqlite3'
TRUTH = ROOT / 'tests/evaluation/ground_truth.json'


def main() -> None:
    payload = json.loads(TRUTH.read_text())
    truth = payload['observations']
    by_pair = defaultdict(list)
    for item in truth:
        by_pair[(item['camera_id'], item['plate'])].append(
            (float(item['t_enter_s']), float(item['t_exit_s']))
        )
    if any(len(windows) != 1 for windows in by_pair.values()):
        raise ValueError('Ground-truth camera/plate pairs must be unique for this evaluation')
    db = sqlite3.connect(f'file:{SNAPSHOT}?mode=ro&immutable=1', uri=True)
    try:
        rows = db.execute(
            'SELECT camera_id, plate, pts_s FROM observations WHERE plate IS NOT NULL'
        ).fetchall()
    finally:
        db.close()
    predicted = {(cam, plate) for cam, plate, _ in rows}
    matched = {
        (cam, plate) for cam, plate, pts in rows
        if any(start <= pts <= end for start, end in by_pair.get((cam, plate), ()))
    }
    expected = set(by_pair)
    cameras = sorted({cam for cam, _ in expected} | {cam for cam, _ in predicted})
    per_camera = {}
    for cam in cameras:
        actual = {p for p in expected if p[0] == cam}
        got = {p for p in predicted if p[0] == cam}
        hits = {p for p in matched if p[0] == cam}
        per_camera[cam] = {
            'truth_pairs': len(actual), 'predicted_pairs': len(got),
            'time_matched_pairs': len(hits), 'unmatched_predicted_pairs': len(got - hits),
            'unmatched_truth_pairs': len(actual - hits),
        }
    report = {
        'dataset': 'Generated synthetic scenes; pre-existing, not held out',
        'sample_rate': '1 frame per second, from snapshot provenance',
        'snapshot_sha256': hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
        'truth_sha256': hashlib.sha256(TRUTH.read_bytes()).hexdigest(),
        'unit': ('Distinct camera/plate pair; matched if at least one stored prediction '
                 'has the same camera and plate within the labeled time window'),
        'truth_pairs': len(expected), 'predicted_pairs': len(predicted),
        'time_matched_pairs': len(matched),
        'unmatched_predicted_pairs': len(predicted - matched),
        'unmatched_truth_pairs': len(expected - matched),
        'pair_precision': round(len(matched) / len(predicted), 4) if predicted else None,
        'pair_recall': round(len(matched) / len(expected), 4) if expected else None,
        'per_camera': per_camera,
        'limitations': [
            ('Synthetic corpus previously used for development; no held-out data or '
             'field deployment.'),
            ('Pair-level matching collapses repeated predictions, so extra wrong-time rows for '
             'an otherwise matched pair are not counted separately.'),
            ('One frame per second, one snapshot, generated labels; not real-camera OCR '
             'accuracy or a confidence interval.'),
            ('Camera C-033 produced no plate predictions in this snapshot; absent or missed '
             'pairs count against recall.'),
        ],
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
