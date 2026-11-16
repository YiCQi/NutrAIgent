import json
from datetime import date as date_cls
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .engine import analysis, targets

app = FastAPI(title="NutrAIgent", version="0.1.0")
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect()
    return _conn


class ProfileIn(BaseModel):
    age: int = Field(ge=10, le=120)
    sex: Literal["male", "female"]
    height_cm: float = Field(gt=50, lt=260)
    weight_kg: float = Field(gt=20, lt=400)
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal: Literal["muscle_gain", "fat_loss", "maintenance"]
    dietary_preferences: list[str] = []


class IntakeIn(BaseModel):
    log_date: date_cls
    food_id: int
    grams: float = Field(gt=0)
    meal: str = "other"


def _profile_row(conn):
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is None:
        raise HTTPException(404, "profile not set")
    return row


def _to_profile(r) -> targets.Profile:
    return targets.Profile(r["age"], r["sex"], r["height_cm"], r["weight_kg"],
                           r["activity_level"], r["goal"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/foods")
def search_foods(q: str = Query("", max_length=100), limit: int = Query(25, le=100),
                 conn=Depends(get_conn)):
    rows = conn.execute(
        """SELECT f.id, f.name, f.state, f.edible_portion_pct, s.code AS source
           FROM foods f JOIN sources s ON s.id = f.source_id
           WHERE f.name LIKE ? ORDER BY f.name LIMIT ?""",
        (f"%{q}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/foods/{food_id}")
def get_food(food_id: int, conn=Depends(get_conn)):
    f = conn.execute(
        "SELECT f.*, s.code AS source, s.name AS source_name, s.version AS source_version "
        "FROM foods f JOIN sources s ON s.id = f.source_id WHERE f.id = ?", (food_id,)).fetchone()
    if f is None:
        raise HTTPException(404, "food not found")
    nuts = conn.execute(
        """SELECT n.code, n.name, n.unit, fn.value_per_100g AS value
           FROM nutrients n LEFT JOIN food_nutrients fn ON fn.nutrient_id = n.id AND fn.food_id = ?
           ORDER BY n.id""", (food_id,)).fetchall()
    return {**dict(f), "nutrients": [dict(n) for n in nuts]}  # value null = missing


@app.put("/api/profile")
def put_profile(p: ProfileIn, conn=Depends(get_conn)):
    conn.execute(
        """INSERT INTO profile (id, age, sex, height_cm, weight_kg, activity_level, goal, dietary_preferences)
           VALUES (1,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET age=excluded.age, sex=excluded.sex, height_cm=excluded.height_cm,
             weight_kg=excluded.weight_kg, activity_level=excluded.activity_level, goal=excluded.goal,
             dietary_preferences=excluded.dietary_preferences, updated_at=CURRENT_TIMESTAMP""",
        (p.age, p.sex, p.height_cm, p.weight_kg, p.activity_level, p.goal,
         json.dumps(p.dietary_preferences)),
    )
    conn.commit()
    return p


@app.get("/api/profile")
def get_profile(conn=Depends(get_conn)):
    r = dict(_profile_row(conn))
    r["dietary_preferences"] = json.loads(r["dietary_preferences"])
    return r


@app.get("/api/targets")
def get_targets(conn=Depends(get_conn)):
    return targets.compute_targets(_to_profile(_profile_row(conn)))


@app.post("/api/intake", status_code=201)
def add_intake(i: IntakeIn, conn=Depends(get_conn)):
    if conn.execute("SELECT 1 FROM foods WHERE id = ?", (i.food_id,)).fetchone() is None:
        raise HTTPException(404, "food not found")
    cur = conn.execute(
        "INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES (?,?,?,?)",
        (i.log_date.isoformat(), i.meal, i.food_id, i.grams))
    conn.commit()
    return {"id": cur.lastrowid}


@app.delete("/api/intake/{entry_id}", status_code=204)
def delete_intake(entry_id: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM intake_log WHERE id = ?", (entry_id,))
    conn.commit()


@app.get("/api/intake/{log_date}")
def get_intake(log_date: date_cls, conn=Depends(get_conn)):
    intake = analysis.daily_intake(conn, log_date.isoformat())
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is not None:
        t = targets.compute_targets(_to_profile(row))
        intake["comparison"] = analysis.compare(intake, t["targets"])
    return intake
