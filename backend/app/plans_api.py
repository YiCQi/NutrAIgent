from datetime import date as date_cls
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import jobs, planner
from .ai import providers
from .deps import get_conn, get_provider_factory

router = APIRouter(prefix="/api/plans", tags=["plans"])
RUNNING: set[int] = set()


def _setting(conn, key, default=""):
    r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


def _cfg(conn):
    return providers.ProviderConfig(
        provider=_setting(conn, "ai_provider", "anthropic"), model=_setting(conn, "ai_model"),
        api_key=_setting(conn, "ai_api_key"), base_url=_setting(conn, "ai_base_url"))


class GenerateIn(BaseModel):
    start_date: date_cls
    days: int = Field(7, ge=1, le=7)
    meals: list[Literal["breakfast", "lunch", "dinner", "snack"]] = ["breakfast", "lunch", "dinner"]
    notes: str = Field("", max_length=600)
    lang: Literal["en", "zh"] = "en"


class ItemPatch(BaseModel):
    grams: float | None = Field(None, gt=0, le=5000)
    food_id: int | None = None


class ItemIn(BaseModel):
    plan_date: date_cls
    meal: Literal["breakfast", "lunch", "dinner", "snack"]
    food_id: int
    grams: float = Field(gt=0, le=5000)


class LogIn(BaseModel):
    plan_date: date_cls
    meal: Literal["breakfast", "lunch", "dinner", "snack"] | None = None  # None = whole day


class RegenIn(BaseModel):
    notes: str = Field("", max_length=600)
    lang: Literal["en", "zh"] = "en"


def _plan_or_404(conn, pid):
    p = conn.execute("SELECT * FROM meal_plans WHERE id = ?", (pid,)).fetchone()
    if p is None:
        raise HTTPException(404, "plan not found")
    return p


@router.get("")
def list_plans(conn=Depends(get_conn)):
    rows = conn.execute("SELECT id, title, start_date, updated_at FROM meal_plans ORDER BY updated_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/generate")
def generate_plan(body: GenerateIn, conn=Depends(get_conn), make=Depends(get_provider_factory)):
    """NDJSON stream of progress; ends with {type:'done', plan_id} or {type:'error'}."""
    if conn.execute("SELECT 1 FROM profile WHERE id = 1").fetchone() is None:
        raise HTTPException(409, "set up your profile first (targets are needed)")
    cfg = _cfg(conn)
    cur = conn.execute("INSERT INTO meal_plans (title, start_date, notes) VALUES (?,?,?)",
                       (f"{body.start_date.isoformat()} +{body.days}d", body.start_date.isoformat(), body.notes))
    conn.commit()
    pid = cur.lastrowid
    dates = planner.week_dates(body.start_date.isoformat(), body.days)
    RUNNING.add(pid)

    def events():
        try:
            yield {"type": "plan", "plan_id": pid}
            provider = make(cfg)
            yield from planner.generate(conn, provider, pid, dates, body.lang, body.meals, body.notes)
        except Exception:
            if not conn.execute("SELECT 1 FROM plan_items WHERE plan_id = ? LIMIT 1", (pid,)).fetchone():
                conn.execute("DELETE FROM meal_plans WHERE id = ?", (pid,))  # nothing produced: drop the shell
                conn.commit()
            raise

    return StreamingResponse(jobs.stream_in_background(events, lambda: RUNNING.discard(pid)),
                             media_type="application/x-ndjson")


@router.get("/{pid}")
def get_plan(pid: int, conn=Depends(get_conn)):
    _plan_or_404(conn, pid)
    view = planner.plan_view(conn, pid)
    view["pending"] = pid in RUNNING
    return view


@router.delete("/{pid}", status_code=204)
def delete_plan(pid: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM meal_plans WHERE id = ?", (pid,))
    conn.commit()


@router.post("/{pid}/items", status_code=201)
def add_item(pid: int, body: ItemIn, conn=Depends(get_conn)):
    _plan_or_404(conn, pid)
    f = conn.execute("SELECT name FROM foods WHERE id = ?", (body.food_id,)).fetchone()
    if f is None:
        raise HTTPException(404, "food not found")
    cur = conn.execute("INSERT INTO plan_items (plan_id, plan_date, meal, position, label, food_id, grams) "
                       "VALUES (?,?,?,999,?,?,?)", (pid, body.plan_date.isoformat(), body.meal, f["name"], body.food_id, body.grams))
    conn.commit()
    return {"id": cur.lastrowid}


@router.patch("/{pid}/items/{item_id}")
def patch_item(pid: int, item_id: int, body: ItemPatch, conn=Depends(get_conn)):
    row = conn.execute("SELECT id FROM plan_items WHERE id = ? AND plan_id = ?", (item_id, pid)).fetchone()
    if row is None:
        raise HTTPException(404, "item not found")
    if body.food_id is not None:
        f = conn.execute("SELECT name FROM foods WHERE id = ?", (body.food_id,)).fetchone()
        if f is None:
            raise HTTPException(404, "food not found")
        conn.execute("UPDATE plan_items SET food_id = ?, label = ? WHERE id = ?", (body.food_id, f["name"], item_id))
    if body.grams is not None:
        conn.execute("UPDATE plan_items SET grams = ? WHERE id = ?", (body.grams, item_id))
    conn.commit()
    return {"id": item_id}


@router.delete("/{pid}/items/{item_id}", status_code=204)
def delete_item(pid: int, item_id: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM plan_items WHERE id = ? AND plan_id = ?", (item_id, pid))
    conn.commit()


@router.post("/{pid}/log")
def log_plan(pid: int, body: LogIn, conn=Depends(get_conn)):
    """Copy planned items (a meal or a whole day) into the food diary for that date."""
    _plan_or_404(conn, pid)
    q = "SELECT food_id, grams, meal FROM plan_items WHERE plan_id = ? AND plan_date = ?"
    args = [pid, body.plan_date.isoformat()]
    if body.meal:
        q += " AND meal = ?"
        args.append(body.meal)
    rows = conn.execute(q, args).fetchall()
    conn.executemany("INSERT INTO intake_log (log_date, meal, food_id, grams) VALUES (?,?,?,?)",
                     [(body.plan_date.isoformat(), r["meal"], r["food_id"], r["grams"]) for r in rows])
    conn.commit()
    return {"logged": len(rows)}


@router.post("/{pid}/days/{plan_date}/regenerate")
def regenerate_day(pid: int, plan_date: date_cls, body: RegenIn, conn=Depends(get_conn), make=Depends(get_provider_factory)):
    p = _plan_or_404(conn, pid)
    if pid in RUNNING:
        raise HTTPException(409, "this plan is being generated")
    meals = [r["meal"] for r in conn.execute("SELECT DISTINCT meal FROM plan_items WHERE plan_id = ? AND plan_date = ?",
                                              (pid, plan_date.isoformat()))] or ["breakfast", "lunch", "dinner"]
    cfg = _cfg(conn)
    RUNNING.add(pid)

    def events():
        provider = make(cfg)
        yield from planner.generate(conn, provider, pid, [plan_date.isoformat()], body.lang, meals,
                                    "; ".join(x for x in (p["notes"], body.notes) if x))

    return StreamingResponse(jobs.stream_in_background(events, lambda: RUNNING.discard(pid)),
                             media_type="application/x-ndjson")
