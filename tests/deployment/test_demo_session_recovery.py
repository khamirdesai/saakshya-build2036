"""Regression check for an expired public-demo session in the original UI."""
import shutil
import subprocess

import pytest

from deployment.app import prepare_ui


def test_expired_session_reopens_demo_gate_without_affecting_other_statuses(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the demo UI recovery")
    prepare_ui(tmp_path)
    script = r'''
const fs = require("fs");
const assert = require("assert/strict");
const source = fs.readFileSync(process.argv[1], "utf8");
const match = source.match(
  /\/\/ BEGIN public demo session recovery\n([\s\S]*?)  \/\/ END public demo session recovery/
);
assert.ok(match, "recovery code is present in wrapped UI");
const recover = new Function("res", "state", "sessionStorage", "document", match[1]);
for (const status of [200, 401, 403]) {
  const state = { token: "expired-example", principal: { role: "supervisor" } };
  const ids = ["#gate", "#who", "#officer-name", "#btn-token", "#public-demo-status"];
  const elements = Object.fromEntries(ids.map(id => [id, { hidden: true, textContent: "" }]));
  const removed = [];
  const storage = { removeItem: key => removed.push(key) };
  const document = { querySelector: id => elements[id] };
  recover({ status }, state, storage, document);
  if (status === 401) {
    assert.equal(state.token, "");
    assert.equal(state.principal, null);
    assert.equal(elements["#gate"].hidden, false);
    assert.match(elements["#public-demo-status"].textContent, /Use demo access/);
    assert.deepEqual(removed, ["saakshya.token"]);
  } else {
    assert.equal(state.token, "expired-example");
    assert.equal(elements["#gate"].hidden, true);
    assert.deepEqual(removed, []);
  }
}
'''
    subprocess.run([node, "-e", script, str(tmp_path / "app.js")], check=True)
