import pytest

from app.modules.binding import (
    BindingError, bind_parties, clean_buyer, clean_claimer, clean_new_claimer,
    has_control_char, normalize_name,
)


def test_normalize_name():
    assert normalize_name(None) == ""
    assert normalize_name("  alice  ") == "alice"
    assert normalize_name("a b") == "a b"


def test_has_control_char():
    assert has_control_char("a\tb")
    assert has_control_char("x\x00y")
    assert not has_control_char("alice")


def test_clean_claimer_accepts_boundary_len():
    assert clean_claimer("a" * 32) == "a" * 32


@pytest.mark.parametrize("raw", ["", None, "   "])
def test_clean_claimer_empty(raw):
    with pytest.raises(BindingError) as ei:
        clean_claimer(raw)
    assert ei.value.code == "claimer_empty"


@pytest.mark.parametrize("raw", ["a\tb", "x" * 33])
def test_clean_claimer_dirty(raw):
    with pytest.raises(BindingError) as ei:
        clean_claimer(raw)
    assert ei.value.code == "claimer_dirty"


@pytest.mark.parametrize("raw", [None, ""])
def test_clean_buyer_absent_is_none(raw):
    assert clean_buyer(raw, "alice") is None


@pytest.mark.parametrize("raw", ["   ", "a\tb", "x" * 33])
def test_clean_buyer_dirty(raw):
    with pytest.raises(BindingError) as ei:
        clean_buyer(raw, "alice")
    assert ei.value.code == "buyer_dirty"


def test_clean_buyer_equal_claimer():
    with pytest.raises(BindingError) as ei:
        clean_buyer("  alice ", "alice")
    assert ei.value.code == "buyer_equal_claimer"


def test_clean_buyer_valid_stripped():
    assert clean_buyer("  bob ", "alice") == "bob"


def test_bind_parties_single_and_dual():
    assert bind_parties("alice", None) == ("alice", None)
    assert bind_parties(" alice ", " bob ") == ("alice", "bob")


def test_clean_new_claimer():
    assert clean_new_claimer(" dora ", "alice") == "dora"
    with pytest.raises(BindingError) as ei:
        clean_new_claimer("alice", "alice")
    assert ei.value.code == "same_claimer"
    with pytest.raises(BindingError) as ei:
        clean_new_claimer("  ", "alice")
    assert ei.value.code == "claimer_empty"
