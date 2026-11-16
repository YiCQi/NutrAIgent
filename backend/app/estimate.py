"""AI estimates for missing micronutrient values of foods eaten on a day.

Only the nutrients in ESTIMATE_CODES and only where the database has no value. Stored with estimated = 1 and shown
as "AI预测" everywhere the value is used. One LLM call per batch of foods; numbers outside plausible ranges are dropped.
"""
import sqlite3

from . import recommend
from .ai.providers import Provider

ESTIMATE_CODES = ("calcium_mg", "iron_mg", "vitamin_c_mg", "vitamin_b12_ug")
MAX_PLAUSIBLE = {"calcium_mg": 2000.0, "iron_mg": 100.0, "vitamin_c_mg": 1000.0, "vitamin_b12_ug": 200.0}
BATCH = 8

PROMPT = """You estimate nutrient content for a nutrition app. For each food give the typical value per 100 g of
the edible food, USDA-style. Foods (food_id: name):
<<foods>>
Nutrients: calcium_mg (mg), iron_mg (mg), vitamin_c_mg (mg), vitamin_b12_ug (ug).
Reply with ONE JSON object and nothing else:
{"foods":[{"food_id":1,"calcium_mg":0,"iron_mg":0,"vitamin_c_mg":0,"vitamin_b12_ug":0}]}
Use 0 only when the food really contains none of that nutrient. Numbers only, no text."""


def missing_foods(conn: sqlite3.Connection, day: str) -> list[dict]:
    """Foods eaten on the day that lack a value for at least one estimable nutrient."""
    codes = ESTIMATE_CODES
    foods = conn.execute("SELECT DISTINCT f.id, f.name FROM intake_log l JOIN foods f ON f.id = l.food_id "
                         "WHERE l.log_date = ? ORDER BY f.name", (day,)).fetchall()
    out = []
    for f in foods:
        have = {r["code"] for r in conn.execute(
            "SELECT n.code FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id "
            "WHERE fn.food_id = ? AND fn.value_per_100g IS NOT NULL", (f["id"],))}
        missing = [c for c in codes if c not in have]
        if missing:
            out.append({"id": f["id"], "name": f["name"], "missing": missing})
    return out


def _ask(provider: Provider, batch: list[dict]) -> dict:
    listing = "\n".join(f"{f['id']}: {f['name']}" for f in batch)
    return recommend.propose(provider, PROMPT.replace("<<foods>>", listing))


def estimate(conn: sqlite3.Connection, provider: Provider, foods: list[dict]) -> dict:
    """Fill only missing values. Returns counts and the names of foods the model did not answer for."""
    nid = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    stored, unanswered = 0, []
    for i in range(0, len(foods), BATCH):
        batch = foods[i:i + BATCH]
        answers = {}
        for f in _ask(provider, batch).get("foods") or []:
            if isinstance(f, dict) and isinstance(f.get("food_id"), (int, str)) and str(f["food_id"]).isdigit():
                answers[int(f["food_id"])] = f
        for f in batch:
            got = answers.get(f["id"])
            if got is None:
                unanswered.append(f["name"])
                continue
            for code in f["missing"]:
                v = got.get(code)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= MAX_PLAUSIBLE[code]:
                    continue
                # only fills a NULL or absent value; existing data is never overwritten
                conn.execute(
                    "INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g, qualifier, estimated) "
                    "VALUES (?, ?, ?, NULL, 1) "
                    "ON CONFLICT(food_id, nutrient_id) DO UPDATE SET value_per_100g = excluded.value_per_100g, "
                    "qualifier = NULL, estimated = 1 WHERE food_nutrients.value_per_100g IS NULL",
                    (f["id"], nid[code], float(v)))
                stored += 1
    conn.commit()
    return {"stored": stored, "unanswered": unanswered}
