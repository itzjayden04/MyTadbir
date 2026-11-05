"""The 10 Department Main Modules and their 50 sub-modules (source: project brief, Section 6).

Bilingual labels. BM translations are working drafts; confirm official terms before the demo.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sub:
    key: str
    en: str
    bm: str


@dataclass(frozen=True)
class Dept:
    key: str
    en: str
    bm: str
    agencies: str
    subs: tuple[Sub, ...]


DEPARTMENTS: tuple[Dept, ...] = (
    Dept("health", "Health", "Kesihatan", "KKM / Hospitals", (
        Sub("emergency_triage", "Emergency triage & bed dispatcher", "Triaj kecemasan & penghantar katil"),
        Sub("appointment_referral", "Appointment & referral coordinator", "Penyelaras temu janji & rujukan"),
        Sub("clinic_queue", "Clinic queue optimizer", "Pengoptimum giliran klinik"),
        Sub("contact_tracer", "Contact tracer", "Pengesan kontak"),
        Sub("pharmacy_refill", "Pharmacy refill dispatcher", "Penghantar ulangan ubat farmasi"),
        Sub("discharge_homecare", "Discharge & home-care coordinator", "Penyelaras discaj & penjagaan di rumah"),
        Sub("mc_document", "MC document assistant", "Pembantu dokumen sijil cuti sakit"),
        Sub("health_inspection", "Health inspection scheduler", "Penjadual pemeriksaan kesihatan"),
    )),
    Dept("education", "Education", "Pendidikan", "KPT / Schools", (
        Sub("enrolment_transfer", "Enrolment & transfer assistant", "Pembantu pendaftaran & pertukaran"),
        Sub("scholarship_prescreen", "Scholarship pre-screener", "Pra-saringan biasiswa"),
        Sub("dropout_risk", "Dropout risk responder", "Responden risiko keciciran"),
        Sub("school_infra", "School infrastructure dispatcher", "Penghantar infrastruktur sekolah"),
        Sub("substitute_teacher", "Substitute teacher coordinator", "Penyelaras guru ganti"),
        Sub("exam_document", "Exam document assistant", "Pembantu dokumen peperiksaan"),
        Sub("special_needs", "Special needs support coordinator", "Penyelaras sokongan keperluan khas"),
    )),
    Dept("local_gov", "Local Government", "Kerajaan Tempatan", "DBKL / MBPJ / MBS", (
        Sub("incident_dispatcher", "Incident dispatcher (Aduan Civil)", "Penghantar insiden (Aduan Sivil)"),
        Sub("licence_precheck", "Licence & permit pre-checker", "Pra-semak lesen & permit"),
        Sub("facility_booking", "Facility booking manager", "Pengurus tempahan fasiliti"),
        Sub("waste_scheduler", "Illegal dumping & waste scheduler", "Penjadual pembuangan haram & sisa"),
        Sub("streetlight_road", "Streetlight & road defect dispatcher", "Penghantar kerosakan lampu jalan & jalan raya"),
        Sub("hawker_licence", "Hawker licence assistant", "Pembantu lesen penjaja"),
        Sub("renovation_permit", "Renovation permit pre-screen", "Pra-saringan permit pengubahsuaian"),
        Sub("noise_pest", "Noise & pest enforcement dispatcher", "Penghantar penguatkuasaan bunyi & perosak"),
    )),
    Dept("immigration", "Immigration", "Imigresen", "JIM", (
        Sub("passport_renewal", "Passport renewal assistant", "Pembantu pembaharuan pasport"),
        Sub("visa_eligibility", "Visa eligibility pre-checker", "Pra-semak kelayakan visa"),
        Sub("foreign_worker", "Foreign worker compliance monitor", "Pemantau pematuhan pekerja asing"),
        Sub("border_declaration", "Border entry declaration assistant", "Pembantu pengisytiharan kemasukan sempadan"),
        Sub("long_term_pass", "Long-term pass renewal coordinator", "Penyelaras pembaharuan pas jangka panjang"),
    )),
    Dept("road_transport", "Road Transport", "Pengangkutan Jalan", "JPJ", (
        Sub("licence_renewal", "Driving licence renewal", "Pembaharuan lesen memandu"),
        Sub("roadtax_insurance", "Road tax & insurance coordinator", "Penyelaras cukai jalan & insurans"),
        Sub("summons_payment", "Summons payment agent", "Ejen pembayaran saman"),
        Sub("puspakom", "PUSPAKOM inspection scheduler", "Penjadual pemeriksaan PUSPAKOM"),
        Sub("driving_test", "Driving test booking agent", "Ejen tempahan ujian memandu"),
    )),
    Dept("inland_revenue", "Inland Revenue", "Hasil Dalam Negeri", "LHDN", (
        Sub("tax_filing", "Individual tax filing assistant", "Pembantu pemfailan cukai individu"),
        Sub("audit_precheck", "Audit document pre-checker", "Pra-semak dokumen audit"),
        Sub("refund_dispute", "Refund & dispute agent", "Ejen bayaran balik & pertikaian"),
        Sub("business_tax_reg", "Business tax registration assistant", "Pembantu pendaftaran cukai perniagaan"),
    )),
    Dept("social_welfare", "Social Welfare", "Kebajikan Masyarakat", "JKM", (
        Sub("aid_eligibility", "Aid eligibility pre-checker", "Pra-semak kelayakan bantuan"),
        Sub("child_protection", "Child protection responder", "Responden perlindungan kanak-kanak"),
        Sub("elderly_oku", "Elderly & OKU assistance coordinator", "Penyelaras bantuan warga emas & OKU"),
        Sub("disaster_relief", "Disaster relief dispatch coordinator", "Penyelaras penghantaran bantuan bencana"),
    )),
    Dept("police_home", "Police / Home Affairs", "Polis / Dalam Negeri", "PDRM / KDN", (
        Sub("police_report", "Police report pre-filler & router", "Pra-isi & penghala laporan polis"),
        Sub("lost_document", "Lost document replacement assistant", "Pembantu penggantian dokumen hilang"),
        Sub("community_patrol", "Community patrol dispatcher", "Penghantar rondaan komuniti"),
        Sub("domestic_violence", "Domestic violence emergency responder", "Responden kecemasan keganasan rumah tangga"),
    )),
    Dept("agri_env", "Agriculture & Environment", "Pertanian & Alam Sekitar", "MAFS / DOE", (
        Sub("agri_subsidy", "Agriculture subsidy pre-checker", "Pra-semak subsidi pertanian"),
        Sub("pollution_complaint", "Pollution complaint dispatcher", "Penghantar aduan pencemaran"),
        Sub("flood_landslide", "Flood & landslide early warning responder", "Responden amaran awal banjir & tanah runtuh"),
    )),
    Dept("cross_agency", "Cross-Agency Services", "Perkhidmatan Rentas Agensi", "Multiple", (
        Sub("utility_outage", "Utility outage coordinator", "Penyelaras gangguan utiliti"),
        Sub("doc_request_verify", "Government document request & verification agent", "Ejen permohonan & pengesahan dokumen kerajaan"),
    )),
)

BY_KEY = {d.key: d for d in DEPARTMENTS}

# High-risk actions that always stop at the officer approval gate.
HIGH_RISK_ACTIONS = {
    "issue_fine", "child_protection_action", "domestic_violence_action",
    "permit_rejection", "contractor_dispatch_over_threshold",
}

assert len(DEPARTMENTS) == 10
assert sum(len(d.subs) for d in DEPARTMENTS) == 50
