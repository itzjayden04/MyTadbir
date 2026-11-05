"""Download the public legal corpus and record provenance.

Inputs (hand-curated, committed):
  agc_acts.tsv       federal Acts from the Attorney General's Chambers portal (lom.agc.gov.my)
  sources.tsv        other official documents: by-laws, forms, circulars, notices (direct URLs)

Output:
  raw/<dept>/<doc_id>.<ext>   the files (git-ignored; re-run this script to rebuild)
  manifest.json               one entry per file: source URL, title, agency, dates, sha256

Every citation the Policy RAG agent makes points at a manifest entry, so it can be traced
back to the exact official URL and the date we downloaded it.

Usage:  python corpus/fetch.py [--only DOC_ID ...] [--force]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
AGC_BASE = "https://lom.agc.gov.my/ilims"
UA = "Mozilla/5.0 (MyTadbir corpus builder; FOI 2026 student project)"


def load_entries() -> list[dict]:
    entries: list[dict] = []
    with open(HERE / "agc_acts.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            for lang, key in (("en", "path_en"), ("bm", "path_bm")):
                if not r[key]:
                    continue
                entries.append({
                    "doc_id": f"act{r['act']}_{lang}",
                    "kind": "act",
                    "dept": r["dept"],
                    "tier": int(r["tier"]),
                    "agency": "Attorney General's Chambers (Laws of Malaysia)",
                    "title_en": f"{r['title_en']} (Act {r['act']})",
                    "title_bm": f"{r['title_bm']} (Akta {r['act']})",
                    "lang": lang,
                    "as_at": r["as_at"],
                    "url": AGC_BASE + urllib.parse.quote(r[key]),
                })
    src = HERE / "sources.tsv"
    if src.exists():
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if not r.get("doc_id") or r["doc_id"].startswith("#"):
                    continue
                r["tier"] = int(r["tier"])
                entries.append(r)
    return entries


def download(url: str, dest: Path) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data), ctype


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    manifest_path = HERE / "manifest.json"
    old = {e["doc_id"]: e for e in json.loads(manifest_path.read_text("utf-8"))} if manifest_path.exists() else {}
    out, failed = [], []
    for e in load_entries():
        if args.only and e["doc_id"] not in args.only:
            if e["doc_id"] in old:
                out.append(old[e["doc_id"]])
            continue
        ext = ".html" if e.get("kind") == "webpage" else (Path(urllib.parse.urlparse(e["url"]).path).suffix.lower() or ".pdf")
        dest = RAW / e["dept"] / f"{e['doc_id']}{ext}"
        if dest.exists() and not args.force and e["doc_id"] in old:
            out.append(old[e["doc_id"]])
            continue
        try:
            size, ctype = download(e["url"], dest)
        except Exception as exc:  # noqa: BLE001
            failed.append((e["doc_id"], str(exc)))
            print(f"FAIL {e['doc_id']}: {exc}", file=sys.stderr)
            continue
        if "html" in ctype.lower() and e.get("kind") != "webpage":
            failed.append((e["doc_id"], f"got HTML, not a document ({ctype})"))
            dest.unlink(missing_ok=True)
            continue
        e.update({
            "file": str(dest.relative_to(HERE)).replace("\\", "/"),
            "bytes": size,
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        out.append(e)
        print(f"ok   {e['doc_id']:<28} {size/1024:8.0f} KB")
        time.sleep(1)  # be polite to government servers

    out.sort(key=lambda x: (x["dept"], x["tier"], x["doc_id"]))
    manifest_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print(f"\n{len(out)} documents in manifest, {len(failed)} failed")
    for d, why in failed:
        print(f"  - {d}: {why}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
