"""Legal & Policy RAG agent: local retrieval over the official corpus, no LLM calls, no token cost.

build_index()  reads corpus/manifest.json, extracts text per PDF page (or per web page), chunks it,
               and writes corpus/index.jsonl. Run: python -m app.services.rag  (from backend/)
search(q)      BM25 over the chunks, optionally filtered by department. Every hit carries its
               citation: document title, page, official URL, as-at date and the file's SHA-256.

Citations can only come from here, so the agents cannot cite a document that is not in the corpus.
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[3] / "corpus"
INDEX = CORPUS / "index.jsonl"
CHUNK_WORDS = 220
OVERLAP = 40

_STOP = set("""the of and to a in for is on that by with as or be are this from at an it any
yang dan di ke dari untuk dalam pada ini itu atau dengan oleh adalah bagi tidak boleh hendaklah mana""".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1]


def _pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix == ".html":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            t.decompose()
        return [(1, soup.get_text(" ", strip=True))]
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    except Exception as exc:  # noqa: BLE001
        print(f"  ! cannot read {path.name}: {exc}", file=sys.stderr)
        return []
    if sum(len(t.split()) for _, t in pages) < 15 * max(1, len(pages)) // 2:
        pages = _ocr(path)  # scanned PDF with no text layer (most gazetted by-laws)
    return pages


def _ocr(path: Path) -> list[tuple[int, str]]:
    """Local OCR (RapidOCR, no API cost), cached per file in corpus/ocr/."""
    cache = CORPUS / "ocr" / (path.stem + ".json")
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text("utf-8"))]
    import numpy as np
    import pypdfium2 as pdfium
    from rapidocr_onnxruntime import RapidOCR

    engine = _ocr_engine()
    pdf = pdfium.PdfDocument(str(path))
    out = []
    for i in range(len(pdf)):
        res, _ = engine(np.array(pdf[i].render(scale=2).to_pil()))
        out.append((i + 1, " ".join(r[1] for r in res or [])))
    print(f"  ocr {path.name}: {len(out)} pages", file=sys.stderr)
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    return out


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def build_index() -> dict:
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    n_chunks, empty = 0, []
    with open(INDEX, "w", encoding="utf-8") as out:
        for doc in manifest:
            path = CORPUS / doc["file"]
            doc_chunks = 0
            for page, text in _pages(path):
                words = re.sub(r"\s+", " ", text).strip().split(" ")
                if len(words) < 15:
                    continue
                for start in range(0, len(words), CHUNK_WORDS - OVERLAP):
                    chunk = " ".join(words[start:start + CHUNK_WORDS])
                    out.write(json.dumps({
                        "chunk_id": f"{doc['doc_id']}:p{page}:{start}", "doc_id": doc["doc_id"], "page": page,
                        "dept": doc["dept"], "kind": doc["kind"], "lang": doc["lang"],
                        "title_en": doc["title_en"], "title_bm": doc["title_bm"], "agency": doc["agency"],
                        "url": doc["url"], "as_at": doc.get("as_at", ""), "sha256": doc.get("sha256", ""),
                        "text": chunk,
                    }, ensure_ascii=False) + "\n")
                    doc_chunks += 1
                    if start + CHUNK_WORDS >= len(words):
                        break
            n_chunks += doc_chunks
            if not doc_chunks:
                empty.append(doc["doc_id"])  # scanned PDF without a text layer, or JS-only page
    _load.cache_clear()
    return {"documents": len(manifest), "chunks": n_chunks, "no_text": empty}


def invalidate() -> None:
    """Called by the Memory Bag after an add / update / delete, so the next search sees the new state."""
    _load.cache_clear()


@lru_cache(maxsize=1)
def _load():
    from rank_bm25 import BM25Plus

    from . import memory_bag

    chunks = memory_bag.load_chunks()  # remembered scan state; no re-reading of documents
    if not chunks and INDEX.exists():
        chunks = [json.loads(line) for line in open(INDEX, encoding="utf-8")]
    bm25 = BM25Plus([_tokens(c["title_en"] + " " + c["title_bm"] + " " + c["text"]) for c in chunks]) if chunks else None
    # Tag postings: tag -> positions of the passages filed under it.
    postings: dict[str, set[int]] = {}
    ctags = memory_bag.chunk_tag_map() if memory_bag.DB.exists() else {}
    for i, c in enumerate(chunks):
        c["tags"] = ctags.get(c["chunk_id"], [])
        for t in c["tags"]:
            postings.setdefault(t, set()).add(i)
    return chunks, bm25, postings


def search(query: str, *, dept: str | None = None, kinds: set[str] | None = None, k: int = 5,
           tags: set[str] | None = None, explain: bool = False):
    """Tag-first lookup: narrow to passages filed under the query's tags, rank only those with BM25.
    Falls back to the whole bag when the tags find too little. explain=True also returns how it narrowed."""
    from . import tagger

    chunks, bm25, postings = _load()
    info = {"tags": [], "candidates": len(chunks), "total": len(chunks), "narrowed": False}
    if not bm25:
        return ([], info) if explain else []
    qtags = set(tags) if tags is not None else tagger.query_tags(query)
    cand = set().union(*(postings.get(t, set()) for t in qtags)) if qtags else set()
    if dept and cand:
        cand = {i for i in cand if chunks[i]["dept"] == dept}
    tokens = _tokens(query)
    if len(cand) >= k:
        idx = sorted(cand)
        scores = dict(zip(idx, bm25.get_batch_scores(tokens, idx)))
        info.update(tags=sorted(qtags), candidates=len(idx), narrowed=True)
    else:
        all_scores = bm25.get_scores(tokens)
        scores = dict(enumerate(all_scores))
        info.update(tags=sorted(qtags))
    hits, seen = [], set()
    for i in sorted(scores, key=lambda j: -scores[j]):
        c = chunks[i]
        if scores[i] <= 0:
            break
        if dept and c["dept"] != dept:
            continue
        if kinds and c["kind"] not in kinds:
            continue
        key = (c["doc_id"], c["page"])
        if key in seen:
            continue
        seen.add(key)
        hits.append({**c, "score": round(float(scores[i]), 2)})
        if len(hits) == k:
            break
    return (hits, info) if explain else hits


def cite(hit: dict, lang: str = "en") -> str:
    title = hit["title_bm"] if lang == "bm" else hit["title_en"]
    return f"{title}, page {hit['page']}" if lang == "en" else f"{title}, muka surat {hit['page']}"


if __name__ == "__main__":
    print(build_index())
