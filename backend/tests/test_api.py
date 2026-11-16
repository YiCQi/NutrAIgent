import pytest
from fastapi.testclient import TestClient

from app import db
from app.engine.targets import Profile, compute_targets
from app.main import app, get_conn


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    c.execute("INSERT INTO foods (name, source_id, state) VALUES ('Oats', 1, 'raw')")
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    c.execute("INSERT INTO food_nutrients VALUES (1,?,?)", (ids["energy_kcal"], 380.0))
    c.execute("INSERT INTO food_nutrients VALUES (1,?,?)", (ids["sodium_mg"], 0.0))  # true zero
    # fibre_g absent -> missing
    c.commit()
    return c


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_mifflin_known_value():
    t = compute_targets(Profile(30, "male", 180, 80, "sedentary", "maintenance"))
    assert t["trace"]["bmr_kcal"] == 1780.0  # 800+1125-150+5
    assert t["targets"]["energy_kcal"]["value"] == round(1780 * 1.2, 1)


def test_zero_vs_missing(client):
    f = client.get("/api/foods/1").json()
    by = {n["code"]: n["value"] for n in f["nutrients"]}
    assert by["sodium_mg"] == 0.0
    assert by["fibre_g"] is None


def test_intake_flow(client):
    assert client.get("/api/targets").status_code == 404
    client.put("/api/profile", json=dict(age=30, sex="male", height_cm=180, weight_kg=80,
                                         activity_level="sedentary", goal="maintenance"))
    r = client.post("/api/intake", json=dict(log_date="2026-01-01", food_id=1, grams=200))
    assert r.status_code == 201
    d = client.get("/api/intake/2026-01-01").json()
    assert d["totals"]["energy_kcal"]["value"] == 760.0
    assert d["totals"]["fibre_g"]["missing_entries"] == [1]
    assert d["totals"]["sodium_mg"]["missing_entries"] == []
    fibre = next(c for c in d["comparison"] if c["nutrient"] == "fibre_g")
    assert fibre["status"] == "unknown" and fibre["incomplete_data"]


def test_unknown_food_404(client):
    r = client.post("/api/intake", json=dict(log_date="2026-01-01", food_id=99, grams=10))
    assert r.status_code == 404
