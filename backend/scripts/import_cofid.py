"""Import UK CoFID 2021 (McCance & Widdowson integrated dataset, xlsx) into the NutrAIgent DB.

Usage: python scripts/import_cofid.py [--xlsx FILE] [--db PATH]

Data rules (per CoFID 'Notes' sheet):
- numeric value        -> stored (0 = measured zero)
- 'Tr'  (trace)        -> value 0.0 + qualifier 'trace'
- 'N'   (present, no reliable amount) -> value NULL + qualifier 'N' (treated as MISSING in totals)
- blank cell           -> no row = MISSING
Values are per 100 g (alcoholic drinks per 100 ml; not converted).
Sheets are joined on (Food Code, Food Name) because source code 13-669 is duplicated
(Aubergine / Watercress); the second occurrence is stored as '13-669#2'.
Fibre = AOAC fibre (matches the UK 30 g AOAC reference); NSP not used.
Saturated fat = 'Satd FA /100g fd' (per 100 g food).
`food_group` = CoFID group code (names not in the workbook). `edible_portion_pct` from the
'Edible proportion' fraction x100; 'N' -> NULL.
Idempotent: re-running replaces this source's foods.
"""
import argparse
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db  # noqa: E402

SOURCE = ("cofid", "UK McCance and Widdowson's Composition of Foods Integrated Dataset", "2021",
          "https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid",
          "Open Government Licence v3.0")

# (sheet, CoFID tag in row 2) -> (our code)
NUTRIENT_MAP = {
    ("1.3 Proximates", "KCALS"): "energy_kcal",
    ("1.3 Proximates", "PROT"): "protein_g",
    ("1.3 Proximates", "CHO"): "carbohydrate_g",
    ("1.3 Proximates", "FAT"): "fat_g",
    ("1.3 Proximates", "AOACFIB"): "fibre_g",
    ("1.3 Proximates", "TOTSUG"): "sugars_g",
    ("1.3 Proximates", "SATFOD"): "sat_fat_g",
    ("1.4 Inorganics", "NA"): "sodium_mg",
    ("1.4 Inorganics", "CA"): "calcium_mg",
    ("1.4 Inorganics", "FE"): "iron_mg",
    ("1.5 Vitamins", "VITC"): "vitamin_c_mg",
    ("1.3 Proximates", "CHOL"): "cholesterol_mg",
    ("1.4 Inorganics", "K"): "potassium_mg",
    ("1.4 Inorganics", "MG"): "magnesium_mg",
    ("1.4 Inorganics", "P"): "phosphorus_mg",
    ("1.4 Inorganics", "ZN"): "zinc_mg",
    ("1.4 Inorganics", "SE"): "selenium_ug",
    ("1.4 Inorganics", "I"): "iodine_ug",
    ("1.5 Vitamins", "RETEQU"): "vitamin_a_ug",
    ("1.5 Vitamins", "VITD"): "vitamin_d_ug",
    ("1.5 Vitamins", "VITE"): "vitamin_e_mg",
    ("1.5 Vitamins", "VITK1"): "vitamin_k_ug",
    ("1.5 Vitamins", "FOLT"): "folate_ug",
    ("1.5 Vitamins", "VITB12"): "vitamin_b12_ug",
}
# Units are checked against the sheet's header text, e.g. 'Sodium (mg)'.
UNIT_RE = re.compile(r"\((kcal|g|mg|µg|ug)\)\s*$")
UNIT_NORM = {"kcal": "kcal", "g": "g", "mg": "mg", "µg": "ug", "ug": "ug"}
# Sheet headers without a unit. CoFID 1.3 'Cholesterol' has no unit in its header; the dataset reports
# cholesterol in mg per 100 g (assumption, to confirm against the CoFID user guide).
UNIT_OVERRIDE = {("1.3 Proximates", "CHOL"): "mg"}


def column_unit(sheet, tag, header):
    if (sheet, tag) in UNIT_OVERRIDE:
        return UNIT_OVERRIDE[(sheet, tag)]
    m = UNIT_RE.search(str(header))
    return UNIT_NORM.get(m.group(1)) if m else None


def derive_state(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    if "raw" in words and "cooked" not in words:
        return "raw"
    if "cooked" in words and "raw" not in words:
        return "cooked"
    return "unknown"


def parse_value(v):
    """Return (value, qualifier) or None for missing."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v), None
    s = str(v).strip()
    if s == "":
        return None
    if s == "Tr":
        return 0.0, "trace"
    if s == "N":
        return None, "N"
    try:
        return float(s), None
    except ValueError:
        raise ValueError(f"unrecognised CoFID value: {v!r}")


def sheet_rows(wb, name):
    rows = list(wb[name].iter_rows(values_only=True))
    return rows[0], rows[1], rows[3:]  # header, tags, data (row index 2 is a name-only/blank row)


def run(xlsx: Path, conn) -> dict:
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    nut_ids = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    nut_unit = {r["code"]: r["unit"] for r in conn.execute("SELECT code, unit FROM nutrients")}

    conn.execute(
        "INSERT INTO sources (code, name, version, url, licence) VALUES (?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, version=excluded.version, "
        "url=excluded.url, licence=excluded.licence", SOURCE)
    sid = conn.execute("SELECT id FROM sources WHERE code = ?", (SOURCE[0],)).fetchone()["id"]
    conn.execute("DELETE FROM foods WHERE source_id = ?", (sid,))

    # Foods from Factors sheet; key (code, name) -> food id
    hdr, _, data = sheet_rows(wb, "1.2 Factors")
    seen = {}
    key_to_food = {}
    for r in data:
        code, name = r[0], r[1]
        if code is None or name is None:
            continue
        sfid = str(code)
        seen[sfid] = seen.get(sfid, 0) + 1
        if seen[sfid] > 1:
            sfid = f"{sfid}#{seen[sfid]}"
        ep = r[7]
        edible = None
        if isinstance(ep, (int, float)) or (isinstance(ep, str) and ep.strip() not in ("", "N")):
            edible = round(float(ep) * 100, 2)
        cur = conn.execute(
            "INSERT INTO foods (name, source_id, source_food_id, food_group, state, edible_portion_pct)"
            " VALUES (?,?,?,?,?,?)",
            (name, sid, sfid, r[3], derive_state(f"{name} {r[2] or ''}"), edible))
        key_to_food[(str(code), name)] = cur.lastrowid

    n_vals = n_trace = n_n = 0
    for sheet in sorted({s for s, _ in NUTRIENT_MAP}):
        hdr, tags, data = sheet_rows(wb, sheet)
        cols = {}
        for i, t in enumerate(tags):
            if (sheet, t) in NUTRIENT_MAP:
                code = NUTRIENT_MAP[(sheet, t)]
                unit = column_unit(sheet, t, hdr[i])
                if unit != nut_unit[code]:
                    raise SystemExit(f"unit mismatch {sheet}/{t}: header {hdr[i]!r} vs {nut_unit[code]}")
                cols[i] = code
        missing_tags = [k for k in NUTRIENT_MAP if k[0] == sheet and k[1] not in tags]
        if missing_tags:
            raise SystemExit(f"tags not found: {missing_tags}")
        batch = []
        for r in data:
            food_id = key_to_food.get((str(r[0]), r[1])) if r[0] is not None else None
            if food_id is None:
                continue
            for i, code in cols.items():
                p = parse_value(r[i])
                if p is None:
                    continue
                val, q = p
                n_vals += 1
                n_trace += q == "trace"
                n_n += q == "N"
                batch.append((food_id, nut_ids[code], val, q))
        conn.executemany(
            "INSERT OR REPLACE INTO food_nutrients (food_id, nutrient_id, value_per_100g, qualifier)"
            " VALUES (?,?,?,?)", batch)
    conn.commit()
    return {"foods": len(key_to_food), "rows": n_vals, "trace": n_trace, "N": n_n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path,
                    default=Path(__file__).resolve().parents[1] / "data/raw/cofid/CoFID_2021.xlsx")
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    a = ap.parse_args()
    print(run(a.xlsx, db.connect(a.db)))


if __name__ == "__main__":
    main()
