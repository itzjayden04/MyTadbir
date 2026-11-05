"""Execution & Tool-Calling Agent: the only place that performs actions.

Every action is visible: API calls (method, URL, request, response, latency), SQL writes, and
generated files are emitted to the live trace and written to the audit ledger under the Case ID.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx

from ..core.context import CaseContext
from ..core.trace import bus
from ..db.models import Document, SessionLocal
from . import audit

GENERATED = Path(__file__).resolve().parents[2] / "data" / "generated"
GENERATED.mkdir(parents=True, exist_ok=True)
WEATHER_URL = "https://api.data.gov.my/weather/forecast/"


async def api_call(ctx: CaseContext, actor: str, method: str, url: str, request: dict | None,
                   handler: Callable[[], Any], *, live: bool = False) -> Any:
    t0 = time.perf_counter()
    try:
        resp = handler()
        if hasattr(resp, "model_dump"):
            resp = resp.model_dump()
        ok = True
    except Exception as exc:  # noqa: BLE001
        resp, ok = {"error": getattr(exc, "detail", str(exc)), "status_code": getattr(exc, "status_code", 500)}, False
    ms = int((time.perf_counter() - t0) * 1000)
    rec = {"method": method, "url": url, "request": request, "response": resp, "ok": ok, "ms": ms,
           "source": "live" if live else "mock"}
    audit.log("execution_agent", "api_call", rec, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "execution_agent", "api_call", rec)
    if not ok:
        raise RuntimeError(f"{method} {url} failed: {resp}")
    return resp


async def sql_write(ctx: CaseContext, table: str, op: str, row: dict) -> None:
    rec = {"table": table, "op": op, "row": row}
    audit.log("execution_agent", "sql_write", rec, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "execution_agent", "sql_write", rec)


async def weather(ctx: CaseContext, district: str) -> dict:
    """Live MET Malaysia forecast via data.gov.my. Falls back to a labelled offline value."""
    def fetch():
        r = httpx.get(WEATHER_URL, params={"contains": f"{district}@location__location_name", "limit": 7}, timeout=15)
        r.raise_for_status()
        rows = sorted(r.json(), key=lambda x: x["date"])
        if not rows:
            raise RuntimeError("no forecast rows")
        return rows[0]
    try:
        return await api_call(ctx, "execution_agent", "GET", f"{WEATHER_URL}?contains={district}@location__location_name",
                              None, fetch, live=True)
    except Exception:  # noqa: BLE001
        fallback = {"location": {"location_name": district}, "summary_forecast": "Ribut petir (offline fallback)",
                    "afternoon_forecast": "Ribut petir", "offline_fallback": True}
        await bus.emit(ctx.thread_id, ctx.case_id, "service", "execution_agent", "fallback",
                       {"what": "weather", "note": "live API unreachable; using labelled offline value"})
        return fallback


def save_document(ctx: CaseContext, *, kind: str, title: str, path: Path, department: str | None,
                  user_id: str | None = None) -> str:
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    with SessionLocal() as s:
        s.add(Document(id=doc_id, case_id=ctx.case_id, user_id=user_id or ctx.identity.get("user_id"),
                       department=department, kind=kind, title=title, path=str(path)))
        s.commit()
    return doc_id


def is_rainy(fc: dict) -> bool:
    text = " ".join(str(fc.get(k, "")) for k in ("morning_forecast", "afternoon_forecast", "night_forecast", "summary_forecast")).lower()
    return any(w in text for w in ("hujan", "ribut", "rain", "thunder"))
