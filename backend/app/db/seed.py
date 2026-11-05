"""Demo accounts and sample records. All people, MyKad numbers and records here are fictitious.

Demo logins (for the competition demo only):
    citizen  aisyah   / Demo@2026
    officer  pegawai  / Officer@2026
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from .models import Appointment, Payment, SessionLocal, User

DEMO_USERS = [
    {"id": "aisyah", "role": "citizen", "name": "Nur Aisyah binti Rahman", "mykad": "900101-10-1234",
     "password": "Demo@2026", "profile": {"address": "Jalan SS 2/24, Petaling Jaya", "phone": "012-345 6789"}},
    {"id": "pegawai", "role": "officer", "name": "Encik Hafiz Kamal (MBPJ)", "mykad": None,
     "password": "Officer@2026", "profile": {"agency": "Majlis Bandaraya Petaling Jaya"}},
]


def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()


def check_pw(pw: str, stored: str) -> bool:
    salt_hex, _ = stored.split("$", 1)
    return hash_pw(pw, bytes.fromhex(salt_hex)) == stored


def seed() -> None:
    with SessionLocal() as s:
        if s.get(User, "aisyah"):
            return
        for u in DEMO_USERS:
            s.add(User(id=u["id"], role=u["role"], name=u["name"], mykad=u["mykad"], password_hash=hash_pw(u["password"]),
                       verified=u["role"] == "citizen", profile=u["profile"]))
        now = datetime.now(timezone.utc)
        # History so the trackers are not empty on first login (clearly older, already settled items).
        s.add(Payment(id="PAY-HIST01", user_id="aisyah", department="local_gov", description_en="MBPJ assessment tax (2nd half 2026)",
                      description_bm="Cukai taksiran MBPJ (separuh kedua 2026)", amount=287.0, status="paid"))
        s.add(Payment(id="PAY-HIST02", user_id="aisyah", department="inland_revenue", description_en="Income tax refund YA2025",
                      description_bm="Bayaran balik cukai pendapatan TT2025", amount=412.5, direction="in", status="refunded"))
        s.add(Appointment(id="APT-HIST01", user_id="aisyah", department="health", title_en="Klinik Kesihatan SS3: follow-up",
                          title_bm="Klinik Kesihatan SS3: rawatan susulan", when=now + timedelta(days=6, hours=2),
                          location="Klinik Kesihatan Kelana Jaya"))
        s.add(Appointment(id="APT-HIST02", user_id="aisyah", department="road_transport", title_en="PUSPAKOM inspection",
                          title_bm="Pemeriksaan PUSPAKOM", when=now + timedelta(days=12, hours=1), location="PUSPAKOM Padang Jawa"))
        s.commit()
