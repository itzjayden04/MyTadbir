"""Tags: labels on every passage, document, case and upload, like a filing clerk's index.

Tags are computed once, with rules only (no API calls), and stored. A lookup first narrows to the
passages that share the query's tags, then ranks only those, so the agent does not search or send
unrelated content. Tag kinds (prefix:value):

    dept:local_gov        owning department
    topic:incident_dispatcher   a service / sub-module the text is about (from the router lexicon)
    act:133               an Act number mentioned
    place:petaling_jaya   a Malaysian place mentioned
    kind:bylaw            document type
    year:2024             a year mentioned in the title or as-at date
"""
from __future__ import annotations

import re

from ..router.lexicon import LEXICON

PLACES = {
    "petaling jaya": "petaling_jaya", "petaling": "petaling_jaya", "pj": "petaling_jaya", "damansara": "petaling_jaya",
    "kuala lumpur": "kuala_lumpur", "dbkl": "kuala_lumpur", "shah alam": "shah_alam", "subang": "subang_jaya",
    "klang": "klang", "putrajaya": "putrajaya", "cyberjaya": "cyberjaya", "selangor": "selangor", "johor": "johor",
    "penang": "pulau_pinang", "pulau pinang": "pulau_pinang", "perak": "perak", "kedah": "kedah", "kelantan": "kelantan",
    "terengganu": "terengganu", "pahang": "pahang", "melaka": "melaka", "negeri sembilan": "negeri_sembilan",
    "sabah": "sabah", "sarawak": "sarawak", "perlis": "perlis", "langkawi": "langkawi",
}
_ACT = re.compile(r"\b(?:act|akta)\s*(\d{1,3})\b", re.I)
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
# Extra topic words that are common in legal text but absent from the citizen-facing lexicon.
LEGAL_TOPICS = {
    "incident_dispatcher": ["saliran", "drainage", "parit", "longkang"],
    "licence_precheck": ["pelesenan", "licensing", "lesen tred", "establisymen makanan", "food establishment", "premis"],
    "hawker_licence": ["penjaja", "hawker"],
    "waste_scheduler": ["sampah sarap", "refuse", "pepejal", "solid waste"],
    "renovation_permit": ["kerja tanah", "earthworks", "permit bangunan", "building plan", "pelan bangunan"],
    "summons_payment": ["kompaun", "compound", "saman"],
    "licence_renewal": ["lesen memandu", "driving licence"],
    "tax_filing": ["cukai pendapatan", "income tax", "borang be"],
    "child_protection": ["kanak-kanak", "child"],
    "domestic_violence": ["keganasan rumah tangga", "domestic violence"],
    "flood_landslide": ["banjir", "flood", "paras air"],
    "pollution_complaint": ["kualiti alam", "environmental quality", "pencemaran"],
}


_PAT: dict[tuple[str, bool], re.Pattern] = {}


def _pattern(sub: str, strict: bool) -> re.Pattern | None:
    """Whole-word matcher per topic. Strict (used for legal passages) skips one-word everyday phrases
    like "appointment" that appear in almost every Act, keeping only distinctive phrases."""
    key = (sub, strict)
    if key not in _PAT:
        phrases = [p for p in LEXICON[sub][1] if not strict or len(p.split()) > 1] + LEGAL_TOPICS.get(sub, [])
        _PAT[key] = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(p) for p in phrases) + r")(?![a-z])") if phrases else None
    return _PAT[key]


def tag_text(text: str, *, dept: str | None = None, kind: str | None = None, extra: str = "", strict: bool = False) -> set[str]:
    t = " " + re.sub(r"\s+", " ", (text + " " + extra).lower()) + " "
    tags: set[str] = set()
    if dept:
        tags.add(f"dept:{dept}")
    if kind:
        tags.add(f"kind:{kind}")
    for sub, (sub_dept, _) in LEXICON.items():
        pat = _pattern(sub, strict)
        if pat and pat.search(t):
            tags.add(f"topic:{sub}")
            if not dept:
                tags.add(f"dept:{sub_dept}")
    for name, slug in PLACES.items():
        if f" {name} " in t or f" {name}," in t or f" {name}." in t:
            tags.add(f"place:{slug}")
    tags.update(f"act:{m}" for m in _ACT.findall(t))
    return tags


def doc_tags(doc: dict) -> set[str]:
    title = f"{doc.get('title_en', '')} {doc.get('title_bm', '')}"
    tags = tag_text(title, dept=doc.get("dept"), kind=doc.get("kind"), extra=doc.get("agency", ""))
    tags.update(f"year:{y}" for y in _YEAR.findall(title + " " + str(doc.get("as_at", ""))))
    return tags


def query_tags(text: str, *, dept: str | None = None, submodule: str | None = None) -> set[str]:
    """Tags used to narrow a lookup. Only topic/act/place tags narrow; dept is a separate filter."""
    tags = {x for x in tag_text(text) if x.split(":")[0] in {"topic", "act", "place"}}
    if submodule:
        tags.add(f"topic:{submodule}")
    return tags
