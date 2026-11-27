# Original application deployment

This wrapper serves the original `ui/` files and FastAPI implementation in `src/saakshya`. It adds demonstration labels and an optional temporary demo-access button inside the original sign-in screen. It does not replace the interface or fabricate API responses.

The shipped SQLite snapshot comes from the original synthetic-media generator and analytics seeder, run on 27 November 2026 at one sampled frame per second. The six videos were actually decoded and processed. The resulting 261 observations and 206 observations with plate values are execution counts, not an accuracy score. Eight cameras are registered: six corpus cameras and two unmeasured own-feed placeholders. Camera grading, search, role/purpose checks, cases, evidence and audit use the original implementations.

## Start locally

From the repository root, with Python 3.12 or newer:

```sh
uv venv --python 3.12
uv pip install -e '.[dev]'
PYTHONPATH=src:. .venv/bin/python -m uvicorn deployment.app:build --factory --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`. Select a demonstration role, choose **Use demo access**, then **Enter the workspace**. Try the synthetic plate `GJ18JX7786`. The estate administrator is refused vehicle searches by the original authorisation service.

```sh
PYTHONPATH=src:. .venv/bin/python -m pytest tests/deployment/test_public_original_app.py -q
docker build -t saakshya-build2036 .
docker run --rm -p 8080:8080 saakshya-build2036
```

The container runs as an unprivileged user. Its default port is 8080 and it respects `PORT`. `/submission/health` reports deployment readiness. `requirements-runtime.txt` records dependency versions exercised in the Linux review environment. Optional analytics/model packages remain in the original `pyproject.toml`; the public server reads the processed corpus and opens local recordings on demand. It does not run a continuous model worker or access a government feed. The historical films separately demonstrate the earlier vision implementation.

## Recreate the corpus snapshot

Use a separate local demonstration database; never pass a government database to this packaging script.

```sh
uv pip install -e '.[dev,analytics]'
.venv/bin/python tools/sandbox/make_media.py
.venv/bin/python tools/demo/seed.py --db sqlite:///var/demo.db --fps 1
PYTHONPATH=src .venv/bin/python deployment/prepare_snapshot.py --source-root . --database var/demo.db
```

The original seeder prints newly minted tokens to its terminal. Do not commit that output. The packaging script refuses government/unlabelled camera domains, strips issued token hashes from the distributed snapshot and extracts unenhanced preview frames at actual stored observation timestamps. Previews are labelled viewing material, not sealed evidence. The original seeder's six evidence records attest metadata only; the UI reports that scope when verification runs.

## Hosted sandbox behavior

Authentication remains enabled. Temporary public demo identities use the original token service and server-side roles. The public instance cannot change camera integrations, connect arbitrary streams or invoke external scene analysis. Local corpus viewing remains available. Queries and case actions are written into the demonstration audit log, and instance state can reset at restart. Use fictional case details only.

The proposed cloud configuration is one instance at most, request-based billing and scaling to zero while idle. A final public application URL will be added after deployment and end-to-end verification. The separately hosted [video page](https://khamirdesai.github.io/saakshya-build2036/videos/) contains the unchanged original films.
