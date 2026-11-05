from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
import os

DB_URL = os.environ.get("MYTADBIR_DB", "sqlite:///./mytadbir.db")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Thread(Base):
    """One citizen conversation. Groups every Case ID it spawned."""
    __tablename__ = "threads"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    citizen_ref: Mapped[str | None] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"))
    seq: Mapped[int] = mapped_column(Integer, default=0)  # run order within the thread
    intent: Mapped[str] = mapped_column(Text)
    primary_department: Mapped[str] = mapped_column(String)
    current_department: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(default=0.0)
    verify_flag: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String, default="queued")
    # queued | running | awaiting_approval | handoff | done | failed
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AuditEntry(Base):
    """Append-only, hash-chained ledger keyed by Case ID. Never updated or deleted."""
    __tablename__ = "audit_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    case_id: Mapped[str | None] = mapped_column(String, index=True)
    thread_id: Mapped[str | None] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String, unique=True)


class Approval(Base):
    """Human-in-the-loop gate for high-risk actions."""
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    action: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    proposed: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | approved | rejected
    officer: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    """One citizen notification stream per thread."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"))
    case_id: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String, default="in_app")
    message_en: Mapped[str] = mapped_column(Text)
    message_bm: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    """Demo accounts only. MyKad numbers here are fictitious; passwords are salted hashes."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # username
    role: Mapped[str] = mapped_column(String)  # citizen | officer
    name: Mapped[str] = mapped_column(String)
    mykad: Mapped[str | None] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(default=False)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Ticket(Base):
    __tablename__ = "work_tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    location: Mapped[dict] = mapped_column(JSON, default=dict)
    contractor: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="open")  # open | dispatched | on_site | closed
    pdf_path: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)
    description_en: Mapped[str] = mapped_column(Text)
    description_bm: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column()
    direction: Mapped[str] = mapped_column(String, default="out")  # out (citizen pays) | in (refund/aid)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | paid | refunded | failed
    receipt_path: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    department: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # upload | work_ticket | receipt | brief | checklist | licence
    title: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)
    title_en: Mapped[str] = mapped_column(String)
    title_bm: Mapped[str] = mapped_column(String)
    when: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="booked")


class MapPoint(Base):
    __tablename__ = "map_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # incident | contractor | school | flood_watch
    label: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column()
    lng: Mapped[float] = mapped_column()
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
