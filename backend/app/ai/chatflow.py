"""One chat turn: persist messages, route to fast log-parsing or the tool agent, stream events."""
import json
import sqlite3

from .. import recipes
from . import agent, edits, nllog, tools
from .providers import Provider, ProviderError

HISTORY_LIMIT = 20
RUNNING: set[int] = set()  # conversation ids with a turn in progress (survives client disconnects)


def _save(conn, conv_id, role, content, meta=None):
    cur = conn.execute("INSERT INTO messages (conversation_id, role, content, meta) VALUES (?,?,?,?)",
                       (conv_id, role, content, json.dumps(meta or {}, default=str)))
    conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
    conn.commit()
    return cur.lastrowid


def message_dict(row) -> dict:
    return {"id": row["id"], "role": row["role"], "content": row["content"],
            "meta": json.loads(row["meta"] or "{}"), "created_at": row["created_at"]}


def run_turn(conn: sqlite3.Connection, provider: Provider, conv_id: int, content: str, today: str,
             lang: str = "en"):
    """Generator of events; ends with {'type':'done','message':{...}}.

    On failure, the error is saved as an assistant message (so it survives client disconnects
    and is visible after a reload), then re-raised for the live stream.
    """
    try:
        yield from _run_turn(conn, provider, conv_id, content, today, lang)
    except Exception as e:
        msg = str(e) if isinstance(e, ProviderError) else f"internal error: {type(e).__name__}"
        _save(conn, conv_id, "assistant", f"Error: {msg}", {"kind": "error", "error": msg})
        raise


def _run_turn(conn: sqlite3.Connection, provider: Provider, conv_id: int, content: str, today: str,
              lang: str = "en"):
    _save(conn, conv_id, "user", content)
    conn.execute("UPDATE conversations SET title = ? WHERE id = ? AND title = 'New chat'",
                 (content.strip().replace(chr(10), " ")[:40] or "New chat", conv_id))
    conn.commit()
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                        (conv_id, HISTORY_LIMIT)).fetchall()
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    yield {"type": "status", "key": "understanding"}
    logged = edits.logged_for_prompt(conn, today)[-40:]
    parsed = nllog.parse(provider, history, today, lang, recipes.names(conn), logged)

    if parsed["intent"] == "ask":
        reply, meta = parsed["question"].strip(), {"kind": "ask"}
    elif parsed["intent"] == "edit":
        changes, dropped = edits.build(conn, parsed["changes"], today)
        if changes:
            n = len(changes)
            reply = f"Found {n} change{'s' if n != 1 else ''} to today's log. Review, then confirm."
            meta = {"kind": "edit", "day": today, "changes": changes, "status": "pending"}
        else:
            reply, meta = "I could not match that to today's logged food. Tell me the food name or the amount.", {"kind": "ask"}
    elif parsed["intent"] == "log" and parsed.get("items"):
        proposals = []
        for kind, val in nllog.build_proposals(conn, parsed, today):
            if kind == "match":
                yield {"type": "status", "key": "matching", "arg": val}
            else:
                proposals = val
        n = len(proposals)
        reply = f"Recognised {n} item{'s' if n != 1 else ''}. Review the matches and amounts below, then confirm."
        meta = {"kind": "log", "count": n, "proposals": proposals, "status": "pending"}
    else:
        ctx = tools.Context(conn=conn, today=today)
        reply, trace = "", []
        for ev in agent.iter_chat(ctx, provider, history, lang):
            if ev["type"] == "done":
                reply, trace = ev["reply"], ev["trace"]
            elif ev["type"] == "tool":
                yield {"type": "status", "key": "tool_" + ev["tool"], "arg": _tool_arg(ev)}
            elif ev["type"] == "model":
                yield {"type": "status", "key": "thinking", "arg": ev["step"]}
        meta = {"trace": trace}
    mid = _save(conn, conv_id, "assistant", reply, meta)
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    yield {"type": "done", "message": message_dict(row)}


def _tool_arg(ev) -> str:
    i = ev.get("input") or {}
    return str(i.get("query") or i.get("date") or "")
