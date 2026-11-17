from app import db
from app.engine import analysis, targets


def _profile(sex="female", weight=60.0):
    return targets.Profile(age=30, sex=sex, height_cm=165.0, weight_kg=weight,
                           activity_level="light", goal="maintenance")


def test_ala_and_linoleic_targets_scale_with_energy():
    res = targets.compute_targets(_profile())
    energy = res["targets"]["energy_kcal"]["value"]
    assert res["targets"]["ala_g"]["value"] == round(energy * 0.005 / 9, 2)  # 0.5 E%
    assert res["targets"]["linoleic_g"]["value"] == round(energy * 0.04 / 9, 2)  # 4 E%
    assert res["targets"]["epa_dha_g"]["value"] == 0.25


def test_sex_neutral_nrv_targets():
    f = targets.compute_targets(_profile("female"))["targets"]
    m = targets.compute_targets(_profile("male"))["targets"]
    assert f["zinc_mg"] == m["zinc_mg"] == {"value": 10.0, "unit": "mg", "kind": "min"}
    assert f["vitamin_d_ug"]["value"] == 5.0 and f["folate_ug"]["value"] == 200.0
    assert "cholesterol_mg" not in f  # no reference value: display only


def test_epa_dha_derived_total_and_missing_rules():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('t','T')")
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Fish', 1)")
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Egg', 1)")
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,0.5)", (ids["epa_g"],))
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,1.0)", (ids["dha_g"],))
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (2,?,0.2)", (ids["epa_g"],))
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',1,200)")
    c.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',2,100)")
    c.commit()
    tot = analysis.daily_intake(c, "2026-01-02")["totals"]
    assert tot["epa_dha_g"]["value"] == 3.2  # EPA 1.0 (fish) + 0.2 (egg) + DHA 2.0 (fish), measured parts only
    assert tot["epa_dha_g"]["missing_entries"] == [2]  # Egg lacks DHA, so the pair is incomplete
    assert tot["epa_g"]["missing_entries"] == []  # Egg has EPA
