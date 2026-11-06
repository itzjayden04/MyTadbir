import asyncio

from app.router.intent_router import route
from app.services import complexity


def test_levels_and_model_plan():
    assert complexity.assess("summons_payment")[0] == 2
    assert complexity.assess("incident_dispatcher", has_photo=True)[0] == 4
    assert complexity.assess("child_protection")[0] == 5
    assert complexity.assess("facility_booking")[0] == 1
    assert complexity.model_for("legal_reasoning", 1) is None                      # no model call
    assert complexity.model_for("legal_reasoning", 3)[0] == "deepseek-flash"
    assert complexity.model_for("legal_reasoning", 4) == ("deepseek-v4-pro", "low")
    assert complexity.model_for("legal_reasoning", 5) == ("deepseek-v4-pro", "high")
    assert complexity.raise_for_severity(3, "critical") == 5


def test_router_attaches_level():
    d = asyncio.run(route("Saya nak bayar saman"))
    assert d.intents[0].level == 2 and d.intents[0].level_reasons
