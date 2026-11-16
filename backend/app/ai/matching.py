"""Deterministic food matching: alias table first, then a re-ranker over database search hits.

Plain search orders by name length, which prefers odd short names (Broccoli raab, glutinous rice,
Yam). The re-ranker scores how well a food name fits the query: extra words in the name that the
query did not ask for are penalised (heavily for variant words such as leaves/raab/frozen/canned),
a different first word is penalised, "with salt" is penalised (salt is logged as its own item),
and a raw/cooked mismatch with the requested state is penalised. Lower score = better.
"""
import re

from .. import foods
from .aliases import ALIASES

PENALTY = {
    "leaves": 3, "raab": 3, "glutinous": 3, "imitation": 3, "babyfood": 3, "candied": 2, "restaurant": 2,
    "fast": 2, "frozen": 1.5, "canned": 1.5, "dried": 1.5, "dehydrated": 2, "flavored": 2, "flavoured": 2,
    "mix": 1.5, "powder": 1.5, "juice": 2, "soup": 2, "sauce": 1.5, "snacks": 2, "pickled": 2, "smoked": 1.5,
    "cured": 1.5, "fried": 1.0, "breaded": 2, "stuffed": 2, "unprepared": 0.5, "substitute": 3, "analog": 3,
    "oil-roasted": 2, "spread": 2, "burger": 2, "stew": 2, "sandwich": 2, "pie": 2, "cake": 2, "jam": 2,
}
SOURCE_BIAS = {"usda_foundation": 0.0, "usda_sr_legacy": 0.05, "cofid": 0.1}
NEUTRAL = ("without added salt", "without salt", "unsalted", "no salt added")


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9%.]+", s.lower())


def _stem(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _fit(nw: str, qw: str) -> bool:
    """Same word up to plural; a longer different word (lambsquarters vs lamb) does not fit."""
    return nw == qw or _stem(nw) == _stem(qw)


def score(name: str, query: str, state: str | None = None, food_state: str | None = None,
          source: str | None = None) -> float:
    q = _words(query)
    n = name.lower()
    for p in NEUTRAL:
        n = n.replace(p, " ")
    nw = _words(n)
    pen = 0.0
    for w in nw:
        if not any(_fit(w, x) for x in q):
            pen += PENALTY.get(w, 0.4)
    if "with salt" in n and not any(x == "salt" for x in q):
        pen += 1.0
    if nw and q and not _fit(nw[0], q[0]):
        pen += 1.5
    if state in ("raw", "cooked") and food_state in ("raw", "cooked") and food_state != state:
        pen += 3.0
    return pen + SOURCE_BIAS.get(source or "", 0.1)


def alias_query(label: str | None, terms: list[str]) -> str | None:
    """Canonical search query for a wording, or None. Exact key match (label, then first search term),
    then longest Chinese key contained in the label."""
    for cand in [label] + list(terms[:1]):
        if isinstance(cand, str) and cand.strip().lower() in ALIASES:
            return ALIASES[cand.strip().lower()]
    if isinstance(label, str):
        hits = [k for k in ALIASES if len(k) >= 2 and re.search(r"[一-鿿]", k) and k in label]
        if hits:
            return ALIASES[max(hits, key=len)]
    return None


def candidates(conn, label: str | None, terms: list[str], state: str | None, limit: int = 6) -> list[dict]:
    """Best-first candidate foods for one wording. Alias query leads; model terms follow as fallback."""
    queries = []
    aq = alias_query(label, terms)
    if aq:
        queries.append(aq)
    queries += [t for t in terms if isinstance(t, str) and t.strip()]
    if queries:  # progressively shorter versions of the first query as a last resort
        words = queries[0].split()
        queries += [" ".join(words[:k]) for k in range(len(words) - 1, 0, -1)]
    seen, out = set(), []
    for q in queries:
        res = foods.search(conn, q, 150)
        if not res:
            continue
        for r in res:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            s = score(r["name"], q, state, r["state"], r["source"])
            if r["source"] == "user_recipe":
                s = -10 if " ".join(_words(r["name"])) == " ".join(_words(q)) else s + 1.0
            out.append({**r, "_score": s})
        break
    out.sort(key=lambda r: (r["_score"], len(r["name"]), r["name"]))
    return out[:limit]
