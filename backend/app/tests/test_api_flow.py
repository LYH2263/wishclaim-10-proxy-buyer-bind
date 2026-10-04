"""End-to-end HTTP flow for the claimer/buyer split."""
from datetime import datetime, timedelta, timezone

import pytest


def make_wish(client, title="t"):
    r = client.post("/api/wishes", json={"title": title, "note": "n"})
    assert r.status_code == 200
    return r.json()["id"]


def claim_dual(client, wid, claimer="alice", buyer="bob"):
    body = {"claimer": claimer}
    if buyer is not None:
        body["buyer"] = buyer
    return client.post(f"/api/wishes/{wid}/claim", json=body)


def by_id(rows, wid):
    return next(r for r in rows if r["id"] == wid)


def test_dual_binding_projected_everywhere(client):
    wid = make_wish(client)
    r = claim_dual(client, wid)
    assert r.status_code == 200
    assert r.json()["claimer"] == "alice" and r.json()["buyer"] == "bob"
    assert r.json()["parties"] == {"claimer": "alice", "buyer": "bob", "dual": True}

    wall = by_id(client.get("/api/wishes").json(), wid)
    assert wall["parties"]["dual"] is True
    detail = client.get(f"/api/wishes/{wid}").json()
    assert detail["buyer"] == "bob"
    mine_alice = client.get("/api/mine?actor=alice").json()
    mine_bob = client.get("/api/mine?actor=bob").json()
    assert by_id(mine_alice, wid)["claimer"] == "alice"
    assert by_id(mine_bob, wid)["buyer"] == "bob"


@pytest.mark.parametrize("body", [{"claimer": "alice", "buyer": ""}, {"claimer": "alice"}])
def test_empty_buyer_degrades_to_claimer_only(client, body):
    wid = make_wish(client)
    r = client.post(f"/api/wishes/{wid}/claim", json=body)
    assert r.status_code == 200
    assert r.json()["buyer"] is None and r.json()["parties"]["dual"] is False


def test_binding_rejections(client):
    wid = make_wish(client)
    r = client.post(f"/api/wishes/{wid}/claim", json={"claimer": "alice", "buyer": "alice"})
    assert r.status_code == 400 and r.json()["detail"] == "buyer_equal_claimer"

    for bad_buyer in ["   ", "a\tb", "x" * 33]:
        r = client.post(f"/api/wishes/{wid}/claim", json={"claimer": "alice", "buyer": bad_buyer})
        assert r.status_code == 400 and r.json()["detail"] == "buyer_dirty", bad_buyer

    for bad_claimer in ["", "  "]:
        r = client.post(f"/api/wishes/{wid}/claim", json={"claimer": bad_claimer})
        assert r.status_code == 400 and r.json()["detail"] == "claimer_empty", bad_claimer


def test_fulfill_gate_three_parties(client):
    w1, w2 = make_wish(client, "a"), make_wish(client, "b")
    assert claim_dual(client, w1).status_code == 200
    assert claim_dual(client, w2).status_code == 200

    assert client.post(f"/api/wishes/{w1}/fulfill", json={"actor": "alice"}).status_code == 200
    assert client.post(f"/api/wishes/{w2}/fulfill", json={"actor": "bob"}).status_code == 200

    w3 = make_wish(client, "c")
    claim_dual(client, w3)
    r = client.post(f"/api/wishes/{w3}/fulfill", json={"actor": "eve"})
    assert r.status_code == 403 and r.json()["detail"] == "not_party"
    r = client.post(f"/api/wishes/{w3}/fulfill", json={})
    assert r.status_code == 403 and r.json()["detail"] == "not_party"


def test_release_gate_and_clears_buyer(client):
    wid = make_wish(client)
    claim_dual(client, wid)

    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "bob"})
    assert r.status_code == 403 and r.json()["detail"] == "not_claimer"
    untouched = client.get(f"/api/wishes/{wid}").json()
    assert untouched["status"] == "claimed" and untouched["buyer"] == "bob"

    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "alice"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "released"
    assert d["claimer"] is None and d["buyer"] is None
    assert d["claimed_at"] is None and d["expires_at"] is None
    assert d["parties"] == {"claimer": None, "buyer": None, "dual": False}


def test_ttl_sweep_clears_buyer(client):
    # Seed row "过期锁样例" (ghost/zombie) exists and is already expired.
    from app.db import connect
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    c = connect()
    c.execute(
        "INSERT INTO wishes(title,note,status,claimer,buyer,claimed_at,expires_at,data_quality)"
        " VALUES (?,?,?,?,?,?,?,?)",
        ("手工过期", "", "claimed", "carol", "dave", past, past, "clean"),
    )
    c.commit(); c.close()

    rows = client.get("/api/wishes").json()
    hand = next(r for r in rows if r["title"] == "手工过期")
    assert hand["status"] == "open" and hand["claimer"] is None and hand["buyer"] is None
    ghost = next(r for r in rows if r["title"] == "过期锁样例")
    assert ghost["status"] == "open" and ghost["buyer"] is None


def test_transfer_flow(client):
    wid = make_wish(client)
    claim_dual(client, wid)
    old = client.get(f"/api/wishes/{wid}").json()

    for actor in ["bob", "eve"]:
        r = client.post(f"/api/wishes/{wid}/transfer", json={"actor": actor, "new_claimer": "dora"})
        assert r.status_code == 403 and r.json()["detail"] == "not_claimer", actor

    r = client.post(f"/api/wishes/{wid}/transfer", json={"actor": "alice", "new_claimer": " dora "})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "claimed" and d["claimer"] == "dora" and d["buyer"] is None
    assert d["claimed_at"] >= old["claimed_at"] and d["expires_at"] > old["expires_at"]

    # Old buyer loses rights once the binding is cleared.
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert r.status_code == 403 and r.json()["detail"] == "not_party"

    for body, code in [
        ({"actor": "dora", "new_claimer": "dora"}, "same_claimer"),
        ({"actor": "dora", "new_claimer": "  "}, "claimer_empty"),
        ({"actor": "dora", "new_claimer": "a\tb"}, "claimer_dirty"),
    ]:
        r = client.post(f"/api/wishes/{wid}/transfer", json=body)
        assert r.status_code == 400 and r.json()["detail"] == code, body


def test_done_keeps_party_snapshot(client):
    wid = make_wish(client)
    claim_dual(client, wid)
    assert client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"}).status_code == 200
    row = by_id(client.get("/api/done").json(), wid)
    assert row["claimer"] == "alice" and row["buyer"] == "bob"
    assert row["parties"]["dual"] is True


def test_mine_params_compat(client):
    wid = make_wish(client)
    claim_dual(client, wid)
    assert by_id(client.get("/api/mine?claimer=alice").json(), wid)
    assert by_id(client.get("/api/mine?actor=bob").json(), wid)
    assert client.get("/api/mine").status_code == 400
    assert client.get("/api/mine?actor=%20%20").status_code == 400
    assert all(r["id"] != wid for r in client.get("/api/mine?actor=eve").json())


def test_concurrent_second_claim_locked(client):
    wid = make_wish(client)
    assert claim_dual(client, wid, claimer="alice", buyer="bob").status_code == 200
    r = claim_dual(client, wid, claimer="eve")
    assert r.status_code == 409 and r.json()["detail"] == "locked"
