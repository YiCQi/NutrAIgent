from app.engine import analysis


def _intake(value, missing=()):
    return {"totals": {"calcium_mg": {"value": value, "unit": "mg", "missing_entries": list(missing)}}}


TARGET = {"calcium_mg": {"value": 700.0, "unit": "mg", "kind": "min"}}


def test_min_target_never_excess():
    row = analysis.compare(_intake(1400.0), TARGET)[0]
    assert row["status"] == "ok" and row["percent"] == 200.0  # above 150% is not excess for a minimum


def test_min_target_low_and_unknown():
    assert analysis.compare(_intake(300.0), TARGET)[0]["status"] == "deficient"
    assert analysis.compare(_intake(600.0), TARGET)[0]["status"] == "low"
    assert analysis.compare(_intake(300.0, missing=[7]), TARGET)[0]["status"] == "unknown"


def test_short_min_nutrient_is_a_gap_status():
    from app.engine import gaps
    comp = analysis.compare(_intake(300.0), TARGET)
    assert comp[0]["kind"] == "min" and comp[0]["status"] in gaps.SHORT_STATUSES
