"""Nutrient gaps for a day: what is still short of target, what is over its limit, energy left, and whether
the same nutrient was also short (or over) the day before. Arithmetic only, no AI.
Missing data is never counted as zero: nutrients with unknown status are listed separately."""
import sqlite3
from datetime import date as date_cls, timedelta

from . import analysis, targets

ENERGY = "energy_kcal"
SHORT_STATUSES = ("low", "deficient")


def _targets(conn: sqlite3.Connection) -> dict:
    r = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if r is None:
        raise ValueError("profile not set")
    p = targets.Profile(r["age"], r["sex"], r["height_cm"], r["weight_kg"], r["activity_level"], r["goal"])
    return targets.compute_targets(p)["targets"]


def assess(conn: sqlite3.Connection, day: str) -> dict:
    intake = analysis.daily_intake(conn, day)
    comp = analysis.compare(intake, _targets(conn))
    entries = len(intake["entries"])
    short, excess, unknown = [], [], []
    for c in comp:
        if c["status"] == "unknown":
            unknown.append(c["nutrient"])
        if c["kind"] == "target" and c["status"] in SHORT_STATUSES:
            short.append({"nutrient": c["nutrient"], "unit": c["unit"], "intake": c["intake"],
                          "target": c["target"], "percent": c["percent"],
                          "gap": round(c["target"] - c["intake"], 1)})
        if c["status"] == "excess" and c["nutrient"] != ENERGY:
            excess.append({"nutrient": c["nutrient"], "unit": c["unit"], "intake": c["intake"], "limit": c["target"]})
    e = next((c for c in comp if c["nutrient"] == ENERGY), None)
    left = max(0.0, round(e["target"] - e["intake"], 1)) if e else 0.0
    return {"date": day, "entries": entries, "energy_left_kcal": left, "short": short, "excess": excess,
            "unknown": unknown}


def assess_with_carry(conn: sqlite3.Connection, day: str) -> dict:
    """assess() plus a 'repeated' flag: short (or over) on this day AND on the day before (only if yesterday
    had any log entries; an empty day is not evidence)."""
    today = assess(conn, day)
    prev_day = (date_cls.fromisoformat(day) - timedelta(days=1)).isoformat()
    prev = assess(conn, prev_day)
    prev_short = {s["nutrient"] for s in prev["short"]} if prev["entries"] else set()
    prev_excess = {x["nutrient"] for x in prev["excess"]} if prev["entries"] else set()
    for s in today["short"]:
        s["repeated"] = s["nutrient"] in prev_short
    for x in today["excess"]:
        x["repeated"] = x["nutrient"] in prev_excess
    today["yesterday"] = {"date": prev_day, "logged": prev["entries"] > 0,
                          "short": sorted(prev_short), "excess": sorted(prev_excess)}
    return today
