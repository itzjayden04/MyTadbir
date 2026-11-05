import asyncio
import csv
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.context import CaseContext
from app.core.module import Module, ModuleResult, registry
from app.main import app
from app.router.classifier import KeywordClassifier
from app.router.intent_router import route

SET = Path(__file__).with_name("routing_set.tsv")


def _load():
    with open(SET, encoding="utf-8") as f:
        return [(r["text"], r["expected"].split(",")) for r in csv.DictReader(f, delimiter="\t")]


def test_keyword_routing_accuracy():
    clf = KeywordClassifier()
    rows = _load()
    wrong = []
    for text, expected in rows:
        got = [g.submodule for g in clf.classify(text).intents]
        if sorted(got) != sorted(expected):
            wrong.append((text, expected, got))
    acc = 1 - len(wrong) / len(rows)
    print(f"\nkeyword routing accuracy: {acc:.0%} on {len(rows)} requests")
    for w in wrong:
        print("  MISS", w)
    assert acc >= 0.9


def test_multi_intent_split_order_and_linking():
    d = asyncio.run(route("Saya nak renew lesen memandu dan bayar saman", citizen_ref="900101-10-1234"))
    assert d.status == "routed" and d.language == "bm"
    assert [i.submodule for i in d.intents] == ["summons_payment", "licence_renewal"]  # summons runs first
    assert d.intents[0].order_note and "assumption" in d.intents[0].order_note
    assert len({i.case_id for i in d.intents}) == 2


def test_vague_request_asks_one_question():
    d = asyncio.run(route("tolong saya"))
    assert d.status == "needs_clarification"
    assert d.clarifying_question and not d.intents


class _FloodHandoff(Module):
    """Test double: a sub-module that asks for a handoff to Agriculture & Environment."""
    name = "incident_dispatcher"
    kind = "submodule"
    department = "local_gov"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        return ModuleResult(status="handoff", handoff_to="agri_env", summary_en="flood risk")


def test_api_runs_cases_sequentially_with_handoff(monkeypatch):
    monkeypatch.setitem(registry._modules, "incident_dispatcher", _FloodHandoff)
    with TestClient(app) as c:
        r = c.post("/api/requests", json={"text": "Longkang tersumbat depan sekolah"}).json()
        assert r["status"] == "routed"
        tid, cid = r["thread_id"], r["intents"][0]["case_id"]
        cases = c.get(f"/api/threads/{tid}").json()
        assert cases[0]["status"] == "done"
        assert cases[0]["context"]["handoff_chain"] == ["local_gov", "agri_env"]
        actions = [e["action"] for e in c.get(f"/api/cases/{cid}/timeline").json()]
        assert actions.index("handoff_queued") < actions.index("case_closed")
        assert actions.count("dispatched") == 2  # one department after the other, same Case ID
