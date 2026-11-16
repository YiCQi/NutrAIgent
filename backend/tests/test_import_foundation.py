import importlib.util
import json
from pathlib import Path

from app import db

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_usda_foundation.py"
spec = importlib.util.spec_from_file_location("imp_found", SCRIPT)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)


def nut(i, unit, amount=None):
    n = {"nutrient": {"id": i, "unitName": unit}}
    if amount is not None:
        n["amount"] = amount
    return n


def test_foundation_import(tmp_path):
    data = {"FoundationFoods": [{
        "fdcId": 10, "description": "Hummus, raw", "foodCategory": {"description": "Legumes"},
        "foodNutrients": [
            nut(2047, "kcal", 300), nut(2048, "kcal", 290),   # specific wins over general
            nut(1003, "g", 8.0),
            nut(1093, "mg", 0),                                # measured zero
            nut(1178, "µg", 1.5),                         # unit normalised
            nut(1004, "g"),                                    # no amount -> missing
            nut(1005, "g", -0.4),                              # negative by-difference carb -> 0.0
        ],
        "foodPortions": [{"value": 2.0, "measureUnit": {"name": "tablespoon"}, "modifier": "",
                          "gramWeight": 33.9},
                         {"value": 1.0, "measureUnit": {"name": "undetermined"}, "gramWeight": 0}],
    }]}
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    conn = db.connect(":memory:")
    s = imp.run(p, conn)
    assert s == {"foods": 1, "nutrient_values": 5, "portions": 1, "clamped_negative": 1}
    imp.run(p, conn)
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 1

    def val(code):
        r = conn.execute("SELECT value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id "
                         "WHERE n.code=?", (code,)).fetchone()
        return None if r is None else r[0]

    assert val("energy_kcal") == 290
    assert val("sodium_mg") == 0.0
    assert val("vitamin_b12_ug") == 1.5
    assert val("fat_g") is None
    assert val("carbohydrate_g") == 0.0
    assert conn.execute("SELECT description FROM portions").fetchone()[0] == "2 tablespoon"
    assert conn.execute("SELECT state, food_group FROM foods").fetchone()[:] == ("raw", "Legumes")
