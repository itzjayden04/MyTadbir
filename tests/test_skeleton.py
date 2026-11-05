from app.db.models import AuditEntry, SessionLocal
from app.departments.catalog import DEPARTMENTS
from app.services import audit



def test_catalog_counts():
    assert len(DEPARTMENTS) == 10
    assert sum(len(d.subs) for d in DEPARTMENTS) == 50
    keys = [s.key for d in DEPARTMENTS for s in d.subs]
    assert len(keys) == len(set(keys))


def test_audit_chain_detects_tampering():
    audit.log("router", "classified", {"dept": "local_gov"}, case_id="C-1")
    audit.log("local_gov", "ticket_created", {"ticket": "T-1"}, case_id="C-1")
    assert audit.verify_chain()[0] is True
    assert [e["action"] for e in audit.timeline("C-1")] == ["classified", "ticket_created"]

    with SessionLocal() as s:
        e = s.query(AuditEntry).filter_by(action="classified").one()
        e.payload = {"dept": "health"}
        s.commit()
        bad_id = e.id
    assert audit.verify_chain() == (False, bad_id)
