"""Bilingual (BM / EN) keyword lexicon for the offline intent classifier.

Used when no Claude API key is configured, and as a safety net when the model call fails.
Each sub-module lists phrases that strongly signal it. Matching is case-insensitive substring
matching on the normalised text, so keep phrases distinctive.
"""
from __future__ import annotations

LEXICON: dict[str, tuple[str, list[str]]] = {
    # --- Local Government
    "incident_dispatcher": ("local_gov", ["longkang", "parit", "drain", "clogged", "tersumbat", "banjir kilat", "flash flood", "pokok tumbang", "fallen tree", "lubang jalan", "aduan", "complaint"]),
    "licence_precheck": ("local_gov", ["lesen perniagaan", "business licence", "business license", "lesen premis", "premise licence", "lesen kedai", "buka kedai", "open a shop", "open a cafe", "buka kafe", "pelan premis", "layout plan", "lesen komposit", "permit perniagaan", "lesen establisymen"]),
    "facility_booking": ("local_gov", ["tempah dewan", "book hall", "tempahan dewan", "book the hall", "sewa dewan", "court booking", "tempah gelanggang", "facility booking"]),
    "waste_scheduler": ("local_gov", ["sampah", "rubbish", "garbage", "pembuangan haram", "illegal dumping", "tong sampah", "waste collection", "kutipan sampah"]),
    "streetlight_road": ("local_gov", ["lampu jalan", "streetlight", "street light", "jalan berlubang", "pothole", "road damage", "jalan rosak"]),
    "hawker_licence": ("local_gov", ["penjaja", "hawker", "gerai", "stall", "food truck", "trak makanan"]),
    "renovation_permit": ("local_gov", ["ubah suai", "ubahsuai", "renovation", "renovate", "extend my house", "besarkan rumah", "permit bangunan"]),
    "noise_pest": ("local_gov", ["bising", "noise", "nyamuk", "mosquito", "tikus", "rats", "pest", "anjing liar", "stray dog"]),
    # --- Road Transport (JPJ)
    "licence_renewal": ("road_transport", ["renew lesen memandu", "renew driving licence", "renew my driving", "renew lesen", "pembaharuan lesen memandu", "lesen memandu", "driving licence", "driving license", "lesen tamat"]),
    "roadtax_insurance": ("road_transport", ["cukai jalan", "road tax", "roadtax", "insurans kereta", "car insurance"]),
    "summons_payment": ("road_transport", ["saman", "summons", "summon", "bayar saman", "pay summons", "pay my summons", "traffic fine", "ekompaun"]),
    "puspakom": ("road_transport", ["puspakom", "pemeriksaan kenderaan", "vehicle inspection"]),
    "driving_test": ("road_transport", ["ujian memandu", "driving test", "ujian jpj", "ambil lesen", "learner"]),
    # --- Health
    "emergency_triage": ("health", ["kecemasan", "emergency", "sesak nafas", "chest pain", "sakit dada", "pengsan", "unconscious", "ambulans", "ambulance"]),
    "appointment_referral": ("health", ["temu janji", "appointment", "rujukan", "referral", "pakar", "specialist"]),
    "clinic_queue": ("health", ["giliran klinik", "clinic queue", "klinik kesihatan", "nombor giliran"]),
    "contact_tracer": ("health", ["kontak rapat", "close contact", "contact tracing", "dijangkiti", "infected"]),
    "pharmacy_refill": ("health", ["ubat", "medicine", "refill", "farmasi", "pharmacy", "preskripsi", "prescription"]),
    "discharge_homecare": ("health", ["discaj", "discharge", "penjagaan di rumah", "home care", "keluar wad"]),
    "mc_document": ("health", ["sijil cuti sakit", "medical certificate", "cuti sakit", "sick leave"]),
    "health_inspection": ("health", ["pemeriksaan kesihatan premis", "health inspection", "kebersihan premis makanan", "food hygiene"]),
    # --- Education
    "enrolment_transfer": ("education", ["daftar sekolah", "school enrolment", "tahun satu", "year one", "year 1", "pindah sekolah", "school transfer", "tukar sekolah"]),
    "scholarship_prescreen": ("education", ["biasiswa", "scholarship", "ptptn", "pinjaman pendidikan"]),
    "dropout_risk": ("education", ["ponteng", "truancy", "berhenti sekolah", "drop out", "dropout"]),
    "school_infra": ("education", ["kelas bocor", "classroom leak", "bangunan sekolah", "school building", "tandas sekolah", "school toilet"]),
    "substitute_teacher": ("education", ["guru ganti", "substitute teacher", "tiada guru", "no teacher"]),
    "exam_document": ("education", ["sijil spm", "spm certificate", "slip keputusan", "exam result", "sijil peperiksaan", "upsr", "stpm"]),
    "special_needs": ("education", ["pendidikan khas", "special needs", "autisme", "autism", "disleksia", "dyslexia"]),
    # --- Immigration
    "passport_renewal": ("immigration", ["pasport", "passport"]),
    "visa_eligibility": ("immigration", ["visa", "pas lawatan", "visit pass"]),
    "foreign_worker": ("immigration", ["pekerja asing", "foreign worker", "permit kerja", "work permit", "plks"]),
    "border_declaration": ("immigration", ["pengisytiharan masuk", "arrival card", "mdac", "border entry", "kastam"]),
    "long_term_pass": ("immigration", ["pas jangka panjang", "long-term pass", "long term pass", "mm2h", "pas tanggungan", "dependant pass"]),
    # --- Inland Revenue (LHDN)
    "tax_filing": ("inland_revenue", ["cukai pendapatan", "income tax", "e-filing", "efiling", "borang be", "isytihar cukai", "file my tax"]),
    "audit_precheck": ("inland_revenue", ["audit cukai", "tax audit", "notis audit"]),
    "refund_dispute": ("inland_revenue", ["bayaran balik cukai", "tax refund", "refund cukai", "rayuan cukai", "tax appeal"]),
    "business_tax_reg": ("inland_revenue", ["daftar cukai perniagaan", "register business tax", "no cukai", "tin number", "nombor pengenalan cukai"]),
    # --- Social Welfare (JKM)
    "aid_eligibility": ("social_welfare", ["bantuan jkm", "welfare aid", "bantuan kewangan", "financial aid", "bantuan bulanan", "miskin", "low income", "b40"]),
    "child_protection": ("social_welfare", ["dera kanak", "child is being abused", "being abused", "child abuse", "kanak-kanak didera", "abused child", "pengabaian kanak"]),
    "elderly_oku": ("social_welfare", ["warga emas", "elderly", "oku", "disabled", "kurang upaya", "kad oku"]),
    "disaster_relief": ("social_welfare", ["mangsa banjir", "flood victim", "pusat pemindahan", "evacuation centre", "bantuan bencana", "disaster relief"]),
    # --- Police / Home Affairs
    "police_report": ("police_home", ["laporan polis", "police report", "dirompak", "robbed", "dicuri", "stolen", "pecah rumah", "break-in", "scam", "penipuan"]),
    "lost_document": ("police_home", ["hilang ic", "lost ic", "mykad hilang", "hilang mykad", "lost mykad", "kad pengenalan hilang", "lost my ic", "lost identity card"]),
    "community_patrol": ("police_home", ["rondaan", "patrol", "kawasan tidak selamat", "unsafe area", "lepak"]),
    "domestic_violence": ("police_home", ["keganasan rumah tangga", "domestic violence", "dipukul suami", "husband hit", "dipukul isteri", "abusive partner"]),
    # --- Agriculture & Environment
    "agri_subsidy": ("agri_env", ["subsidi baja", "fertiliser subsidy", "fertilizer subsidy", "subsidi pertanian", "farm subsidy", "petani", "farmer", "nelayan", "fisherman"]),
    "pollution_complaint": ("agri_env", ["pencemaran", "pollution", "asap kilang", "factory smoke", "bau busuk", "foul smell", "sungai tercemar", "river polluted", "pembakaran terbuka", "open burning"]),
    "flood_landslide": ("agri_env", ["tanah runtuh", "landslide", "paras air sungai", "river level", "amaran banjir", "flood warning"]),
    # --- Cross-Agency
    "utility_outage": ("cross_agency", ["bekalan elektrik", "blackout", "power outage", "elektrik terputus", "gangguan air", "water disruption", "tiada air", "no water", "tnb"]),
    "doc_request_verify": ("cross_agency", ["sahkan dokumen", "verify document", "salinan sijil", "certified copy", "sijil kelahiran", "birth certificate", "sijil nikah", "marriage certificate"]),
}

# Phrases that separate bundled requests ("renew X and pay Y").
SPLITTERS = [" dan juga ", " and also ", " serta ", " dan ", " and ", " also ", " juga ", ";", " lepas tu ", " then "]

# Words that tell us the message is in Bahasa Malaysia.
BM_MARKERS = ["saya", "nak", "tolong", "dan", "yang", "untuk", "bayar", "lesen", "longkang", "tidak", "boleh", "macam mana", "bagaimana", "sudah", "dah"]
