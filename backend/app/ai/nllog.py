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

from .. import foods
from .providers import Provider

MEALS = ("breakfast", "lunch", "dinner", "snack", "other")

PARSE_SYSTEM = """You are the parser of a nutrition-tracking app. Today is {today}.
Read the user's latest message (earlier messages are context) and reply with ONE JSON object, nothing else.
If the user is reporting food or drink they consumed (or asking to log it):
{{"intent":"log","items":[{{
  "label":"the food as the user wrote it",
  "search_terms":["english database name","simpler english name","even simpler"],
  "state":"raw|cooked|any",
  "quantity":number or null,"unit":"g|ml|piece|slice|cup|bowl|tbsp|tsp|serving|null",
  "grams_estimate":typical total weight in grams of what the user ate (number),
  "meal":"breakfast|lunch|dinner|snack|other","date":"YYYY-MM-DD or null for today"}}]}}
One item per food or dish the user ate. Do NOT split a dish into seasonings or cooking ingredients (no soy sauce, sugar, oil items unless the user ate them on their own). Use the closest generic database food for a dish (e.g. braised pork ribs -> "pork spare ribs braised cooked"). Only split when the message clearly lists separate foods or drinks; "coffee with soy milk" is two items.
Otherwise (questions, advice, intake/targets queries, chat):
{{"intent":"chat"}}
Database food names are English (USDA/UK style, e.g. "Rice, white, cooked", "Okra, cooked, boiled"). Never output nutrient values."""


def parse(provider: Provider, history: list[dict], today: str) -> dict:
    """One model call. Returns {'intent': 'chat'} if the output is not usable JSON."""
    resp = provider.complete(PARSE_SYSTEM.format(today=today),
                             [{"role": m["role"], "content": m["content"]} for m in history], [])
    text = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {"intent": "chat"}
    try:
        data = json.loads(text[a:b + 1])
    except ValueError:
        return {"intent": "chat"}
    return data if isinstance(data, dict) and data.get("intent") == "log" else {"intent": "chat"}


def _candidates(conn, terms: list[str], state: str | None, limit: int = 6) -> list[dict]:
    seen, out = set(), []
    attempts = [t for t in terms if isinstance(t, str) and t.strip()]
    if attempts:  # progressively shorter versions of the first term as a last resort
        words = attempts[0].split()
        attempts += [" ".join(words[:k]) for k in range(len(words) - 1, 0, -1)]
    for t in attempts:
        res = foods.search(conn, t, limit)
        if res:
            for r in res:
                if r["id"] not in seen:
                    seen.add(r["id"]); out.append(r)
            break
    if state in ("raw", "cooked"):  # stable: matching state first
        out.sort(key=lambda r: r["state"] != state)
    return out[:limit]


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


def build_proposals(conn: sqlite3.Connection, parsed: dict, today: str):
    """Yield ('match', label) progress then finally ('done', proposals)."""
    proposals = []
    for it in (parsed.get("items") or [])[:15]:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label") or "?")[:80]
        yield "match", label
        cands = _candidates(conn, it.get("search_terms") or [], it.get("state"))
        meal = it.get("meal") if it.get("meal") in MEALS else "other"
        day = _valid_date(it.get("date"), today)
        if not cands:
            proposals.append({"label": label, "food_id": None, "food_name": None, "grams": None,
                              "grams_basis": "no database match found", "meal": meal, "log_date": day,
                              "alternatives": []})
            continue
        top = cands[0]
        grams, basis = resolve_grams(conn, top["id"], it.get("quantity"), it.get("unit"), it.get("grams_estimate"))
        proposals.append({
            "label": label, "food_id": top["id"], "food_name": top["name"], "source": top["source"],
            "grams": grams, "grams_basis": basis, "meal": meal, "log_date": day,
            "alternatives": [{"food_id": c["id"], "food_name": c["name"], "source": c["source"]} for c in cands],
        })
    yield "done", proposals
