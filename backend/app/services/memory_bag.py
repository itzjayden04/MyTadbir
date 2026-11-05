"""Memory Bag: the policy agent's persistent scan state.

The corpus is scanned once and remembered in corpus/memory_bag.db, so the AI never re-reads every
document on each request. A re-scan runs at most once every RESCAN_DAYS (default 30). It only changes
what changed, through three operations recorded in a change log:

    add      a new source appears            -> download, extract, store its chunks
    update   a source's file hash changed    -> delete its old chunks, add the new ones
    delete   a source was removed / retired  -> delete its chunks, mark the document deleted

Unchanged documents are only "touched" (last_checked updated). Failed checks keep the previous state.

CLI (from backend/):
    python -m app.services.memory_bag status
    python -m app.services.memory_bag sync            # only if a re-scan is due
    python -m app.services.memory_bag sync --force    # re-check every source now
    python -m app.services.memory_bag import          # first run: load the existing scan, no network
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import rag, tagger

CORPUS = rag.CORPUS
DB = CORPUS / "memory_bag.db"
RESCAN_DAYS = 30
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
  doc_id TEXT PRIMARY KEY, url TEXT, title_en TEXT, title_bm TEXT, dept TEXT, kind TEXT, lang TEXT,
  agency TEXT, as_at TEXT, access TEXT DEFAULT 'public', tier INTEGER, sha256 TEXT, bytes INTEGER,
  file TEXT, n_chunks INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
  first_seen TEXT, last_checked TEXT, last_changed TEXT);
CREATE TABLE IF NOT EXISTS chunks(chunk_id TEXT PRIMARY KEY, doc_id TEXT, page INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, doc_id TEXT, op TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tags(tag TEXT, doc_id TEXT, chunk_id TEXT);
CREATE INDEX IF NOT EXISTS tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS tags_doc ON tags(doc_id);
"""
DOC_FIELDS = ["url", "title_en", "title_bm", "dept", "kind", "lang", "agency", "as_at", "tier"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _fetch_module():
    spec = importlib.util.spec_from_file_location("corpus_fetch", CORPUS / "fetch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chunks(doc_id: str, path: Path) -> list[tuple[str, int, str]]:
    out = []
    for page, text in rag._pages(path):
        words = re.sub(r"\s+", " ", text).strip().split(" ")
        if len(words) < 15:
            continue
        for start in range(0, len(words), rag.CHUNK_WORDS - rag.OVERLAP):
            out.append((f"{doc_id}:p{page}:{start}", page, " ".join(words[start:start + rag.CHUNK_WORDS])))
            if start + rag.CHUNK_WORDS >= len(words):
                break
    return out


def _log(con, doc_id: str, op: str, detail: str = "") -> None:
    con.execute("INSERT INTO events(ts, doc_id, op, detail) VALUES (?,?,?,?)", (_now(), doc_id, op, detail))


# ---------------------------------------------------------------- the three state operations
def _tag(con, entry: dict, rows) -> None:
    """File the document and each passage under its tags (rules only, no API calls)."""
    con.execute("DELETE FROM tags WHERE doc_id=?", (entry["doc_id"],))
    dtags = tagger.doc_tags(entry)
    con.executemany("INSERT INTO tags VALUES (?,?,NULL)", [(t, entry["doc_id"]) for t in dtags])
    base = {t for t in dtags if t.split(":")[0] in {"topic", "act"}}
    con.executemany("INSERT INTO tags VALUES (?,?,?)", [
        (t, entry["doc_id"], cid) for cid, _, text in rows
        for t in (tagger.tag_text(text, strict=True) | base) if t.split(":")[0] in {"topic", "act", "place"}])


def add(con, entry: dict, path: Path, sha: str, size: int) -> int:
    rows = _chunks(entry["doc_id"], path)
    con.executemany("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?)", [(cid, entry["doc_id"], p, t) for cid, p, t in rows])
    _tag(con, entry, rows)
    now = _now()
    con.execute(
        f"INSERT OR REPLACE INTO docs(doc_id, {', '.join(DOC_FIELDS)}, access, sha256, bytes, file, n_chunks, status, first_seen, last_checked, last_changed)"
        f" VALUES (?, {', '.join('?' * len(DOC_FIELDS))}, ?, ?, ?, ?, ?, 'active', COALESCE((SELECT first_seen FROM docs WHERE doc_id=?), ?), ?, ?)",
        [entry["doc_id"], *[entry.get(f) for f in DOC_FIELDS], entry.get("access", "public"), sha, size,
         str(path.relative_to(CORPUS)).replace("\\", "/"), len(rows), entry["doc_id"], now, now, now])
    return len(rows)


def delete(con, doc_id: str, reason: str) -> None:
    con.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    con.execute("DELETE FROM tags WHERE doc_id=?", (doc_id,))
    con.execute("UPDATE docs SET status='deleted', n_chunks=0, last_changed=? WHERE doc_id=?", (_now(), doc_id))
    _log(con, doc_id, "delete", reason)


def update(con, entry: dict, path: Path, sha: str, size: int, old_sha: str) -> int:
    con.execute("DELETE FROM chunks WHERE doc_id=?", (entry["doc_id"],))
    n = add(con, entry, path, sha, size)
    _log(con, entry["doc_id"], "update", f"hash {old_sha[:10]} -> {sha[:10]}, {n} chunks")
    return n


# ---------------------------------------------------------------- import / sync
def import_existing() -> dict:
    """First run: load the scan already on disk (manifest + raw files + OCR cache). No network."""
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    with _lock, _db() as con:
        n = 0
        for e in manifest:
            path = CORPUS / e["file"]
            if not path.exists() or con.execute("SELECT 1 FROM docs WHERE doc_id=? AND status='active'", (e["doc_id"],)).fetchone():
                continue
            chunks = add(con, e, path, e.get("sha256", ""), e.get("bytes", 0))
            con.execute("UPDATE docs SET last_checked=? WHERE doc_id=?", (e.get("retrieved_at") or _now(), e["doc_id"]))
            _log(con, e["doc_id"], "add", f"imported from previous scan, {chunks} chunks")
            n += 1
        con.execute("INSERT OR REPLACE INTO meta VALUES ('last_full_scan', ?)",
                    (min((e.get("retrieved_at") or _now()) for e in manifest),))
    rag.invalidate()
    return {"imported": n}


def due() -> bool:
    with _db() as con:
        row = con.execute("SELECT value FROM meta WHERE key='last_full_scan'").fetchone()
    if not row:
        return True
    return datetime.fromisoformat(row["value"]) < datetime.now(timezone.utc) - timedelta(days=RESCAN_DAYS)


def sync(force: bool = False, only: set[str] | None = None) -> dict:
    """Re-check sources if a re-scan is due (or forced). Applies add / update / delete only where needed."""
    if not force and not only and not due():
        return {"skipped": "re-scan not due", "next_scan": next_scan()}
    fetch = _fetch_module()
    entries = {e["doc_id"]: e for e in fetch.load_entries()}
    stats = {"add": 0, "update": 0, "delete": 0, "unchanged": 0, "failed": 0}
    with _lock, _db() as con:
        known = {r["doc_id"]: dict(r) for r in con.execute("SELECT * FROM docs")}
        targets = only or set(entries) | {d for d, r in known.items() if r["status"] == "active"}
        for doc_id in sorted(targets):
            e, k = entries.get(doc_id), known.get(doc_id)
            if e is None:  # source retired from the lists
                if k and k["status"] == "active":
                    delete(con, doc_id, "source removed from source lists")
                    stats["delete"] += 1
                continue
            if k and k["status"] == "deleted":
                continue  # deleted by an officer: stays deleted until added again on purpose
            if e.get("access") == "login" or (k and k["access"] == "login"):
                continue  # not fetchable automatically; downloaded once by hand, updated by hand
            ext = ".html" if e.get("kind") == "webpage" else (Path(e["url"].split("?")[0]).suffix.lower() or ".pdf")
            dest = CORPUS / "raw" / e["dept"] / f"{doc_id}{ext}"
            try:
                size, ctype = fetch.download(e["url"], dest)
                if "html" in ctype.lower() and e.get("kind") != "webpage":
                    raise RuntimeError(f"got HTML instead of a document ({ctype})")
            except Exception as exc:  # noqa: BLE001
                _log(con, doc_id, "check_failed", str(exc)[:200])
                stats["failed"] += 1
                continue
            sha = hashlib.sha256(dest.read_bytes()).hexdigest()
            if k and k["status"] == "active" and k["sha256"] == sha:
                con.execute("UPDATE docs SET last_checked=? WHERE doc_id=?", (_now(), doc_id))
                stats["unchanged"] += 1
            elif k and k["status"] == "active":
                (CORPUS / "ocr" / f"{doc_id}.json").unlink(missing_ok=True)  # stale OCR
                update(con, e, dest, sha, size, k["sha256"] or "")
                stats["update"] += 1
            else:
                n = add(con, e, dest, sha, size)
                _log(con, doc_id, "add", f"{n} chunks")
                stats["add"] += 1
        if not only:
            con.execute("INSERT OR REPLACE INTO meta VALUES ('last_full_scan', ?)", (_now(),))
    rag.invalidate()
    return stats


def add_manual(meta: dict, filename: str, data: bytes) -> dict:
    """Add (or replace) a document someone downloaded by hand, e.g. from a site that needs a login.
    Stored once in the bag; later versions are updated the same way."""
    doc_id = re.sub(r"[^a-z0-9_]+", "_", (meta.get("doc_id") or Path(filename).stem).lower()).strip("_")[:60]
    ext = Path(filename).suffix.lower() or ".pdf"
    dest = CORPUS / "raw" / meta.get("dept", "cross_agency") / f"{doc_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    entry = {"doc_id": doc_id, "url": meta.get("url", ""), "title_en": meta.get("title_en") or doc_id,
             "title_bm": meta.get("title_bm") or meta.get("title_en") or doc_id, "dept": meta.get("dept", "cross_agency"),
             "kind": meta.get("kind", "document"), "lang": meta.get("lang", "bm"), "agency": meta.get("agency", ""),
             "as_at": meta.get("as_at", ""), "tier": 2, "access": "login"}
    with _lock, _db() as con:
        k = con.execute("SELECT sha256, status FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
        if k and k["status"] == "active":
            if k["sha256"] == sha:
                return {"doc_id": doc_id, "op": "unchanged"}
            (CORPUS / "ocr" / f"{doc_id}.json").unlink(missing_ok=True)
            n = update(con, entry, dest, sha, len(data), k["sha256"] or "")
            op = "update"
        else:
            (CORPUS / "ocr" / f"{doc_id}.json").unlink(missing_ok=True)
            n = add(con, entry, dest, sha, len(data))
            _log(con, doc_id, "add", f"manual upload, {n} chunks")
            op = "add"
    rag.invalidate()
    return {"doc_id": doc_id, "op": op, "chunks": n}


def delete_doc(doc_id: str, reason: str = "deleted by officer") -> dict:
    with _lock, _db() as con:
        delete(con, doc_id, reason)
    rag.invalidate()
    return {"doc_id": doc_id, "op": "delete"}


def restore_doc(doc_id: str) -> dict:
    """Undo a delete: re-index from the stored file without downloading."""
    with _lock, _db() as con:
        k = con.execute("SELECT * FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
        if not k:
            raise KeyError(doc_id)
        path = CORPUS / k["file"]
        n = add(con, dict(k), path, k["sha256"], k["bytes"])
        _log(con, doc_id, "add", f"restored, {n} chunks")
    rag.invalidate()
    return {"doc_id": doc_id, "op": "add", "chunks": n}


def next_scan() -> str | None:
    with _db() as con:
        row = con.execute("SELECT value FROM meta WHERE key='last_full_scan'").fetchone()
    return (datetime.fromisoformat(row["value"]) + timedelta(days=RESCAN_DAYS)).isoformat() if row else None


def status() -> dict:
    with _db() as con:
        c = {r["status"]: r["n"] for r in con.execute("SELECT status, COUNT(*) n FROM docs GROUP BY status")}
        chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        last = con.execute("SELECT value FROM meta WHERE key='last_full_scan'").fetchone()
        events = [dict(r) for r in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50")]
    return {"active_documents": c.get("active", 0), "deleted_documents": c.get("deleted", 0), "chunks": chunks,
            "last_full_scan": last["value"] if last else None, "next_scan": next_scan(), "rescan_days": RESCAN_DAYS,
            "recent_changes": events}


def documents() -> list[dict]:
    tags = doc_tag_map()
    with _db() as con:
        return [{**dict(r), "tags": sorted(tags.get(r["doc_id"], []))} for r in con.execute("SELECT * FROM docs ORDER BY dept, tier, doc_id")]


def retag_all() -> dict:
    """(Re)tag every stored passage from the text already in the bag. No downloads, no API calls."""
    with _lock, _db() as con:
        docs = [dict(r) for r in con.execute("SELECT * FROM docs WHERE status='active'")]
        for d in docs:
            rows = [(r["chunk_id"], r["page"], r["text"]) for r in con.execute("SELECT * FROM chunks WHERE doc_id=?", (d["doc_id"],))]
            _tag(con, d, rows)
        n = con.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    rag.invalidate()
    return {"documents": len(docs), "tag_links": n}


def tag_counts(prefix: str | None = None, limit: int = 60) -> list[dict]:
    with _db() as con:
        q = "SELECT tag, COUNT(DISTINCT doc_id) docs, COUNT(chunk_id) passages FROM tags"
        args: list = []
        if prefix:
            q += " WHERE tag LIKE ?"
            args.append(prefix + ":%")
        q += " GROUP BY tag ORDER BY docs DESC, passages DESC LIMIT ?"
        return [dict(r) for r in con.execute(q, [*args, limit])]


def doc_tag_map() -> dict[str, list[str]]:
    with _db() as con:
        out: dict[str, list[str]] = {}
        for r in con.execute("SELECT doc_id, tag FROM tags WHERE chunk_id IS NULL"):
            out.setdefault(r["doc_id"], []).append(r["tag"])
        return out


def chunk_tag_map() -> dict[str, list[str]]:
    with _db() as con:
        out: dict[str, list[str]] = {}
        for r in con.execute("SELECT chunk_id, tag FROM tags WHERE chunk_id IS NOT NULL"):
            out.setdefault(r["chunk_id"], []).append(r["tag"])
        return out


def load_chunks() -> list[dict]:
    """Active chunks joined with their document's citation fields (used by rag.search)."""
    if not DB.exists():
        return []
    with _db() as con:
        rows = con.execute(
            "SELECT c.chunk_id, c.doc_id, c.page, c.text, d.dept, d.kind, d.lang, d.title_en, d.title_bm, d.agency,"
            " d.url, d.as_at, d.sha256 FROM chunks c JOIN docs d ON d.doc_id = c.doc_id WHERE d.status='active'")
        return [dict(r) for r in rows]


def start_scheduler() -> None:
    """On startup: import the previous scan if the bag is empty, then check once a day whether a monthly
    re-scan is due. Runs in a background thread so requests are never blocked."""
    def loop():
        import time

        try:
            with _db() as con:
                empty = con.execute("SELECT COUNT(*) FROM docs").fetchone()[0] == 0
            if empty and (CORPUS / "manifest.json").exists():
                print("memory bag:", import_existing(), file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print("memory bag import failed:", exc, file=sys.stderr)
        while True:
            try:
                if due():
                    print("memory bag monthly re-scan:", sync(), file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print("memory bag re-scan failed:", exc, file=sys.stderr)
            time.sleep(24 * 3600)

    threading.Thread(target=loop, name="memory-bag", daemon=True).start()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "import":
        print(import_existing())
    elif cmd == "retag":
        print(retag_all())
    elif cmd == "sync":
        print(sync(force="--force" in sys.argv))
    else:
        s = status()
        s["recent_changes"] = s["recent_changes"][:10]
        print(json.dumps(s, indent=2, ensure_ascii=False))
