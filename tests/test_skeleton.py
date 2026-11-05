import os
import sys
import tempfile
from pathlib import Path

os.environ["MYTADBIR_DB"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import AuditEntry, SessionLocal, init_db  # noqa: E402
from app.departments.catalog import DEPARTMENTS  # noqa: E402
from app.services import audit  # noqa: E402

init_db()


def test_catalog_counts():
    assert len(DEPARTMENTS) == 10
    assert sum(len(d.subs) for d in DEPARTMENTS) == 50
    keys = [s.key for d in DEPARTMENTS for s in d.subs]
    assert len(keys) == len(set(keys))


def test_audit_chain_detects_tampering():
    audit.log("router", "classified", {"dept": "local_gov"}, case_id="C-1")
    audit.log("local_gov", "ticket_created", {"ticket": "T-1"}, case_id="C-1")
    assert audit.verify_chain() == (True, None)
    assert [e["action"] for e in audit.timeline("C-1")] == ["classified", "ticket_created"]

    with SessionLocal() as s:
        e = s.query(AuditEntry).filter_by(action="classified").one()
        e.payload = {"dept": "health"}
        s.commit()
        bad_id = e.id
    assert audit.verify_chain() == (False, bad_id)
