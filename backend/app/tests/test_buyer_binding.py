from app.modules.buyer_binding import (
    DIRTY,
    SAME,
    NOT_PARTICIPANT,
    bind_check,
    classify_buyer,
    fulfill_guard,
    buyer_slot,
    people_line,
    project,
)

# ---------- 绑定轨 ----------

def test_classify_none_and_empty_mean_unbound():
    assert classify_buyer(None) == (None, None)
    assert classify_buyer("") == (None, None)

def test_classify_trims_name():
    assert classify_buyer("  bob  ") == ("bob", None)

def test_classify_whitespace_only_is_dirty():
    # 脏 buyer：必须报错，不能静默回退仅 claimer
    assert classify_buyer("   ") == (None, DIRTY)
    assert classify_buyer("\t") == (None, DIRTY)

def test_bind_check_rejects_same_person():
    # 拍板 1：buyer 与 claimer 不可相同（带空格也算同一人）
    assert bind_check("alice", "alice") == {"ok": False, "reason": SAME}
    assert bind_check("alice", " alice ")["reason"] == SAME

def test_bind_check_allows_distinct_buyer_and_unbound():
    assert bind_check("alice", "bob")["ok"] is True
    assert bind_check("alice", None)["ok"] is True

# ---------- 门禁轨 ----------

def test_guard_allows_claimer_and_buyer():
    # 拍板 2：二人皆可
    assert fulfill_guard("alice", "alice", "bob") == {"ok": True, "reason": "", "role": "claimer"}
    assert fulfill_guard("bob", "alice", "bob") == {"ok": True, "reason": "", "role": "buyer"}

def test_guard_rejects_stranger_and_blank_actor():
    assert fulfill_guard("carol", "alice", "bob")["reason"] == NOT_PARTICIPANT
    assert fulfill_guard(None, "alice", "bob")["reason"] == NOT_PARTICIPANT
    assert fulfill_guard("  ", "alice", "bob")["reason"] == NOT_PARTICIPANT

def test_guard_unbound_track_only_claimer():
    # buyer 空（旧轨）：只有 claimer 可核销
    assert fulfill_guard("alice", "alice", None)["role"] == "claimer"
    assert fulfill_guard("bob", "alice", None)["reason"] == NOT_PARTICIPANT

# ---------- 投影轨 ----------

def test_buyer_slot():
    assert buyer_slot(None) is None
    assert buyer_slot("   ") is None
    assert buyer_slot(" bob ") == "bob"

def test_people_line_falls_back_to_claimer_only():
    # buyer 空则退回改造前仅 claimer
    assert people_line("alice", None) == "alice"
    assert people_line("alice", "   ") == "alice"
    assert people_line(None, None) == "—"

def test_people_line_pins_both():
    assert people_line("alice", "bob") == "alice / 代买 bob"

def test_project_adds_people_and_keeps_fields():
    p = project({"id": 1, "claimer": "alice", "buyer": "bob", "status": "claimed"})
    assert p["people"] == "alice / 代买 bob"
    assert p["claimer"] == "alice" and p["buyer"] == "bob"
