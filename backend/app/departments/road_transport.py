"""Road Transport (JPJ): summons payment and driving licence renewal (second demo scenario)."""
from __future__ import annotations

import uuid

from ..core.context import CaseContext
from ..core.module import Module, ModuleResult, registry
from ..db.models import Approval, Payment, SessionLocal
from ..mocks import gov_apis
from ..services import execution, identity, notification, pdfgen, policy


def _mykad(ctx: CaseContext) -> str:
    return ctx.identity.get("mykad") or "900101-10-1234"


@registry.register
class SummonsPayment(Module):
    name = "summons_payment"
    kind = "submodule"
    department = "road_transport"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        idv = await identity.verify(ctx)
        if not idv.get("verified"):
            return ModuleResult(status="error", summary_en="Identity could not be verified.", summary_bm="Identiti tidak dapat disahkan.")
        mk = _mykad(ctx)
        res = await execution.api_call(ctx, "execution_agent", "GET", f"/mock/jpj/summons?mykad={mk}", None,
                                       lambda: gov_apis.jpj_summons(mk))
        unpaid = [s for s in res["summons"] if s["status"] == "unpaid"]
        if not unpaid:
            return ModuleResult(status="ok", summary_en="No outstanding JPJ summons.", summary_bm="Tiada saman JPJ tertunggak.")
        await policy.retrieve(ctx, "kompaun saman kesalahan bayaran", dept="road_transport", k=3, kinds={"act"})
        total = sum(s["amount"] for s in unpaid)
        with SessionLocal() as s:
            pay = Payment(id=f"PAY-{uuid.uuid4().hex[:6].upper()}", case_id=ctx.case_id, user_id=ctx.identity.get("user_id"),
                          department="road_transport", description_en=f"JPJ summons {unpaid[0]['summons_no']}",
                          description_bm=f"Saman JPJ {unpaid[0]['summons_no']}", amount=total, status="pending")
            s.add(pay)
            a = Approval(case_id=ctx.case_id, action="citizen_confirm_payment",
                         reason=f"Paying RM{total:.2f} needs the citizen's confirmation.",
                         proposed={"payment_id": pay.id, "summons": unpaid, "amount": total})
            s.add(a)
            s.commit()
            aid, pid = a.id, pay.id
        await execution.sql_write(ctx, "payments", "INSERT", {"id": pid, "amount": total, "status": "pending"})
        await notification.notify(ctx, f"You have 1 unpaid JPJ summons (RM{total:.2f}). Please confirm the payment to continue.",
                                  f"Anda ada 1 saman JPJ belum dibayar (RM{total:.2f}). Sila sahkan bayaran untuk meneruskan.")
        ctx.scratch.update({"payment_id": pid, "summons": unpaid})
        return ModuleResult(status="needs_approval", data={"approval_id": aid, "payment_id": pid, "amount": total},
                            summary_en=f"Found 1 unpaid summons (RM{total:.2f}); waiting for the citizen to confirm payment.",
                            summary_bm=f"1 saman belum dibayar (RM{total:.2f}); menunggu pengesahan bayaran rakyat.")

    async def resume(self, ctx: CaseContext, approved: bool) -> ModuleResult:
        pid, summons = ctx.scratch["payment_id"], ctx.scratch["summons"]
        if not approved:
            with SessionLocal() as s:
                s.get(Payment, pid).status = "failed"
                s.commit()
            return ModuleResult(status="ok", summary_en="Citizen cancelled the payment.", summary_bm="Rakyat membatalkan bayaran.")
        mk = _mykad(ctx)
        receipts = []
        for sm in summons:
            req = {"summons_no": sm["summons_no"], "mykad": mk, "amount": sm["amount"]}
            r = await execution.api_call(ctx, "execution_agent", "POST", "/mock/jpj/summons/pay", req,
                                         lambda req=req: gov_apis.jpj_pay(gov_apis.PayRequest(**req)))
            receipts.append(r)
        pdf = pdfgen.receipt(receipts[0]["receipt_no"], ctx.case_id, [
            ("Summons / Saman", sm["summons_no"]), ("Offence / Kesalahan", f"{sm['offence_en']} / {sm['offence_bm']}"),
            ("Amount / Jumlah", f"RM{sm['amount']:.2f}"), ("Status", "PAID / DIBAYAR")])
        doc = execution.save_document(ctx, kind="receipt", title=f"Receipt {receipts[0]['receipt_no']}", path=pdf, department="road_transport")
        with SessionLocal() as s:
            p = s.get(Payment, pid)
            p.status, p.receipt_path = "paid", str(pdf)
            s.commit()
        await execution.sql_write(ctx, "payments", "UPDATE", {"id": pid, "status": "paid"})
        await execution.sql_write(ctx, "documents", "INSERT", {"id": doc, "kind": "receipt"})
        return ModuleResult(status="ok", data={"receipt_no": receipts[0]["receipt_no"]},
                            summary_en=f"Summons paid. Receipt {receipts[0]['receipt_no']}.",
                            summary_bm=f"Saman dibayar. Resit {receipts[0]['receipt_no']}.")


@registry.register
class LicenceRenewal(Module):
    name = "licence_renewal"
    kind = "submodule"
    department = "road_transport"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        await identity.verify(ctx)  # reused from the earlier case in this thread
        mk = _mykad(ctx)
        lic = await execution.api_call(ctx, "execution_agent", "GET", f"/mock/jpj/licence?mykad={mk}", None,
                                       lambda: gov_apis.jpj_licence(mk))
        await policy.retrieve(ctx, "pembaharuan lesen memandu tempoh sah lesen", dept="road_transport", k=4)
        try:
            r = await execution.api_call(ctx, "execution_agent", "POST", "/mock/jpj/licence/renew", {"mykad": mk, "years": 1},
                                         lambda: gov_apis.jpj_renew(gov_apis.RenewRequest(mykad=mk, years=1)))
        except RuntimeError:
            return ModuleResult(status="error", summary_en="Renewal blocked by JPJ (unpaid summons).",
                                summary_bm="Pembaharuan disekat oleh JPJ (saman belum dibayar).")
        with SessionLocal() as s:
            pid = f"PAY-{uuid.uuid4().hex[:6].upper()}"
            s.add(Payment(id=pid, case_id=ctx.case_id, user_id=ctx.identity.get("user_id"), department="road_transport",
                          description_en="Driving licence renewal (1 year)", description_bm="Pembaharuan lesen memandu (1 tahun)",
                          amount=r["fee"], status="paid"))
            s.commit()
        await execution.sql_write(ctx, "payments", "INSERT", {"id": pid, "amount": r["fee"], "status": "paid"})
        await notification.notify(ctx, f"Done: summons paid and licence renewed to {r['new_expiry']}. Your digital licence is in MyJPJ.",
                                  f"Selesai: saman dibayar dan lesen diperbaharui hingga {r['new_expiry']}. Lesen digital dalam MyJPJ.")
        return ModuleResult(status="ok", data={"old_expiry": lic.get("expiry"), **r},
                            summary_en=f"Licence renewed to {r['new_expiry']} (fee RM{r['fee']:.2f}).",
                            summary_bm=f"Lesen diperbaharui hingga {r['new_expiry']} (yuran RM{r['fee']:.2f}).")
