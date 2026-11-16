import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import db, jobs, planner
from app.main import app, get_conn, get_provider_factory
from tests.test_ai import Scripted, events, text


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    foods = [("Oats, raw", 380, 13, 66, 7), ("Chicken breast, cooked", 165, 31, 0, 3.6), ("Rice, white, cooked", 130, 2.7, 28, 0.3),
             ("Broccoli, cooked", 35, 2.4, 7, 0.4)]
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    for i, (n, kcal, p, cb, f) in enumerate(foods, 1):
        c.execute("INSERT INTO foods (name, source_id) VALUES (?,1)", (n,))
        for code, v in (("energy_kcal", kcal), ("protein_g", p), ("carbohydrate_g", cb), ("fat_g", f)):
            c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (?,?,?)", (i, ids[code], v))
    c.commit()
    return c


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


PROFILE = dict(age=30, sex="male", height_cm=175, weight_kg=70, activity_level="light", goal="maintenance")


def day_json(extra_item=None):
    items_b = [{"label": "燕麦", "search_terms": ["oats raw"], "grams": 150}]
    items_l = [{"label": "鸡胸肉", "search_terms": ["chicken breast cooked"], "grams": 300},
               {"label": "米饭", "search_terms": ["rice white cooked"], "grams": 400},
               {"label": "西兰花", "search_terms": ["broccoli cooked"], "grams": 200},
               {"label": "神秘", "search_terms": ["zzzz"], "grams": 50}]
    if extra_item:
        items_l.append(extra_item)
    return json.dumps({"meals": [{"meal": "breakfast", "items": items_b}, {"meal": "lunch", "items": items_l},
                                 {"meal": "dinner", "items": [{"label": "x", "search_terms": ["rice"], "grams": -5}]}]})


def test_match_day_scales_to_energy_target(conn):
    prop = json.loads(day_json())
    items, dropped = planner.match_day(conn, prop, 2000, ("breakfast", "lunch", "dinner"))
    assert dropped == 2  # unmatched 'zzzz' + invalid grams
    kcal = sum(planner._food_nutrients(conn, i["food_id"])["energy_kcal"] * i["grams"] / 100 for i in items)
    assert kcal == pytest.approx(2000, rel=0.04)  # exact up to 5 g rounding
    assert {i["meal"] for i in items} == {"breakfast", "lunch"}
    # clip: a tiny proposal is only scaled up to SCALE_MAX, staying visibly under target
    small = {"meals": [{"meal": "lunch", "items": [{"label": "b", "search_terms": ["broccoli cooked"], "grams": 100}]}]}
    items, _ = planner.match_day(conn, small, 2000, ("lunch",))
    assert items[0]["grams"] == 180.0


def test_compact_array_format(conn):
    prop = {"breakfast": [["燕麦", "oats raw", 150]], "lunch": [["鸡胸肉", "chicken breast cooked", 300], ["坏", "zzzz", 10], ["x", "rice", "bad"]],
            "snack": [["米饭", "rice white cooked", 100]]}
    items, dropped = planner.match_day(conn, prop, 1000, ("breakfast", "lunch", "dinner"))
    assert {i["meal"] for i in items} == {"breakfast", "lunch"} and dropped == 2  # snack not requested


def test_generate_view_edit_log(client, conn):
    assert client.post("/api/plans/generate", json={"start_date": "2026-01-05", "days": 2}).status_code == 409  # no profile
    client.put("/api/profile", json=PROFILE)
    fake = Scripted([text(day_json()), text(day_json())])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    r = client.post("/api/plans/generate", json={"start_date": "2026-01-05", "days": 2, "lang": "zh", "notes": "no beef"})
    app.dependency_overrides.pop(get_provider_factory)
    evs = events(r)
    assert evs[0]["type"] == "plan" and evs[-1]["type"] == "done" and evs[-1]["dropped"] == 4
    assert "Simplified Chinese" in fake.seen[0][0] and "no beef" in fake.seen[0][0]
    pid = evs[-1]["plan_id"]

    plan = client.get(f"/api/plans/{pid}").json()
    assert [d["date"] for d in plan["days"]] == ["2026-01-05", "2026-01-06"]
    day = plan["days"][0]
    assert [m["meal"] for m in day["meals"]] == ["breakfast", "lunch"]
    assert day["totals"]["energy_kcal"] == pytest.approx(plan["targets"]["energy_kcal"]["value"], rel=0.05)
    item = day["meals"][1]["items"][0]
    assert item["nutrients"]["protein_g"] > 0

    assert client.patch(f"/api/plans/{pid}/items/{item['id']}", json={"grams": 300}).status_code == 200
    assert client.post(f"/api/plans/{pid}/items", json={"plan_date": "2026-01-05", "meal": "snack", "food_id": 1, "grams": 30}).status_code == 201
    assert client.post(f"/api/plans/{pid}/items", json={"plan_date": "2026-01-05", "meal": "snack", "food_id": 99, "grams": 30}).status_code == 404
    again = client.get(f"/api/plans/{pid}").json()["days"][0]
    assert [m["meal"] for m in again["meals"]] == ["breakfast", "lunch", "snack"]

    n = client.post(f"/api/plans/{pid}/log", json={"plan_date": "2026-01-05", "meal": "snack"}).json()["logged"]
    assert n == 1
    day_log = client.get("/api/intake/2026-01-05").json()
    assert day_log["entries"][0]["meal"] == "snack" and day_log["entries"][0]["grams"] == 30

    assert client.delete(f"/api/plans/{pid}/items/{item['id']}").status_code == 204
    assert client.delete(f"/api/plans/{pid}").status_code == 204
    assert client.get(f"/api/plans/{pid}").status_code == 404
    assert conn.execute("SELECT COUNT(*) FROM plan_items").fetchone()[0] == 0  # cascade


def test_regenerate_day_and_failed_generation_cleans_up(client, conn):
    client.put("/api/profile", json=PROFILE)
    fake = Scripted([text(day_json())])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    pid = events(client.post("/api/plans/generate", json={"start_date": "2026-01-05", "days": 1}))[-1]["plan_id"]
    fake2 = Scripted([text(day_json({"label": "x", "search_terms": ["oats"], "grams": 20}))])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake2)
    r = client.post(f"/api/plans/{pid}/days/2026-01-05/regenerate", json={"lang": "en"})
    assert events(r)[-1]["type"] == "done"
    assert len(client.get(f"/api/plans/{pid}").json()["days"]) == 1  # replaced, not duplicated
    app.dependency_overrides.pop(get_provider_factory)

    r = client.post("/api/plans/generate", json={"start_date": "2026-02-01", "days": 1})  # no key configured -> error
    evs = events(r)
    assert evs[-1]["type"] == "error"
    assert [p["start_date"] for p in client.get("/api/plans").json()] == ["2026-01-05"]  # shell removed


def test_background_job_survives_client_disconnect():
    done = threading.Event()

    def make():
        yield {"type": "a"}
        time.sleep(0.2)
        done.set()
        yield {"type": "b"}

    stream = jobs.stream_in_background(make)
    next(stream)          # read one event, then walk away like a closed tab
    stream.close()
    assert done.wait(2)   # worker still finished
