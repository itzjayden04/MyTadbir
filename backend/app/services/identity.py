"""Identity & Verification Agent: verify once per thread, reuse the result for every later case."""
from __future__ import annotations

from ..core.context import CaseContext
from ..core.trace import bus
from ..mocks import gov_apis
from . import audit, execution

_VERIFIED: dict[str, dict] = {}  # thread_id -> verification result


async def verify(ctx: CaseContext) -> dict:
    if ctx.thread_id in _VERIFIED:
        res = _VERIFIED[ctx.thread_id]
        await bus.emit(ctx.thread_id, ctx.case_id, "service", "identity_agent", "reused",
                       {"mykad": res["mykad"], "note": "already verified in this thread; no second check"})
        return res
    mykad = ctx.identity.get("mykad", "")
    res = await execution.api_call(ctx, "identity_agent", "POST", "/mock/mydigitalid/verify", {"mykad": mykad},
                                   lambda: gov_apis.mydigitalid_verify({"mykad": mykad}))
    if res.get("verified"):
        _VERIFIED[ctx.thread_id] = res
    audit.log("identity_agent", "verified" if res.get("verified") else "verification_failed", res,
              case_id=ctx.case_id, thread_id=ctx.thread_id)
    return res
