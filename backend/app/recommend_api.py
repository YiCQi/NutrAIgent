import json
from datetime import date as date_cls
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import jobs, recommend
from .ai import providers
from .deps import get_conn, get_provider_factory
from .engine import gaps

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
RUNNING: set[str] = set()


class GenerateIn(BaseModel):
    lang: Literal["en", "zh"] = "en"


def _setting(conn, key, default=""):
    r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


def _cfg(conn):
    return providers.ProviderConfig(
        provider=_setting(conn, "ai_provider", "anthropic"), model=_setting(conn, "ai_model"),
        api_key=_setting(conn, "ai_api_key"), base_url=_setting(conn, "ai_base_url"))


def _need_profile(conn):
    if conn.execute("SELECT 1 FROM profile WHERE id = 1").fetchone() is None:
        raise HTTPException(409, "set up your profile first (targets are needed)")


def _signature(a: dict):
    """What the suggestion was based on: each short nutrient's rounded gap, each excess nutrient."""
    return (sorted((s["nutrient"], round(s["gap"])) for s in a["short"]),
            sorted(x["nutrient"] for x in a["excess"]))


@router.get("/{day}")
def get_recommendation(day: date_cls, conn=Depends(get_conn)):
    _need_profile(conn)
    key = day.isoformat()
    live = gaps.assess_with_carry(conn, key)
    row = conn.execute("SELECT content, created_at FROM recommendations WHERE log_date = ?", (key,)).fetchone()
    stored = json.loads(row["content"]) if row else None
    return {"date": key, "live": live, "stored": stored,
            "created_at": row["created_at"] if row else None,
            "stale": stored is not None and _signature(stored["assessment"]) != _signature(live),
            "pending": key in RUNNING}


@router.post("/{day}/generate")
def generate_recommendation(day: date_cls, body: GenerateIn, conn=Depends(get_conn),
                            make=Depends(get_provider_factory)):
    """NDJSON stream of progress; ends with {type:'done', recommendation} or {type:'error'}."""
    _need_profile(conn)
    key = day.isoformat()
    if key in RUNNING:
        raise HTTPException(409, "already generating for this day")
    cfg = _cfg(conn)
    RUNNING.add(key)

    def events():
        provider = make(cfg)
        provider.timeout = 300
        yield from recommend.generate(conn, provider, key, body.lang)

    return StreamingResponse(jobs.stream_in_background(events, lambda: RUNNING.discard(key)),
                             media_type="application/x-ndjson")
