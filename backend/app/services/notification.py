"""Notification Agent: one citizen notification stream per thread (in-app; SMS/email are mocked)."""
from __future__ import annotations

from ..core.context import CaseContext
from ..core.trace import bus
from ..db.models import Notification, SessionLocal
from . import audit


async def notify(ctx: CaseContext, en: str, bm: str, channel: str = "in_app") -> None:
    with SessionLocal() as s:
        s.add(Notification(thread_id=ctx.thread_id, case_id=ctx.case_id, channel=channel, message_en=en, message_bm=bm))
        s.commit()
    rec = {"channel": channel, "message_en": en, "message_bm": bm}
    audit.log("notification_agent", "notified", rec, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "notification_agent", "notified", rec)
