"""Import USDA FoodData Central Foundation Foods (JSON) into the NutrAIgent DB.

Usage: python scripts/import_usda_foundation.py [--json FILE] [--db PATH]

Data rules:
- foodNutrient with `amount` -> stored (0 = measured zero). No entry, or entry without
  `amount` -> no row = MISSING.
- Where several FDC nutrient ids can supply one of our nutrients, the first present id wins
  (see NUTRIENT_MAP order). Foundation reports energy mostly as Atwater factors (2047/2048),
  not 1008, so energy: 1008 > 2048 (specific) > 2047 (general).
- Carbohydrate by difference (1005) can be slightly negative in the source (analytical artefact,
  e.g. -0.7 g in raw pork belly). Stored as 0.0 and counted in the `clamped_negative` stat.
  Any other negative amount aborts the import.
- Values per 100 g. `state` from words 'raw'/'cooked' in description else 'unknown'.
- edible_portion_pct NULL (not provided).
Idempotent: re-running replaces this source's foods.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db  # noqa: E402

SOURCE = ("usda_foundation", "USDA FoodData Central - Foundation Foods", "2026-10-29",
          "https://fdc.nal.usda.gov/download-datasets/", "CC0 1.0")

# our code -> FDC nutrient ids in priority order
NUTRIENT_MAP = {
    "energy_kcal": [1008, 2048, 2047],
    "protein_g": [1003],
    "carbohydrate_g": [1005, 1050],
    "fat_g": [1004],
    "fibre_g": [1079, 2033],
    "sugars_g": [1063, 2000],
    "sat_fat_g": [1258],
    "sodium_mg": [1093],
    "calcium_mg": [1087],
    "iron_mg": [1089],
    "vitamin_c_mg": [1162],
    "vitamin_b12_ug": [1178],
    "ala_g": [1404],
    "epa_g": [1278],
    "dha_g": [1272],
    "linoleic_g": [1269],
    "cholesterol_mg": [1253],
    "potassium_mg": [1092],
    "magnesium_mg": [1090],
    "phosphorus_mg": [1091],
    "zinc_mg": [1095],
    "selenium_ug": [1103],
    "iodine_ug": [1100],
    "vitamin_a_ug": [1106],
    "vitamin_d_ug": [1114],
    "vitamin_e_mg": [1109],
    "vitamin_k_ug": [1185],
    "folate_ug": [1177],
}


def norm_unit(u: str) -> str:
    return u.strip().lower().replace("µ", "u").replace("μ", "u")


def derive_state(description: str) -> str:
    words = set(re.findall(r"[a-z]+", description.lower()))
    if "raw" in words and "cooked" not in words:
        return "raw"
    if "cooked" in words and "raw" not in words:
        return "cooked"
    return "unknown"


def run(json_path: Path, conn) -> dict:
    foods = json.loads(Path(json_path).read_text(encoding="utf-8"))["FoundationFoods"]
    nut_ids = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    nut_unit = {r["code"]: r["unit"] for r in conn.execute("SELECT code, unit FROM nutrients")}

    conn.execute(
        "INSERT INTO sources (code, name, version, url, licence) VALUES (?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, version=excluded.version, "
        "url=excluded.url, licence=excluded.licence", SOURCE)
    sid = conn.execute("SELECT id FROM sources WHERE code = ?", (SOURCE[0],)).fetchone()["id"]
    conn.execute("DELETE FROM foods WHERE source_id = ?", (sid,))

    n_vals = n_port = n_clamped = 0
    for f in foods:
        cur = conn.execute(
            "INSERT INTO foods (name, source_id, source_food_id, food_group, state) VALUES (?,?,?,?,?)",
            (f["description"], sid, str(f["fdcId"]), (f.get("foodCategory") or {}).get("description"),
             derive_state(f["description"])))
        food_id = cur.lastrowid

        by_id = {}
        for n in f.get("foodNutrients", []):
            if n.get("amount") is None:
                continue
            nut = n["nutrient"]
            by_id[nut["id"]] = (float(n["amount"]), norm_unit(nut.get("unitName", "")))
        for code, fdc_ids in NUTRIENT_MAP.items():
            for fid in fdc_ids:
                if fid in by_id:
                    amount, unit = by_id[fid]
                    if amount < 0:
                        if fid != 1005:
                            raise SystemExit(f"unexpected negative amount: fdc {fid} in {f['fdcId']}")
                        amount = 0.0
                        n_clamped += 1
                    if unit != nut_unit[code]:
                        raise SystemExit(f"unit mismatch fdc {fid} ({unit}) vs {code} ({nut_unit[code]})")
                    conn.execute(
                        "INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                        (food_id, nut_ids[code], amount))
                    n_vals += 1
                    break

        for p in f.get("foodPortions", []):
            grams = p.get("gramWeight")
            if not grams or grams <= 0:
                continue
            unit = (p.get("measureUnit") or {}).get("name", "")
            if unit == "undetermined":
                unit = ""
            val = p.get("value", p.get("amount"))
            parts = [f"{val:g}" if isinstance(val, (int, float)) else "", unit,
                     p.get("portionDescription") or "", p.get("modifier") or ""]
            desc = " ".join(x.strip() for x in parts if x and x.strip())
            conn.execute("INSERT INTO portions (food_id, description, grams) VALUES (?,?,?)",
                         (food_id, desc or "serving", float(grams)))
            n_port += 1
    conn.commit()
    return {"foods": len(foods), "nutrient_values": n_vals, "portions": n_port,
            "clamped_negative": n_clamped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=Path(__file__).resolve().parents[1] /
                    "data/raw/usda_foundation_json/FoodData_Central_foundation_food_json_2026-10-29.json")
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    a = ap.parse_args()
    print(run(a.json, db.connect(a.db)))


if __name__ == "__main__":
    main()
