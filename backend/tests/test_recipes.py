import json

import pytest
from fastapi.testclient import TestClient

from app import db, recipes
from app.ai import nllog
from app.main import app, get_conn, get_provider_factory
from tests.test_ai import Scripted, events, text


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    names = ["Pork, spare ribs, braised", "Soy sauce", "Salt, table", "Sugars, granulated"]
    for n in names:
        c.execute("INSERT INTO foods (name, source_id) VALUES (?,1)", (n,))
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    rows = [  # food_id, code, value per 100 g (fibre missing for soy sauce; salt has sodium)
        (1, "energy_kcal", 300), (1, "sodium_mg", 80), (1, "fibre_g", 0),
        (2, "energy_kcal", 60), (2, "sodium_mg", 5600),
        (3, "energy_kcal", 0), (3, "sodium_mg", 38758), (3, "fibre_g", 0),
        (4, "energy_kcal", 400), (4, "sodium_mg", 1), (4, "fibre_g", 0)]
    for f, code, v in rows:
        c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                  (f, ids[code], v))
    c.commit()
    return c


def nut(conn, food_id, code):
    r = conn.execute("SELECT value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id "
                     "WHERE fn.food_id = ? AND n.code = ?", (food_id, code)).fetchone()
    return None if r is None else r[0]


ING = [{"food_id": 1, "grams": 200}, {"food_id": 2, "grams": 15}, {"food_id": 3, "grams": 2},
       {"food_id": 4, "grams": 10}]


def test_recipe_nutrients_computed_and_missing_propagates(conn):
    rid = recipes.create(conn, "红烧排骨", ING)
    raw = 227.0
    # per 100 g = sum / yield * 100 with yield defaulting to the raw total
    kcal = (200 * 300 + 15 * 60 + 0 + 10 * 400) / 100 / raw * 100
    assert nut(conn, rid, "energy_kcal") == pytest.approx(kcal, abs=1e-3)
    na = (200 * 80 + 15 * 5600 + 2 * 38758 + 10 * 1) / 100 / raw * 100
    assert nut(conn, rid, "sodium_mg") == pytest.approx(na, abs=1e-2)
    assert nut(conn, rid, "fibre_g") is None  # soy sauce has no fibre data -> recipe unknown, not 0

    recipes.update(conn, rid, "红烧排骨", ING, yield_g=150)  # cooked weight after water loss
    assert nut(conn, rid, "energy_kcal") == pytest.approx(kcal * raw / 150, abs=1e-3)
    assert recipes.get(conn, rid)["yield_g"] == 150


def test_recipe_rules(conn):
    rid = recipes.create(conn, "A", ING)
    with pytest.raises(recipes.RecipeError):
        recipes.create(conn, "A", ING)  # duplicate name
    with pytest.raises(recipes.RecipeError):
        recipes.create(conn, "B", [{"food_id": rid, "grams": 10}])  # recipe inside recipe
    with pytest.raises(recipes.RecipeError):
        recipes.create(conn, "C", [{"food_id": 999, "grams": 10}])
    with pytest.raises(recipes.RecipeError):
        recipes.create(conn, "D", [])
    conn.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-01','other',?,100)", (rid,))
    with pytest.raises(recipes.RecipeError):
        recipes.delete(conn, rid)  # in use
    conn.execute("DELETE FROM intake_log")
    recipes.delete(conn, rid)
    assert recipes.list_all(conn) == []
    assert conn.execute("SELECT COUNT(*) FROM food_nutrients WHERE food_id = ?", (rid,)).fetchone()[0] == 0


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_recipe_api_and_logging(client, conn):
    r = client.post("/api/recipes", json={"name": "红烧排骨", "ingredients": ING})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.post("/api/recipes", json={"name": "红烧排骨", "ingredients": ING}).status_code == 409
    assert client.get("/api/recipes").json()[0]["n_ingredients"] == 4
    # recipe behaves like any food: searchable (first), loggable, counted in the day total
    hits = client.get("/api/foods", params={"q": "红烧排骨"}).json()
    assert hits[0]["id"] == rid and hits[0]["source"] == "user_recipe"
    assert client.post("/api/intake", json={"log_date": "2026-01-01", "food_id": rid, "grams": 100}).status_code == 201
    day = client.get("/api/intake/2026-01-01").json()
    assert day["totals"]["energy_kcal"]["value"] > 0
    assert day["entries"][0]["nutrients"]["energy_kcal"] > 0
    assert client.delete(f"/api/recipes/{rid}").status_code == 409  # logged
    assert client.put(f"/api/recipes/{rid}", json={"name": "红烧排骨", "ingredients": ING[:2]}).status_code == 200
    assert client.get("/api/recipes/999").status_code == 404


def test_recipe_proposal_from_ingredients(conn):
    parsed = {"intent": "log", "items": [{
        "label": "红烧排骨", "recipe_name": "红烧排骨", "grams_estimate": 250, "meal": "dinner",
        "ingredients": [
            {"label": "排骨", "search_terms": ["pork spare ribs braised"], "grams_estimate": 200},
            {"label": "酱油", "search_terms": ["soy sauce"], "grams_estimate": 15},
            {"label": "盐", "search_terms": ["salt table"], "grams_estimate": 2},
            {"label": "神秘酱", "search_terms": ["zzzz"], "grams_estimate": 5}]}]}
    out = list(nllog.build_proposals(conn, parsed, "2026-01-02"))[-1][1]
    rec = out[0]
    assert rec["kind"] == "recipe" and rec["save"] is False and rec["eat_g"] == 250.0
    assert [i["food_name"] for i in rec["ingredients"]] == ["Pork, spare ribs, braised", "Soy sauce", "Salt, table", None]
    assert rec["yield_g"] == 217.0  # unmatched row has no grams


def test_ask_when_info_missing_and_status_keys(client):
    cid = client.post("/api/conversations").json()["id"]
    fake = Scripted([text(json.dumps({"intent": "ask", "question": "用了哪些调料？大概多少？"}))])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    r = client.post(f"/api/conversations/{cid}/chat", json={"content": "我吃了红烧排骨", "lang": "zh"})
    app.dependency_overrides.pop(get_provider_factory)
    evs = events(r)
    assert evs[0] == {"type": "status", "key": "understanding"}
    msg = evs[-1]["message"]
    assert msg["content"] == "用了哪些调料？大概多少？" and msg["meta"] == {"kind": "ask"}
    assert "Chinese" in fake.seen[0][0]  # language hint reached the parser prompt


def test_parse_includes_saved_recipe_names(conn):
    recipes.create(conn, "红烧排骨", ING)
    p = Scripted([text('{"intent":"chat"}')])
    nllog.parse(p, [{"role": "user", "content": "x"}], "2026-01-02", "en", recipes.names(conn))
    assert "红烧排骨" in p.seen[0][0]


def test_predicted_sauce_flags_totals_and_per100(conn):
    parsed = {"intent": "log", "items": [{
        "label": "红烧排骨", "recipe_name": "红烧排骨", "total_g": 300, "grams_estimate": 150, "meal": "dinner",
        "ingredients": [
            {"label": "排骨", "search_terms": ["pork spare ribs braised"], "role": "main", "predicted": False,
             "grams_estimate": 200},
            {"label": "酱油", "search_terms": ["soy sauce"], "role": "sauce", "predicted": True, "grams_estimate": 15},
            {"label": "神秘酱", "search_terms": ["zzzz"], "role": "sauce", "predicted": True, "grams_estimate": 5}]}]}
    rec = list(nllog.build_proposals(conn, parsed, "2026-01-02"))[-1][1][0]
    main, soy, nothing = rec["ingredients"]
    assert (main["role"], main["predicted"]) == ("main", False)
    assert main["grams_basis"] == "typical weight estimated by the AI (please check)"
    assert (soy["role"], soy["predicted"], soy["grams_basis"]) == ("sauce", True, "predicted by AI (please check)")
    assert soy["grams"] == 15.0 and soy["per100"]["fibre_g"] is None  # missing stays None, not 0
    assert nothing["food_id"] is None and nothing["per100"] == {} and nothing["role"] == "sauce"
    assert rec["yield_g"] == 300.0 and rec["eat_g"] == 150.0  # model total_g used as cooked weight
    no_total = dict(parsed["items"][0]); del no_total["total_g"]
    rec2 = list(nllog.build_proposals(conn, {"items": [no_total]}, "2026-01-02"))[-1][1][0]
    assert rec2["yield_g"] == 215.0  # no total_g: falls back to ingredient sum (unmatched row adds nothing)
