import importlib.util
from pathlib import Path

import openpyxl

from app import db

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_cofid.py"
spec = importlib.util.spec_from_file_location("imp_cofid", SCRIPT)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

PAD = [None] * 7


def _sheet(wb, title, cols, rows):
    ws = wb.create_sheet(title)
    ws.append(["Food Code", "Food Name", "Description", "Group", "Previous", "Refs", "Footnote"] + [c[0] for c in cols])
    ws.append(PAD + [c[1] for c in cols])
    ws.append([None] * (7 + len(cols)))
    for r in rows:
        ws.append(r)


def make_xlsx(path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    foods = [("1-1", "Oats, raw"), ("1-2", "Salt"), ("1-2", "Pepper")]  # duplicate code
    ws = wb.create_sheet("1.2 Factors")
    ws.append(["Food Code", "Food Name", "Description", "Group", "Previous", "Refs", "Footnote", "Edible proportion"])
    ws.append([None] * 8)
    ws.append([None] * 8)
    ws.append(["1-1", "Oats, raw", "d", "AA", None, None, None, "0.9"])
    ws.append(["1-2", "Salt", "d", "AB", None, None, None, "N"])
    ws.append(["1-2", "Pepper", "d", "AB", None, None, None, 1])
    _sheet(wb, "1.3 Proximates",
           [("Energy (kcal) (kcal)", "KCALS"), ("Protein (g)", "PROT"), ("Carbohydrate (g)", "CHO"),
            ("Fat (g)", "FAT"), ("AOAC fibre (g)", "AOACFIB"), ("Total sugars (g)", "TOTSUG"),
            ("Satd FA /100g fd (g)", "SATFOD")],
           [["1-1", "Oats, raw", None, None, None, None, None, "380", 12, 60, 7, "Tr", "N", None],
            ["1-2", "Salt", None, None, None, None, None, 0, 0, 0, 0, 0, 0, 0],
            ["1-2", "Pepper", None, None, None, None, None, 250, 10, 60, 3, 25, 0.6, 1]])
    _sheet(wb, "1.4 Inorganics", [("Sodium (mg)", "NA"), ("Calcium (mg)", "CA"), ("Iron (mg)", "FE")],
           [["1-1", "Oats, raw", None, None, None, None, None, 5, 50, 4],
            ["1-2", "Salt", None, None, None, None, None, 39000, 0, 0],
            ["1-2", "Pepper", None, None, None, None, None, 20, 400, 10]])
    _sheet(wb, "1.5 Vitamins", [("Vitamin B12 (µg)", "VITB12"), ("Vitamin C (mg)", "VITC")],
           [["1-1", "Oats, raw", None, None, None, None, None, 0, "Tr"],
            ["1-2", "Salt", None, None, None, None, None, None, None],
            ["1-2", "Pepper", None, None, None, None, None, 0, 21]])
    wb.save(path)


def test_cofid_import(tmp_path):
    x = tmp_path / "c.xlsx"
    make_xlsx(x)
    conn = db.connect(":memory:")
    s = imp.run(x, conn)
    assert s["foods"] == 3
    imp.run(x, conn)  # idempotent
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 3
    ids = {r[0] for r in conn.execute("SELECT source_food_id FROM foods")}
    assert ids == {"1-1", "1-2", "1-2#2"}

    def val(food, code):
        return conn.execute(
            "SELECT value_per_100g, qualifier FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id "
            "JOIN foods f ON f.id=fn.food_id WHERE f.name=? AND n.code=?", (food, code)).fetchone()

    assert tuple(val("Oats, raw", "energy_kcal")) == (380.0, None)      # string number parsed
    assert tuple(val("Oats, raw", "fat_g")) == (7.0, None)
    assert tuple(val("Oats, raw", "fibre_g")) == (0.0, "trace")         # Tr
    assert tuple(val("Oats, raw", "sugars_g")) == (None, "N")           # N -> missing
    assert val("Oats, raw", "sat_fat_g") is None                        # blank -> missing
    assert tuple(val("Salt", "energy_kcal")) == (0.0, None)             # measured zero
    assert val("Salt", "vitamin_c_mg") is None
    assert tuple(val("Pepper", "calcium_mg")) == (400.0, None)          # duplicate code joined by name
    edible = {r[0]: r[1] for r in conn.execute("SELECT name, edible_portion_pct FROM foods")}
    assert edible == {"Oats, raw": 90.0, "Salt": None, "Pepper": 100.0}
    assert conn.execute("SELECT state FROM foods WHERE name='Oats, raw'").fetchone()[0] == "raw"
