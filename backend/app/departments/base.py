"""Department Main Module: the orchestrator that owns a case.

Each department decides which of ITS OWN sub-modules to run, in order. Sub-modules may call shared
services but never another department. To involve another department, a sub-module returns
status="handoff" and the Case Manager runs that department afterwards, with the same Case ID.
"""
from __future__ import annotations

from ..core.context import CaseContext
from ..core.module import ModuleResult, registry
from ..core.trace import bus
from ..services import audit
from .catalog import BY_KEY


class DepartmentModule:
    def __init__(self, key: str) -> None:
        self.key = key
        self.dept = BY_KEY[key]

    def plan(self, ctx: CaseContext) -> list[str]:
        """Which sub-modules to run, in order. Default: the router's hint, if it belongs to us."""
        hint = ctx.scratch.get("submodule_hint")
        own = {s.key for s in self.dept.subs}
        return [hint] if hint in own else [self.dept.subs[0].key]

    async def run(self, ctx: CaseContext) -> ModuleResult:
        plan = self.plan(ctx)
        await bus.emit(ctx.thread_id, ctx.case_id, "department", self.key, "plan", {"submodules": plan})
        audit.log(self.key, "department_plan", {"submodules": plan}, case_id=ctx.case_id, thread_id=ctx.thread_id)
        last = ModuleResult(status="ok")
        for sub in plan:
            await bus.emit(ctx.thread_id, ctx.case_id, "submodule", sub, "start", {})
            if sub in registry.names(kind="submodule"):
                last = await registry.get(sub).run(ctx)
            else:
                name = next(s for s in self.dept.subs if s.key == sub)
                last = ModuleResult(
                    status="stub", data={"submodule": sub},
                    summary_en=f"{name.en}: not built for the demo yet. The case is logged and queued for an officer.",
                    summary_bm=f"{name.bm}: belum dibina untuk demo. Kes direkod dan dibaris gilir untuk pegawai.",
                )
            ctx.scratch[sub] = last.data
            audit.log(sub, f"submodule_{last.status}", {"summary": last.summary_en, **last.data},
                      case_id=ctx.case_id, thread_id=ctx.thread_id)
            await bus.emit(ctx.thread_id, ctx.case_id, "submodule", sub, last.status,
                           {"summary_en": last.summary_en, "summary_bm": last.summary_bm})
            if last.status == "needs_approval":
                ctx.scratch["pending_submodule"] = sub
            if last.status in {"handoff", "needs_approval", "error"}:
                break
        return last


def get_department(key: str) -> DepartmentModule:
    # Departments with custom planning subclass DepartmentModule and register here later.
    return DEPARTMENT_OVERRIDES.get(key, DepartmentModule)(key)


DEPARTMENT_OVERRIDES: dict[str, type[DepartmentModule]] = {}
