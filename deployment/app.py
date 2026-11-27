"""Serve the original application with an isolated synthetic demonstration store.

No browser API interception, invented responses or substitute product interface.
The upstream FastAPI routes, authorisation and service implementations handle
requests. Only deployment boot, labelled demo access and public-demo boundaries
are added here. Government ingest and paid AI providers are not started.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "deployment" / "snapshot"


def restore_snapshot(source: Path, target: Path, *, old_root: str = "", evidence_root: Path | None = None) -> None:
    """Copy a reviewed SQLite snapshot and relocate its local file references."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as original, sqlite3.connect(target) as copy:
        original.backup(copy)
        if old_root:
            tables = copy.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (table,) in tables:
                # Names originate from our SQLite schema, never a request.
                for column in copy.execute(f'PRAGMA table_info("{table}")').fetchall():
                    name, kind = column[1], str(column[2]).upper()
                    if any(t in kind for t in ("TEXT", "VARCHAR", "CHAR")):
                        for before, after in (
                            (old_root + "/var/media", str(SNAPSHOT / "media")),
                            (old_root + "/var/demo_evidence", str(evidence_root or ROOT / "var/demo_evidence")),
                            (old_root, str(ROOT)),
                        ):
                            copy.execute(
                                f'UPDATE "{table}" SET "{name}"=replace("{name}", ?, ?) '
                                f'WHERE instr("{name}", ?) > 0',
                                (before, after, before),
                            )
        copy.commit()


def prepare_ui(destination: Path) -> None:
    """Keep the original UI; add source labels and a demo-access control."""
    shutil.copytree(ROOT / "ui", destination, dirs_exist_ok=True)
    page = (destination / "index.html").read_text()
    page = page.replace("SAAKSHYA — Gujarat Police CCTV Intelligence", "SAAKSHYA — Build 2036 Prototype")
    page = page.replace("Gujarat Police · CCTV evidence", "Build 2036 · Synthetic demonstration")
    page = page.replace("Official · sensitive", "Public prototype demo")
    page = page.replace(
        "Law-enforcement use only. Every query is attributed and written to a hash-chained audit log.",
        "Original SAAKSHYA application · Synthetic corpus only · No government feeds connected.",
    )
    page = page.replace("ગુજરાત પોલીસ · ગૃહ વિભાગ", "Build 2036 · Frontier 06")
    page = page.replace("Gujarat Police · Home Department", "Earlier Gujarat challenge prototype")
    page = page.replace(
        '<form id="gate-form">',
        '<div class="field"><label for="public-demo-role">Demonstration role</label>'
        '<select id="public-demo-role"><option value="supervisor">Supervisor</option>'
        '<option value="investigator">Investigator, Ahmedabad</option>'
        '<option value="admin">Estate administrator</option>'
        '<option value="auditor">Auditor</option></select></div>'
        '<button type="button" class="ghost" id="public-demo-access">Use demo access</button>'
        '<p class="gate-note" id="public-demo-status" role="status">'
        'Get a temporary role-scoped token for this synthetic sandbox. '
        'The original server sign-in and purpose checks still apply.</p>'
        '<p class="gate-note"><a href="https://khamirdesai.github.io/saakshya-build2036/videos/">'
        'Watch the original prototype recordings</a></p><form id="gate-form">',
    )
    page = page.replace("</body>", '<script type="module" src="/ui/demo-access.js"></script></body>')
    (destination / "index.html").write_text(page)
    shutil.copy2(ROOT / "deployment" / "demo-access.js", destination / "demo-access.js")

    # A two-hour demo token can expire while the browser tab remains open, or
    # become invalid after the server is restarted. The original UI otherwise
    # keeps the old officer name visible and asks the visitor to paste a token.
    # Apply this only to the public synthetic wrapper: keep the original gate
    # and authentication, but return the visitor to its demo-access control.
    application = destination / "app.js"
    source = application.read_text()
    fetch_line = "  const res = await fetch(path, { ...opts, headers });"
    if source.count(fetch_line) != 1:
        raise RuntimeError("Original app API client changed; demo recovery cannot be applied safely")
    recovery = """
  // BEGIN public demo session recovery
  if (res.status === 401 && state.principal && state.token) {
    state.token = "";
    state.principal = null;
    sessionStorage.removeItem("saakshya.token");
    const gate = document.querySelector("#gate");
    if (gate) gate.hidden = false;
    const who = document.querySelector("#who");
    if (who) who.textContent = "not signed in";
    const officer = document.querySelector("#officer-name");
    if (officer) officer.textContent = "Sign in";
    const tokenButton = document.querySelector("#btn-token");
    if (tokenButton) tokenButton.textContent = "Sign in";
    const message = document.querySelector("#public-demo-status");
    if (message) message.textContent = "Your demo session ended. Select Use demo access, then Enter the workspace to continue.";
  }
  // END public demo session recovery
"""
    application.write_text(source.replace(fetch_line, fetch_line + recovery, 1))


def build():
    # Public demo configuration never reads the submitter's .env or credentials.
    os.environ["SAAKSHYA_REQUIRE_AUTH"] = "1"
    os.environ["SAAKSHYA_GOOGLE_MAPS_DISABLE"] = "1"
    os.environ["AI_PROVIDER"] = "disabled"
    os.environ["SAAKSHYA_MODELS_OFFLINE"] = "1"
    os.environ["SAAKSHYA_AI_WORKER"] = "0"
    os.environ["SAAKSHYA_MEDIA_DISABLED"] = "1"
    os.environ["SAAKSHYA_DEMO_SIMULATION"] = "0"
    os.environ["SAAKSHYA_MEDIA"] = str(SNAPSHOT / "media")
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "SAAKSHYA_WHEP_BASE"):
        os.environ.pop(name, None)

    runtime = Path(os.environ.get("SAAKSHYA_DEMO_RUNTIME", "/tmp/saakshya-build2036"))
    runtime.mkdir(parents=True, exist_ok=True)
    db = runtime / "demo.db"
    seed = SNAPSHOT / "demo.sqlite3"
    if not seed.is_file():
        raise RuntimeError("Missing reviewed synthetic snapshot: deployment/snapshot/demo.sqlite3")
    old_root_file = SNAPSHOT / "source-root.txt"
    evidence_root = runtime / "evidence"
    os.environ["SAAKSHYA_EVIDENCE"] = str(evidence_root)
    shutil.copytree(SNAPSHOT / "evidence", evidence_root, dirs_exist_ok=True)
    restore_snapshot(seed, db, old_root=old_root_file.read_text().strip() if old_root_file.exists() else "", evidence_root=evidence_root)
    ui = runtime / "ui"
    prepare_ui(ui)

    from saakshya.api.app import create_app
    from saakshya.api.deps import AppState
    from saakshya.security import Role

    state = AppState(f"sqlite:///{db}", evidence_root=evidence_root)
    app = create_app(state=state, static_dir=ui)

    @asynccontextmanager
    async def demo_lifespan(_app):
        # Intentionally do not boot the upstream government evaluation grid.
        # Media previews are opened on demand by the original application.
        yield
        if state.snapshots is not None:
            state.snapshots.selected.stop()
        state.store.engine.dispose()

    app.router.lifespan_context = demo_lifespan
    roles = {
        "supervisor": ("supervisor.demo", Role.SUPERVISOR, (), "Supervisor · synthetic demo"),
        "investigator": ("investigator.ahd", Role.INVESTIGATOR, ("Ahmedabad",), "Investigator · synthetic demo"),
        "admin": ("admin.demo", Role.ADMIN, (), "Estate administrator · synthetic demo"),
        "auditor": ("auditor.demo", Role.AUDITOR, (), "Auditor · synthetic demo"),
    }
    for user_id, role, districts, name in roles.values():
        state.tokens.upsert_user(user_id, role, districts=districts, display_name=name)
    issued: dict[str, tuple[float, str]] = {}
    token_lock = threading.Lock()

    @app.post("/submission/demo-session", include_in_schema=False)
    async def demo_session(role: str = Query("supervisor")):
        if role not in roles:
            raise HTTPException(400, detail={"code": "DEMO_ROLE", "message": "Choose a listed demonstration role."})
        with token_lock:
            entry = issued.get(role)
            if entry is None or time.monotonic() - entry[0] >= 1800:
                entry = (time.monotonic(), state.tokens.mint(roles[role][0], label="public synthetic demo", ttl=timedelta(hours=2)))
                issued[role] = entry
        return JSONResponse({"user_id": roles[role][0], "token": entry[1], "case_id": "DEMO-BUILD2036", "purpose": "Review the synthetic prototype demonstration"}, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def sandbox_boundaries(request: Request, call_next):
        # The public instance offers the original workflow on synthetic data.
        # It cannot be repointed at arbitrary cameras or external AI services.
        path = request.url.path
        blocked = request.method not in {"GET", "HEAD", "OPTIONS"} and (
            path.startswith(("/registry/", "/admin/", "/edge/", "/zones"))
            or path.endswith(("/whep", "/scene"))
            or path == "/watchlist"
        )
        if request.method == "POST" and path.endswith("/view"):
            from saakshya.live.snapshot import local_media_url
            parts = path.strip("/").split("/")
            blocked = len(parts) != 3 or parts[0] != "cameras" or not local_media_url(parts[1])
        if blocked:
            return JSONResponse({"detail": {"code": "PUBLIC_DEMO_BOUNDARY", "message": "External integrations and estate changes are disabled in the public synthetic sandbox."}}, status_code=403)
        response = await call_next(request)
        response.headers["X-SAAKSHYA-Demo"] = "original-app-synthetic-corpus"
        return response

    @app.get("/submission/health", include_in_schema=False)
    async def deployment_health():
        return {"status": "ok", "mode": "original-app-synthetic-corpus", "government_connected": False}

    return app
