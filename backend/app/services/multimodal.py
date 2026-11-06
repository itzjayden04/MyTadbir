"""Multimodal Inspection Agent: photo severity (deepseek-flash vision, low effort) + GPS from EXIF."""
from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from .. import llm
from ..core.context import CaseContext
from ..core.trace import bus
from . import audit


class Inspection(BaseModel):
    subject_en: str = Field(description="What the photo shows, one sentence in English.")
    subject_bm: str = Field(description="Same sentence in Bahasa Malaysia.")
    severity: str = Field(description="low | medium | high | critical")
    hazards: list[str] = Field(default_factory=list, description="Visible hazards, short phrases.")
    blockage_pct: int | None = Field(default=None, description="For drains: estimated % blocked, else null.")
    standing_water: bool = False
    near_school_or_public_area: bool = Field(default=False, description="True only if visible in the photo or stated in the text.")
    confidence: float = Field(ge=0, le=1)


SYSTEM = """You are the Multimodal Inspection Agent of a Malaysian municipal council. Look at the citizen's
photo and their message and describe only what is visible or stated. Do not invent details. Rate severity
for public safety: critical = immediate danger to people, high = likely flooding/injury within hours,
medium = needs repair within days, low = cosmetic."""


def exif_gps(path: str) -> dict | None:
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS

        exif = Image.open(path).getexif()
        gps = {GPSTAGS.get(k, k): v for k, v in exif.get_ifd(0x8825).items()}
        if not gps:
            return None

        def dec(v, ref):
            d, m, s = (float(x) for x in v)
            out = d + m / 60 + s / 3600
            return -out if ref in ("S", "W") else out

        return {"lat": round(dec(gps["GPSLatitude"], gps["GPSLatitudeRef"]), 6),
                "lng": round(dec(gps["GPSLongitude"], gps["GPSLongitudeRef"]), 6), "source": "photo EXIF"}
    except Exception:  # noqa: BLE001
        return None


async def inspect(ctx: CaseContext, path: str, text: str) -> tuple[Inspection, dict | None]:
    gps = exif_gps(path)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "multimodal_agent", "gps",
                   gps or {"note": "no GPS in photo; will ask citizen to confirm location"})
    if llm.available() and Path(path).exists():
        part = llm.image_part(path)
        result, meta = await asyncio.to_thread(lambda: llm.chat_json(
            "inspect_image", SYSTEM, [part, {"type": "text", "text": f"Citizen message: {text}"}] if part else text,
            Inspection, max_tokens=1500, level=ctx.scratch.get("level")))
        llm_meta = meta.model_dump()
    else:
        # Offline estimate so the demo still runs without an API key; clearly labelled.
        t = text.lower()
        sev = "high" if any(w in t for w in ("naik", "banjir", "flood", "sekolah", "school")) else "medium"
        result = Inspection(subject_en="Blocked roadside drain (offline estimate from text only)",
                            subject_bm="Longkang tepi jalan tersumbat (anggaran luar talian daripada teks)",
                            severity=sev, hazards=["standing water"], blockage_pct=None,
                            standing_water="naik" in t or "water" in t,
                            near_school_or_public_area="sekolah" in t or "school" in t, confidence=0.4)
        llm_meta = {"model": "offline-rules", "effort": "-"}
    payload = {**result.model_dump(), "gps": gps, "llm": llm_meta}
    audit.log("multimodal_agent", "inspected", payload, case_id=ctx.case_id, thread_id=ctx.thread_id)
    await bus.emit(ctx.thread_id, ctx.case_id, "service", "multimodal_agent", "inspected", payload)
    return result, gps
