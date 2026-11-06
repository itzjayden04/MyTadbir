"""Complexity levels 1-5: how hard a case is decides which model each step uses.

The level is set by rules when the case is created (no API call), and can only go up while the case
runs (for example, a photo inspected as "critical" lifts it to 5). Higher levels use deepseek-v4-pro
for legal reasoning; lower levels stay on deepseek-flash or skip the model entirely.

    1  Information or status        e.g. track a case, book a facility
    2  Routine transaction          e.g. pay a summons, renew a licence or road tax
    3  Assessment from evidence     e.g. a drain or pollution report, aid eligibility
    4  Legal or compliance judgement e.g. business-licence pre-check, renovation permit
    5  Safety-critical or rights-affecting  e.g. child protection, domestic violence, emergencies
"""
from __future__ import annotations

BASE: dict[int, set[str]] = {
    1: {"facility_booking", "clinic_queue", "doc_request_verify", "exam_document", "mc_document"},
    2: {"roadtax_insurance", "summons_payment", "licence_renewal", "passport_renewal", "appointment_referral",
        "pharmacy_refill", "tax_filing", "puspakom", "driving_test", "waste_scheduler", "streetlight_road",
        "noise_pest", "enrolment_transfer", "border_declaration", "substitute_teacher"},
    3: {"incident_dispatcher", "pollution_complaint", "utility_outage", "flood_landslide", "school_infra",
        "aid_eligibility", "elderly_oku", "lost_document", "police_report", "visa_eligibility", "foreign_worker",
        "refund_dispute", "scholarship_prescreen", "agri_subsidy", "discharge_homecare"},
    4: {"licence_precheck", "renovation_permit", "hawker_licence", "audit_precheck", "business_tax_reg",
        "long_term_pass", "health_inspection", "contact_tracer", "dropout_risk", "special_needs"},
    5: {"emergency_triage", "child_protection", "domestic_violence", "disaster_relief", "community_patrol"},
}
_BASE_OF = {sub: lvl for lvl, subs in BASE.items() for sub in subs}

# Model and effort per task and level. None = no model call (local rules and citations only).
PLAN: dict[str, dict[int, tuple[str, str] | None]] = {
    "route":           {1: ("deepseek-flash", "low"), 2: ("deepseek-flash", "low"), 3: ("deepseek-flash", "low"),
                        4: ("deepseek-flash", "low"), 5: ("deepseek-flash", "low")},  # level unknown before routing
    "inspect_image":   {1: ("deepseek-flash", "low"), 2: ("deepseek-flash", "low"), 3: ("deepseek-flash", "low"),
                        4: ("deepseek-flash", "high"), 5: ("deepseek-flash", "high")},  # only flash reads images
    "legal_reasoning": {1: None, 2: ("deepseek-flash", "low"), 3: ("deepseek-flash", "high"),
                        4: ("deepseek-v4-pro", "low"), 5: ("deepseek-v4-pro", "high")},
    "summarise":       {1: ("deepseek-flash", "low"), 2: ("deepseek-flash", "low"), 3: ("deepseek-flash", "low"),
                        4: ("deepseek-flash", "high"), 5: ("deepseek-v4-pro", "low")},
    "notify":          {lvl: ("deepseek-flash", "low") for lvl in range(1, 6)},
}
LABEL = {1: ("Information", "Maklumat"), 2: ("Routine", "Rutin"), 3: ("Assessment", "Penilaian"),
         4: ("Legal judgement", "Pertimbangan undang-undang"), 5: ("Safety-critical", "Kritikal keselamatan")}


def assess(submodule: str, *, has_photo: bool = False, has_file: bool = False, verify_flag: bool = False) -> tuple[int, list[str]]:
    level = _BASE_OF.get(submodule, 2)
    reasons = [f"{LABEL[level][0].lower()} service ({submodule})"]
    if (has_photo or has_file) and level < 5:
        level += 1
        reasons.append("evidence to examine (photo or file)")
    if verify_flag and level < 5:
        level += 1
        reasons.append("low routing confidence")
    return min(level, 5), reasons


def raise_for_severity(level: int, severity: str) -> int:
    return max(level, {"critical": 5, "high": 4}.get(severity, level))


def model_for(task: str, level: int | None) -> tuple[str, str] | None:
    return PLAN[task][min(max(level or 3, 1), 5)]
