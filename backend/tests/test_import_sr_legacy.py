import importlib.util
import sys
from pathlib import Path

from app import db

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_usda_sr_legacy.py"
spec = importlib.util.spec_from_file_location("imp_sr", SCRIPT)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)


def _w(p, text):
    p.write_text(text, encoding="utf-8")


def make_fixture(tmp_path):
    _w(tmp_path / "sr_legacy_food.csv", '"fdc_id","NDB_number"\n"1","11"\n')
    _w(tmp_path / "food.csv",
       '"fdc_id","data_type","description","food_category_id","publication_date"\n'
       '"1","sr_legacy_food","Oats, raw","8","2019-04-01"\n'
       '"2","sr_legacy_food","Rice, cooked","20","2019-04-01"\n')
    _w(tmp_path / "food_category.csv", '"id","code","description"\n"8","0800","Cereals"\n"20","2000","Grains"\n')
    _w(tmp_path / "measure_unit.csv", '"id","name"\n"1000","cup"\n"9999","undetermined"\n')
    rows = ['"id","name","unit_name","nutrient_number","rank"']
    for fid, (code, unit) in imp.NUTRIENT_MAP.items():
        rows.append(f'"{fid}","n{fid}","{unit}","0","0"')
    _w(tmp_path / "nutrient.csv", "\n".join(rows) + "\n")
    _w(tmp_path / "food_nutrient.csv",
       '"id","fdc_id","nutrient_id","amount"\n'
       '"1","1","1008","380"\n"2","1","1093","0"\n"3","2","1008","130"\n"4","1","9999","5"\n')
    _w(tmp_path / "food_portion.csv",
       '"id","fdc_id","seq_num","amount","measure_unit_id","portion_description","modifier","gram_weight"\n'
       '"1","1","1","1","1000","","dry","81"\n"2","2","1","1","9999","","","0"\n')


def test_import_zero_vs_missing_and_idempotent(tmp_path):
    make_fixture(tmp_path)
    conn = db.connect(":memory:")
    s = imp.run(tmp_path, conn)
    assert s == {"foods": 2, "nutrient_values": 3, "portions": 1}
    imp.run(tmp_path, conn)  # idempotent
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 2
    q = ("SELECT value_per_100g FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id "
         "WHERE fn.food_id=? AND n.code=?")
    oats = conn.execute("SELECT id FROM foods WHERE name='Oats, raw'").fetchone()[0]
    assert conn.execute(q, (oats, "sodium_mg")).fetchone()[0] == 0.0       # measured zero
    assert conn.execute(q, (oats, "fibre_g")).fetchone() is None            # missing
    assert conn.execute("SELECT state FROM foods WHERE id=?", (oats,)).fetchone()[0] == "raw"
    assert conn.execute("SELECT description FROM portions").fetchone()[0] == "1 cup dry"
