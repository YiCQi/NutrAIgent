import json

import pytest

from app import db, estimate
from app.engine import analysis
from tests.test_ai import Scripted, text


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Milk', 1)")  # id 1: has calcium only
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Rice', 1)")  # id 2: calcium NULL, rest absent
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,120)", (ids["calcium_mg"],))
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (2,?,NULL)", (ids["calcium_mg"],))
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',1,200)")
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',2,150)")
    c.commit()
    return c


def test_missing_foods_lists_only_gaps(conn):
    foods = estimate.missing_foods(conn, "2026-01-02")
    by_name = {f["name"]: f["missing"] for f in foods}
    assert by_name["Milk"] == ["iron_mg", "vitamin_c_mg", "vitamin_b12_ug"]  # calcium present, not estimated
    assert by_name["Rice"] == list(estimate.ESTIMATE_CODES)


def test_estimate_fills_only_missing_and_flags_them(conn):
    answer = {"foods": [
        {"food_id": 1, "calcium_mg": 999, "iron_mg": 0.03, "vitamin_c_mg": 0, "vitamin_b12_ug": 0.4},
        {"food_id": 2, "calcium_mg": 30, "iron_mg": 500, "vitamin_c_mg": 0, "vitamin_b12_ug": 0},
    ]}
    result = estimate.estimate(conn, Scripted([text(json.dumps(answer))]), estimate.missing_foods(conn, "2026-01-02"))
    assert result == {"stored": 6, "unanswered": []}  # Rice iron 500 is out of range and dropped
    milk_ca = conn.execute("SELECT value_per_100g, estimated FROM food_nutrients WHERE food_id = 1 AND nutrient_id = "
                           "(SELECT id FROM nutrients WHERE code = 'calcium_mg')").fetchone()
    assert (milk_ca["value_per_100g"], milk_ca["estimated"]) == (120, 0)  # measured value untouched
    rice_ca = conn.execute("SELECT value_per_100g, estimated FROM food_nutrients WHERE food_id = 2 AND nutrient_id = "
                           "(SELECT id FROM nutrients WHERE code = 'calcium_mg')").fetchone()
    assert (rice_ca["value_per_100g"], rice_ca["estimated"]) == (30, 1)
    intake = analysis.daily_intake(conn, "2026-01-02")
    assert intake["totals"]["iron_mg"]["estimated"] is True
    assert intake["totals"]["calcium_mg"]["estimated"] is True  # Rice's calcium is an estimate
    assert estimate.missing_foods(conn, "2026-01-02")[0]["missing"] == ["iron_mg"]  # Rice iron still missing


def test_unanswered_foods_reported(conn):
    answer = {"foods": [{"food_id": 1, "iron_mg": 0.1, "vitamin_c_mg": 0, "vitamin_b12_ug": 0.1}]}
    result = estimate.estimate(conn, Scripted([text(json.dumps(answer))]), estimate.missing_foods(conn, "2026-01-02"))
    assert result["unanswered"] == ["Rice"]
