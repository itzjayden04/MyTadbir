"""DeepSeek client. The model and effort for each call come from the case's complexity level (1-5):
see services/complexity.py for the full task x level table. In short, levels 1-3 stay on
deepseek-flash, level 4 uses deepseek-v4-pro (low effort) for legal reasoning, and level 5 uses
deepseek-v4-pro (high effort). Level 1 skips the legal-reasoning model call altogether.

Measured on the drain case: v4-pro/high 88 s and 5.3k tokens; v4-pro/low 44 s and 2.5k tokens;
flash/low 21 s.

Every call reports the model, effort and token usage to the live trace, so the demo shows exactly
which model ran each step.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

TASKS: dict[str, tuple[str, str]] = {
    "route": ("deepseek-flash", "low"),
    "inspect_image": ("deepseek-flash", "low"),
    "summarise": ("deepseek-flash", "low"),
    "notify": ("deepseek-flash", "low"),
    "legal_reasoning": (os.environ.get("MYTADBIR_LEGAL_MODEL", "deepseek-v4-pro"), "low"),
}


def _load_env() -> None:
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text("utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY")) and os.environ.get("MYTADBIR_OFFLINE") != "1"


def image_part(path: str) -> dict | None:
    p = Path(path)
    mt = mimetypes.guess_type(p.name)[0]
    if not p.exists() or mt not in {"image/jpeg", "image/png", "image/webp"}:
        return None
    return {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{base64.b64encode(p.read_bytes()).decode()}"}}


class LLMResult(BaseModel):
    model: str
    effort: str
    level: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0


def plan(task: str, level: int | None) -> tuple[str, str] | None:
    from .services.complexity import model_for

    return model_for(task, level)


def chat_json(task: str, system: str, user: str | list, schema: type[T], *, max_tokens: int = 2000,
              level: int | None = None) -> tuple[T, LLMResult]:
    """One JSON-mode call at the model/effort set by the case level. Raises on transport errors or
    if the output never validates."""
    model, effort = plan(task, level) or TASKS[task]
    schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    messages = [
        {"role": "system", "content": f"{system}\n\nReply with one JSON object only, matching this JSON schema:\n{schema_hint}"},
        {"role": "user", "content": user},
    ]
    url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"}
    last_err: Exception | None = None
    for attempt in range(2):
        body = {"model": model, "messages": messages, "reasoning_effort": effort,
                "response_format": {"type": "json_object"}, "max_tokens": max_tokens}
        r = httpx.post(url, headers=headers, json=body, timeout=90)
        r.raise_for_status()
        d = r.json()
        u = d.get("usage", {})
        meta = LLMResult(model=d.get("model", model), effort=effort, level=level, prompt_tokens=u.get("prompt_tokens", 0),
                         completion_tokens=u.get("completion_tokens", 0),
                         reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0))
        content = (d["choices"][0]["message"].get("content") or "").strip()
        try:
            return schema.model_validate_json(content), meta
        except ValidationError as exc:
            last_err = exc
            log.warning("%s: invalid JSON from %s (attempt %d)", task, model, attempt + 1)
            messages += [{"role": "assistant", "content": content},
                         {"role": "user", "content": f"That did not match the schema: {exc.errors()[:3]}. Reply again with valid JSON only."}]
    raise RuntimeError(f"{task}: model output never matched schema") from last_err
