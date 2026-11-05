"""Local Government: Incident dispatcher (Aduan Civil), the flagship demo flow."""
from __future__ import annotations

import uuid

from ..core.context import CaseContext
from ..core.module import Module, ModuleResult, registry
from ..core.trace import bus
from ..db.models import Approval, MapPoint, SessionLocal, Ticket
from ..mocks import gov_apis
from ..services import execution, multimodal, notification, pdfgen, policy

# Demo default when the photo has no GPS: a residential street beside a school in Petaling Jaya.
DEMO_LOCATION = {"lat": 3.1073, "lng": 101.6067, "address": "Jalan SS 2/24, Petaling Jaya (beside a primary school)",
                 "district": "Petaling", "source": "demo default (citizen confirms on map)"}
APPROVAL_COST_THRESHOLD = 5000  # RM: dispatches estimated above this wait for an officer
COST_BY_SEVERITY = {"low": 400, "medium": 1200, "high": 2800, "critical": 8000}


def _priority(sev: str, rain: bool, school: bool) -> str:
    if sev == "critical" or (sev == "high" and (rain or school)):
        return "P1"
    if sev in {"high", "medium"}:
        return "P2"
    return "P3"


@registry.register
class IncidentDispatcher(Module):
    name = "incident_dispatcher"
    kind = "submodule"
    department = "local_gov"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        photo = next((e.path for e in ctx.evidence if e.kind == "photo" and e.path), None)
        text = next((e.text for e in ctx.evidence if e.kind == "text" and e.text), ctx.intent)

        # 1-2. Inspect the photo and find the location
        if photo:
            insp, gps = await multimodal.inspect(ctx, photo, text)
        else:
            insp, gps = await multimodal.inspect(ctx, "", text)
        loc = {**DEMO_LOCATION, **gps} if gps else dict(DEMO_LOCATION)
        school = insp.near_school_or_public_area or "sekolah" in text.lower() or "school" in text.lower()

        # 3. Live weather for the district
        fc = await execution.weather(ctx, loc["district"])
        rain = execution.is_rainy(fc)

        # 4. By-laws and priority rules
        hits = await policy.retrieve(ctx, "parit longkang saliran tersumbat penyelenggaraan majlis kerja jalan halangan",
                                     dept="local_gov", k=5, kinds={"act", "bylaw"})
        facts = {"severity": insp.severity, "hazards": insp.hazards, "standing_water": insp.standing_water,
                 "near_school": school, "rain_forecast": fc.get("summary_forecast"), "location": loc["address"]}
        pr = await policy.reason(ctx, "Who is responsible for clearing this drain, and how urgent is it (P1/P2/P3)?", facts, hits)
        priority = (pr.priority if pr and pr.priority in {"P1", "P2", "P3"} else None) or _priority(insp.severity, rain, school)
        await bus.emit(ctx.thread_id, ctx.case_id, "submodule", self.name, "priority",
                       {"priority": priority, "rule": "severity x rain forecast x school zone",
                        "inputs": {"severity": insp.severity, "rain": rain, "school": school}})

        # 5. Work ticket: SQL row + PDF
        ticket_id = f"WT-{uuid.uuid4().hex[:5].upper()}"
        cites = [f"{h['title_en']}, p.{h['page']}" for h in hits[:3]]
        est = COST_BY_SEVERITY.get(insp.severity, 1200)
        with SessionLocal() as s:
            s.add(Ticket(id=ticket_id, case_id=ctx.case_id, kind="drain_blockage", priority=priority, location=loc, status="open"))
            s.add(MapPoint(case_id=ctx.case_id, kind="incident", label=f"{ticket_id} · {priority}", lat=loc["lat"], lng=loc["lng"],
                           meta={"severity": insp.severity}))
            s.commit()
        await execution.sql_write(ctx, "work_tickets", "INSERT", {"id": ticket_id, "priority": priority, "status": "open"})
        pdf = pdfgen.work_ticket(ticket_id, ctx.case_id, [
            ("Issue / Isu", f"{insp.subject_en}<br/>{insp.subject_bm}"),
            ("Severity / Keterukan", insp.severity), ("Priority / Keutamaan", priority),
            ("Location / Lokasi", f"{loc['address']} ({loc['lat']}, {loc['lng']}) · {loc['source']}"),
            ("Weather / Cuaca", f"{fc.get('summary_forecast')} (MET Malaysia via data.gov.my)"),
            ("Hazards / Bahaya", ", ".join(insp.hazards) or "-"), ("Estimated cost / Anggaran kos", f"RM{est:,}"),
        ], cites or ["No matching clause found in corpus; priority set by severity rules (assumption)."])
        doc_id = execution.save_document(ctx, kind="work_ticket", title=f"Work ticket {ticket_id}", path=pdf, department="local_gov")
        await bus.emit(ctx.thread_id, ctx.case_id, "service", "execution_agent", "artifact",
                       {"doc_id": doc_id, "title": f"Work ticket {ticket_id}", "kind": "pdf"})
        ctx.scratch.update({"ticket_id": ticket_id, "priority": priority, "location": loc, "severity": insp.severity,
                            "rain": rain, "est_cost": est})

        # 6. Human-in-the-loop gate for expensive dispatches
        if est > APPROVAL_COST_THRESHOLD:
            with SessionLocal() as s:
                a = Approval(case_id=ctx.case_id, action="contractor_dispatch_over_threshold",
                             reason=f"Estimated cost RM{est:,} is above the RM{APPROVAL_COST_THRESHOLD:,} auto-dispatch limit.",
                             proposed={"ticket_id": ticket_id, "priority": priority, "location": loc, "citations": cites})
                s.add(a)
                s.commit()
                aid = a.id
            await notification.notify(ctx, f"Your report is ticket {ticket_id} ({priority}). An officer is approving the repair crew now.",
                                      f"Aduan anda ialah tiket {ticket_id} ({priority}). Pegawai sedang meluluskan pasukan pembaikan.")
            return ModuleResult(status="needs_approval", data={"approval_id": aid, "ticket_id": ticket_id},
                                summary_en=f"Ticket {ticket_id} waits for officer approval (cost above limit).",
                                summary_bm=f"Tiket {ticket_id} menunggu kelulusan pegawai (kos melebihi had).")
        return await self.dispatch(ctx)

    async def resume(self, ctx: CaseContext, approved: bool) -> ModuleResult:
        if not approved:
            await notification.notify(ctx, "An officer reviewed your report and will contact you about next steps.",
                                      "Pegawai telah menyemak aduan anda dan akan menghubungi anda untuk langkah seterusnya.")
            return ModuleResult(status="ok", summary_en="Officer rejected automatic dispatch.", summary_bm="Pegawai menolak penghantaran automatik.")
        return await self.dispatch(ctx)

    async def dispatch(self, ctx: CaseContext) -> ModuleResult:
        t, loc, pr = ctx.scratch["ticket_id"], ctx.scratch["location"], ctx.scratch["priority"]
        req = {"ticket_id": t, "trade": "drainage", "lat": loc["lat"], "lng": loc["lng"], "priority": pr}
        d = await execution.api_call(ctx, "execution_agent", "POST", "/mock/mbpj/dispatch", req,
                                     lambda: gov_apis.dispatch(gov_apis.DispatchRequest(**req)))
        c = d["contractor"]
        with SessionLocal() as s:
            tk = s.get(Ticket, t)
            tk.status, tk.contractor = "dispatched", {**c, "dispatch_id": d["dispatch_id"], "eta": d["eta"]}
            s.add(MapPoint(case_id=ctx.case_id, kind="contractor", label=f"{c['name']} → {t}", lat=c["lat"], lng=c["lng"],
                           meta={"eta_minutes": d["eta_minutes"], "to": [loc["lat"], loc["lng"]]}))
            s.commit()
        await execution.sql_write(ctx, "work_tickets", "UPDATE", {"id": t, "status": "dispatched", "contractor": c["id"]})
        await notification.notify(
            ctx, f"Ticket {t} ({pr}): {c['name']} is on the way, about {d['eta_minutes']} minutes. You can track it in My Cases.",
            f"Tiket {t} ({pr}): {c['name']} sedang dalam perjalanan, kira-kira {d['eta_minutes']} minit. Jejak di Kes Saya.")
        handoff = "agri_env" if ctx.scratch.get("rain") and ctx.scratch.get("severity") in {"high", "critical"} else None
        return ModuleResult(status="handoff" if handoff else "ok", handoff_to=handoff,
                            data={"ticket_id": t, "dispatch_id": d["dispatch_id"], "contractor": c["name"], "eta_minutes": d["eta_minutes"]},
                            summary_en=f"Ticket {t} ({pr}) created and {c['name']} dispatched, ETA {d['eta_minutes']} min."
                                       + (" Flood risk: handing off to Agriculture & Environment." if handoff else ""),
                            summary_bm=f"Tiket {t} ({pr}) dicipta dan {c['name']} dihantar, anggaran {d['eta_minutes']} minit."
                                       + (" Risiko banjir: diserahkan kepada Pertanian & Alam Sekitar." if handoff else ""))
