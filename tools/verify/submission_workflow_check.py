#!/usr/bin/env python3
"""Reproduce a bounded judge-workflow and metadata tamper check.

Uses the original app with the repository's synthetic snapshot, in an isolated
copy. Never connects to cameras or alters the snapshot. No issued token is
printed or stored. Run from the repository root after installing `.[dev]`:

    python tools/verify/submission_workflow_check.py

This checks a single known search case and a single kind of metadata alteration
across the six snapshot evidence entries. It is not an accuracy, throughput,
field-deployment, image-integrity, or universal security evaluation.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from deployment.app import SNAPSHOT, build


def session_headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post("/submission/demo-session", params={"role": role})
    response.raise_for_status()
    session = response.json()
    return {
        "Authorization": "Bearer " + session["token"],
        "X-Case-Id": session["case_id"],
        "X-Purpose": session["purpose"],
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> dict:
    snapshot = SNAPSHOT / "demo.sqlite3"
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="saakshya-workflow-") as directory:
        os.environ["SAAKSHYA_DEMO_RUNTIME"] = directory
        with TestClient(build()) as client:
            supervisor = session_headers(client, "supervisor")
            admin = session_headers(client, "admin")
            plate = {"plate": "GJ18JX7786"}
            checks = {
                "anonymous_search_status": client.get("/search", params=plate).status_code,
                "missing_case_purpose_status": client.get(
                    "/search", params=plate, headers={"Authorization": supervisor["Authorization"]}
                ).status_code,
                "administrator_search_status": client.get(
                    "/search", params=plate, headers=admin
                ).status_code,
                "unfiltered_search_status": client.get("/search", headers=supervisor).status_code,
            }
            require(
                checks
                == {
                    "anonymous_search_status": 401,
                    "missing_case_purpose_status": 400,
                    "administrator_search_status": 403,
                    "unfiltered_search_status": 400,
                },
                f"Unexpected access/search boundary results: {checks}",
            )
            search = client.get("/search", params=plate, headers=supervisor)
            require(search.status_code == 200, "Known-plate search failed")
            result = search.json()
            candidates = result["candidates"]
            cameras = sorted({candidate["camera_id"] for candidate in candidates})
            require(
                result["stage_counts"]["exact"] == 7 and len(candidates) == 7 and len(cameras) == 2,
                "Unexpected known-plate search result",
            )
            require(
                all(candidate["status"] == "REQUIRES_VERIFICATION" for candidate in candidates),
                "Unverified lead was not labelled",
            )
            absent = client.get("/search", params={"plate": "ZZ99ZZ9999"}, headers=supervisor)
            require(
                absent.status_code == 200 and len(absent.json()["candidates"]) == 0,
                "Absent-plate negative control failed",
            )
            baseline = client.get("/evidence/chain/verify?fresh=1", headers=supervisor)
            require(baseline.status_code == 200, "Initial evidence verification request failed")
            baseline_data = baseline.json()
            require(
                baseline_data["verified"] is True and baseline_data["records_in_chain"] == 6,
                "Unexpected clean chain verification",
            )
            database = Path(directory) / "demo.db"
            trials = []
            with sqlite3.connect(database) as db:
                rows = db.execute(
                    "SELECT evidence_id, camera_id, frame_sha256, clip_sha256 "
                    "FROM evidence ORDER BY created_at_us"
                ).fetchall()
                require(len(rows) == 6, "Unexpected number of test records")
                metadata_only = sum(
                    not frame_hash and not clip_hash for _, _, frame_hash, clip_hash in rows
                )
                for index, (evidence_id, camera_id, _, _) in enumerate(rows, start=1):
                    db.execute(
                        "UPDATE evidence SET camera_id = ? WHERE evidence_id = ?",
                        (f"{camera_id}-ALTERED", evidence_id),
                    )
                    db.commit()
                    changed = client.get("/evidence/chain/verify?fresh=1", headers=supervisor)
                    data = changed.json()
                    detected = (
                        changed.status_code == 200
                        and data["verified"] is False
                        and any(evidence_id in failure for failure in data["failures"])
                    )
                    db.execute(
                        "UPDATE evidence SET camera_id = ? WHERE evidence_id = ?",
                        (camera_id, evidence_id),
                    )
                    db.commit()
                    restored = client.get("/evidence/chain/verify?fresh=1", headers=supervisor)
                    restoration_passed = (
                        restored.status_code == 200 and restored.json()["verified"] is True
                    )
                    trials.append(
                        {
                            "trial": index,
                            "altered_field": "camera_id",
                            "detected": detected,
                            "restored_chain_verified": restoration_passed,
                        }
                    )
                    require(detected and restoration_passed, f"Tamper trial {index} failed")
            audit_ok, audit_problem = client.app.state.saakshya.store.verify_audit_chain()
            require(audit_ok, f"Audit chain did not verify: {audit_problem}")
            return {
                "run_utc": datetime.now(UTC).isoformat(),
                "scope": (
                    "Original app API on an isolated copy of the synthetic demonstration snapshot; "
                    "no camera feeds, model inference, or field deployment."
                ),
                "snapshot_sha256": digest,
                "baseline": {
                    "known_plate": plate["plate"],
                    "exact_matches": 7,
                    "cameras": cameras,
                    "all_leads_require_verification": True,
                    "absent_plate_matches": 0,
                    "evidence_records_verified": 6,
                    "metadata_only_records": metadata_only,
                },
                "access_control_http_status": checks,
                "tamper_experiment": {
                    "alteration": (
                        "Change the camera_id field of one record, preserving its original hash; "
                        "verify with fresh=1; restore and reverify."
                    ),
                    "records_tested": len(trials),
                    "alterations_detected": sum(t["detected"] for t in trials),
                    "restorations_verified": sum(t["restored_chain_verified"] for t in trials),
                    "trials": trials,
                },
                "audit_chain_verified_after_checks": audit_ok,
                "limitations": [
                    "Single synthetic snapshot and one known search case.",
                    (
                        "Six trials exercise one metadata alteration each; not an exhaustive "
                        "tampering or security assessment."
                    ),
                    "Metadata-only evidence does not prove an image was retained or verified.",
                    (
                        "Does not measure OCR quality, live-camera coverage, operator time saved, "
                        "or field outcomes."
                    ),
                ],
            }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
