from __future__ import annotations

from pydantic import BaseModel, Field


class IntentGuess(BaseModel):
    """One intent the classifier found in the citizen's message."""
    text: str = Field(description="The part of the citizen's message this intent comes from, verbatim.")
    department: str = Field(description="Primary owning department key.")
    submodule: str = Field(description="Most likely sub-module key inside that department.")
    confidence: float = Field(ge=0, le=1)
    secondary_department: str | None = Field(
        default=None,
        description="Only if this one intent needs a second department after the primary finishes. Otherwise null.",
    )
    reason: str = Field(default="", description="One short sentence on why.")


class ClassifierOutput(BaseModel):
    language: str = Field(description="'bm' or 'en': the language the citizen wrote in.")
    intents: list[IntentGuess]
    clarifying_question: str | None = Field(
        default=None,
        description="Only when the request is too vague to route. One short question in the citizen's language.",
    )


class RoutedIntent(BaseModel):
    case_id: str
    seq: int
    text: str
    department: str
    submodule: str
    confidence: float
    verify_flag: bool
    secondary_department: str | None = None
    reason: str = ""
    order_note: str | None = None


class RoutingDecision(BaseModel):
    thread_id: str
    language: str
    classifier: str  # "claude" | "keyword"
    status: str  # "routed" | "needs_clarification"
    clarifying_question: str | None = None
    intents: list[RoutedIntent] = []
