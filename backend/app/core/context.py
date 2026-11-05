"""Case context bundle: travels with a case through every sub-module and handoff."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    kind: str  # "photo" | "audio" | "document" | "text"
    path: str | None = None
    text: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseContext:
    case_id: str
    thread_id: str
    department: str
    intent: str
    language: str = "en"  # "en" | "bm"
    identity: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    prior_cases: list[str] = field(default_factory=list)
    verify_flag: bool = False
    handoff_chain: list[str] = field(default_factory=list)  # departments that have owned this case, in order
    scratch: dict[str, Any] = field(default_factory=dict)  # results from earlier sub-modules in this case
