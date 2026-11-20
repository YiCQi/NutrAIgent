"""Change or delete today's logged intake from the chat.

The model only names entry ids from the list it was given; everything else (existence, date, ranges, meal
names) is checked here. Nothing changes until the user confirms the proposal card.
"""
import sqlite3

MEALS = ("breakfast", "lunch", "dinner", "snack", "other")
MAX_GRAMS = 5000.0
MAX_CHANGES = 20


def logged_for_prompt(conn: sqlite3.Connection, day: str) -> list[str]:
    """Entries with ids, for the parser: '#12 Rice, white, cooked 150 g (lunch)'."""
    return [f"#{r['id']} {r['name']} {r['grams']:g} g ({r['meal']})" for r in conn.execute(
        "SELECT l.id, f.name, l.grams, l.meal FROM intake_log l JOIN foods f ON f.id = l.food_id "
        "WHERE l.log_date = ? ORDER BY l.id", (day,))]


def build(conn: sqlite3.Connection, changes, day: str) -> tuple[list[dict], int]:
    """Validate model changes against today's entries. Returns (proposals, dropped count)."""
    rows = {r["id"]: r for r in conn.execute(
        "SELECT l.id, l.grams, l.meal, f.name FROM intake_log l JOIN foods f ON f.id = l.food_id "
        "WHERE l.log_date = ?", (day,))}
    out, dropped, seen = [], 0, set()
    for c in (changes or [])[:MAX_CHANGES]:
        eid = c.get("entry_id") if isinstance(c, dict) else None
        action = c.get("action") if isinstance(c, dict) else None
        if not isinstance(eid, int) or isinstance(eid, bool) or eid not in rows or eid in seen:
            dropped += 1
            continue
        r = rows[eid]
        p = {"entry_id": eid, "name": r["name"], "action": action, "old_grams": r["grams"], "old_meal": r["meal"],
             "new_grams": None, "new_meal": None}
        if action == "delete":
            pass
        elif action == "grams":
            g = c.get("grams")
            if not isinstance(g, (int, float)) or isinstance(g, bool) or not 0 < g <= MAX_GRAMS:
                dropped += 1
                continue
            p["new_grams"] = float(g)
        elif action == "meal":
            if c.get("meal") not in MEALS:
                dropped += 1
                continue
            p["new_meal"] = c["meal"]
        else:
            dropped += 1
            continue
        seen.add(eid)
        out.append(p)
    return out, dropped


def apply(conn: sqlite3.Connection, day: str, changes: list[dict]) -> list[dict]:
    """Apply confirmed changes in one transaction. Entries that no longer exist for the day are skipped."""
    results = []
    try:
        for p in changes:
            exists = conn.execute("SELECT 1 FROM intake_log WHERE id = ? AND log_date = ?",
                                  (p["entry_id"], day)).fetchone()
            if exists is None:
                results.append({"entry_id": p["entry_id"], "result": "skipped"})
                continue
            if p["action"] == "delete":
                conn.execute("DELETE FROM intake_log WHERE id = ?", (p["entry_id"],))
            elif p["action"] == "grams":
                conn.execute("UPDATE intake_log SET grams = ? WHERE id = ?", (p["new_grams"], p["entry_id"]))
            elif p["action"] == "meal":
                conn.execute("UPDATE intake_log SET meal = ? WHERE id = ?", (p["new_meal"], p["entry_id"]))
            results.append({"entry_id": p["entry_id"], "result": "done"})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return results
