import pytest

from app import db
from app.ai import chatflow, providers


class Failing(providers.Provider):
    def __init__(self):
        pass

    def complete(self, system, messages, tools_):
        raise providers.ProviderError("timed out after 300 s")


def test_failed_turn_saves_error_as_assistant_message():
    conn = db.connect(":memory:")
    conv_id = conn.execute("INSERT INTO conversations (title) VALUES ('New chat')").lastrowid
    conn.commit()

    with pytest.raises(providers.ProviderError):
        list(chatflow.run_turn(conn, Failing(), conv_id, "garlic broccoli shrimp", "2026-11-16"))

    rows = conn.execute("SELECT role, content, meta FROM messages WHERE conversation_id = ? ORDER BY id",
                        (conv_id,)).fetchall()
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["content"] == "Error: timed out after 300 s"
    assert '"kind": "error"' in rows[1]["meta"]
