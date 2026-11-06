"""Legal & Policy RAG Agent: retrieve clauses locally, then (optionally) reason over them.

Retrieval is local BM25 (no tokens). Reasoning uses deepseek-v4-pro at high effort and may only cite
the chunk IDs it was given; any other citation is dropped and the point is marked as an assumption.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from .. import llm
from ..core.context import CaseContext
from ..core.trace import bus
from . import audit, rag, tagger


class Finding(BaseModel):
    point_en: str
    point_bm: str
    chunk_ids: list[str] = Field(default_factory=list, description="IDs of the provided excerpts that support this point. Empty if none do.")
    is_assumption: bool = Field(description="True if no provided excerpt supports this point.")


class PolicyReasoning(BaseModel):
    findings: list[Finding]
    priority: str | None = Field(default=None, description="For incidents: P1 | P2 | P3, else null.")
    outcome: str | None = Field(default=None, description="For pre-checks: likely_compliant | gaps_found | likely_reject, else null.")


def _cite(h: dict) -> dict:
    return {"chunk_id": h["chunk_id"], "doc_id": h["doc_id"], "title_en": h["title_en"], "title_bm": h["title_bm"],
            "page": h["page"], "url": h["url"], "as_at": h["as_at"], "agency": h["agency"],
            "excerpt": h["text"][:400], "score": h["score"]}


async def retrieve(ctx: CaseContext, query: str, *, dept: str | None, k: int = 5, kinds: set[str] | None = None) -> list[dict]:
    hint = ctx.scratch.get("submodule_hint")
    tags = tagger.query_tags(query, submodule=hint if hint else None)
    hits, info = await asyncio.to_thread(rag.search, query, dept=dept, k=k, kinds=kinds, tags=tags, explain=True)
    cites = [_cite(h) for h in hits]
    audit.log("policy_rag_agent", "retrieved", {"query": query, "dept": dept, "citations": cites},
              case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "policy_rag_agent", "retrieved",
                   {"query": query, "citations": cites, "tags": info["tags"],
                    "searched": f"{info['candidates']} of {info['total']} passages" + (" (tag-filtered)" if info["narrowed"] else ""),
                    "llm": {"model": "none (tag index + local BM25)", "tokens": 0}})
    return hits


async def reason(ctx: CaseContext, question: str, facts: dict, hits: list[dict]) -> PolicyReasoning | None:
    if not llm.available() or not hits:
        return None
    if llm.plan("legal_reasoning", ctx.scratch.get("level")) is None:
        await bus.emit(ctx.thread_id, ctx.case_id, "service", "policy_rag_agent", "skipped",
                       {"reason": "level 1 case: citations only, no model call", "llm": {"model": "none", "tokens": 0}})
        return None
    excerpts = "\n\n".join(f"[{h['chunk_id']}] {h['title_en']} p.{h['page']}:\n{h['text']}" for h in hits)
    system = ("You are the Legal & Policy agent of a Malaysian government service. Apply ONLY the excerpts "
              "provided to the facts. Cite excerpt IDs exactly as given. If something you need is not in the "
              "excerpts, still state it but set is_assumption=true and leave chunk_ids empty. Never invent a "
              "section number, fee or deadline that is not in an excerpt. Write each point in English and BM.")
    user = f"Question: {question}\n\nFacts: {facts}\n\nExcerpts:\n{excerpts}"
    out, meta = await asyncio.to_thread(lambda: llm.chat_json("legal_reasoning", system, user, PolicyReasoning,
                                                               max_tokens=6000, level=ctx.scratch.get("level")))
    valid_ids = {h["chunk_id"] for h in hits}
    for f in out.findings:
        bad = [c for c in f.chunk_ids if c not in valid_ids]
        if bad:
            f.chunk_ids = [c for c in f.chunk_ids if c in valid_ids]
        if not f.chunk_ids:
            f.is_assumption = True
    payload = {**out.model_dump(), "llm": meta.model_dump()}
    audit.log("policy_rag_agent", "reasoned", payload, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "policy_rag_agent", "reasoned", payload)
    return out
