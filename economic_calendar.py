"""
Calendrier économique - annonces US à fort impact (indices Futures NQ/ES).

Les indices US réagissent surtout aux données USD (Fed, inflation, emploi).
On filtre les événements US à fort impact (importance = 1 chez TradingView),
plus quelques mots-clés majeurs (FOMC, CPI, NFP, Powell...).

Source : API du calendrier économique de TradingView (celle qui alimente leur
widget). Gratuite, sans clé, robuste depuis un serveur cloud.
"""
from __future__ import annotations
import time
import datetime as dt
import requests

TV_URL = "https://economic-calendar.tradingview.com/events"
# Pays suivis (l'or dépend surtout de l'USD)
COUNTRIES = "US"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "Accept": "application/json",
}

# Filet de sécurité : événements majeurs à garder même si TradingView les
# note en importance moyenne. Volontairement restreint pour éviter le bruit.
ALWAYS_KEEP = ("FOMC", "Rate Decision", "CPI", "PCE", "Powell")

_cache: dict = {"ts": 0, "data": []}
_CACHE_TTL = 1800  # 30 min

# Diagnostic de la dernière récupération (visible via /agenda)
LAST = {"count": 0, "status": None, "error": None}


def _fetch() -> list[dict]:
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL and _cache["data"]:
        return _cache["data"]
    frm = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")
    to = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
          ).strftime("%Y-%m-%dT00:00:00.000Z")
    try:
        r = requests.get(TV_URL, params={"from": frm, "to": to,
                                         "countries": COUNTRIES},
                         headers=_HEADERS, timeout=20)
        LAST["status"] = r.status_code
        r.raise_for_status()
        data = r.json().get("result", [])
        _cache["ts"] = now
        _cache["data"] = data
        LAST["count"] = len(data)
        LAST["error"] = None
        return data
    except Exception as e:  # on ne casse pas le bot, on renvoie le cache
        LAST["error"] = f"{type(e).__name__}: {e}"
        print(f"[calendar] fetch échoué: {LAST['error']}")
        return _cache["data"]


def _parse_dt(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        # format "2026-07-02T12:30:00.000Z"
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_relevant(ev: dict) -> bool:
    importance = ev.get("importance", -99)
    title = ev.get("title") or ""
    if importance is not None and importance >= 1:
        return True
    return any(k.lower() in title.lower() for k in ALWAYS_KEEP)


def _normalize(ev: dict) -> dict:
    country = (ev.get("country") or "").upper()
    return {
        "title": ev.get("title"),
        "currency": "USD" if country == "US" else country,
        "impact": "High" if (ev.get("importance") or -1) >= 1 else "Medium",
        "when": _parse_dt(ev.get("date")),
        "forecast": ev.get("forecast") if ev.get("forecast") is not None else "",
        "previous": ev.get("previous") if ev.get("previous") is not None else "",
    }


def upcoming(within_minutes: int = 60) -> list[dict]:
    """Événements pertinents qui tombent dans les `within_minutes` à venir."""
    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(minutes=within_minutes)
    out = []
    for ev in _fetch():
        if not _is_relevant(ev):
            continue
        n = _normalize(ev)
        if n["when"] and now <= n["when"] <= horizon:
            out.append(n)
    return sorted(out, key=lambda x: x["when"])


def today_agenda() -> list[dict]:
    """Tous les événements pertinents du jour (pour le brief matinal)."""
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for ev in _fetch():
        if not _is_relevant(ev):
            continue
        n = _normalize(ev)
        if n["when"] and n["when"].date() == now.date():
            out.append(n)
    return sorted(out, key=lambda x: x["when"])
