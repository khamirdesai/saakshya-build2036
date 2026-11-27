"""Exercise the original API through its public-demonstration packaging."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from deployment.app import ROOT, SNAPSHOT, build


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SAAKSHYA_DEMO_RUNTIME", str(tmp_path / "runtime"))
    with TestClient(build()) as c:
        yield c


def demo_headers(client, role="supervisor"):
    response = client.post("/submission/demo-session", params={"role": role})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    return {"Authorization": "Bearer " + data["token"],
            "X-Case-Id": data["case_id"], "X-Purpose": data["purpose"]}


def test_original_api_authentication_and_purpose_are_enforced(client):
    assert client.get("/search", params={"plate": "GJ18JX7786"}).status_code == 401
    headers = demo_headers(client)
    result = client.get("/search", params={"plate": "GJ18JX7786"}, headers=headers)
    assert result.status_code == 200
    assert result.json()["stage_counts"]["exact"] == 7
    assert client.get("/search", params={"plate": "GJ18JX7786"},
                      headers={"Authorization": headers["Authorization"]}).status_code == 400


def test_real_role_controls_refuse_an_administrator_search(client):
    admin = demo_headers(client, "admin")
    assert client.get("/search", params={"plate": "GJ18JX7786"}, headers=admin).status_code == 403
    assert client.post("/submission/demo-session?role=not-a-role").status_code == 400


def test_original_evidence_and_audit_chains_survive_relocation(client):
    response = client.get("/evidence/chain/verify?fresh=1", headers=demo_headers(client))
    assert response.status_code == 200
    assert response.json()["verified"] is True
    state = client.app.state.saakshya
    assert state.store.verify_audit_chain() == (True, None)
    assert state.store.stats()["observations"] == 261
    assert state.store.stats()["cameras"] == 8


def test_public_demo_cannot_change_estate_or_connect_external_streams(client):
    headers = demo_headers(client, "admin")
    for path in ["/registry/cameras/import", "/cameras/not-a-source/view", "/cameras/C-014/whep", "/copilot/scene"]:
        result = client.post(path, json={}, headers=headers)
        assert result.status_code == 403
        assert result.json()["detail"]["code"] == "PUBLIC_DEMO_BOUNDARY"


def test_original_ui_and_demo_labels_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Public prototype demo" in page.text
    assert 'id="search-form"' in page.text
    assert 'id="view-investigate"' in page.text
    assert 'id="public-demo-access"' in page.text
    assert client.get("/ui/style.css").content == (ROOT / "ui/style.css").read_bytes()
    health = client.get("/submission/health").json()
    assert health["government_connected"] is False


def test_distributed_snapshot_has_no_issued_tokens():
    with sqlite3.connect(SNAPSHOT / "demo.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM api_tokens").fetchone()[0] == 0
