"""Case Manager: the router's control layer that runs cases one at a time.

It is the only component that invokes a Department Main Module, and it invokes exactly one at a time.
Cases in a thread run in their routed order. A handoff is queued and run after the current department
finishes, with the same Case ID and context. Nothing ever runs in parallel.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from ..core.context import CaseContext, Evidence
from ..core.module import registry
from ..core.trace import bus
from ..db.models import Case, SessionLocal, Thread
from ..departments.base import get_department
from ..services import audit

log = logging.getLogger(__name__)
MAX_HANDOFFS = 3


def _ctx(case: Case, lang: str) -> CaseContext:
    c = case.context or {}
    ctx = CaseContext(
        case_id=case.id, thread_id=case.thread_id, department=case.current_department, intent=case.intent,
        language=lang, identity=c.get("identity", {}),
        evidence=[Evidence(kind=e["kind"], path=e.get("path"), text=e.get("text")) for e in c.get("evidence", [])],
        history=c.get("history", []), prior_cases=c.get("prior_cases", []), verify_flag=case.verify_flag,
        handoff_chain=c.get("handoff_chain", []),
    )
    ctx.scratch["submodule_hint"] = c.get("submodule_hint")
    return ctx


def _set(case_id: str, **fields) -> None:
    with SessionLocal() as s:
        c = s.get(Case, case_id)
        for k, v in fields.items():
            setattr(c, k, v)
        s.commit()


async def run_thread(thread_id: str) -> list[dict]:
    with SessionLocal() as s:
        lang = s.get(Thread, thread_id).language
        cases = list(s.scalars(select(Case).where(Case.thread_id == thread_id, Case.status == "queued").order_by(Case.seq)))
    results = []
    for case in cases:
        results.append(await run_case(case, lang))
    await bus.emit(thread_id, None, "case_manager", "case_manager", "thread_done", {"cases": [r["case_id"] for r in results]})
    return results


async def run_case(case: Case, lang: str) -> dict:
    ctx = _ctx(case, lang)
    secondary = (case.context or {}).get("secondary_department")
    dept_key = case.current_department
    outcome = None
    for hop in range(MAX_HANDOFFS + 1):
        ctx.department = dept_key
        ctx.handoff_chain.append(dept_key)
        _set(case.id, status="running", current_department=dept_key)
        await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "dispatch",
                       {"department": dept_key, "hop": hop})
        audit.log("case_manager", "dispatched", {"department": dept_key, "hop": hop},
                  case_id=ctx.case_id, thread_id=ctx.thread_id)

        outcome = await get_department(dept_key).run(ctx)

        nxt = outcome.handoff_to if outcome.status == "handoff" else None
        if nxt is None and secondary and hop == 0 and outcome.status in {"ok", "stub"}:
            nxt = secondary  # router flagged this intent as needing a second department
        if not nxt or nxt in ctx.handoff_chain:
            break
        audit.log("case_manager", "handoff_queued", {"from": dept_key, "to": nxt},
                  case_id=ctx.case_id, thread_id=ctx.thread_id)
        await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "handoff",
                       {"from": dept_key, "to": nxt})
        dept_key = nxt
        ctx.scratch["submodule_hint"] = None  # the new owner plans for itself

    # Always-on modules: once per case, after the departments finish.
    for name in registry.names(kind="always_on"):
        r = await registry.get(name).run(ctx)
        ctx.scratch[name] = r.data
        await bus.emit(ctx.thread_id, ctx.case_id, "always_on", name, r.status, r.data)

    final = {"needs_approval": "awaiting_approval", "error": "failed"}.get(outcome.status, "done")
    with SessionLocal() as s:
        c = s.get(Case, case.id)
        c.status = final
        c.context = {**(c.context or {}), "handoff_chain": ctx.handoff_chain,
                     "result": {"status": outcome.status, "summary_en": outcome.summary_en,
                                "summary_bm": outcome.summary_bm, "data": outcome.data}}
        s.commit()
    audit.log("case_manager", "case_closed" if final == "done" else f"case_{final}",
              {"chain": ctx.handoff_chain, "status": outcome.status}, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "case_manager", "case_manager", "case_done",
                   {"status": final, "chain": ctx.handoff_chain})
    return {"case_id": case.id, "status": final, "chain": ctx.handoff_chain}
