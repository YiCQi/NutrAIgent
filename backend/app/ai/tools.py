"""Deterministic tools the LLM may call. All numbers come from the DB / engine, never from the model."""
import sqlite3
from dataclasses import dataclass, field
from datetime import date as date_cls

from .. import foods
from ..engine import analysis, targets

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
    {"name": "propose_log_entries",
     "description": "Propose food-log entries for the user to confirm in the UI. Does NOT save anything. "
                    "Each entry needs a food_id from search_foods and grams (use portion gram weights from "
                    "get_food; ask the user if the amount is unclear).",
     "parameters": {"type": "object", "properties": {"entries": {"type": "array", "items": {
         "type": "object", "properties": {
             "food_id": {"type": "integer"}, "grams": {"type": "number"},
             "meal": {"type": "string", "enum": MEALS}, "log_date": {"type": "string"}},
         "required": ["food_id", "grams"]}}}, "required": ["entries"]}},
]

KEY_NUTRIENTS = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")


@dataclass
class Context:
    conn: sqlite3.Connection
    today: str
    proposals: list = field(default_factory=list)


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
        if name == "propose_log_entries":
            accepted, errors = [], []
            for e in args.get("entries", []):
                row = conn.execute("SELECT id, name FROM foods WHERE id = ?", (e.get("food_id"),)).fetchone()
                grams = e.get("grams")
                day = _valid_date(e.get("log_date"), ctx.today)
                meal = e.get("meal") if e.get("meal") in MEALS else "other"
                if row is None:
                    errors.append(f"food_id {e.get('food_id')} not found")
                elif not isinstance(grams, (int, float)) or grams <= 0 or grams > 5000:
                    errors.append(f"invalid grams for food_id {row['id']}")
                elif day is None:
                    errors.append("invalid log_date")
                else:
                    p = {"food_id": row["id"], "food_name": row["name"], "grams": float(grams),
                         "meal": meal, "log_date": day}
                    accepted.append(p)
            ctx.proposals.extend(accepted)
            return {"proposed": accepted, "errors": errors,
                    "note": "Not saved. The user must confirm in the UI."}
        return {"error": f"unknown tool {name}"}
    except (KeyError, TypeError, ValueError) as e:
        return {"error": f"bad arguments: {e}"}
