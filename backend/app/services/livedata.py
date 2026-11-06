"""Live public data from data.gov.my (no key needed), cached so the map never hammers the source.

- JPS flood-warning stations: water level, alert/warning/danger thresholds, trend, rainfall.
- MET Malaysia weather warnings (thunderstorms, strong winds, etc.).
If the source is unreachable, the last good copy is returned with stale=True; nothing is invented.
"""
from __future__ import annotations

import time

import httpx

BASE = "https://api.data.gov.my"
TTL = 600  # seconds
_cache: dict[str, tuple[float, list]] = {}


def _get(path: str, params: dict) -> tuple[list, bool, float]:
    key = path + str(sorted(params.items()))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1], False, hit[0]
    try:
        r = httpx.get(f"{BASE}{path}", params=params, timeout=20, follow_redirects=True)
        r.raise_for_status()
        rows = r.json()
        _cache[key] = (time.time(), rows)
        return rows, False, time.time()
    except Exception:  # noqa: BLE001
        if hit:
            return hit[1], True, hit[0]
        return [], True, 0.0


def flood_stations(state: str | None = None) -> dict:
    params = {"limit": 2000}
    if state:
        params["contains"] = f"{state.upper()}@state"
    rows, stale, ts = _get("/flood-warning/", params)
    out = []
    for r in rows:
        if r.get("latitude") is None or r.get("longitude") is None:
            continue
        out.append({
            "id": r.get("station_id"), "name": r.get("station_name"), "lat": r["latitude"], "lng": r["longitude"],
            "district": r.get("district"), "state": r.get("state"), "basin": r.get("main_basin"),
            "level": r.get("water_level_current"), "indicator": (r.get("water_level_indicator") or "NORMAL").upper(),
            "normal": r.get("water_level_normal_level"), "alert": r.get("water_level_alert_level"),
            "warning": r.get("water_level_warning_level"), "danger": r.get("water_level_danger_level"),
            "trend": r.get("water_level_trend"), "updated": r.get("water_level_update_datetime"),
            "rain_today": r.get("rainfall_total_today"),
        })
    return {"source": "JPS via data.gov.my", "stale": stale, "fetched_at": ts, "stations": out}


def weather_warnings() -> dict:
    rows, stale, ts = _get("/weather/warning/", {"limit": 10})
    out = [{"title_en": (w.get("warning_issue") or {}).get("title_en"), "title_bm": (w.get("warning_issue") or {}).get("title_bm"),
            "issued": (w.get("warning_issue") or {}).get("issued"), "valid_from": w.get("valid_from"), "valid_to": w.get("valid_to"),
            "text_en": (w.get("text_en") or "")[:600], "text_bm": (w.get("text_bm") or "")[:600]} for w in rows]
    return {"source": "MET Malaysia via data.gov.my", "stale": stale, "fetched_at": ts, "warnings": out}
