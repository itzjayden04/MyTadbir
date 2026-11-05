from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from .core.trace import bus
from .db.models import Case, SessionLocal, init_db
from .router.case_manager import run_thread
from .router.intent_router import route
from .router.schemas import RoutingDecision
from .departments.catalog import DEPARTMENTS
from .services import audit


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    audit.log("system", "startup")
    yield


app = FastAPI(title="MyTadbir API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    ok, bad = audit.verify_chain()
    return {"status": "ok", "audit_chain_valid": ok, "first_bad_entry": bad}


@app.get("/api/catalog")
def catalog():
    return [
        {"key": d.key, "en": d.en, "bm": d.bm, "agencies": d.agencies,
         "subs": [{"key": s.key, "en": s.en, "bm": s.bm} for s in d.subs]}
        for d in DEPARTMENTS
    ]


class CitizenRequest(BaseModel):
    text: str
    citizen_ref: str | None = None
    identity: dict | None = None
    thread_id: str | None = None


@app.post("/api/requests", response_model=RoutingDecision)
async def submit_request(req: CitizenRequest, background: BackgroundTasks):
    decision = await route(req.text, identity=req.identity, thread_id=req.thread_id, citizen_ref=req.citizen_ref)
    if decision.status == "routed":
        background.add_task(run_thread, decision.thread_id)
    return decision


@app.get("/api/threads/{thread_id}")
def get_thread(thread_id: str):
    with SessionLocal() as s:
        cases = s.scalars(select(Case).where(Case.thread_id == thread_id).order_by(Case.seq)).all()
        return [
            {"case_id": c.id, "seq": c.seq, "intent": c.intent, "primary_department": c.primary_department,
             "current_department": c.current_department, "confidence": c.confidence,
             "verify_flag": c.verify_flag, "status": c.status, "context": c.context}
            for c in cases
        ]


@app.get("/api/cases/{case_id}/timeline")
def case_timeline(case_id: str):
    return audit.timeline(case_id)


@app.get("/api/threads/{thread_id}/trace")
async def trace_stream(thread_id: str, request: Request):
    q = bus.subscribe(thread_id)

    async def gen():
        try:
            while not await request.is_disconnected():
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                    yield {"event": "trace", "data": json.dumps(evt, ensure_ascii=False)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(thread_id, q)

    return EventSourceResponse(gen())
