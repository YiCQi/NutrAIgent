import json

import pytest

from app import db
from app.ai import agent, tools
from app.engine import gaps
from tests.test_ai import Scripted, text, tool_use

PROFILE_SQL = ("INSERT INTO profile (id, age, sex, height_cm, weight_kg, activity_level, goal) "
               "VALUES (1, 30, 'male', 175, 70, 'light', 'maintenance')")


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    foods = {
        # id 1: lentils (fibre known); id 2: soy sauce (fibre missing -> unknown when eaten)
        "Lentils, cooked": {"energy_kcal": 116, "protein_g": 9, "carbohydrate_g": 20, "fat_g": 0.4,
                            "fibre_g": 7.9, "sodium_mg": 2},
        "Soy sauce": {"energy_kcal": 53, "protein_g": 8, "carbohydrate_g": 5, "fat_g": 0.1, "sodium_mg": 5000},
    }
    for i, (name, vals) in enumerate(foods.items(), 1):
        c.execute("INSERT INTO foods (name, source_id) VALUES (?,1)", (name,))
        for code, v in vals.items():
            if code == "fibre_g" and name == "Soy sauce":
                continue
            c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                      (i, ids[code], v))
    c.execute(PROFILE_SQL)
    # yesterday: lentils only (so most nutrients are short); 2026-01-05 / 01-04: nothing logged
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-01','lunch',1,100)")
    c.commit()
    return c


def ctx(c, day="2026-01-02"):
    return tools.Context(conn=c, today=day)


def test_assess_short_excess_and_energy_left(conn):
    a = gaps.assess(conn, "2026-01-01")
    assert a["entries"] == 1
    fibre = next(s for s in a["short"] if s["nutrient"] == "fibre_g")
    assert fibre["gap"] == pytest.approx(30 - 7.9, abs=0.05)  # fibre target 30 g
    assert 0 < a["energy_left_kcal"] < gaps._targets(conn)["energy_kcal"]["value"]
    # nothing logged -> every target nutrient short, nothing 'repeated' yet
    empty = gaps.assess(conn, "2026-01-03")
    assert empty["entries"] == 0 and len(empty["short"]) >= len(a["short"])


def test_carry_over_marks_repeated_only_when_yesterday_logged(conn):
    # 01-02 is empty but 01-01 was logged: nutrients short yesterday are flagged repeated today
    today = gaps.assess_with_carry(conn, "2026-01-02")
    yesterday_short = set(today["yesterday"]["short"])
    assert today["yesterday"]["logged"] is True and "fibre_g" in yesterday_short
    assert all(s["repeated"] == (s["nutrient"] in yesterday_short) for s in today["short"])
    # 01-05 after an empty 01-04: no evidence, so nothing repeated
    fresh = gaps.assess_with_carry(conn, "2026-01-05")
    assert fresh["yesterday"]["logged"] is False
    assert not any(s["repeated"] for s in fresh["short"])


def test_evaluate_meal_totals_coverage_and_missing_data(conn):
    a = gaps.assess_with_carry(conn, "2026-01-02")
    out = tools.evaluate_meal(conn, a, [{"food_id": 1, "grams": 200}])
    assert out["kcal"] == pytest.approx(232, abs=0.1)
    assert out["totals"]["fibre_g"] == pytest.approx(15.8, abs=0.05)
    assert out["covers_short_percent"]["fibre_g"] == pytest.approx(100 * 15.8 / 30, abs=0.2)
    assert out["exceeds_energy_left"] is False
    # soy sauce has no fibre row: that total is unknown (None), never 0
    mixed = tools.evaluate_meal(conn, a, [{"food_id": 1, "grams": 100}, {"food_id": 2, "grams": 10}])
    assert mixed["totals"]["fibre_g"] is None and mixed["covers_short_percent"]["fibre_g"] is None
    # sodium limit already exceeded in a day -> adding a lot is flagged
    salty = dict(a, excess=[{"nutrient": "sodium_mg", "unit": "mg", "intake": 3000, "limit": 2400, "repeated": False}])
    assert "sodium_mg" in tools.evaluate_meal(conn, salty, [{"food_id": 2, "grams": 100}])["over_limit"]


def test_tool_errors(conn):
    assert tools.call(ctx(conn), "evaluate_meal", {"items": [{"food_id": 1, "grams": 5000}]})["error"].startswith(
        "grams out of range")
    assert tools.call(ctx(conn), "evaluate_meal", {"items": [{"food_id": 99, "grams": 10}]})["error"] == \
        "food 99 not found"
    assert tools.call(ctx(conn), "evaluate_meal", {"items": []})["error"].startswith("items must be")
    assert tools.call(ctx(conn), "get_nutrient_gaps", {"date": "bad"})["error"] == "date must be YYYY-MM-DD"
    bare = db.connect(":memory:")  # no profile
    assert tools.call(ctx(bare), "get_nutrient_gaps", {}) == {"error": "profile not set"}


def test_agent_gap_flow_uses_tools(conn):
    p = Scripted([
        tool_use("1", "get_nutrient_gaps"),
        tool_use("2", "evaluate_meal", items=[{"food_id": 1, "grams": 200}]),
        text("Lentils 200 g cover about half of your fibre gap."),
    ])
    out = list(agent.iter_chat(ctx(conn), p, [{"role": "user", "content": "what should I eat?"}], "en"))
    assert out[-1]["trace"] == [{"tool": "get_nutrient_gaps", "input": {}, "error": None},
                                {"tool": "evaluate_meal", "input": {"items": [{"food_id": 1, "grams": 200}]},
                                 "error": None}]
    fed_back = json.dumps(p.seen[2][1])  # tool results (DB numbers) reached the model
    assert "covers_short_percent" in fed_back and "fibre_g" in fed_back
    assert "get_nutrient_gaps" in agent.SYSTEM
