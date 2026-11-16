"""Daily intake aggregation and comparison vs targets. No AI involved."""
import sqlite3

ENTRY_KEYS = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")


def daily_intake(conn: sqlite3.Connection, log_date: str) -> dict:
    """Sum nutrients for a date. Missing data is tracked, never treated as zero."""
    entries = conn.execute(
        """SELECT l.id, l.meal, l.grams, f.id AS food_id, f.name
           FROM intake_log l JOIN foods f ON f.id = l.food_id
           WHERE l.log_date = ? ORDER BY l.id""",
        (log_date,),
    ).fetchall()
    nutrients = conn.execute("SELECT id, code, unit FROM nutrients").fetchall()
    totals = {n["code"]: {"value": 0.0, "unit": n["unit"], "missing_entries": []} for n in nutrients}
    per_entry = {}
    for e in entries:
        vals = {
            r["nutrient_id"]: r["value_per_100g"]
            for r in conn.execute(
                "SELECT nutrient_id, value_per_100g FROM food_nutrients WHERE food_id = ?",
                (e["food_id"],),
            )
        }
        per_entry[e["id"]] = {}
        for n in nutrients:
            v = vals.get(n["id"])  # absent row or NULL -> missing
            if v is None:
                totals[n["code"]]["missing_entries"].append(e["id"])
            else:
                totals[n["code"]]["value"] += v * e["grams"] / 100.0
            if n["code"] in ENTRY_KEYS:  # per-entry numbers for the UI (None = missing)
                per_entry[e["id"]][n["code"]] = None if v is None else round(v * e["grams"] / 100.0, 1)
    for t in totals.values():
        t["value"] = round(t["value"], 2)
    out = []
    for e in entries:
        d = dict(e)
        d["nutrients"] = per_entry[e["id"]]
        out.append(d)
    return {"date": log_date, "entries": out, "totals": totals}


def compare(intake: dict, targets: dict) -> list[dict]:
    """Per-nutrient status. 'unknown' if any entry lacks data and total is below target."""
    out = []
    for code, t in targets.items():
        tot = intake["totals"].get(code)
        if tot is None:
            continue
        val, goal = tot["value"], t["value"]
        pct = round(100 * val / goal, 1) if goal else None
        incomplete = bool(tot["missing_entries"])
        if t["kind"] == "max":
            status = "excess" if val > goal else ("ok_incomplete" if incomplete else "ok")
        elif pct is not None and pct >= 100:
            status = "ok" if pct <= 150 else "excess"
        else:
            status = "unknown" if incomplete else ("deficient" if pct is not None and pct < 80 else "low")
        out.append({"nutrient": code, "intake": val, "target": goal, "unit": t["unit"],
                    "kind": t["kind"], "percent": pct, "status": status,
                    "incomplete_data": incomplete})
    return out
