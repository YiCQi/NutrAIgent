"""Import USDA FoodData Central SR Legacy (CSV) into the NutrAIgent SQLite DB.

Usage: python scripts/import_usda_sr_legacy.py [--raw DIR] [--db PATH]

Data rules:
- food_nutrient row present (even amount 0) -> stored value (0 = measured zero).
- No row for a nutrient -> no food_nutrients row = MISSING. Never inferred as 0.
- Values are per 100 g (FDC convention).
- `state` is derived only from the words 'raw' / 'cooked' in the description, else 'unknown'.
- edible_portion_pct is NULL: not provided in FDC SR Legacy CSV.
Idempotent: re-running replaces this source's foods.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db  # noqa: E402

SOURCE = ("usda_sr_legacy", "USDA FoodData Central - SR Legacy", "2018-04",
          "https://fdc.nal.usda.gov/download-datasets/", "CC0 1.0")

# FDC nutrient id -> (our code, expected FDC unit)
NUTRIENT_MAP = {
    1008: ("energy_kcal", "KCAL"),
    1003: ("protein_g", "G"),
    1005: ("carbohydrate_g", "G"),
    1004: ("fat_g", "G"),
    1079: ("fibre_g", "G"),
    2000: ("sugars_g", "G"),
    1258: ("sat_fat_g", "G"),
    1093: ("sodium_mg", "MG"),
    1087: ("calcium_mg", "MG"),
    1089: ("iron_mg", "MG"),
    1162: ("vitamin_c_mg", "MG"),
    1178: ("vitamin_b12_ug", "UG"),
    1404: ("ala_g", "G"),
    1278: ("epa_g", "G"),
    1272: ("dha_g", "G"),
    1269: ("linoleic_g", "G"),
    1253: ("cholesterol_mg", "MG"),
    1092: ("potassium_mg", "MG"),
    1090: ("magnesium_mg", "MG"),
    1091: ("phosphorus_mg", "MG"),
    1095: ("zinc_mg", "MG"),
    1103: ("selenium_ug", "UG"),
    1100: ("iodine_ug", "UG"),
    1106: ("vitamin_a_ug", "UG"),
    1114: ("vitamin_d_ug", "UG"),
    1109: ("vitamin_e_mg", "MG"),
    1185: ("vitamin_k_ug", "UG"),
    1177: ("folate_ug", "UG"),
}
UNIT_MAP = {"KCAL": "kcal", "G": "g", "MG": "mg", "UG": "ug"}


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def derive_state(description: str) -> str:
    words = set(re.findall(r"[a-z]+", description.lower()))
    if "raw" in words and "cooked" not in words:
        return "raw"
    if "cooked" in words and "raw" not in words:
        return "cooked"
    return "unknown"


def find_dir(raw: Path) -> Path:
    hits = list(raw.glob("**/sr_legacy_food.csv"))
    if not hits:
        raise SystemExit(f"sr_legacy_food.csv not found under {raw}")
    return hits[0].parent


def run(raw: Path, conn) -> dict:
    d = find_dir(raw)
    nut_ids = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    fdc_nut = {int(r["id"]): r for r in read_csv(d / "nutrient.csv")}
    for fid, (code, unit) in NUTRIENT_MAP.items():
        if fdc_nut[fid]["unit_name"] != unit or UNIT_MAP[unit] != conn.execute(
                "SELECT unit FROM nutrients WHERE code = ?", (code,)).fetchone()["unit"]:
            raise SystemExit(f"unit mismatch for nutrient {fid} {code}")

    conn.execute(
        "INSERT INTO sources (code, name, version, url, licence) VALUES (?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, version=excluded.version, "
        "url=excluded.url, licence=excluded.licence", SOURCE)
    sid = conn.execute("SELECT id FROM sources WHERE code = ?", (SOURCE[0],)).fetchone()["id"]
    conn.execute("DELETE FROM foods WHERE source_id = ?", (sid,))  # cascades values/portions

    cats = {r["id"]: r["description"] for r in read_csv(d / "food_category.csv")}
    units = {r["id"]: r["name"] for r in read_csv(d / "measure_unit.csv")}

    fdc_to_food = {}
    for r in read_csv(d / "food.csv"):
        cur = conn.execute(
            "INSERT INTO foods (name, source_id, source_food_id, food_group, state) VALUES (?,?,?,?,?)",
            (r["description"], sid, r["fdc_id"], cats.get(r["food_category_id"]),
             derive_state(r["description"])))
        fdc_to_food[r["fdc_id"]] = cur.lastrowid

    n_vals = 0
    batch = []
    for r in read_csv(d / "food_nutrient.csv"):
        fid = int(r["nutrient_id"])
        food_id = fdc_to_food.get(r["fdc_id"])
        if fid not in NUTRIENT_MAP or food_id is None or r["amount"] == "":
            continue
        batch.append((food_id, nut_ids[NUTRIENT_MAP[fid][0]], float(r["amount"])))
    conn.executemany(
        "INSERT OR REPLACE INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
        batch)
    n_vals = len(batch)

    portions = []
    for r in read_csv(d / "food_portion.csv"):
        food_id = fdc_to_food.get(r["fdc_id"])
        try:
            grams = float(r["gram_weight"])
        except ValueError:
            continue
        if food_id is None or grams <= 0:
            continue
        unit = units.get(r["measure_unit_id"], "")
        if unit in ("undetermined", ""):
            unit = ""
        parts = [r["amount"], unit, r["portion_description"], r["modifier"]]
        desc = " ".join(p.strip() for p in parts if p and p.strip())
        portions.append((food_id, desc or "serving", grams))
    conn.executemany("INSERT INTO portions (food_id, description, grams) VALUES (?,?,?)", portions)
    conn.commit()
    return {"foods": len(fdc_to_food), "nutrient_values": n_vals, "portions": len(portions)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path(__file__).resolve().parents[1] / "data/raw/usda_sr_legacy")
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    a = ap.parse_args()
    conn = db.connect(a.db)
    print(run(a.raw, conn))


if __name__ == "__main__":
    main()
