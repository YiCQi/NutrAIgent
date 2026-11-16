import json

import pytest
from fastapi.testclient import TestClient

from app import db, recommend
from app.ai import tools
from app.engine import gaps
from app.main import app, get_conn, get_provider_factory
from tests.test_ai import Scripted, text
from tests.test_gaps import conn, ctx  # noqa: F401  (fixtures: lentils id 1, soy sauce id 2, yesterday logged)


def add_broccoli(c):
    c.execute("INSERT INTO foods (name, source_id) VALUES ('Broccoli, cooked', 1)")
    fid = c.execute("SELECT id FROM foods WHERE name = 'Broccoli, cooked'").fetchone()["id"]
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    for code, v in {"energy_kcal": 35, "protein_g": 2.4, "carbohydrate_g": 7, "fat_g": 0.4, "fibre_g": 3.3}.items():
        c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)",
                  (fid, ids[code], v))
    c.commit()
    return fid


OPTIONS = {"options": [
    {"title": "Lentil bowl", "meal": "lunch", "items": [["Lentils", "Lentils, cooked", 200]]},
    {"title": "Broccoli side", "meal": "dinner", "items": [["Broccoli", "Broccoli, cooked", 300]]},
    {"title": "Nothing matches", "meal": "lunch", "items": [["x", "zzzz nothing", 100]]},
]}


def test_generate_evaluates_sorts_and_stores(conn):
    add_broccoli(conn)
    p = Scripted([text(json.dumps(OPTIONS))])
    events = list(recommend.generate(conn, p, "2026-01-02", "en"))
    rec = events[-1]["recommendation"]
    assert events[-1]["type"] == "done"
    titles = [o["title"] for o in rec["options"]]
    assert titles == ["Lentil bowl", "Broccoli side"]  # lentils cover more fibre -> first
    assert rec["options"][0]["covers_short_percent"]["fibre_g"] == pytest.approx(100 * 15.8 / 30, abs=0.2)
    assert rec["options"][0]["items"][0]["label"] == "Lentils"
    assert rec["dropped"] >= 1  # unmatched wording
    row = conn.execute("SELECT content FROM recommendations WHERE log_date = '2026-01-02'").fetchone()
    assert json.loads(row["content"])["options"][0]["title"] == "Lentil bowl"


def test_yesterday_repeated_gaps_weigh_double(conn):
    a = gaps.assess_with_carry(conn, "2026-01-02")
    fibre_opt = {"covers_short_percent": {"fibre_g": 50.0, "protein_g": 0.0}}
    protein_opt = {"covers_short_percent": {"fibre_g": 0.0, "protein_g": 60.0}}
    a["short"] = [dict(s, repeated=s["nutrient"] == "fibre_g") for s in a["short"]]
    assert recommend.score(fibre_opt, a) > recommend.score(protein_opt, a)  # 50*2 beats 60*1
    a["short"] = [dict(s, repeated=False) for s in a["short"]]
    assert recommend.score(fibre_opt, a) < recommend.score(protein_opt, a)


def test_no_shortfall_skips_the_model(conn, monkeypatch):
    a = gaps.assess_with_carry(conn, "2026-01-02")
    monkeypatch.setattr(recommend.gaps, "assess_with_carry", lambda c, d: dict(a, short=[]))
    p = Scripted([])  # would raise if called
    rec = list(recommend.generate(conn, p, "2026-01-02", "en"))[-1]["recommendation"]
    assert rec["options"] == [] and p.seen == []


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_get_generate_and_stale(client, conn):
    add_broccoli(conn)
    provider = Scripted([text(json.dumps(OPTIONS))])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg, transport=None: provider)
    try:
        r = client.get("/api/recommendations/2026-01-02")
        assert r.status_code == 200 and r.json()["stored"] is None and r.json()["stale"] is False
        r = client.post("/api/recommendations/2026-01-02/generate", json={"lang": "en"})
        lines = [json.loads(x) for x in r.text.splitlines() if x.strip()]
        assert lines[-1]["type"] == "done" and len(lines[-1]["recommendation"]["options"]) == 2
        body = client.get("/api/recommendations/2026-01-02").json()
        assert body["stored"]["options"][0]["title"] == "Lentil bowl" and body["stale"] is False
        # new intake changes the gaps -> stored snapshot is flagged stale
        conn.execute("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES ('2026-01-02','lunch',1,300)")
        conn.commit()
        assert client.get("/api/recommendations/2026-01-02").json()["stale"] is True
    finally:
        app.dependency_overrides.pop(get_provider_factory, None)


def test_api_needs_profile():
    bare = db.connect(":memory:")
    app.dependency_overrides[get_conn] = lambda: bare
    try:
        assert TestClient(app).get("/api/recommendations/2026-01-02").status_code == 409
    finally:
        app.dependency_overrides.clear()
