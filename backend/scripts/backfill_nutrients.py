"""Add nutrients introduced after the first import to an EXISTING database, without re-importing foods.

Usage: python scripts/backfill_nutrients.py [--db PATH] [--raw DIR]

Why not re-run the importers: each importer deletes its source's foods, and intake_log references foods
without ON DELETE, so the delete fails once anything is logged. This script only touches food_nutrients.

Rules (same as the importers):
- Only codes that are NOT in ORIGINAL_CODES (the 12 first-import nutrients) are processed.
- Blank/absent source values are skipped (= missing). Trace/N qualifiers are kept as in the importers.
- A value is inserted when no row exists. An existing row is replaced only if it is an AI estimate
  (estimated = 1) or NULL; measured values are never overwritten.
- Foods are matched by (source, source_food_id). Unmatched source foods are counted, not created.
- Idempotent: safe to re-run.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from app import db  # noqa: E402
import import_cofid as cofid  # noqa: E402
import import_usda_foundation as fnd  # noqa: E402
import import_usda_sr_legacy as sr  # noqa: E402

ORIGINAL_CODES = {
    "energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sugars_g", "sat_fat_g",
    "sodium_mg", "calcium_mg", "iron_mg", "vitamin_c_mg", "vitamin_b12_ug",
}


def sr_values(raw: Path):
    d = sr.find_dir(raw)
    mapping = {fid: code for fid, (code, _unit) in sr.NUTRIENT_MAP.items() if code not in ORIGINAL_CODES}
    for r in sr.read_csv(d / "food_nutrient.csv"):
        fid = int(r["nutrient_id"])
        if fid in mapping and r["amount"] != "":
            yield r["fdc_id"], mapping[fid], float(r["amount"]), None


def foundation_values(json_path: Path):
    foods = json.loads(Path(json_path).read_text(encoding="utf-8"))["FoundationFoods"]
    for f in foods:
        by_id = {}
        for n in f.get("foodNutrients", []):
            if n.get("amount") is not None:
                by_id[n["nutrient"]["id"]] = float(n["amount"])
        for code, fdc_ids in fnd.NUTRIENT_MAP.items():
            if code in ORIGINAL_CODES:
                continue
            for fid in fdc_ids:
                if fid in by_id:
                    amount = by_id[fid]
                    if amount < 0:
                        raise SystemExit(f"unexpected negative amount: fdc {fid} in {f['fdcId']}")
                    yield str(f["fdcId"]), code, amount, None
                    break


def cofid_values(xlsx: Path, conn):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    units = {r["code"]: r["unit"] for r in conn.execute("SELECT code, unit FROM nutrients")}
    # (Food Code, Food Name) -> source_food_id, assigned exactly as import_cofid does ('#n' for repeats)
    seen, key_to_sfid = {}, {}
    for r in cofid.sheet_rows(wb, "1.2 Factors")[2]:
        code, name = r[0], r[1]
        if code is None or name is None:
            continue
        sfid = str(code)
        seen[sfid] = seen.get(sfid, 0) + 1
        if seen[sfid] > 1:
            sfid = f"{sfid}#{seen[sfid]}"
        key_to_sfid[(str(code), name)] = sfid
    for (sheet, tag), code in cofid.NUTRIENT_MAP.items():
        if code in ORIGINAL_CODES:
            continue
        hdr, tags, data = cofid.sheet_rows(wb, sheet)
        if tag not in tags:
            raise SystemExit(f"tag not found: {sheet}/{tag}")
        i = tags.index(tag)
        unit = cofid.column_unit(sheet, tag, hdr[i])
        if unit != units[code]:
            raise SystemExit(f"unit mismatch {sheet}/{tag}: header {hdr[i]!r} vs {units[code]}")
        for r in data:
            if r[0] is None or r[1] is None:
                continue
            sfid = key_to_sfid.get((str(r[0]), r[1]))
            p = cofid.parse_value(r[i])
            if sfid is None or p is None:
                continue
            yield sfid, code, p[0], p[1]


def _apply(conn, source_code, values):
    """values: iterable of (source_food_id, code, value, qualifier)."""
    row = conn.execute("SELECT id FROM sources WHERE code = ?", (source_code,)).fetchone()
    if row is None:
        raise SystemExit(f"source {source_code} not in DB: import it first")
    food = {r["source_food_id"]: r["id"] for r in conn.execute(
        "SELECT id, source_food_id FROM foods WHERE source_id = ?", (row["id"],))}
    nut = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM nutrients")}
    unmatched = written = 0
    for sfid, code, val, q in values:
        fid = food.get(sfid)
        if fid is None:
            unmatched += 1
            continue
        conn.execute(
            "INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g, qualifier, estimated) "
            "VALUES (?,?,?,?,0) ON CONFLICT(food_id, nutrient_id) DO UPDATE SET "
            "value_per_100g = excluded.value_per_100g, qualifier = excluded.qualifier, estimated = 0 "
            "WHERE food_nutrients.estimated = 1 OR food_nutrients.value_per_100g IS NULL",
            (fid, nut[code], val, q))
        written += 1
    conn.commit()
    return {"written": written, "unmatched": unmatched}


def run(raw: Path, conn) -> dict:
    fnd_json = next((raw / "usda_foundation_json").glob("*.json"))
    return {
        "usda_sr_legacy": _apply(conn, "usda_sr_legacy", sr_values(raw / "usda_sr_legacy")),
        "usda_foundation": _apply(conn, "usda_foundation", foundation_values(fnd_json)),
        "cofid": _apply(conn, "cofid", cofid_values(raw / "cofid" / "CoFID_2021.xlsx", conn)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--raw", type=Path, default=HERE.parent / "data" / "raw")
    a = ap.parse_args()
    print(run(a.raw, db.connect(a.db)))


if __name__ == "__main__":
    main()
