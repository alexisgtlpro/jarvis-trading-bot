"""
Calendrier économique - annonces à fort impact sur l'or (XAUUSD).

L'or réagit surtout aux données USD (Fed, inflation, emploi) et au risque
géopolitique. On filtre les événements USD à impact "High", plus les
décisions de taux et les discours de la Fed.

Source : flux hebdomadaire public de Forex Factory (gratuit, sans clé API).
"""
from __future__ import annotations
import time
import datetime as dt
import requests

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Devises/événements qui bougent l'or en priorité
RELEVANT_CURRENCIES = {"USD"}
# Mots-clés à toujours garder même hors USD "High"
ALWAYS_KEEP = ("FOMC", "Fed", "Interest Rate", "CPI", "Non-Farm", "NFP",
               "Powell", "PCE", "Unemployment", "GDP")

_cache: dict = {"ts": 0, "data": []}
_CACHE_TTL = 1800  # 30 min


def _fetch() -> list[dict]:
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL and _cache["data"]:
        return _cache["data"]
    try:
        r = requests.get(FF_URL, timeout=15,
                         headers={"User-Agent": "jarvis-trading/1.0"})
        r.raise_for_status()
        data = r.json()
        _cache["ts"] = now
        _cache["data"] = data
        return data
    except Exception as e:  # réseau HS, flux indispo : on ne casse pas le bot
        print(f"[calendar] fetch échoué: {e}")
        return _cache["data"]


def _parse_dt(item: dt.datetime | str) -> dt.datetime | None:
    raw = item.get("date") if isinstance(item, dict) else item
    if not raw:
        return None
    try:
        # format ISO type "2026-07-02T12:30:00-04:00"
        return dt.datetime.fromisoformat(raw)
    except Exception:
        return None


def _is_relevant(ev: dict) -> bool:
    impact = (ev.get("impact") or "").lower()
    cur = (ev.get("country") or ev.get("currency") or "").upper()
    title = ev.get("title") or ev.get("event") or ""
    if cur in RELEVANT_CURRENCIES and impact == "high":
        return True
    return any(k.lower() in title.lower() for k in ALWAYS_KEEP)


def upcoming(within_minutes: int = 60) -> list[dict]:
    """Événements pertinents qui tombent dans les `within_minutes` à venir."""
    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(minutes=within_minutes)
    out = []
    for ev in _fetch():
        if not _is_relevant(ev):
            continue
        when = _parse_dt(ev)
        if when is None:
            continue
        when_utc = when.astimezone(dt.timezone.utc)
        if now <= when_utc <= horizon:
            out.append({
                "title": ev.get("title") or ev.get("event"),
                "currency": ev.get("country") or ev.get("currency"),
                "impact": ev.get("impact"),
                "when": when_utc,
                "forecast": ev.get("forecast", ""),
                "previous": ev.get("previous", ""),
            })
    return sorted(out, key=lambda x: x["when"])


def today_agenda() -> list[dict]:
    """Tous les événements pertinents du jour (pour un résumé matinal)."""
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for ev in _fetch():
        if not _is_relevant(ev):
            continue
        when = _parse_dt(ev)
        if when is None:
            continue
        when_utc = when.astimezone(dt.timezone.utc)
        if when_utc.date() == now.date():
            out.append({
                "title": ev.get("title") or ev.get("event"),
                "currency": ev.get("country") or ev.get("currency"),
                "impact": ev.get("impact"),
                "when": when_utc,
                "forecast": ev.get("forecast", ""),
                "previous": ev.get("previous", ""),
            })
    return sorted(out, key=lambda x: x["when"])
