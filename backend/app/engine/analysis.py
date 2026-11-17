"""Daily intake aggregation and comparison vs targets. No AI involved."""
import sqlite3

DERIVED_EPA_DHA = "epa_dha_g"


def daily_intake(conn: sqlite3.Connection, log_date: str) -> dict:
    """Sum nutrients for a date. Missing data is tracked, never treated as zero."""
    entries = conn.execute(
        """SELECT l.id, l.meal, l.grams, f.id AS food_id, f.name
           FROM intake_log l JOIN foods f ON f.id = l.food_id
           WHERE l.log_date = ? ORDER BY l.id""",
        (log_date,),
    ).fetchall()
    nutrients = conn.execute("SELECT id, code, unit FROM nutrients").fetchall()
    totals = {n["code"]: {"value": 0.0, "unit": n["unit"], "missing_entries": [], "estimated": False}
              for n in nutrients}
    per_entry = {}
    for e in entries:
        vals = {
            r["nutrient_id"]: (r["value_per_100g"], bool(r["estimated"]))
            for r in conn.execute(
                "SELECT nutrient_id, value_per_100g, estimated FROM food_nutrients WHERE food_id = ?",
                (e["food_id"],),
            )
        }
        per_entry[e["id"]] = {}
        for n in nutrients:
            v, est = vals.get(n["id"], (None, False))  # absent row or NULL -> missing
            if v is None:
                totals[n["code"]]["missing_entries"].append(e["id"])
            else:
                totals[n["code"]]["value"] += v * e["grams"] / 100.0
                totals[n["code"]]["estimated"] |= est
            # per-entry amount for every nutrient, used for the UI source tooltips (None = missing)
            per_entry[e["id"]][n["code"]] = None if v is None else round(v * e["grams"] / 100.0, 2)
    # derived total: EPA+DHA (EFSA AI is given for the pair). Missing if either part is missing.
    for e in entries:
        epa, dha = per_entry[e["id"]]["epa_g"], per_entry[e["id"]]["dha_g"]
        per_entry[e["id"]][DERIVED_EPA_DHA] = None if epa is None or dha is None else round(epa + dha, 2)
    totals[DERIVED_EPA_DHA] = {
        "value": round(totals["epa_g"]["value"] + totals["dha_g"]["value"], 2), "unit": "g",
        "missing_entries": sorted(set(totals["epa_g"]["missing_entries"]) | set(totals["dha_g"]["missing_entries"])),
        "estimated": totals["epa_g"]["estimated"] or totals["dha_g"]["estimated"],
    }
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
        elif t["kind"] == "min":  # minimum only: more is never flagged
            if pct is not None and pct >= 100:
                status = "ok"
            else:
                status = "unknown" if incomplete else ("deficient" if pct is not None and pct < 80 else "low")
        elif pct is not None and pct >= 100:
            status = "ok" if pct <= 150 else "excess"
        else:
            status = "unknown" if incomplete else ("deficient" if pct is not None and pct < 80 else "low")
        out.append({"nutrient": code, "intake": val, "target": goal, "unit": t["unit"],
                    "kind": t["kind"], "percent": pct, "status": status,
                    "incomplete_data": incomplete})
    return out
