"""Food lookup helpers shared by the REST API and the AI tools."""
import re
import sqlite3


def search(conn: sqlite3.Connection, q: str, limit: int = 25) -> list[dict]:
    """Every whitespace/comma separated token must start a word in the food name (any order)."""
    tokens = [t for t in re.split(r"[\s,\-()/]+", q.strip()) if t]

    def esc(t):
        return t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    padded = ("(' ' || replace(replace(replace(replace(replace(f.name, ',', ' '), '(', ' '), '-', ' '), ')', ' '), '/', ' '))")
    where = " AND ".join(f"{padded} LIKE ? ESCAPE '\\'" for _ in tokens) or "1=1"
    params = [f"% {esc(t)}%" for t in tokens]
    first = f"{esc(tokens[0])}%" if tokens else "%"
    rows = conn.execute(
        f"""SELECT f.id, f.name, f.state, f.edible_portion_pct, s.code AS source
           FROM foods f JOIN sources s ON s.id = f.source_id
           WHERE {where}
           ORDER BY (s.code = 'user_recipe') DESC, (f.name LIKE ? ESCAPE '\\') DESC, length(f.name), f.name LIMIT ?""",
        (*params, first, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def detail(conn: sqlite3.Connection, food_id: int) -> dict | None:
    f = conn.execute(
        "SELECT f.*, s.code AS source, s.name AS source_name, s.version AS source_version "
        "FROM foods f JOIN sources s ON s.id = f.source_id WHERE f.id = ?", (food_id,)).fetchone()
    if f is None:
        return None
    nuts = conn.execute(
        """SELECT n.code, n.name, n.unit, fn.value_per_100g AS value, fn.qualifier
           FROM nutrients n LEFT JOIN food_nutrients fn ON fn.nutrient_id = n.id AND fn.food_id = ?
           ORDER BY n.id""", (food_id,)).fetchall()
    portions = conn.execute(
        "SELECT id, description, grams FROM portions WHERE food_id = ? ORDER BY id", (food_id,)).fetchall()
    return {**dict(f), "nutrients": [dict(n) for n in nuts],  # value null = missing
            "portions": [dict(p) for p in portions]}
