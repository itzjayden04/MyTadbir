"""Mock government APIs with realistic REST/JSON shapes.

Mounted at /mock/* so judges can browse them in the OpenAPI docs (/docs). The Execution Agent calls
the same handlers, and every call is recorded in the trace and audit ledger with its request and
response. Data below is fictitious demo data.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/mock", tags=["mock government APIs"])

# ---------------------------------------------------------------- MBPJ contractor dispatch
CONTRACTORS = [
    {"id": "KTR-PJ-014", "name": "Syarikat Saliran Damansara Sdn Bhd", "trade": "drainage", "lat": 3.1213, "lng": 101.6305, "crew": 4, "phone": "03-7700 1414"},
    {"id": "KTR-PJ-022", "name": "Kejuruteraan Bukit Gasing Enterprise", "trade": "drainage", "lat": 3.0962, "lng": 101.6612, "crew": 3, "phone": "03-7955 2222"},
    {"id": "KTR-PJ-031", "name": "Teguh Infra Maintenance Sdn Bhd", "trade": "drainage", "lat": 3.1081, "lng": 101.6037, "crew": 5, "phone": "03-7880 3131"},
    {"id": "KTR-PJ-040", "name": "Cahaya Lampu Services", "trade": "streetlight", "lat": 3.1150, "lng": 101.6420, "crew": 2, "phone": "03-7722 4040"},
]
DISPATCHES: dict[str, dict] = {}


def _km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class DispatchRequest(BaseModel):
    ticket_id: str
    trade: str
    lat: float
    lng: float
    priority: str  # P1 | P2 | P3


@router.get("/mbpj/contractors")
def list_contractors(trade: str, lat: float, lng: float):
    rows = [{**c, "distance_km": round(_km(lat, lng, c["lat"], c["lng"]), 2)} for c in CONTRACTORS if c["trade"] == trade]
    return {"contractors": sorted(rows, key=lambda c: c["distance_km"])}


@router.post("/mbpj/dispatch")
def dispatch(req: DispatchRequest):
    near = list_contractors(req.trade, req.lat, req.lng)["contractors"]
    if not near:
        raise HTTPException(404, "no contractor for this trade")
    c = near[0]
    eta_min = {"P1": 45, "P2": 180, "P3": 1440}.get(req.priority, 240) + int(c["distance_km"] * 4)
    d = {"dispatch_id": f"DSP-{uuid.uuid4().hex[:6].upper()}", "ticket_id": req.ticket_id, "contractor": c,
         "status": "dispatched", "eta": (datetime.now(timezone.utc) + timedelta(minutes=eta_min)).isoformat(),
         "eta_minutes": eta_min}
    DISPATCHES[d["dispatch_id"]] = d
    return d


# ---------------------------------------------------------------- JPJ
SUMMONS = {
    "900101-10-1234": [{"summons_no": "JPJ-SMN-2026-118204", "offence_en": "Exceeding the speed limit", "offence_bm": "Melebihi had laju",
                        "date": "2026-08-14", "location": "Lebuhraya Persekutuan, KM 12", "amount": 150.0, "status": "unpaid",
                        "blocks_renewal": True}],
}
LICENCES = {"900101-10-1234": {"licence_no": "D-900101-10-1234", "class": "D", "expiry": "2026-11-20", "status": "valid"}}


@router.get("/jpj/summons")
def jpj_summons(mykad: str):
    return {"mykad": mykad, "summons": SUMMONS.get(mykad, [])}


class PayRequest(BaseModel):
    summons_no: str
    mykad: str
    amount: float


@router.post("/jpj/summons/pay")
def jpj_pay(req: PayRequest):
    for s in SUMMONS.get(req.mykad, []):
        if s["summons_no"] == req.summons_no:
            if abs(s["amount"] - req.amount) > 0.001:
                raise HTTPException(400, "amount mismatch")
            s["status"] = "paid"
            return {"receipt_no": f"RCPT-{uuid.uuid4().hex[:8].upper()}", "summons_no": s["summons_no"], "amount": s["amount"], "status": "paid"}
    raise HTTPException(404, "summons not found")


@router.get("/jpj/licence")
def jpj_licence(mykad: str):
    return LICENCES.get(mykad) or {"status": "not_found"}


class RenewRequest(BaseModel):
    mykad: str
    years: int = 1


@router.post("/jpj/licence/renew")
def jpj_renew(req: RenewRequest):
    lic = LICENCES.get(req.mykad)
    if not lic:
        raise HTTPException(404, "licence not found")
    if any(s["status"] == "unpaid" and s.get("blocks_renewal") for s in SUMMONS.get(req.mykad, [])):
        raise HTTPException(409, "renewal blocked: unpaid summons")
    y, m, d = map(int, lic["expiry"].split("-"))
    lic["expiry"] = f"{y + req.years:04d}-{m:02d}-{d:02d}"
    fee = {1: 30.0, 2: 60.0, 3: 90.0, 5: 150.0}.get(req.years, 30.0 * req.years)
    return {"licence_no": lic["licence_no"], "new_expiry": lic["expiry"], "fee": fee, "status": "renewed",
            "digital_licence": "MyJPJ"}


# ---------------------------------------------------------------- MyDigital ID (mock)
@router.post("/mydigitalid/verify")
def mydigitalid_verify(payload: dict):
    mykad = payload.get("mykad", "")
    ok = len(mykad.replace("-", "")) == 12 and mykad.replace("-", "").isdigit()
    return {"mykad": mykad, "verified": ok, "assurance_level": "high" if ok else None, "method": "MyDigital ID (mock)"}
