from app.modules.projection import parties_view, project_wish, project_wishes


def test_parties_view():
    assert parties_view("alice", None) == {"claimer": "alice", "buyer": None, "dual": False}
    assert parties_view("alice", "bob")["dual"] is True


def test_project_wish_columns_and_parties():
    row = {
        "id": 1, "title": "t", "note": "n", "status": "claimed",
        "claimer": "alice", "buyer": "bob", "claimed_at": None,
        "expires_at": None, "data_quality": "clean",
    }
    d = project_wish(row)
    assert d["id"] == 1 and d["buyer"] == "bob"
    assert d["parties"] == {"claimer": "alice", "buyer": "bob", "dual": True}


def test_project_wish_missing_buyer_falls_back_none():
    d = project_wish({"id": 2, "claimer": "alice"})
    assert d["buyer"] is None
    assert d["parties"]["dual"] is False


def test_project_wishes():
    assert project_wishes([{"id": 1}])[0]["id"] == 1
