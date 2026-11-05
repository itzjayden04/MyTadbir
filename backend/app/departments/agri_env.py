"""Agriculture & Environment: Flood & landslide early warning responder (receives Aduan Civil handoffs)."""
from __future__ import annotations

from ..core.context import CaseContext
from ..core.module import Module, ModuleResult, registry
from ..db.models import MapPoint, SessionLocal
from ..services import execution, notification, policy
from .base import DEPARTMENT_OVERRIDES, DepartmentModule


@registry.register
class FloodLandslideResponder(Module):
    name = "flood_landslide"
    kind = "submodule"
    department = "agri_env"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        loc = ctx.scratch.get("location") or {}
        await policy.retrieve(ctx, "banjir saliran amaran paras air kerja penyaliran", dept="agri_env", k=3)
        if loc:
            with SessionLocal() as s:
                s.add(MapPoint(case_id=ctx.case_id, kind="flood_watch", label="Flood watch (24h)", lat=loc["lat"],
                               lng=loc["lng"], meta={"radius_m": 400}))
                s.commit()
            await execution.sql_write(ctx, "map_points", "INSERT", {"kind": "flood_watch", "radius_m": 400, "hours": 24})
        await notification.notify(ctx, "Your area is on a 24-hour flood watch while the drain is cleared. Avoid the low road if water rises.",
                                  "Kawasan anda dalam pemantauan banjir 24 jam semasa longkang dibersihkan. Elakkan jalan rendah jika air naik.")
        return ModuleResult(status="ok", data={"flood_watch_hours": 24},
                            summary_en="Location put on 24-hour flood watch.", summary_bm="Lokasi diletakkan dalam pemantauan banjir 24 jam.")


class AgriEnv(DepartmentModule):
    def plan(self, ctx: CaseContext) -> list[str]:
        # A handoff from Local Government about a blocked drain in rain goes to flood watch.
        if ctx.scratch.get("submodule_hint") is None and ctx.scratch.get("rain"):
            return ["flood_landslide"]
        return super().plan(ctx)


DEPARTMENT_OVERRIDES["agri_env"] = AgriEnv
