import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.ai import chatflow, edits
from app.deps import get_conn
from app.main import app
from tests.test_ai import Scripted, text

DAY = "2026-01-02"


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Rice, white, cooked', 1)")  # id 1
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Broccoli, cooked', 1)")  # id 2
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES (?, 'lunch', 1, 200)", (DAY,))  # id 1
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES (?, 'lunch', 2, 100)", (DAY,))  # id 2
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2025-12-31', 'lunch', 1, 50)")  # id 3
    c.commit()
    return c


def test_logged_for_prompt_lists_ids_for_day_only(conn):
    assert edits.logged_for_prompt(conn, DAY) == [
        "#1 Rice, white, cooked 200 g (lunch)", "#2 Broccoli, cooked 100 g (lunch)"]


def test_build_validates_ids_ranges_and_meals(conn):
    changes = [
        {"entry_id": 1, "action": "grams", "grams": 150},
        {"entry_id": 2, "action": "delete"},
        {"entry_id": 3, "action": "delete"},        # other day: rejected
        {"entry_id": 99, "action": "delete"},       # unknown id
        {"entry_id": 1, "action": "grams", "grams": 0},   # duplicate / bad range
        {"entry_id": 2, "action": "meal", "meal": "brunch"},  # bad meal
        {"entry_id": 1, "action": "meal", "meal": "dinner"},  # duplicate entry 1
    ]
    out, dropped = edits.build(conn, changes, DAY)
    assert [(p["entry_id"], p["action"]) for p in out] == [(1, "grams"), (2, "delete")]
    assert out[0]["new_grams"] == 150.0 and out[0]["old_grams"] == 200.0
    assert dropped == 5


def test_apply_changes_and_skips_missing(conn):
    out, _ = edits.build(conn, [{"entry_id": 1, "action": "grams", "grams": 150},
                                {"entry_id": 2, "action": "delete"}], DAY)
    conn.execute("DELETE FROM intake_log WHERE id = 2")  # removed meanwhile
    conn.commit()
    results = edits.apply(conn, DAY, out)
    assert results == [{"entry_id": 1, "result": "done"}, {"entry_id": 2, "result": "skipped"}]
    assert conn.execute("SELECT grams FROM intake_log WHERE id = 1").fetchone()[0] == 150.0


def test_chat_turn_builds_pending_edit_proposal(conn):
    conv = conn.execute("INSERT INTO conversations (title) VALUES ('New chat')").lastrowid
    conn.commit()
    parsed = {"intent": "edit", "changes": [{"entry_id": 1, "action": "grams", "grams": 150},
                                            {"entry_id": 2, "action": "delete"}]}
    provider = Scripted([text(json.dumps(parsed))])
    events = list(chatflow.run_turn(conn, provider, conv, "rice 150 g and drop the broccoli", DAY))
    msg = events[-1]["message"]
    assert msg["meta"]["kind"] == "edit" and msg["meta"]["status"] == "pending"
    assert msg["meta"]["day"] == DAY and len(msg["meta"]["changes"]) == 2
    # nothing changed yet
    assert conn.execute("SELECT COUNT(*) FROM intake_log WHERE log_date = ?", (DAY,)).fetchone()[0] == 2


def test_confirm_endpoint_applies_chosen_changes_once(conn):
    conv = conn.execute("INSERT INTO conversations (title) VALUES ('New chat')").lastrowid
    conn.execute("INSERT INTO messages (conversation_id, role, content, meta) VALUES (?, 'assistant', 'x', ?)",
                 (conv, json.dumps({"kind": "edit", "day": DAY, "status": "pending", "changes": [
                     {"entry_id": 1, "action": "grams", "new_grams": 150.0, "name": "Rice"},
                     {"entry_id": 2, "action": "delete", "name": "Broccoli"}]})))
    conn.commit()
    mid = conn.execute("SELECT id FROM messages").fetchone()[0]
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        r = client.post(f"/api/messages/{mid}/confirm-edits", json={"include": [0]})
        assert r.status_code == 200 and r.json()["status"] == "saved"
        assert conn.execute("SELECT grams FROM intake_log WHERE id = 1").fetchone()[0] == 150.0
        assert conn.execute("SELECT COUNT(*) FROM intake_log WHERE id = 2").fetchone()[0] == 1  # not chosen
        assert client.post(f"/api/messages/{mid}/confirm-edits", json={}).status_code == 409  # handled once
    finally:
        app.dependency_overrides.clear()
