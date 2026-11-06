from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sse_starlette.sse import EventSourceResponse

from . import departments  # noqa: F401  (registers sub-modules)
from . import llm
from .core.trace import bus
from .db.models import (Appointment, Approval, AuditEntry, Case, Document, MapPoint, Notification, Payment,
                        SessionLocal, Thread, Ticket, User, init_db)
from .db.seed import check_pw, seed
from .departments.catalog import DEPARTMENTS
from .mocks import gov_apis
from .modules import always_on  # noqa: F401
from .router import case_manager
from .router.intent_router import route
from .router.schemas import RoutingDecision
from .services import audit, complexity, intake, memory_bag, rag, tagger

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = Path(__file__).resolve().parents[1] / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
FRONTEND = ROOT / "frontend"
SESSIONS: dict[str, str] = {}  # token -> user id (demo only)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed()
    if os.environ.get("MYTADBIR_OFFLINE") != "1":
        memory_bag.start_scheduler()
    audit.log("system", "startup", {"llm": "deepseek" if llm.available() else "offline"})
    yield


app = FastAPI(title="MyTadbir API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:8000"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(gov_apis.router)


# ---------------------------------------------------------------- auth (demo accounts)
class Login(BaseModel):
    username: str
    password: str


def current_user(authorization: str | None = Header(default=None)) -> User:
    token = (authorization or "").removeprefix("Bearer ").strip()
    uid = SESSIONS.get(token)
    if not uid:
        raise HTTPException(401, "not signed in")
    with SessionLocal() as s:
        return s.get(User, uid)


def _user_out(u: User) -> dict:
    return {"id": u.id, "role": u.role, "name": u.name, "mykad": u.mykad, "verified": u.verified, "profile": u.profile}


@app.post("/api/auth/login")
def login(body: Login):
    with SessionLocal() as s:
        u = s.get(User, body.username.strip().lower())
        if not u or not check_pw(body.password, u.password_hash):
            raise HTTPException(401, "Wrong username or password")
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = u.id
    audit.log(u.id, "login", {"method": "password"})
    return {"token": token, "user": _user_out(u)}


@app.post("/api/auth/mydigitalid")
def login_mydigitalid():
    """Mock MyDigital ID sign-in: signs in the demo citizen after a simulated app approval."""
    with SessionLocal() as s:
        u = s.get(User, "aisyah")
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = u.id
    audit.log(u.id, "login", {"method": "MyDigital ID (mock)"})
    return {"token": token, "user": _user_out(u)}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    SESSIONS.pop((authorization or "").removeprefix("Bearer ").strip(), None)
    return {"ok": True}


@app.get("/api/me")
def me(u: User = Depends(current_user)):
    return _user_out(u)


# ---------------------------------------------------------------- system
@app.get("/api/health")
def health():
    ok, bad = audit.verify_chain()
    return {"status": "ok", "audit_chain_valid": ok, "first_bad_entry": bad,
            "llm": {"provider": "deepseek", "model_by_level": complexity.PLAN} if llm.available() else {"provider": "offline"}}


@app.get("/api/catalog")
def catalog():
    return [{"key": d.key, "en": d.en, "bm": d.bm, "agencies": d.agencies,
             "subs": [{"key": s.key, "en": s.en, "bm": s.bm} for s in d.subs]} for d in DEPARTMENTS]


# ---------------------------------------------------------------- requests
@app.post("/api/requests", response_model=RoutingDecision)
async def submit_request(background: BackgroundTasks, text: str = Form(""), thread_id: str | None = Form(None),
                         department: str | None = Form(None), photos: list[UploadFile] = File(default=[]),
                         files: list[UploadFile] = File(default=[]), u: User = Depends(current_user)):
    """Accepts exactly three input types: text, images (photos[]) and files (files[]: PDF/DOC/DOCX)."""
    staged: list[tuple[str, bytes, str]] = []
    try:
        for group, expect in ((photos, "image"), (files, "file")):
            for f in group:
                if not f.filename:
                    continue
                data = await f.read()
                intake.check(f.filename, len(data), expect)
                staged.append((f.filename, data, expect))
    except intake.InputRejected as e:
        raise HTTPException(415, {"en": e.en, "bm": e.bm}) from e
    if not text.strip() and not staged:
        raise HTTPException(400, {"en": "Type a message or attach a photo or file.", "bm": "Taip mesej atau lampirkan foto atau fail."})
    paths, doc_paths, excerpts = [], [], []
    for name, data, expect in staged:
        p = UPLOADS / f"{uuid.uuid4().hex[:8]}_{Path(name).name}"
        p.write_bytes(data)
        (paths if expect == "image" else doc_paths).append(str(p))
        if expect == "file":
            ex = await asyncio.to_thread(intake.excerpt, str(p))
            if ex:
                excerpts.append(f"[Attached file {Path(name).name}]: {ex}")
    hint = f"[Citizen chose department: {department}] " if department else ""
    body = hint + text + ("\n\n" + "\n".join(excerpts) if excerpts else "")
    decision = await route(body, image_paths=paths,
                           doc_paths=doc_paths, thread_id=thread_id, citizen_ref=u.id,
                           identity={"user_id": u.id, "name": u.name, "mykad": u.mykad})
    with SessionLocal() as s:
        for p in paths + doc_paths:
            s.add(Document(id=f"DOC-{uuid.uuid4().hex[:8].upper()}", case_id=decision.intents[0].case_id if decision.intents else None,
                           user_id=u.id, department=decision.intents[0].department if decision.intents else None,
                           kind="upload", title=Path(p).name.split("_", 1)[-1], path=p))
        s.commit()
    if decision.status == "routed":
        background.add_task(case_manager.run_thread, decision.thread_id)
    return decision


@app.get("/api/threads")
def list_threads(u: User = Depends(current_user)):
    with SessionLocal() as s:
        threads = s.scalars(select(Thread).where(Thread.citizen_ref == u.id).order_by(Thread.created_at.desc())).all()
        out = []
        for t in threads:
            cases = s.scalars(select(Case).where(Case.thread_id == t.id).order_by(Case.seq)).all()
            out.append({"thread_id": t.id, "created_at": t.created_at.isoformat(), "title": cases[0].intent[:60] if cases else "",
                        "cases": [{"case_id": c.id, "department": c.current_department, "status": c.status} for c in cases]})
        return out


def _case_out(c: Case) -> dict:
    ctx = c.context or {}
    return {"case_id": c.id, "thread_id": c.thread_id, "seq": c.seq, "intent": c.intent,
            "primary_department": c.primary_department, "current_department": c.current_department,
            "confidence": c.confidence, "verify_flag": c.verify_flag, "status": c.status,
            "chain": ctx.get("handoff_chain", []), "result": (ctx.get("scratch") or {}).get("result"),
            "wrap": (ctx.get("scratch") or {}).get("reasoning_next_steps"),
            "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat()}


@app.get("/api/threads/{thread_id}")
def get_thread(thread_id: str):
    with SessionLocal() as s:
        return [_case_out(c) for c in s.scalars(select(Case).where(Case.thread_id == thread_id).order_by(Case.seq))]


@app.get("/api/cases")
def my_cases(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Case).order_by(Case.created_at.desc())
        if u.role == "citizen":
            q = q.join(Thread).where(Thread.citizen_ref == u.id)
        return [_case_out(c) for c in s.scalars(q)]


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
                    yield {"event": "trace", "data": json.dumps(evt, ensure_ascii=False, default=str)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(thread_id, q)

    return EventSourceResponse(gen())


# ---------------------------------------------------------------- approvals (human in the loop)
@app.get("/api/approvals")
def approvals(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Approval, Case).join(Case, Case.id == Approval.case_id).order_by(Approval.created_at.desc())
        if u.role == "citizen":
            q = q.join(Thread, Thread.id == Case.thread_id).where(Thread.citizen_ref == u.id)
        return [{"id": a.id, "case_id": a.case_id, "thread_id": c.thread_id, "action": a.action, "reason": a.reason,
                 "proposed": a.proposed, "status": a.status, "officer": a.officer, "created_at": a.created_at.isoformat(),
                 "actor": "citizen" if a.action.startswith("citizen_") else "officer"} for a, c in s.execute(q)]


class Decision(BaseModel):
    approved: bool


@app.post("/api/approvals/{approval_id}/decide")
async def decide(approval_id: int, body: Decision, u: User = Depends(current_user)):
    with SessionLocal() as s:
        a = s.get(Approval, approval_id)
    if a is None:
        raise HTTPException(404)
    needs = "citizen" if a.action.startswith("citizen_") else "officer"
    if u.role != needs:
        raise HTTPException(403, f"Only the {needs} can decide this")
    try:
        return await case_manager.decide(approval_id, body.approved, u.id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


# ---------------------------------------------------------------- trackers
@app.get("/api/payments")
def payments(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Payment).order_by(Payment.created_at.desc())
        if u.role == "citizen":
            q = q.where(Payment.user_id == u.id)
        return [{"id": p.id, "case_id": p.case_id, "department": p.department, "description_en": p.description_en,
                 "description_bm": p.description_bm, "amount": p.amount, "direction": p.direction, "status": p.status,
                 "receipt": bool(p.receipt_path), "created_at": p.created_at.isoformat()} for p in s.scalars(q)]


@app.get("/api/documents")
def documents(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Document).order_by(Document.created_at.desc())
        if u.role == "citizen":
            q = q.where((Document.user_id == u.id) | (Document.user_id.is_(None)))
        return [{"id": d.id, "case_id": d.case_id, "department": d.department, "kind": d.kind, "title": d.title,
                 "tags": sorted(tagger.tag_text(d.title, dept=d.department, kind=d.kind)),
                 "created_at": d.created_at.isoformat()} for d in s.scalars(q)]


@app.get("/api/tags")
def tags(prefix: str | None = None, limit: int = 60):
    """The tag index: how many documents and passages are filed under each label."""
    return memory_bag.tag_counts(prefix, limit)


SUGGEST = {
    "drain": ("Report a clogged drain", "Lapor longkang tersumbat", "Longkang depan rumah saya tersumbat, air bertakung."),
    "flood": ("Check flood warnings near me", "Semak amaran banjir berhampiran", "Ada amaran banjir di kawasan Petaling Jaya?"),
    "roadtax": ("Renew my road tax", "Perbaharui cukai jalan", "Saya nak renew cukai jalan kereta saya."),
    "summons": ("Check and pay my summons", "Semak dan bayar saman", "Saya nak semak dan bayar saman saya."),
    "licence": ("Renew my driving licence", "Perbaharui lesen memandu", "Saya nak renew lesen memandu."),
    "cafe": ("Licence check for a new café", "Semakan lesen kafe baharu", "Saya nak buka kafe di Petaling Jaya, perlu lesen apa?"),
    "clinic": ("Book a clinic appointment", "Tempah temu janji klinik", "Saya nak buat temu janji di klinik kesihatan."),
    "tax": ("File my income tax", "Isytihar cukai pendapatan", "Macam mana nak isi borang BE tahun ini?"),
    "aid": ("Check welfare aid eligibility", "Semak kelayakan bantuan JKM", "Saya ibu tunggal, layak mohon bantuan JKM?"),
    "passport": ("Renew my passport", "Perbaharui pasport", "Saya nak renew pasport."),
    "track": ("Track my open case", "Jejak kes saya", "Apa status kes saya yang terbuka?"),
}


@app.get("/api/suggestions")
def suggestions(lang: str = "en", u: User = Depends(current_user)):
    """Quick-request chips for this user, ranked by context. Rule-based: no API tokens."""
    from datetime import datetime as _dt

    keys: list[str] = []
    with SessionLocal() as s:
        open_cases = s.scalar(select(func.count()).select_from(Case).join(Thread).where(
            Thread.citizen_ref == u.id, Case.status.not_in(["done", "failed"]))) or 0
        pending = s.scalar(select(func.count()).select_from(Payment).where(Payment.user_id == u.id, Payment.status == "pending")) or 0
    if open_cases:
        keys.append("track")
    if pending:
        keys.append("summons")
    month = _dt.now().month
    keys += ["flood", "drain"] if month in (10, 11, 12, 1) else ["drain"]  # northeast monsoon season
    if month in (2, 3, 4, 5):
        keys.append("tax")  # LHDN filing season
    keys += ["roadtax", "summons", "licence", "cafe", "clinic", "aid", "passport"]
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            en, bm, prompt = SUGGEST[k]
            out.append({"key": k, "label": bm if lang == "bm" else en, "prompt": prompt})
    return out[:6]


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    with SessionLocal() as s:
        d = s.get(Document, doc_id)
    if not d or not Path(d.path).exists():
        raise HTTPException(404)
    return FileResponse(d.path, filename=Path(d.path).name)


@app.get("/api/payments/{pid}/receipt")
def payment_receipt(pid: str):
    with SessionLocal() as s:
        p = s.get(Payment, pid)
    if not p or not p.receipt_path:
        raise HTTPException(404)
    return FileResponse(p.receipt_path, filename=Path(p.receipt_path).name)


@app.get("/api/notifications")
def notifications(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Notification, Thread).join(Thread, Thread.id == Notification.thread_id).order_by(Notification.created_at.desc())
        if u.role == "citizen":
            q = q.where(Thread.citizen_ref == u.id)
        return [{"id": n.id, "thread_id": n.thread_id, "case_id": n.case_id, "channel": n.channel, "en": n.message_en,
                 "bm": n.message_bm, "created_at": n.created_at.isoformat()} for n, _ in s.execute(q)]


@app.get("/api/appointments")
def appointments(u: User = Depends(current_user)):
    with SessionLocal() as s:
        q = select(Appointment).order_by(Appointment.when)
        if u.role == "citizen":
            q = q.where(Appointment.user_id == u.id)
        return [{"id": a.id, "case_id": a.case_id, "department": a.department, "title_en": a.title_en, "title_bm": a.title_bm,
                 "when": a.when.isoformat(), "location": a.location, "status": a.status} for a in s.scalars(q)]


@app.get("/api/map")
def map_points():
    with SessionLocal() as s:
        pts = [{"id": p.id, "case_id": p.case_id, "kind": p.kind, "label": p.label, "lat": p.lat, "lng": p.lng, "meta": p.meta}
               for p in s.scalars(select(MapPoint).order_by(MapPoint.id))]
    schools = [{"kind": "school", "label": "Sekolah (demo)", "lat": 3.1081, "lng": 101.6079}]
    return pts + schools


@app.get("/api/impact")
def impact():
    with SessionLocal() as s:
        return {
            "cases": s.scalar(select(func.count()).select_from(Case)) or 0,
            "closed": s.scalar(select(func.count()).select_from(Case).where(Case.status == "done")) or 0,
            "dispatched": s.scalar(select(func.count()).select_from(Ticket).where(Ticket.status == "dispatched")) or 0,
            "fees": round(s.scalar(select(func.sum(Payment.amount)).where(Payment.status == "paid", Payment.direction == "out")) or 0, 2),
            "pending_approvals": s.scalar(select(func.count()).select_from(Approval).where(Approval.status == "pending")) or 0,
            "audit_entries": s.scalar(select(func.count()).select_from(AuditEntry)) or 0,
        }


# ---------------------------------------------------------------- policy library
@app.get("/api/policy/search")
def policy_search(q: str, dept: str | None = None, k: int = 10):
    return [{k2: h[k2] for k2 in ("chunk_id", "doc_id", "title_en", "title_bm", "page", "url", "as_at", "agency", "dept", "score")}
            | {"excerpt": h["text"][:500]} for h in rag.search(q, dept=dept, k=k)]


@app.get("/api/policy/documents")
def policy_documents():
    return memory_bag.documents()


# ---------------------------------------------------------------- memory bag (officer)
def officer(u: User = Depends(current_user)) -> User:
    if u.role != "officer":
        raise HTTPException(403, "Officer only")
    return u


@app.get("/api/memory-bag")
def memory_bag_status():
    return memory_bag.status()


@app.post("/api/memory-bag/rescan")
async def memory_bag_rescan(force: bool = True, u: User = Depends(officer)):
    res = await asyncio.to_thread(memory_bag.sync, force)
    audit.log(u.id, "memory_bag_rescan", res)
    return res


@app.post("/api/memory-bag/documents")
async def memory_bag_add(file: UploadFile = File(...), title_en: str = Form(""), title_bm: str = Form(""),
                         dept: str = Form("cross_agency"), kind: str = Form("document"), agency: str = Form(""),
                         url: str = Form(""), as_at: str = Form(""), u: User = Depends(officer)):
    data = await file.read()
    res = await asyncio.to_thread(memory_bag.add_manual, {"title_en": title_en, "title_bm": title_bm, "dept": dept, "kind": kind,
                                  "agency": agency, "url": url, "as_at": as_at}, file.filename, data)
    audit.log(u.id, "memory_bag_" + res["op"], res)
    return res


@app.delete("/api/memory-bag/documents/{doc_id}")
def memory_bag_delete(doc_id: str, u: User = Depends(officer)):
    res = memory_bag.delete_doc(doc_id)
    audit.log(u.id, "memory_bag_delete", res)
    return res


@app.post("/api/memory-bag/documents/{doc_id}/restore")
async def memory_bag_restore(doc_id: str, u: User = Depends(officer)):
    res = await asyncio.to_thread(memory_bag.restore_doc, doc_id)
    audit.log(u.id, "memory_bag_restore", res)
    return res


# ---------------------------------------------------------------- demo control (presenter)
@app.post("/api/demo/reset")
def demo_reset(u: User = Depends(current_user)):
    from .db.models import Base, engine
    from .services import identity

    Base.metadata.drop_all(engine)
    init_db()
    seed()
    identity._VERIFIED.clear()
    for s_ in gov_apis.SUMMONS.values():
        for x in s_:
            x["status"] = "unpaid"
    gov_apis.LICENCES["900101-10-1234"]["expiry"] = "2026-11-20"
    SESSIONS.clear()
    return {"ok": True}


class Pace(BaseModel):
    seconds: float


@app.post("/api/demo/pace")
def demo_pace(body: Pace):
    bus.pace = max(0.0, min(body.seconds, 3.0))
    return {"pace": bus.pace}


@app.get("/api/demo/pace")
def get_pace():
    return {"pace": bus.pace}


# ---------------------------------------------------------------- frontend
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
