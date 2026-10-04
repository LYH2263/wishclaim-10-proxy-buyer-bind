import os
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.main import app
    with TestClient(app) as c:
        yield c

def _create(client, title="杯子"):
    r = client.post("/api/wishes", json={"title": title, "note": "陶瓷"})
    return r.json()["id"]

def _claim(client, wid, claimer, buyer=None):
    body = {"claimer": claimer}
    if buyer is not None:
        body["buyer"] = buyer
    return client.post(f"/api/wishes/{wid}/claim", json=body)

# ---------- 绑定 ----------

def test_claim_binds_buyer_in_separate_fields(client):
    wid = _create(client)
    r = _claim(client, wid, "alice", "bob")
    assert r.status_code == 200
    assert r.json()["claimer"] == "alice" and r.json()["buyer"] == "bob"
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["claimer"] == "alice" and w["buyer"] == "bob"
    assert w["people"] == "alice / 代买 bob"

def test_claim_without_buyer_falls_back_to_claimer_only(client):
    wid = _create(client)
    assert _claim(client, wid, "alice").status_code == 200
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["buyer"] is None and w["people"] == "alice"

def test_dirty_buyer_must_fail_claim(client):
    # 脏 buyer：认领失败，锁不得落下、不得静默回退仅 claimer
    wid = _create(client)
    r = _claim(client, wid, "alice", "   ")
    assert r.status_code == 400 and r.json()["detail"] == "dirty_buyer"
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "open" and w["claimer"] is None and w["buyer"] is None

def test_buyer_same_as_claimer_rejected(client):
    # 拍板 1
    wid = _create(client)
    r = _claim(client, wid, "alice", " alice ")
    assert r.status_code == 409 and r.json()["detail"] == "buyer_same_as_claimer"
    assert client.get(f"/api/wishes/{wid}").json()["status"] == "open"

def test_buyer_name_is_trimmed(client):
    wid = _create(client)
    _claim(client, wid, "alice", "  bob  ")
    assert client.get(f"/api/wishes/{wid}").json()["buyer"] == "bob"

# ---------- 核销门禁 ----------

def test_fulfill_allowed_for_claimer_or_buyer(client):
    # 拍板 2：claimer 核销
    w1 = _create(client, "a"); _claim(client, w1, "alice", "bob")
    r1 = client.post(f"/api/wishes/{w1}/fulfill", json={"actor": "alice"})
    assert r1.status_code == 200 and r1.json()["fulfilled_by"] == "claimer"

    # buyer 核销
    w2 = _create(client, "b"); _claim(client, w2, "alice", "bob")
    r2 = client.post(f"/api/wishes/{w2}/fulfill", json={"actor": "bob"})
    assert r2.status_code == 200 and r2.json()["fulfilled_by"] == "buyer"

def test_fulfill_denied_for_stranger(client):
    wid = _create(client); _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "carol"})
    assert r.status_code == 403 and r.json()["detail"] == "not_a_participant"
    assert client.get(f"/api/wishes/{wid}").json()["status"] == "claimed"

def test_fulfill_unbound_stranger_denied(client):
    wid = _create(client); _claim(client, wid, "alice")
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert r.status_code == 403 and r.json()["detail"] == "not_a_participant"

def test_fulfill_needs_claim(client):
    wid = _create(client)
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "alice"})
    assert r.status_code == 400 and r.json()["detail"] == "need_claim"

# ---------- 三路 buyer 清空（拍板 3） ----------

def test_release_clears_buyer(client):
    wid = _create(client); _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/release", json={})
    assert r.status_code == 200
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "released" and w["claimer"] is None and w["buyer"] is None
    assert w["people"] == "—"

def test_transfer_clears_buyer_and_resets_lock(client):
    wid = _create(client); _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/transfer", json={"claimer": "carol"})
    assert r.status_code == 200 and r.json()["claimer"] == "carol" and r.json()["buyer"] is None
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["claimer"] == "carol" and w["buyer"] is None and w["status"] == "claimed"

def test_transfer_requires_active_claim(client):
    wid = _create(client)
    assert client.post(f"/api/wishes/{wid}/transfer", json={"claimer": "carol"}).status_code == 400

def test_ttl_sweep_clears_buyer(client):
    from app.db import connect
    wid = _create(client)
    c = connect()
    c.execute("UPDATE wishes SET status='claimed', claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
              ("alice", "bob", "2020-01-01T00:00:00+00:00",
               "2020-01-01T01:00:00+00:00", wid))
    c.commit(); c.close()
    # 任意读触发 sweep
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "open" and w["claimer"] is None and w["buyer"] is None

# ---------- 投影：mine / done ----------

def test_mine_lists_for_both_tracks(client):
    wid = _create(client); _claim(client, wid, "alice", "bob")
    assert any(w["id"] == wid for w in client.get("/api/mine", params={"claimer": "alice"}).json())
    assert any(w["id"] == wid for w in client.get("/api/mine", params={"claimer": "bob"}).json())
    assert client.get("/api/mine", params={"claimer": "carol"}).json() == []

def test_done_pins_two_person_snapshot_after_fulfill(client):
    # 核销后已完成页仍钉写入时二人快照
    wid = _create(client); _claim(client, wid, "alice", "bob")
    client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    done = client.get("/api/done").json()
    row = next(w for w in done if w["id"] == wid)
    assert row["status"] == "fulfilled"
    assert row["claimer"] == "alice" and row["buyer"] == "bob"
    assert row["people"] == "alice / 代买 bob"

def test_wall_pins_people(client):
    wid = _create(client); _claim(client, wid, "alice", "bob")
    row = next(w for w in client.get("/api/wishes").json() if w["id"] == wid)
    assert row["people"] == "alice / 代买 bob"
