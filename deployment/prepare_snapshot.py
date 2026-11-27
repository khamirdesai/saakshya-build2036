"""Package an original demo-seeder run; never accepts a government store.

Usage: python deployment/prepare_snapshot.py --source-root /path/to/original
       --database /path/to/demo.db
The original make_media.py and seed.py must have completed first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

import av
from sqlalchemy import text

from saakshya.live.preview import write_preview
from saakshya.store import Store

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    original = args.source_root.resolve()
    source = Store(f"sqlite:///{args.database.resolve()}")
    cameras = source.list_cameras()
    if any((c.get("source_domain") or "").upper() not in {"SYNTHETIC_CONTROL", "OWN_FEED"} for c in cameras):
        raise SystemExit("Refusing a store with government or unlabelled camera data.")
    out = ROOT / "deployment/snapshot"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "demo.sqlite3"
    with sqlite3.connect(args.database) as a, sqlite3.connect(dest) as b:
        a.backup(b)
        b.execute("DELETE FROM api_tokens")
        for (table,) in b.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            for col in b.execute(f'PRAGMA table_info("{table}")').fetchall():
                if any(k in str(col[2]).upper() for k in ("TEXT", "VARCHAR", "CHAR")):
                    name = col[1]
                    b.execute(f'UPDATE "{table}" SET "{name}"=replace("{name}",?,?) WHERE instr("{name}",?)>0',
                              (str(original), "__SAAKSHYA_SOURCE__", str(original)))
        b.commit()
    (out / "source-root.txt").write_text("__SAAKSHYA_SOURCE__\n")
    shutil.copytree(original / "var/media", out / "media", dirs_exist_ok=True)
    shutil.copytree(original / "var/demo_evidence", out / "evidence", dirs_exist_ok=True)
    os.environ["SAAKSHYA_EVIDENCE"] = str(out / "evidence")
    # A preview is an unenhanced decoded corpus frame, never sealed evidence.
    # Select an actual stored observation timestamp for each available camera.
    previews = 0
    for camera in cameras:
        cid = camera["camera_id"]
        media = out / "media" / f"{cid}.mp4"
        if not media.is_file():
            continue
        with source.engine.connect() as connection:
            row = connection.execute(text("SELECT pts_s FROM observations WHERE camera_id=:cid ORDER BY observation_quality DESC LIMIT 1"), {"cid": cid}).first()
        seconds = float(row[0]) if row else 0.0
        with av.open(str(media)) as container:
            stream = container.streams.video[0]
            container.seek(int(seconds / stream.time_base), stream=stream)
            for frame in container.decode(stream):
                if frame.pts is not None and float(frame.pts * stream.time_base) + .05 >= seconds:
                    write_preview(cid, frame.to_ndarray(format="bgr24"))
                    previews += 1
                    break
    info = json.loads((out / "provenance.json").read_text()) if (out / "provenance.json").exists() else {}
    info.update({"snapshot_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "preview_frames": previews,
                 "previews_are_sealed_evidence": False})
    (out / "provenance.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"Packaged synthetic source: {len(cameras)} cameras, {previews} decoded preview frames; issued tokens removed.")


if __name__ == "__main__":
    main()
