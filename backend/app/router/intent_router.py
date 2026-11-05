"""Intent Router: classify, score, split, pick primary, mint Case IDs. Never executes work.

The five features from the brief:
  1. intent classification -> department mapping       (classifier.py)
  2. confidence scoring & ambiguity handling            (thresholds below)
  3. multi-intent detection & splitting                 (classifier output, one case per intent)
  4. primary department selection & sequential handoff  (primary = owner; secondary recorded for handoff)
  5. Case ID creation & context preservation            (Thread + Case rows with a context bundle)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..core.trace import bus
from ..db.models import Case, SessionLocal, Thread
from ..services import audit
from .classifier import KeywordClassifier, get_classifier
from .schemas import ClassifierOutput, RoutedIntent, RoutingDecision

log = logging.getLogger(__name__)

ROUTE_THRESHOLD = 0.75   # at or above: route normally
VERIFY_THRESHOLD = 0.50  # between the two: route, but flag for officer verification
# below VERIFY_THRESHOLD with nothing else to go on: ask one clarifying question

# Run-order rules for bundled requests: (must run first, before this). Each carries a note shown to
# the citizen and officer. These are assumptions until confirmed against the agency's own rules.
ORDER_RULES: dict[tuple[str, str], str] = {
    ("summons_payment", "licence_renewal"): "Summons first: assumption that an unpaid summons can block licence renewal (to verify with JPJ).",
    ("summons_payment", "roadtax_insurance"): "Summons first: assumption that an unpaid summons can block road tax renewal (to verify with JPJ).",
    ("police_report", "lost_document"): "Police report first: a replacement document usually needs the report number.",
    ("lost_document", "doc_request_verify"): "Replace the lost document first, then request copies or verification.",
}


def _new_case_id(s) -> str:
    yy = datetime.now(timezone.utc).strftime("%y")
    n = (s.scalar(select(func.count()).select_from(Case)) or 0) + 1
    return f"MT-{yy}-{n:06d}"


def _order(intents):
    """Stable topological-ish order: apply ORDER_RULES pairwise, keep citizen's order otherwise."""
    items = list(intents)
    notes: dict[int, str] = {}
    changed = True
    while changed:
        changed = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                rule = ORDER_RULES.get((items[j].submodule, items[i].submodule))
                if rule:
                    items[i], items[j] = items[j], items[i]
                    notes[id(items[i])] = rule
                    changed = True
    return items, notes


async def route(text: str, *, image_paths: list[str] | None = None, identity: dict | None = None,
                thread_id: str | None = None, citizen_ref: str | None = None) -> RoutingDecision:
    image_paths = image_paths or []
    clf = get_classifier()
    try:
        out: ClassifierOutput = clf.classify(text, image_paths)
    except Exception as exc:  # noqa: BLE001
        log.warning("classifier %s failed (%s); falling back to keywords", clf.name, exc)
        clf = KeywordClassifier()
        out = clf.classify(text, image_paths)

    with SessionLocal() as s:
        if thread_id is None or s.get(Thread, thread_id) is None:
            thread_id = thread_id or f"TH-{uuid.uuid4().hex[:8].upper()}"
            s.add(Thread(id=thread_id, citizen_ref=citizen_ref, language=out.language))
            s.commit()
        prior = [c.id for c in s.scalars(select(Case).join(Thread).where(Thread.citizen_ref == citizen_ref))] if citizen_ref else []

    await bus.emit(thread_id, None, "router", "intent_router", "classified", {
        "classifier": clf.name, "language": out.language,
        "intents": [g.model_dump() for g in out.intents],
    })

    usable = [g for g in out.intents if g.confidence >= VERIFY_THRESHOLD]
    weak = [g for g in out.intents if g.confidence < VERIFY_THRESHOLD]
    # Never silently misroute: a lone weak guess becomes a clarifying question...
    if not usable and len(weak) <= 1:
        q = out.clarifying_question or _clarify(out.language, weak[0] if weak else None)
        audit.log("intent_router", "clarification_requested", {"text": text, "question": q,
                  "best_guess": weak[0].model_dump() if weak else None}, thread_id=thread_id)
        await bus.emit(thread_id, None, "router", "intent_router", "needs_clarification", {"question": q})
        return RoutingDecision(thread_id=thread_id, language=out.language, classifier=clf.name,
                               status="needs_clarification", clarifying_question=q)
    # ...while weak guesses inside a multi-intent message are routed with a verify flag.
    ordered, notes = _order(usable + weak)

    routed: list[RoutedIntent] = []
    with SessionLocal() as s:
        for seq, g in enumerate(ordered, start=1):
            case_id = _new_case_id(s)
            verify = g.confidence < ROUTE_THRESHOLD
            context = {
                "identity": identity or {},
                "evidence": [{"kind": "photo", "path": p} for p in image_paths] + [{"kind": "text", "text": text}],
                "history": [{"role": "citizen", "text": text}],
                "prior_cases": prior,
                "submodule_hint": g.submodule,
                "secondary_department": g.secondary_department,
                "linked_cases": [],  # filled below
            }
            s.add(Case(id=case_id, thread_id=thread_id, seq=seq, intent=g.text, primary_department=g.department,
                       current_department=g.department, confidence=g.confidence, verify_flag=verify,
                       status="queued", context=context))
            s.flush()
            routed.append(RoutedIntent(case_id=case_id, seq=seq, text=g.text, department=g.department,
                                       submodule=g.submodule, confidence=g.confidence, verify_flag=verify,
                                       secondary_department=g.secondary_department, reason=g.reason,
                                       order_note=notes.get(id(g))))
        ids = [r.case_id for r in routed]
        for c in s.scalars(select(Case).where(Case.id.in_(ids))):
            c.context = {**c.context, "linked_cases": [i for i in ids if i != c.id]}
        s.commit()

    for r in routed:
        audit.log("intent_router", "case_created", r.model_dump(), case_id=r.case_id, thread_id=thread_id)
        await bus.emit(thread_id, r.case_id, "router", "intent_router", "case_created", r.model_dump())

    return RoutingDecision(thread_id=thread_id, language=out.language, classifier=clf.name,
                           status="routed", intents=routed)


def _clarify(lang: str, guess) -> str:
    if guess is None:
        return ("Boleh terangkan sedikit lagi apa yang anda perlukan?" if lang == "bm"
                else "Could you tell me a bit more about what you need?")
    if lang == "bm":
        return f"Adakah anda maksudkan perkara berkaitan {guess.department.replace('_', ' ')}? Sila beri sedikit butiran lagi."
    return f"Is this about {guess.department.replace('_', ' ')}? Please add a little more detail so I route it correctly."
