import importlib.util
from pathlib import Path

from app import db
from tests.test_import_cofid import make_xlsx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backfill_nutrients.py"
spec = importlib.util.spec_from_file_location("backfill_nutrients", SCRIPT)
bf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bf)


def test_backfill_adds_new_codes_keeps_measured_and_intake(tmp_path):
    x = tmp_path / "c.xlsx"
    make_xlsx(x)
    conn = db.connect(":memory:")
    # an existing CoFID-like DB: foods imported, no intake FK problems allowed
    conn.execute("INSERT INTO sources (code, name) VALUES ('cofid', 'CoFID')")
    sid = conn.execute("SELECT id FROM sources WHERE code='cofid'").fetchone()[0]
    conn.execute("INSERT INTO foods (name, source_id, source_food_id) VALUES ('Oats, raw', ?, '1-1')", (sid,))
    conn.execute("INSERT INTO foods (name, source_id, source_food_id) VALUES ('Salt', ?, '1-2')", (sid,))
    conn.execute("INSERT INTO foods (name, source_id, source_food_id) VALUES ('Pepper', ?, '1-2#2')", (sid,))
    conn.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',1,100)")
    ids = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    # measured calcium must survive; an AI estimate of potassium must be replaced by measured data
    conn.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g, estimated) VALUES (1,?,55,0)",
                 (ids["potassium_mg"],))
    conn.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g, estimated) VALUES (3,?,7,1)",
                 (ids["potassium_mg"],))
    conn.commit()

    res = bf._apply(conn, "cofid", bf.cofid_values(x, conn))
    assert res["unmatched"] == 0 and res["written"] > 0

    def val(food_id, code):
        return tuple(conn.execute("SELECT value_per_100g, estimated FROM food_nutrients WHERE food_id=? AND nutrient_id=?",
                                  (food_id, ids[code])).fetchone())

    assert val(1, "potassium_mg") == (55.0, 0)          # measured existing value not overwritten
    assert val(3, "potassium_mg") == (900.0, 0)         # AI estimate replaced by measured value
    assert val(1, "vitamin_k_ug") == (1.5, 0)           # new code inserted
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 3  # no food deleted
    assert conn.execute("SELECT COUNT(*) FROM intake_log").fetchone()[0] == 1
