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
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,?)", (ids["energy_kcal"], 380.0))
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,?)", (ids["sodium_mg"], 0.0))  # true zero
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


def test_edit_intake_grams(client):
    client.post("/api/intake", json=dict(log_date="2026-01-02", food_id=1, grams=200))
    assert client.patch("/api/intake/1", json=dict(grams=50)).json() == {"id": 1, "grams": 50.0}
    d = client.get("/api/intake/2026-01-02").json()
    assert d["totals"]["energy_kcal"]["value"] == 190.0
    assert d["entries"][0]["grams"] == 50 and d["entries"][0]["nutrients"]["energy_kcal"] == 190.0
    assert client.patch("/api/intake/1", json=dict(grams=0)).status_code == 422
    assert client.patch("/api/intake/999", json=dict(grams=10)).status_code == 404


def test_search_tokens_any_order(client):
    assert [f["name"] for f in client.get("/api/foods", params={"q": "OATS"}).json()] == ["Oats"]
    assert [f["name"] for f in client.get("/api/foods", params={"q": "oa,"}).json()] == ["Oats"]
    assert client.get("/api/foods", params={"q": "ats"}).json() == []  # word-start only
    assert client.get("/api/foods", params={"q": "oats nothing"}).json() == []
    assert client.get("/api/foods", params={"q": "100%"}).json() == []  # wildcard escaped


def test_food_detail_has_portions(client):
    assert client.get("/api/foods/1").json()["portions"] == []


def test_unknown_food_404(client):
    r = client.post("/api/intake", json=dict(log_date="2026-01-01", food_id=99, grams=10))
    assert r.status_code == 404
