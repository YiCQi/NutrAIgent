import json
from datetime import date as date_cls
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import db, foods
from .ai import agent, providers, tools as ai_tools
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
    return foods.search(conn, q, limit)


@app.get("/api/foods/{food_id}")
def get_food(food_id: int, conn=Depends(get_conn)):
    d = foods.detail(conn, food_id)
    if d is None:
        raise HTTPException(404, "food not found")
    return d


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


# ---------------------------------------------------------------- AI (BYOK)
AI_KEYS = ("ai_provider", "ai_model", "ai_base_url", "ai_api_key")


def _setting(conn, key, default=""):
    r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


class AISettingsIn(BaseModel):
    provider: Literal["anthropic", "openai_compatible"]
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field("", max_length=300)
    api_key: str | None = Field(None, max_length=500)  # None = keep existing, "" = clear


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


def _ai_settings_out(conn):
    return {"provider": _setting(conn, "ai_provider", "anthropic"), "model": _setting(conn, "ai_model"),
            "base_url": _setting(conn, "ai_base_url"), "has_key": bool(_setting(conn, "ai_api_key"))}


@app.get("/api/ai/settings")
def get_ai_settings(conn=Depends(get_conn)):
    return _ai_settings_out(conn)  # never returns the key itself


@app.put("/api/ai/settings")
def put_ai_settings(s: AISettingsIn, conn=Depends(get_conn)):
    vals = {"ai_provider": s.provider, "ai_model": s.model.strip(), "ai_base_url": s.base_url.strip()}
    if s.api_key is not None:
        vals["ai_api_key"] = s.api_key.strip()
    for k, v in vals.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
    conn.commit()
    return _ai_settings_out(conn)


def get_provider_factory():
    """Overridable in tests."""
    return providers.make_provider


@app.post("/api/ai/chat")
def ai_chat(body: ChatIn, conn=Depends(get_conn), make=Depends(get_provider_factory)):
    cfg = providers.ProviderConfig(
        provider=_setting(conn, "ai_provider", "anthropic"), model=_setting(conn, "ai_model"),
        api_key=_setting(conn, "ai_api_key"), base_url=_setting(conn, "ai_base_url"))
    try:
        provider = make(cfg)
        ctx = ai_tools.Context(conn=conn, today=date_cls.today().isoformat())
        return agent.run_chat(ctx, provider, [m.model_dump() for m in body.messages])
    except providers.ProviderError as e:
        raise HTTPException(502, str(e))
