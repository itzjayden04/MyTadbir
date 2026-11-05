"""Audit & Database Logger: one immutable, hash-chained ledger keyed by Case ID."""
from __future__ import annotations

import hashlib
import json
import threading

from sqlalchemy import select

from ..db.models import AuditEntry, SessionLocal

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev_hash: str, case_id, actor: str, action: str, payload: dict) -> str:
    body = json.dumps(
        {"prev": prev_hash, "case": case_id, "actor": actor, "action": action, "payload": payload},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def log(actor: str, action: str, payload: dict | None = None,
        case_id: str | None = None, thread_id: str | None = None) -> AuditEntry:
    payload = payload or {}
    with _lock, SessionLocal() as s:
        last = s.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(1)).first()
        prev = last.hash if last else GENESIS
        entry = AuditEntry(
            case_id=case_id, thread_id=thread_id, actor=actor, action=action,
            payload=payload, prev_hash=prev, hash=_digest(prev, case_id, actor, action, payload),
        )
        s.add(entry)
        s.commit()
        return entry


def verify_chain() -> tuple[bool, int | None]:
    """Returns (ok, first_bad_id)."""
    with SessionLocal() as s:
        prev = GENESIS
        for e in s.scalars(select(AuditEntry).order_by(AuditEntry.id)):
            if e.prev_hash != prev or e.hash != _digest(prev, e.case_id, e.actor, e.action, e.payload):
                return False, e.id
            prev = e.hash
    return True, None


def timeline(case_id: str) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(AuditEntry).where(AuditEntry.case_id == case_id).order_by(AuditEntry.id))
        return [
            {"id": e.id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action,
             "payload": e.payload, "hash": e.hash}
            for e in rows
        ]
