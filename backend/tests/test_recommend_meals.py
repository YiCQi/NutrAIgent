import json

from app import recommend
from tests.test_ai import Scripted, text
from tests.test_gaps import conn, ctx  # noqa: F401  (fixtures: lentils id 1; 2026-01-02 empty)
from tests.test_recommend import add_broccoli


def add_food(c, name, nutrients):
    c.execute("INSERT INTO foods (name, source_id) VALUES (?, 1)", (name,))
    fid = c.execute("SELECT id FROM foods WHERE name = ?", (name,)).fetchone()["id"]
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    for code, v in nutrients.items():
        c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                  (fid, ids[code], v))
    c.commit()
    return fid


def log(c, meal):
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02', ?, 1, 100)", (meal,))
    c.commit()


def test_open_slots_close_once_a_later_meal_is_eaten(conn):
    assert recommend.open_meals(conn, "2026-01-02") == ["breakfast", "lunch", "dinner", "snack"]
    log(conn, "lunch")
    assert recommend.open_meals(conn, "2026-01-02") == ["dinner", "snack"]  # breakfast is earlier, closed
    log(conn, "dinner")
    assert recommend.open_meals(conn, "2026-01-02") == ["snack"]


def test_closed_meal_rejected_and_snack_ready_to_eat_only(conn):
    add_broccoli(conn)
    add_food(conn, "Apples, raw, with skin",
             {"energy_kcal": 52, "protein_g": 0.3, "carbohydrate_g": 14, "fat_g": 0.2, "fibre_g": 2.4})
    add_food(conn, "Rice, white, cooked", {"energy_kcal": 130, "protein_g": 2.7, "carbohydrate_g": 28, "fat_g": 0.3})
    log(conn, "dinner")
    proposal = {"options": [
        {"title": "Broccoli dinner", "meal": "dinner", "items": [["Broccoli", "Broccoli, cooked", 300]]},
        {"title": "Rice and apple", "meal": "snack",
         "items": [["Rice", "Rice, white, cooked", 150], ["Apple", "Apples, raw, with skin", 150]]},
    ]}
    rec = list(recommend.generate(conn, Scripted([text(json.dumps(proposal))]), "2026-01-02", "en"))[-1]["recommendation"]
    assert [o["meal"] for o in rec["options"]] == ["snack"]  # dinner slot closed
    snack = rec["options"][0]
    assert snack["title"] == "Apple"  # snack titled by its items, cooked rice removed
    assert [i["label"] for i in snack["items"]] == ["Apple"]
    assert rec["dropped"] >= 2
