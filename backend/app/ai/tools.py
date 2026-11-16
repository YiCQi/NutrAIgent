"""Deterministic tools the LLM may call. All numbers come from the DB / engine, never from the model."""
import sqlite3
from dataclasses import dataclass
from datetime import date as date_cls

from .. import foods
from ..engine import analysis, gaps, targets

MEALS = ["breakfast", "lunch", "dinner", "snack", "other"]

TOOL_SPECS = [
    {"name": "search_foods",
     "description": "Search the food database by name. Returns candidates with id, name, source, state "
                    "and key per-100g values (null = no data). Use short keyword queries.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 15}},
         "required": ["query"]}},
    {"name": "get_food",
     "description": "Full nutrient list (per 100 g; null = missing data, qualifier trace/N) and household "
                    "portions with gram weights for one food id.",
     "parameters": {"type": "object", "properties": {"food_id": {"type": "integer"}},
                    "required": ["food_id"]}},
    {"name": "get_targets",
     "description": "The user's daily nutrient targets and the calculation trace. Fails if no profile.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_daily_intake",
     "description": "Totals logged for a date (YYYY-MM-DD) plus comparison against targets.",
     "parameters": {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]}},
    {"name": "get_nutrient_gaps",
     "description": "For a date (default today): nutrients still short of target (gap in the unit), nutrients over "
                    "their limit, energy left, nutrients with missing data, and whether each was also short or over "
                    "yesterday ('repeated' = priority). Fails if no profile.",
     "parameters": {"type": "object", "properties": {"date": {"type": "string"}}}},
    {"name": "evaluate_meal",
     "description": "Check a proposed meal or snack before recommending it. items = food ids from search_foods with "
                    "grams. Returns totals per nutrient (null if any item lacks data), kcal, percent of each short "
                    "nutrient's gap it covers, over_limit nutrients it adds to, and exceeds_energy_left. Call it for "
                    "every option you propose.",
     "parameters": {"type": "object", "properties": {
         "items": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "object", "properties": {
             "food_id": {"type": "integer"}, "grams": {"type": "number"}}, "required": ["food_id", "grams"]}},
         "date": {"type": "string"}},
         "required": ["items"]}},
]

KEY_NUTRIENTS = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")


@dataclass
class Context:
    conn: sqlite3.Connection
    today: str


def _profile(conn):
    r = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if r is None:
        return None
    return targets.Profile(r["age"], r["sex"], r["height_cm"], r["weight_kg"], r["activity_level"], r["goal"])


def _valid_date(s, default):
    if not s:
        return default
    try:
        return date_cls.fromisoformat(s).isoformat()
    except ValueError:
        return None


def call(ctx: Context, name: str, args: dict) -> dict:
    """Run a tool; always returns a JSON-serialisable dict (errors as {'error': ...})."""
    conn = ctx.conn
    try:
        if name == "search_foods":
            limit = min(int(args.get("limit") or 5), 10)
            out = []
            for f in foods.search(conn, str(args.get("query", "")), limit):
                f.pop("edible_portion_pct", None)
                d = foods.detail(conn, f["id"])
                f["per_100g"] = {n["code"]: n["value"] for n in d["nutrients"] if n["code"] in KEY_NUTRIENTS}
                f["portions"] = [{"description": p["description"], "grams": p["grams"]} for p in d["portions"][:3]]
                out.append(f)
            return {"results": out}
        if name == "get_food":
            d = foods.detail(conn, int(args["food_id"]))
            return d if d else {"error": "food not found"}
        if name == "get_targets":
            p = _profile(conn)
            return targets.compute_targets(p) if p else {"error": "profile not set"}
        if name == "get_daily_intake":
            day = _valid_date(args.get("date"), None)
            if day is None:
                return {"error": "date must be YYYY-MM-DD"}
            intake = analysis.daily_intake(conn, day)
            p = _profile(conn)
            if p:
                intake["comparison"] = analysis.compare(intake, targets.compute_targets(p)["targets"])
            return intake
        if name in ("get_nutrient_gaps", "evaluate_meal"):
            day = _valid_date(args.get("date"), ctx.today)
            if day is None:
                return {"error": "date must be YYYY-MM-DD"}
            if _profile(conn) is None:
                return {"error": "profile not set"}
            a = gaps.assess_with_carry(conn, day)
            return a if name == "get_nutrient_gaps" else evaluate_meal(conn, a, args.get("items"))
        return {"error": f"unknown tool {name}"}
    except (KeyError, TypeError, ValueError) as e:
        return {"error": f"bad arguments: {e}"}


def evaluate_meal(conn: sqlite3.Connection, a: dict, items) -> dict:
    """Totals and gap coverage for a proposed meal. Every number comes from food_nutrients."""
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        return {"error": "items must be a list of 1-10 {food_id, grams}"}
    rows = []
    for it in items:
        fid, g = int(it["food_id"]), float(it["grams"])
        if not 0 < g <= 2000:
            return {"error": f"grams out of range (0-2000) for food {fid}"}
        f = conn.execute("SELECT name FROM foods WHERE id = ?", (fid,)).fetchone()
        if f is None:
            return {"error": f"food {fid} not found"}
        rows.append((fid, f["name"], g))
    codes = [r["code"] for r in conn.execute("SELECT code FROM nutrients ORDER BY id")]
    per = {fid: {r["code"]: r["value_per_100g"] for r in conn.execute(
        """SELECT n.code, fn.value_per_100g FROM nutrients n
           LEFT JOIN food_nutrients fn ON fn.nutrient_id = n.id AND fn.food_id = ?""", (fid,))}
        for fid, _, _ in rows}
    totals = {}
    for code in codes:
        vals = [(per[fid].get(code), g) for fid, _, g in rows]
        totals[code] = None if any(v is None for v, _ in vals) else round(sum(v * g / 100 for v, g in vals), 1)
    covers = {}
    for s in a["short"]:
        v = totals.get(s["nutrient"])
        covers[s["nutrient"]] = None if v is None else (round(min(100.0, 100 * v / s["gap"]), 1)
                                                        if s["gap"] > 0 else 100.0)
    kcal = totals.get(gaps.ENERGY)
    return {"date": a["date"], "items": [{"food_id": fid, "food_name": n, "grams": g} for fid, n, g in rows],
            "totals": totals, "kcal": kcal, "covers_short_percent": covers,
            "over_limit": [x["nutrient"] for x in a["excess"]
                           if totals.get(x["nutrient"]) and totals[x["nutrient"]] > 0.1 * x["limit"]],
            "exceeds_energy_left": None if kcal is None else kcal > a["energy_left_kcal"]}
