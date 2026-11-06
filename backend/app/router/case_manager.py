"""Case Manager: the router's control layer that runs cases one at a time.

It is the only component that invokes a Department Main Module, and it invokes exactly one at a time.
Cases in a thread run in their routed order. A case waiting for a human (approval or citizen
confirmation) pauses the thread: later cases wait until it is resolved. A handoff is queued and run
after the current department finishes, with the same Case ID and context. Nothing runs in parallel.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select

from ..core.context import CaseContext, Evidence
from ..core.module import ModuleResult, registry
from ..core.trace import bus
from ..db.models import Approval, Case, SessionLocal, Thread
from ..departments.base import get_department
from ..services import audit

log = logging.getLogger(__name__)
MAX_HANDOFFS = 3
_locks: dict[str, asyncio.Lock] = {}


def _lock(thread_id: str) -> asyncio.Lock:
    return _locks.setdefault(thread_id, asyncio.Lock())


def _ctx(case: Case, lang: str) -> CaseContext:
    c = case.context or {}
    ctx = CaseContext(
        case_id=case.id, thread_id=case.thread_id, department=case.current_department, intent=case.intent,
        language=lang, identity=c.get("identity", {}),
        evidence=[Evidence(kind=e["kind"], path=e.get("path"), text=e.get("text")) for e in c.get("evidence", [])],
        history=c.get("history", []), prior_cases=c.get("prior_cases", []), verify_flag=case.verify_flag,
        handoff_chain=list(c.get("handoff_chain", [])),
    )
    ctx.scratch.update(c.get("scratch", {}))
    ctx.scratch.setdefault("submodule_hint", c.get("submodule_hint"))
    ctx.scratch.setdefault("level", c.get("level", 3))
    return ctx


def _save(ctx: CaseContext, **fields) -> None:
    with SessionLocal() as s:
        c = s.get(Case, ctx.case_id)
        for k, v in fields.items():
            setattr(c, k, v)
        c.context = {**(c.context or {}), "handoff_chain": ctx.handoff_chain,
                     "scratch": {k: v for k, v in ctx.scratch.items()}}
        s.commit()


async def run_thread(thread_id: str) -> list[dict]:
    async with _lock(thread_id):
        with SessionLocal() as s:
            lang = s.get(Thread, thread_id).language
        results = []
        while True:
            with SessionLocal() as s:
                if s.scalar(select(Case).where(Case.thread_id == thread_id, Case.status == "awaiting_approval")):
                    break  # sequential: nothing else runs while a case waits for a human
                case = s.scalar(select(Case).where(Case.thread_id == thread_id, Case.status == "queued").order_by(Case.seq))
            if case is None:
                await bus.emit(thread_id, None, "case_manager", "case_manager", "thread_done", {})
                break
            results.append(await _run_case(case, lang))
        return results


async def _run_case(case: Case, lang: str) -> dict:
    ctx = _ctx(case, lang)
    return await _drive(ctx, case.current_department, hop=0,
                        secondary=(case.context or {}).get("secondary_department"))


async def _drive(ctx: CaseContext, dept_key: str, hop: int, secondary: str | None,
                 first: ModuleResult | None = None) -> dict:
    outcome = first
    while True:
        if outcome is None:
            ctx.department = dept_key
            if not ctx.handoff_chain or ctx.handoff_chain[-1] != dept_key:
                ctx.handoff_chain.append(dept_key)
            _save(ctx, status="running", current_department=dept_key)
            await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "dispatch", {"department": dept_key, "hop": hop})
            audit.log("case_manager", "dispatched", {"department": dept_key, "hop": hop}, case_id=ctx.case_id, thread_id=ctx.thread_id)
            outcome = await get_department(dept_key).run(ctx)

        if outcome.status == "needs_approval":
            _save(ctx, status="awaiting_approval")
            audit.log("case_manager", "case_awaiting_approval", outcome.data, case_id=ctx.case_id, thread_id=ctx.thread_id)
            await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "paused",
                           {"reason": "waiting for a human decision", **outcome.data})
            aid = outcome.data.get("approval_id")
            if aid:
                with SessionLocal() as s_:
                    action = s_.get(Approval, aid).action
                if not action.startswith("citizen_"):
                    asyncio.create_task(_simulated_officer(aid))
            return {"case_id": ctx.case_id, "status": "awaiting_approval", "chain": ctx.handoff_chain}

        nxt = outcome.handoff_to if outcome.status == "handoff" else None
        if nxt is None and secondary and hop == 0 and outcome.status in {"ok", "stub"}:
            nxt = secondary
        if not nxt or nxt in ctx.handoff_chain or hop >= MAX_HANDOFFS:
            break
        audit.log("case_manager", "handoff_queued", {"from": dept_key, "to": nxt}, case_id=ctx.case_id, thread_id=ctx.thread_id)
        await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "handoff", {"from": dept_key, "to": nxt})
        dept_key, hop, outcome = nxt, hop + 1, None
        ctx.scratch["submodule_hint"] = None  # the new owner plans for itself

    ctx.scratch["final_outcome"] = outcome.summary_en  # authoritative for the summary module
    for name in registry.names(kind="always_on"):
        try:
            r = await registry.get(name).run(ctx)
        except Exception as exc:  # noqa: BLE001  (a summary failing must not fail the case)
            log.warning("always-on %s failed: %s", name, exc)
            continue
        ctx.scratch[name] = r.data
        await bus.emit(ctx.thread_id, ctx.case_id, "always_on", name, r.status, r.data)

    final = "failed" if outcome.status == "error" else "done"
    ctx.scratch["result"] = {"status": outcome.status, "summary_en": outcome.summary_en, "summary_bm": outcome.summary_bm,
                             "data": outcome.data}
    _save(ctx, status=final)
    audit.log("case_manager", "case_closed" if final == "done" else "case_failed",
              {"chain": ctx.handoff_chain, "status": outcome.status}, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "case_done",
                   {"status": final, "chain": ctx.handoff_chain, "summary_en": outcome.summary_en, "summary_bm": outcome.summary_bm})
    return {"case_id": ctx.case_id, "status": final, "chain": ctx.handoff_chain}


OFFICER_REVIEW_SECONDS = float(os.environ.get("MYTADBIR_OFFICER_REVIEW_SECONDS", "20"))


async def _simulated_officer(approval_id: int) -> None:
    """MyTadbir is citizen-only: officers decide in their own back-office system. For the demo, that
    decision is simulated here after a short review time, and arrives in the case like a real one."""
    await asyncio.sleep(OFFICER_REVIEW_SECONDS)
    try:
        await decide(approval_id, True, "officer (MBPJ back office, simulated)")
    except ValueError:
        pass  # already decided


async def decide(approval_id: int, approved: bool, decided_by: str) -> dict:
    """Resolve a paused case (officer approval or citizen confirmation), then continue the thread."""
    with SessionLocal() as s:
        a = s.get(Approval, approval_id)
        if a is None or a.status != "pending":
            raise ValueError("approval not pending")
        a.status, a.officer, a.decided_at = ("approved" if approved else "rejected"), decided_by, datetime.now(timezone.utc)
        s.commit()
        case = s.get(Case, a.case_id)
        lang = s.get(Thread, case.thread_id).language
    ctx = _ctx(case, lang)
    audit.log(decided_by, "approval_" + ("approved" if approved else "rejected"), {"approval_id": approval_id, "action": a.action},
              case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "human", "decision",
                   {"approval_id": approval_id, "approved": approved, "by": decided_by})
    sub = ctx.scratch.get("pending_submodule")
    _save(ctx, status="running")
    outcome = await registry.get(sub).resume(ctx, approved)
    audit.log(sub, f"submodule_{outcome.status}", {"summary": outcome.summary_en, **outcome.data},
              case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "submodule", sub, outcome.status,
                   {"summary_en": outcome.summary_en, "summary_bm": outcome.summary_bm})
    res = await _drive(ctx, case.current_department, hop=len(ctx.handoff_chain) - 1,
                       secondary=(case.context or {}).get("secondary_department"), first=outcome)
    asyncio.create_task(run_thread(ctx.thread_id))  # continue with the next queued case, if any
    return res
