"""One chat turn: persist messages, route to fast log-parsing or the tool agent, stream events."""
import json
import sqlite3

from . import agent, nllog, tools
from .providers import Provider

HISTORY_LIMIT = 20


def _save(conn, conv_id, role, content, meta=None):
    cur = conn.execute("INSERT INTO messages (conversation_id, role, content, meta) VALUES (?,?,?,?)",
                       (conv_id, role, content, json.dumps(meta or {}, default=str)))
    conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
    conn.commit()
    return cur.lastrowid


def message_dict(row) -> dict:
    return {"id": row["id"], "role": row["role"], "content": row["content"],
            "meta": json.loads(row["meta"] or "{}"), "created_at": row["created_at"]}


def run_turn(conn: sqlite3.Connection, provider: Provider, conv_id: int, content: str, today: str):
    """Generator of events; ends with {'type':'done','message':{...}}."""
    _save(conn, conv_id, "user", content)
    conn.execute("UPDATE conversations SET title = ? WHERE id = ? AND title = 'New chat'",
                 (content.strip().replace(chr(10), " ")[:40] or "New chat", conv_id))
    conn.commit()
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                        (conv_id, HISTORY_LIMIT)).fetchall()
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    yield {"type": "status", "text": "Understanding your message…"}
    parsed = nllog.parse(provider, history, today)

    if parsed["intent"] == "log" and parsed.get("items"):
        proposals = []
        for kind, val in nllog.build_proposals(conn, parsed, today):
            if kind == "match":
                yield {"type": "status", "text": f"Matching “{val}” in the food database…"}
            else:
                proposals = val
        n = len(proposals)
        reply = f"Recognised {n} item{'s' if n != 1 else ''}. Review the matches and amounts below, then confirm."
        meta = {"proposals": proposals, "status": "pending"}
    else:
        ctx = tools.Context(conn=conn, today=today)
        reply, trace = "", []
        for ev in agent.iter_chat(ctx, provider, history):
            if ev["type"] == "done":
                reply, trace = ev["reply"], ev["trace"]
            elif ev["type"] == "tool":
                yield {"type": "status", "text": _tool_label(ev)}
            elif ev["type"] == "model":
                yield {"type": "status",
                       "text": "Thinking…" if ev["step"] == 1 else f"Thinking (round {ev['step']})…"}
        meta = {"trace": trace}
    mid = _save(conn, conv_id, "assistant", reply, meta)
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    yield {"type": "done", "message": message_dict(row)}


def _tool_label(ev) -> str:
    i = ev.get("input") or {}
    return {"search_foods": f"Searching foods: {i.get('query', '')}", "get_food": "Reading food details",
            "get_targets": "Reading your targets",
            "get_daily_intake": f"Reading intake for {i.get('date', 'the day')}"}.get(ev["tool"], ev["tool"])
