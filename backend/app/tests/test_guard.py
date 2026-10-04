import pytest

from app.modules.guard import (
    GuardError, claimer_gate, fulfill_gate, party_role,
)


def test_party_role_five_shapes():
    assert party_role("alice", "alice", "bob") == "claimer"
    assert party_role("bob", "alice", "bob") == "buyer"
    assert party_role("eve", "alice", "bob") is None
    assert party_role("", "alice", "bob") is None
    assert party_role("bob", "alice", None) is None


def test_fulfill_gate():
    fulfill_gate("alice", "alice", "bob")
    fulfill_gate("bob", "alice", "bob")
    for actor in ["eve", ""]:
        with pytest.raises(GuardError) as ei:
            fulfill_gate(actor, "alice", "bob")
        assert ei.value.code == "not_party"


def test_claimer_gate():
    claimer_gate("alice", "alice")
    for actor, current in [("bob", "alice"), ("eve", "alice"), ("", "alice"), ("alice", None)]:
        with pytest.raises(GuardError) as ei:
            claimer_gate(actor, current)
        assert ei.value.code == "not_claimer"
