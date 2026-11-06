"""Always-on module: one call per case after the departments finish (deepseek-flash, low effort).

Combines the reasoning summary and next-step suggestions into a single call to save tokens.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from .. import llm
from ..core.context import CaseContext
from ..core.module import Module, ModuleResult, registry


class Step(BaseModel):
    en: str
    bm: str


class Wrap(BaseModel):
    summary_en: str
    summary_bm: str
    next_steps: list[Step]


@registry.register
class ReasoningAndNextSteps(Module):
    name = "reasoning_next_steps"
    kind = "always_on"

    async def run(self, ctx: CaseContext, **kw) -> ModuleResult:
        facts = {k: v for k, v in ctx.scratch.items() if k not in {"submodule_hint"} and not isinstance(v, (bytes,))}
        if llm.available():
            out, meta = await asyncio.to_thread(
                llm.chat_json,
                "summarise",
                "Summarise what the government agents did for this case in 2 short sentences for the citizen, then "
                "give up to 3 practical next steps for the citizen. Use only the facts given. final_outcome is authoritative: "
                "never suggest a step that is already done. English and BM.",
                f"Case {ctx.case_id}, departments in order: {ctx.handoff_chain}. Facts: {facts}", Wrap, max_tokens=1200,
                level=ctx.scratch.get("level"))
            return ModuleResult(status="ok", data={**out.model_dump(), "llm": meta.model_dump()})
        return ModuleResult(status="ok", data={
            "summary_en": f"Handled by {' then '.join(ctx.handoff_chain)}.",
            "summary_bm": f"Dikendalikan oleh {' kemudian '.join(ctx.handoff_chain)}.",
            "next_steps": [{"en": "Track progress in My Cases.", "bm": "Jejak kemajuan di Kes Saya."}],
            "llm": {"model": "offline-template", "effort": "-"}})
