"""Weekly meal planner: the LLM only proposes WHAT to eat (dishes/ingredients and rough grams);
food matching, portion scaling to the energy target and every nutrient number are deterministic.

Per day: LLM call (parallel across days) -> match items to the database -> scale all grams of the
day by one factor so energy meets the target (clipped to 0.6-1.8, so a very off proposal stays visibly
off target instead of being silently distorted) -> store. Totals are always recomputed from the DB.
"""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as date_cls, timedelta

from . import recipes
from .ai import nllog
from .ai.providers import Provider

MEALS = ("breakfast", "lunch", "dinner", "snack")
SCALE_MIN, SCALE_MAX = 0.6, 1.8
TRACKED = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sodium_mg", "sugars_g", "sat_fat_g")

PLAN_SYSTEM = """You plan ONE day of meals for a nutrition app. Date: <<date>>. Write food labels in: <<lang>>.
Daily targets: energy <<kcal>> kcal, protein <<protein>> g, carbohydrate <<carbs>> g, fat <<fat>> g, fibre <<fibre>> g (sodium under <<sodium>> mg).
Meals to plan: <<meals>>.
User preferences / restrictions: <<prefs>>
Saved recipes the user can reuse: <<recipes>>
Main dishes already planned earlier this week (avoid repeating them): <<planned>>
Reply with ONE JSON object and nothing else:
{"breakfast":[[label, english_database_name, grams], ...], "lunch":[...], "dinner":[...], "snack":[...]}
(only the requested meals; label = food as a person would say it in the label language; english_database_name = USDA/UK style name; grams = number)
Rules:
- Practical home-style meals (Chinese home cooking when the label language is Chinese). 3-7 items per meal.
- Split a cooked dish into its main ingredients plus cooking oil and key seasonings (soy sauce, salt, sugar) with realistic grams.
- Each main meal has a protein source and vegetables. Vary foods across days. Respect the restrictions strictly.
- grams = weight as eaten (cooked weight for cooked foods). Stay near the targets, a rough total is fine: the app rescales exactly.
- For a saved recipe use its exact name as english_database_name and the grams of the finished dish.
- english_database_name must follow USDA naming: category first, then the form/preparation, as specific as possible, e.g. "Rice, white, long-grain, cooked" (use "glutinous" only for sticky rice), "Oil, peanut", "Broccoli, cooked, boiled, drained", "Sweet potato, cooked, baked", "Egg, whole, cooked, hard-boiled", "Chicken, thigh, meat only, cooked", "Soy sauce", "Pork, loin, lean, cooked", "Tofu, firm". Wheat buns/mantou: "Bread, steamed" style names are rare, so use "Bread, whole-wheat" or "Rolls, hamburger or hotdog" only if nothing closer.
- Be concise: no explanations, no extra fields.
- Database names are English (USDA/UK style, e.g. "Rice, white, cooked", "Pork, loin, lean, cooked", "Soy sauce"). Never output nutrient values."""


def _food_nutrients(conn, food_id):
    return {r["code"]: r["value_per_100g"] for r in conn.execute(
        "SELECT n.code, fn.value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id "
        "WHERE fn.food_id = ?", (food_id,))}


def day_targets(conn) -> dict:
    from .engine import targets as T
    r = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if r is None:
        raise ValueError("profile not set")
    return T.compute_targets(T.Profile(r["age"], r["sex"], r["height_cm"], r["weight_kg"],
                                       r["activity_level"], r["goal"]))["targets"]


def _prompt(date, lang, targets, meals, prefs, recipe_names, planned):
    t = {k: v["value"] for k, v in targets.items()}
    s = PLAN_SYSTEM
    for k, v in {"date": date, "lang": "Simplified Chinese" if lang == "zh" else "English",
                 "kcal": round(t["energy_kcal"]), "protein": round(t["protein_g"]), "carbs": round(t["carbohydrate_g"]),
                 "fat": round(t["fat_g"]), "fibre": round(t["fibre_g"]), "sodium": round(t["sodium_mg"]),
                 "meals": ", ".join(meals), "prefs": prefs or "none",
                 "recipes": json.dumps(recipe_names, ensure_ascii=False) if recipe_names else "none",
                 "planned": json.dumps(planned[-24:], ensure_ascii=False) if planned else "none"}.items():
        s = s.replace(f"<<{k}>>", str(v))
    return s


def propose_day(provider: Provider, system: str) -> dict:
    """LLM call only (thread-safe, no DB)."""
    resp = provider.complete(system, [{"role": "user", "content": "Plan the day."}], [])
    text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
    a, b = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[a:b + 1]) if a >= 0 and b > a else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _round_g(g: float) -> float:
    return float(round(g / 5) * 5) if g >= 20 else round(g * 2) / 2


def _day_items(proposal: dict, meals):
    """Normalise the model output to (meal, label, search_terms, grams). Accepts {meal: [[label, name, grams]]}
    and the older {"meals":[{"meal","items":[{label,search_terms,grams}]}]} shape."""
    out = []
    if isinstance(proposal.get("meals"), list):
        for m in proposal["meals"]:
            for it in (m.get("items") or []) if isinstance(m, dict) else []:
                if isinstance(it, dict):
                    out.append((m.get("meal"), it.get("label"), it.get("search_terms"), it.get("grams"), it.get("state")))
        return out
    for meal in meals:
        for it in (proposal.get(meal) or [])[:12]:
            if isinstance(it, (list, tuple)) and len(it) >= 3:
                out.append((meal, it[0], [str(it[1])], it[2], None))
    return out


def match_day(conn, proposal: dict, kcal_target: float, meals) -> tuple[list[dict], int]:
    """Match proposed items to DB foods and scale the day to the energy target. Returns (items, dropped)."""
    items, dropped = [], 0
    for meal, label, terms, g, state in _day_items(proposal, meals):
        if meal not in meals:
            continue
        if not isinstance(g, (int, float)) or isinstance(g, bool) or not 0 < g <= 3000:
            dropped += 1
            continue
        r = nllog._match(conn, str(label or "?")[:80], terms, state, None, None, g)
        if r["food_id"] is None:
            dropped += 1
            continue
        items.append({"meal": meal, "label": r["label"], "food_id": r["food_id"], "grams": float(g)})
    total = sum((_food_nutrients(conn, i["food_id"]).get("energy_kcal") or 0) * i["grams"] / 100 for i in items)
    if total > 0 and kcal_target > 0:
        s = max(SCALE_MIN, min(SCALE_MAX, kcal_target / total))
        for i in items:
            i["grams"] = max(0.5, _round_g(i["grams"] * s))
    return items, dropped


def save_day(conn, plan_id: int, plan_date: str, items: list[dict]) -> None:
    conn.execute("DELETE FROM plan_items WHERE plan_id = ? AND plan_date = ?", (plan_id, plan_date))
    conn.executemany(
        "INSERT INTO plan_items (plan_id, plan_date, meal, position, label, food_id, grams) VALUES (?,?,?,?,?,?,?)",
        [(plan_id, plan_date, i["meal"], pos, i["label"], i["food_id"], i["grams"]) for pos, i in enumerate(items)])


def generate(conn, provider: Provider, plan_id: int, dates: list[str], lang: str, meals, notes: str):
    """Generator of progress events. LLM calls run in parallel; DB work stays on this thread."""
    targets = day_targets(conn)
    prefs_row = conn.execute("SELECT dietary_preferences FROM profile WHERE id = 1").fetchone()
    prefs = ", ".join(json.loads(prefs_row["dietary_preferences"] or "[]"))
    prefs = "; ".join(x for x in (prefs, notes.strip()) if x)
    names = recipes.names(conn)
    yield {"type": "status", "key": "plan_asking", "arg": len(dates)}
    # first-day dishes are passed to later days only when calls are sequential; in parallel we rely on the
    # model varying by date, so pass the date and a day index hint instead.
    systems = {d: _prompt(d, lang, targets, meals, prefs + f" (this is day {i + 1} of {len(dates)}; make it different from the other days)",
                          names, []) for i, d in enumerate(dates)}
    dropped_total = 0
    provider.timeout = 300  # a whole day of JSON can take minutes on slow endpoints
    with ThreadPoolExecutor(max_workers=min(4, len(dates))) as ex:
        futs = {ex.submit(propose_day, provider, systems[d]): d for d in dates}
        for fut in as_completed(futs):
            d = futs[fut]
            proposal = fut.result()  # ProviderError propagates to the stream as an error event
            items, dropped = match_day(conn, proposal, targets["energy_kcal"]["value"], meals)
            dropped_total += dropped
            save_day(conn, plan_id, d, items)
            conn.commit()
            yield {"type": "status", "key": "plan_day_done", "arg": d}
    conn.execute("UPDATE meal_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
    conn.commit()
    yield {"type": "done", "plan_id": plan_id, "dropped": dropped_total}


def plan_view(conn: sqlite3.Connection, plan_id: int) -> dict:
    p = conn.execute("SELECT * FROM meal_plans WHERE id = ?", (plan_id,)).fetchone()
    if p is None:
        raise KeyError(plan_id)
    try:
        targets = day_targets(conn)
    except ValueError:
        targets = None
    rows = conn.execute(
        """SELECT i.id, i.plan_date, i.meal, i.position, i.label, i.food_id, i.grams, f.name AS food_name
           FROM plan_items i JOIN foods f ON f.id = i.food_id WHERE i.plan_id = ?
           ORDER BY i.plan_date, i.meal, i.position, i.id""", (plan_id,)).fetchall()
    days: dict[str, dict] = {}
    cache: dict[int, dict] = {}
    for r in rows:
        d = days.setdefault(r["plan_date"], {"date": r["plan_date"], "meals": {}, "totals": {}, "incomplete": []})
        nut = cache.setdefault(r["food_id"], _food_nutrients(conn, r["food_id"]))
        per = {}
        for code in TRACKED:
            v = nut.get(code)
            per[code] = None if v is None else round(v * r["grams"] / 100, 1)
            if v is None:
                if code not in d["incomplete"]:
                    d["incomplete"].append(code)
            else:
                d["totals"][code] = round(d["totals"].get(code, 0) + v * r["grams"] / 100, 1)
        d["meals"].setdefault(r["meal"], []).append(
            {"id": r["id"], "label": r["label"], "food_id": r["food_id"], "food_name": r["food_name"],
             "grams": r["grams"], "nutrients": per})
    out_days = []
    for d in sorted(days):
        day = days[d]
        day["meals"] = [{"meal": m, "items": day["meals"][m]} for m in MEALS if m in day["meals"]]
        out_days.append(day)
    return {"id": p["id"], "title": p["title"], "start_date": p["start_date"], "notes": p["notes"],
            "targets": targets, "days": out_days}


def week_dates(start: str, n: int) -> list[str]:
    s = date_cls.fromisoformat(start)
    return [(s + timedelta(days=i)).isoformat() for i in range(n)]
