"""Diet suggestions per day. engine/gaps.py decides what is short today; the LLM only proposes 2-3 meal
options (foods and grams); every number comes from the database via tools.evaluate_meal. Nutrients that
were also short yesterday count double when options are ranked, so repeated gaps are fixed first.
The result is stored per day (table recommendations) as a snapshot."""
import json
import re
import sqlite3

from . import recipes
from .ai import nllog, tools
from .ai.providers import Provider
from .engine import gaps

MAX_OPTIONS = 3
MAX_ITEMS = 6
REPEAT_WEIGHT = 2
MAIN_MEALS = ("breakfast", "lunch", "dinner")  # in eating order
SNACK_MAX_ITEMS = 3
# A snack must be eaten as it is: database names that say the food was cooked or heat-treated are rejected.
COOKED = re.compile(r"\b(cooked|boiled|fried|baked|steamed|stewed|braised|grilled|broiled|sauteed|simmered)\b", re.I)

PROPOSE_SYSTEM = """You suggest what to eat next for a nutrition app. Date: <<date>>. Write titles and food labels in: <<lang>>.
Still short today (target minus eaten so far):
<<short>>
Already over the limit today: <<excess>>
Meal slots still open today: <<open>> (a meal slot is closed once that meal, or a later one, has been eaten)
Already eaten today (do not suggest these again): <<eaten>>
Energy left today: <<kcal>> kcal
Also short yesterday (give these priority): <<repeated>>
User preferences / restrictions: <<prefs>>
Saved recipes the user can reuse: <<recipes>>
Reply with ONE JSON object and nothing else:
{"options":[{"title":"short meal name","meal":"breakfast|lunch|dinner|snack","items":[[label, english_database_name, grams], ...]}]}
Rules:
- 2 or 3 options. Each covers several of the short nutrients. Cover the ones also short yesterday first.
- "meal" must be one of the open slots above. Never use a closed slot.
- "snack" = ready to eat as it is: fruit, plain yogurt, milk, nuts, cheese, bread, crackers, dried fruit or similar. No cooking or heating, no rice, pasta, oats or other dishes, no invented recipe names. 1 to 3 items. Do not use saved recipes for snacks.
- breakfast/lunch/dinner: 2 to 5 items, practical home-style food, saved recipes allowed. Dishes that are easy to make at home.
- Respect the restrictions strictly.
- Do not add foods rich in a nutrient that is already over the limit.
- grams = amount as eaten. Keep each option within the energy left.
- english_database_name: USDA/UK style, as specific as possible, e.g. "Lentils, mature seeds, cooked", "Broccoli, cooked, boiled, drained", "Salmon, Atlantic, farmed, cooked, dry heat". For a saved recipe use its exact name.
- Be concise. Never output nutrient values."""


def open_meals(conn: sqlite3.Connection, day: str) -> list[str]:
    """Meal slots that can still be proposed: main meals later than every main meal already eaten, plus snack."""
    logged = {r["meal"] for r in conn.execute("SELECT DISTINCT meal FROM intake_log WHERE log_date = ?", (day,))}
    last = max((MAIN_MEALS.index(m) for m in logged if m in MAIN_MEALS), default=-1)
    return [m for i, m in enumerate(MAIN_MEALS) if i > last] + ["snack"]


def eaten_foods(conn: sqlite3.Connection, day: str) -> list[str]:
    rows = conn.execute("SELECT DISTINCT f.name FROM intake_log l JOIN foods f ON f.id = l.food_id "
                        "WHERE l.log_date = ? ORDER BY f.name LIMIT 40", (day,)).fetchall()
    return [r["name"] for r in rows]


def _prefs(conn) -> str:
    r = conn.execute("SELECT dietary_preferences FROM profile WHERE id = 1").fetchone()
    return ", ".join(json.loads(r["dietary_preferences"] or "[]")) if r else ""


def _prompt(conn, a: dict, lang: str) -> str:
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM nutrients")}
    short = [f"- {names.get(s['nutrient'], s['nutrient'])}: {s['gap']} {s['unit']} short"
             + (" (also short yesterday)" if s.get("repeated") else "") for s in a["short"]]
    excess = [names.get(x["nutrient"], x["nutrient"]) for x in a["excess"]]
    repeated = [names.get(s["nutrient"], s["nutrient"]) for s in a["short"] if s.get("repeated")]
    recipe_names = recipes.names(conn)
    values = {
        "date": a["date"], "lang": "Simplified Chinese" if lang == "zh" else "English",
        "short": "\n".join(short) or "- none", "excess": ", ".join(excess) or "none",
        "kcal": round(a["energy_left_kcal"]), "repeated": ", ".join(repeated) or "none",
        "open": ", ".join(open_meals(conn, a["date"])), "eaten": "; ".join(eaten_foods(conn, a["date"])) or "none",
        "prefs": _prefs(conn) or "none",
        "recipes": json.dumps(recipe_names, ensure_ascii=False) if recipe_names else "none",
    }
    s = PROPOSE_SYSTEM
    for k, v in values.items():
        s = s.replace(f"<<{k}>>", str(v))
    return s


def propose(provider: Provider, system: str) -> dict:
    """One LLM call; returns the parsed JSON object or {} (no DB access, thread-safe)."""
    resp = provider.complete(system, [{"role": "user", "content": "Suggest the options."}], [])
    text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
    a, b = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[a:b + 1]) if a >= 0 and b > a else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def score(opt: dict, a: dict) -> float:
    """Sum of gap coverage; nutrients short yesterday too count REPEAT_WEIGHT times."""
    repeated = {s["nutrient"] for s in a["short"] if s.get("repeated")}
    return sum((pct or 0) * (REPEAT_WEIGHT if n in repeated else 1)
               for n, pct in opt["covers_short_percent"].items())


def build_option(conn: sqlite3.Connection, raw: dict, a: dict, open_slots: list[str]):
    """Match one proposed option to the database and evaluate it. Returns (option or None, dropped count).
    A meal in a closed slot is rejected. A snack keeps only ready-to-eat foods and is titled by its items."""
    meal = str(raw.get("meal") or "").lower()
    if meal not in open_slots:
        return None, 1
    is_snack = meal == "snack"
    dropped, items = 0, []
    for row in (raw.get("items") or [])[:SNACK_MAX_ITEMS if is_snack else MAX_ITEMS]:
        g = row[2] if isinstance(row, (list, tuple)) and len(row) >= 3 else None
        if not isinstance(g, (int, float)) or isinstance(g, bool) or not 0 < g <= 2000:
            dropped += 1
            continue
        m = nllog._match(conn, str(row[0] or "?")[:80], [str(row[1])], None, None, None, float(g))
        if m["food_id"] is None:
            dropped += 1
            continue
        if is_snack:
            name = conn.execute("SELECT name FROM foods WHERE id = ?", (m["food_id"],)).fetchone()["name"]
            if COOKED.search(name):
                dropped += 1
                continue
        items.append({"label": m["label"], "food_id": m["food_id"], "grams": float(g)})
    if not items:
        return None, dropped + 1
    ev = tools.evaluate_meal(conn, a, [{"food_id": i["food_id"], "grams": i["grams"]} for i in items])
    if "error" in ev:
        return None, dropped + 1
    for k, it in enumerate(ev["items"]):
        it["label"] = items[k]["label"]
    ev["title"] = " + ".join(i["label"] for i in items) if is_snack else str(raw.get("title") or "")[:80]
    ev["meal"] = meal
    return ev, dropped


def generate(conn: sqlite3.Connection, provider: Provider, day: str, lang: str):
    """Generator of progress events; ends with {'type':'done','recommendation':{...}}."""
    a = gaps.assess_with_carry(conn, day)
    yield {"type": "status", "key": "rec_asking"}
    open_slots = open_meals(conn, day)
    options, dropped = [], 0
    if a["short"]:
        data = propose(provider, _prompt(conn, a, lang))
        raw = data.get("options") if isinstance(data.get("options"), list) else []
        yield {"type": "status", "key": "rec_matching"}
        for o in raw[:MAX_OPTIONS]:
            if not isinstance(o, dict):
                dropped += 1
                continue
            ev, d = build_option(conn, o, a, open_slots)
            dropped += d
            if ev is not None:
                options.append(ev)
    options.sort(key=lambda o: -score(o, a))
    result = {"assessment": a, "options": options, "dropped": dropped}
    conn.execute("INSERT OR REPLACE INTO recommendations (log_date, content, created_at) "
                 "VALUES (?, ?, CURRENT_TIMESTAMP)", (day, json.dumps(result, default=str)))
    conn.commit()
    yield {"type": "done", "recommendation": result}
