import json
import os
import time
from datetime import date as date_cls
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import estimate, featured, foods, jobs, plans_api, presence, recipes_api, recommend_api
from .deps import get_conn, get_provider_factory
from .ai import chatflow, edits, providers
from .engine import analysis, targets

NL = chr(10)
app = FastAPI(title="NutrAIgent", version="0.1.0")
app.include_router(recipes_api.router)
app.include_router(plans_api.router)
app.include_router(recommend_api.router)


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


@app.get("/api/foods/featured")
def featured_foods(conn=Depends(get_conn)):
    return featured.featured(conn)


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


class IntakeEditIn(BaseModel):
    grams: float = Field(gt=0)


@app.patch("/api/intake/{entry_id}")
def edit_intake(entry_id: int, body: IntakeEditIn, conn=Depends(get_conn)):
    cur = conn.execute("UPDATE intake_log SET grams = ? WHERE id = ?", (body.grams, entry_id))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "entry not found")
    return {"id": entry_id, "grams": body.grams}


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


@app.post("/api/intake/{log_date}/estimate")
def estimate_intake(log_date: date_cls, conn=Depends(get_conn), make=Depends(get_provider_factory)):
    """Fill missing nutrients (ESTIMATE_CODES) of the day's foods with AI estimates (flagged estimated)."""
    foods = estimate.missing_foods(conn, log_date.isoformat())
    if not foods:
        return {"stored": 0, "unanswered": [], "foods": 0}
    cfg = providers.ProviderConfig(
        provider=_setting(conn, "ai_provider", "anthropic"), model=_setting(conn, "ai_model"),
        api_key=_setting(conn, "ai_api_key"), base_url=_setting(conn, "ai_base_url"))
    try:
        result = estimate.estimate(conn, make(cfg), foods)
    except providers.ProviderError as e:
        raise HTTPException(502, str(e))
    return {**result, "foods": len(foods)}


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


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    lang: Literal["en", "zh"] = "en"


class StatusIn(BaseModel):
    status: Literal["saved", "discarded"]


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


def _conv_or_404(conn, conv_id):
    c = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if c is None:
        raise HTTPException(404, "conversation not found")
    return c


@app.get("/api/conversations")
def list_conversations(conn=Depends(get_conn)):
    rows = conn.execute("SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/conversations", status_code=201)
def create_conversation(conn=Depends(get_conn)):
    cur = conn.execute("INSERT INTO conversations DEFAULT VALUES")
    conn.commit()
    return {"id": cur.lastrowid, "title": "New chat"}


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, conn=Depends(get_conn)):
    c = _conv_or_404(conn, conv_id)
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)).fetchall()
    return {"id": c["id"], "title": c["title"], "pending": conv_id in chatflow.RUNNING,
            "messages": [chatflow.message_dict(r) for r in rows]}


@app.delete("/api/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()


@app.patch("/api/messages/{message_id}/status")
def set_proposal_status(message_id: int, body: StatusIn, conn=Depends(get_conn)):
    row = conn.execute("SELECT meta FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "message not found")
    meta = json.loads(row["meta"] or "{}")
    meta["status"] = body.status
    conn.execute("UPDATE messages SET meta = ? WHERE id = ?", (json.dumps(meta), message_id))
    conn.commit()
    return {"id": message_id, "status": body.status}


class ConfirmEditsIn(BaseModel):
    include: list[int] | None = None  # indexes into the proposal's changes; None = all


@app.post("/api/messages/{message_id}/confirm-edits")
def confirm_edits(message_id: int, body: ConfirmEditsIn, conn=Depends(get_conn)):
    """Apply the chosen changes of an edit proposal (from the chat) to that day's intake log."""
    row = conn.execute("SELECT meta FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "message not found")
    meta = json.loads(row["meta"] or "{}")
    if meta.get("kind") != "edit":
        raise HTTPException(400, "not an edit proposal")
    if meta.get("status") != "pending":
        raise HTTPException(409, "proposal already handled")
    changes = meta.get("changes", [])
    idx = range(len(changes)) if body.include is None else body.include
    chosen = [changes[i] for i in idx if 0 <= i < len(changes)]
    results = edits.apply(conn, meta["day"], chosen)
    meta["status"] = "saved"
    meta["results"] = results
    conn.execute("UPDATE messages SET meta = ? WHERE id = ?", (json.dumps(meta), message_id))
    conn.commit()
    return {"id": message_id, "status": "saved", "results": results}


@app.post("/api/conversations/{conv_id}/chat")
def chat_stream(conv_id: int, body: ChatIn, conn=Depends(get_conn), make=Depends(get_provider_factory)):
    """NDJSON stream: {type:'status',text} ... then {type:'done',message} or {type:'error',message}."""
    _conv_or_404(conn, conv_id)
    cfg = providers.ProviderConfig(
        provider=_setting(conn, "ai_provider", "anthropic"), model=_setting(conn, "ai_model"),
        api_key=_setting(conn, "ai_api_key"), base_url=_setting(conn, "ai_base_url"))

    if conv_id in chatflow.RUNNING:
        raise HTTPException(409, "a reply is already being generated for this conversation")
    chatflow.RUNNING.add(conv_id)

    def events():
        provider = make(cfg)
        provider.timeout = 300  # meal breakdowns can take minutes on slow endpoints (default 120 s)
        yield from chatflow.run_turn(conn, provider, conv_id, body.content, date_cls.today().isoformat(), body.lang)

    return StreamingResponse(jobs.stream_in_background(events, lambda: chatflow.RUNNING.discard(conv_id)),
                             media_type="application/x-ndjson")


# Browser presence: the page pings while open and says bye on close (see app/presence.py).
PRESENCE = presence.Presence()


@app.post("/api/presence/ping")
def presence_ping(client: str = Query(..., max_length=64)):
    PRESENCE.ping(client, time.time())
    return {"ok": True}


@app.post("/api/presence/bye")
def presence_bye(client: str = Query(..., max_length=64)):
    PRESENCE.bye(client)
    return {"ok": True}


if os.environ.get("NUTRAIGENT_AUTOSTOP") == "1":
    presence.start_watchdog(PRESENCE, busy=lambda: bool(
        chatflow.RUNNING or plans_api.RUNNING or recommend_api.RUNNING))


# One-process mode: serve the built frontend (frontend/dist) from the API server. Registered last so /api wins.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
