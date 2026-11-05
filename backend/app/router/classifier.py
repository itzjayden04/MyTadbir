"""Intent classifiers. The router uses Claude when an API key is set, else the keyword lexicon.

Neither classifier executes anything: they only return department / sub-module guesses.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from pathlib import Path

from ..departments.catalog import BY_KEY, DEPARTMENTS
from .lexicon import BM_MARKERS, LEXICON, SPLITTERS
from .schemas import ClassifierOutput, IntentGuess

log = logging.getLogger(__name__)

MODEL = os.environ.get("MYTADBIR_MODEL", "claude-opus-5-5")
SUB_TO_DEPT = {s.key: d.key for d in DEPARTMENTS for s in d.subs}


def detect_language(text: str) -> str:
    words = re.findall(r"[a-z]+", text.lower())
    hits = sum(1 for w in words if w in BM_MARKERS)
    return "bm" if words and hits / len(words) >= 0.12 else "en"


# ---------------------------------------------------------------- keyword classifier
class KeywordClassifier:
    name = "keyword"

    @staticmethod
    def _score(text: str) -> dict[str, float]:
        t = " " + re.sub(r"\s+", " ", text.lower()) + " "
        scores: dict[str, float] = {}
        for sub, (_, phrases) in LEXICON.items():
            s = sum(1 + 0.5 * (len(p.split()) - 1) for p in phrases if p in t)
            if s:
                scores[sub] = s
        return scores

    def _guess(self, segment: str) -> IntentGuess | None:
        scores = self._score(segment)
        if not scores:
            return None
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        sub, s1 = ranked[0]
        dept = SUB_TO_DEPT[sub]
        s2 = max((s for k, s in ranked[1:] if SUB_TO_DEPT[k] != dept), default=0.0)
        conf = min(0.95, 0.55 + 0.2 * s1)
        if s2:
            conf *= s1 / (s1 + s2)
        return IntentGuess(text=segment.strip(), department=dept, submodule=sub, confidence=round(conf, 2),
                           reason=f"keyword match ({s1:g})")

    def _segments(self, text: str) -> list[str]:
        parts = [text]
        for sp in SPLITTERS:
            nxt = []
            for p in parts:
                nxt.extend(x for x in re.split(re.escape(sp), " " + p + " ", flags=re.I) if x.strip())
            parts = nxt
        return [p.strip(" ,.") for p in parts if p.strip(" ,.")]

    def classify(self, text: str, image_paths: list[str] | None = None) -> ClassifierOutput:
        lang = detect_language(text)
        guesses: list[IntentGuess] = []
        for seg in self._segments(text):
            g = self._guess(seg)
            if g is None:
                continue
            if guesses and guesses[-1].submodule == g.submodule:
                guesses[-1].text += " " + g.text
                continue
            guesses.append(g)
        if not guesses:
            whole = self._guess(text)
            if whole:
                guesses = [whole]
        if not guesses and image_paths:
            # A photo with no usable text: most citizen photos are civic incidents.
            guesses = [IntentGuess(text=text or "(photo only)", department="local_gov",
                                   submodule="incident_dispatcher", confidence=0.5,
                                   reason="photo with no recognisable text; assumed civic incident")]
        question = None
        if not guesses:
            question = ("Boleh terangkan sedikit lagi apa yang anda perlukan? Contohnya: aduan, lesen, bayaran, atau dokumen."
                        if lang == "bm" else
                        "Could you tell me a bit more about what you need? For example: a complaint, a licence, a payment or a document.")
        return ClassifierOutput(language=lang, intents=guesses, clarifying_question=question)


# ---------------------------------------------------------------- Claude classifier
def _catalog_text() -> str:
    lines = []
    for d in DEPARTMENTS:
        lines.append(f"- {d.key} ({d.en} / {d.bm}, {d.agencies}):")
        lines.extend(f"    - {s.key}: {s.en} / {s.bm}" for s in d.subs)
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You are the Intent Router for MyTadbir, a Malaysian government digital desk officer.
You only classify. You never answer the citizen and never promise any action.

Read the citizen's message (Bahasa Malaysia, English or a mix, possibly with a photo) and list every
separate thing they are asking for. For each one, pick exactly one owning department and the single
most likely sub-module inside it, using only these keys:

{_catalog_text()}

Rules:
- Split bundled requests into separate intents (for example "renew my licence and pay my summons" is two).
- Do not split one request into several just because it touches several topics; one problem is one intent.
- Set secondary_department only when the same intent clearly needs a second department to act after the
  first one finishes (for example a blocked drain that is already flooding homes). Otherwise leave it null.
- confidence is your honest probability that the department is right. Use below 0.5 when you are guessing.
- If the message is too vague to route at all, return no intents and one short clarifying question in the
  citizen's language.
- text must quote the relevant part of the citizen's message.
"""


class ClaudeClassifier:
    name = "claude"

    def __init__(self) -> None:
        import anthropic  # imported lazily so the app runs without the SDK configured

        self.client = anthropic.Anthropic(timeout=30, max_retries=1)

    @staticmethod
    def _image_block(path: str) -> dict | None:
        p = Path(path)
        mt = mimetypes.guess_type(p.name)[0]
        if not p.exists() or mt not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            return None
        return {"type": "image", "source": {"type": "base64", "media_type": mt,
                                             "data": base64.b64encode(p.read_bytes()).decode()}}

    def classify(self, text: str, image_paths: list[str] | None = None) -> ClassifierOutput:
        content: list[dict] = [b for b in (self._image_block(p) for p in image_paths or []) if b]
        content.append({"type": "text", "text": text or "(no text, photo only)"})
        resp = self.client.beta.messages.parse(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_format=ClassifierOutput,
            output_config={"effort": "low"},
            # Server-side fallback: if a safety classifier declines, the API reroutes to a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("model declined to classify")
        out: ClassifierOutput = resp.parsed_output
        # Never trust keys blindly: drop anything not in the catalog.
        valid = []
        for g in out.intents:
            if g.department in BY_KEY and SUB_TO_DEPT.get(g.submodule) == g.department:
                if g.secondary_department not in BY_KEY or g.secondary_department == g.department:
                    g.secondary_department = None
                valid.append(g)
            else:
                log.warning("dropping invalid route %s/%s", g.department, g.submodule)
        out.intents = valid
        return out


def get_classifier():
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            return ClaudeClassifier()
        except Exception:  # noqa: BLE001
            log.exception("Claude classifier unavailable, using keyword classifier")
    return KeywordClassifier()
