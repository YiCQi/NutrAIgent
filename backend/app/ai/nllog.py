"""Fast natural-language food logging: ONE LLM call to parse, everything else deterministic.

The LLM only turns text into structured items (names, quantities). Food matching, portion
gram weights and all nutrient numbers come from the database. Amounts the user did not give
in grams fall back, in order, to: a database household portion, then an AI-estimated typical
weight (flagged as such in `grams_basis`).
"""
import json
import re
import sqlite3
from datetime import date as date_cls

from . import matching
from .providers import Provider

MEALS = ("breakfast", "lunch", "dinner", "snack", "other")

PARSE_SYSTEM = """You are the parser of a nutrition-tracking app. Today is <<today>>. The user's language: <<lang>>.
Saved recipes (the user's own dishes): <<recipes>>
Read the user's latest message (earlier messages are context) and reply with ONE JSON object, nothing else. Choose one:

1) The user reports food or drink they consumed and you have enough information:
{"intent":"log","items":[ITEM, ...]}
ITEM = {"label":"the food as the user wrote it",
  "search_terms":["english database name","simpler english name","even simpler"],
  "state":"raw|cooked|any", "quantity":number or null, "unit":"g|ml|piece|slice|cup|bowl|tbsp|tsp|serving|null",
  "grams_estimate":typical total weight in grams of what was eaten,
  "meal":"breakfast|lunch|dinner|snack|other", "date":"YYYY-MM-DD or null for today"}
- Normal food, or one of the saved recipes: plain ITEM (for a saved recipe put its exact name first in search_terms).
- Home-cooked composite dish that is NOT a saved recipe: add to the ITEM
  "recipe_name":"short dish name in the user's language",
  "total_g": estimated weight of the WHOLE cooked dish (all of it, not the portion eaten),
  "ingredients":[{"label":"...","search_terms":[...],"state":"raw|cooked|any","role":"main|sauce",
    "predicted":true|false,"grams_estimate":grams of this ingredient in the WHOLE dish}]
  - The main food(s): role "main".
  - Every seasoning, oil, sauce or condiment: role "sauce" (salt, sugar, soy sauce, oyster sauce, vinegar, cooking wine, cornstarch, cooking oil...).
  - Sauces/seasonings the user NAMED: "predicted":false, use the stated amount if given.
  - Sauces/seasonings the user did NOT name but a typical version of this dish uses: "predicted":true with a typical amount.
    Predict them yourself; do NOT ask the user about seasonings.
  - The ingredient grams should add up to roughly total_g.
  The ITEM's grams_estimate is the weight of the portion the user ate (the whole dish if no portion was given).
- Separate foods or drinks are separate items ("coffee with soy milk" is two items).

2) Information that matters is missing: {"intent":"ask","question":"..."} written in the user's language.
Ask when the amount of a MAIN item is unclear, or when the food is ambiguous. Never ask about seasonings or sauces: predict them (see above). Put all missing points in ONE short message with a brief example of an acceptable answer.
Do NOT ask again if an earlier assistant message already asked and the user answered or said they do not know / skip: then proceed with typical estimates. Do NOT ask about trivial items (a coffee, a piece of fruit): use typical amounts.

3) Anything else (questions, advice, intake or targets queries, chat): {"intent":"chat"}

Database food names are English (USDA/UK style, e.g. "Rice, white, cooked", "Soy sauce", "Salt, table"). Never output nutrient values."""


def parse(provider: Provider, history: list[dict], today: str, lang: str = "en", recipe_names=()) -> dict:
    """One model call. Returns {'intent': 'chat'} if the output is not usable JSON."""
    system = (PARSE_SYSTEM.replace("<<today>>", today)
              .replace("<<lang>>", "Chinese (简体中文)" if lang == "zh" else "English")
              .replace("<<recipes>>", json.dumps(list(recipe_names), ensure_ascii=False) if recipe_names else "none"))
    resp = provider.complete(system, [{"role": m["role"], "content": m["content"]} for m in history], [])
    text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {"intent": "chat"}
    try:
        data = json.loads(text[a:b + 1])
    except ValueError:
        return {"intent": "chat"}
    if not isinstance(data, dict):
        return {"intent": "chat"}
    if data.get("intent") == "log":
        return data
    if data.get("intent") == "ask" and isinstance(data.get("question"), str) and data["question"].strip():
        return data
    return {"intent": "chat"}


def _candidates(conn, label, terms: list[str], state: str | None, limit: int = 6) -> list[dict]:
    return matching.candidates(conn, label, terms, state, limit)


_UNIT_WORDS = {"cup": ["cup"], "tbsp": ["tablespoon", "tbsp"], "tsp": ["teaspoon", "tsp"],
               "slice": ["slice"], "piece": ["piece", "medium", "large", "small", "unit", "each"],
               "bowl": ["cup"], "serving": ["serving", "cup", "medium"]}


def resolve_grams(conn, food_id: int, quantity, unit, estimate) -> tuple[float, str]:
    q = float(quantity) if isinstance(quantity, (int, float)) and quantity > 0 else None
    u = (unit or "").lower() if isinstance(unit, str) else ""
    if q and u in ("g", "gram", "grams"):
        return q, "stated in grams"
    if q and u == "ml":
        return q, "1 ml taken as 1 g (approximate)"
    if q and u in _UNIT_WORDS:
        for p in conn.execute("SELECT description, grams FROM portions WHERE food_id = ? ORDER BY id", (food_id,)):
            m = re.match(r"^(\d+(?:\.\d+)?)\s+(.*)$", p["description"])
            amount, rest = (float(m.group(1)), m.group(2).lower()) if m else (1.0, p["description"].lower())
            if any(re.search(rf"\b{w}", rest) for w in _UNIT_WORDS[u]):
                return round(q * p["grams"] / amount, 1), f"database portion: {p['description']} ({p['grams']:g} g)"
    if isinstance(estimate, (int, float)) and 0 < estimate <= 3000:
        return float(estimate), "typical weight estimated by the AI (please check)"
    return 100.0, "default 100 g (no amount given)"


def _valid_date(s, today):
    if not s:
        return today
    try:
        return date_cls.fromisoformat(str(s)).isoformat()
    except ValueError:
        return today


def per100(conn, food_id: int) -> dict:
    """Per-100 g values of one food, keyed by nutrient code. None = missing (qualifier 'N' or no row)."""
    return {r["code"]: r["value_per_100g"] for r in conn.execute(
        """SELECT n.code, fn.value_per_100g FROM nutrients n
           LEFT JOIN food_nutrients fn ON fn.nutrient_id = n.id AND fn.food_id = ?""", (food_id,))}


def _match(conn, label, terms, state, quantity, unit, estimate):
    """Deterministic food match for one wording; food_id None when nothing matches."""
    cands = _candidates(conn, label, terms or [], state)
    if not cands:
        return {"label": label, "food_id": None, "food_name": None, "grams": None,
                "grams_basis": "no database match found", "alternatives": [], "per100": {}}
    top = cands[0]
    grams, basis = resolve_grams(conn, top["id"], quantity, unit, estimate)
    return {"label": label, "food_id": top["id"], "food_name": top["name"], "source": top["source"],
            "grams": grams, "grams_basis": basis, "per100": per100(conn, top["id"]),
            "alternatives": [{"food_id": c["id"], "food_name": c["name"], "source": c["source"]} for c in cands]}


def _positive(x, limit):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x <= limit else None


def build_proposals(conn: sqlite3.Connection, parsed: dict, today: str):
    """Yield ('match', label) progress then finally ('done', proposals).

    proposal kinds: 'food' (one matched food) | 'recipe' (composite dish: ingredients + yield + save flag).
    """
    proposals = []
    for it in (parsed.get("items") or [])[:15]:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label") or "?")[:80]
        yield "match", label
        meal = it.get("meal") if it.get("meal") in MEALS else "other"
        day = _valid_date(it.get("date"), today)
        ings = it.get("ingredients")
        if isinstance(ings, list) and ings:
            rows = []
            for ing in ings[:25]:
                if not isinstance(ing, dict):
                    continue
                r = _match(conn, str(ing.get("label") or "?")[:80], ing.get("search_terms"), ing.get("state"),
                           None, None, ing.get("grams_estimate"))
                if r["food_id"] is not None and r["grams_basis"].startswith("default"):
                    r["grams_basis"] = "no amount given (default 10 g, please set)"
                    r["grams"] = 10.0
                r["role"] = "sauce" if ing.get("role") == "sauce" else "main"
                r["predicted"] = ing.get("predicted") is True
                if r["predicted"] and r["food_id"] is not None:
                    r["grams_basis"] = "predicted by AI (please check)"
                rows.append(r)
            total = round(sum(r["grams"] or 0 for r in rows), 1)
            eat = _positive(it.get("grams_estimate"), 5000)
            whole = _positive(it.get("total_g"), 10000)  # cooked weight of the whole dish, if the model gave one
            proposals.append({
                "kind": "recipe", "label": label,
                "name": str(it.get("recipe_name") or label)[:80], "save": True,
                "yield_g": whole or total, "eat_g": eat or whole or total,
                "ingredients": rows, "meal": meal, "log_date": day})
            continue
        r = _match(conn, label, it.get("search_terms"), it.get("state"), it.get("quantity"), it.get("unit"),
                   it.get("grams_estimate"))
        r.update({"kind": "food", "meal": meal, "log_date": day})
        proposals.append(r)
    yield "done", proposals
