from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .core.trace import bus
from .db.models import init_db
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
