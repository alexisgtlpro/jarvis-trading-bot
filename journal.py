"""
Journal automatique des signaux.

Chaque signal envoyé est aussi posté vers un Google Sheet (via une petite
Apps Script Web App). On garde ainsi une trace durable pour mesurer la
performance par grade et affiner la stratégie avec de vraies données.

Le disque de Render s'efface à chaque redéploiement : on ne logge donc PAS
en local, mais vers un stockage externe (le Sheet).
"""
from __future__ import annotations
import os
import datetime as dt
import requests

try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo("Europe/Paris")
except Exception:
    PARIS = dt.timezone.utc

JOURNAL_URL = os.getenv("JOURNAL_WEBHOOK_URL", "")


def log_signal(event: dict) -> bool:
    """Envoie une ligne de journal vers le Google Sheet. Ne bloque jamais
    le flux principal : en cas d'échec, on log l'erreur et on continue."""
    if not JOURNAL_URL:
        return False
    now = dt.datetime.now(dt.timezone.utc)
    row = {
        "date_paris": now.astimezone(PARIS).strftime("%Y-%m-%d %H:%M"),
        "ticker": event.get("ticker", ""),
        "tf": event.get("tf", ""),
        "direction": event.get("dir", ""),
        "grade": event.get("grade", ""),
        "score": event.get("score", ""),
        "session": event.get("sess", ""),
        "entry_low": event.get("entry_low", ""),
        "entry_high": event.get("entry_high", ""),
        "sl": event.get("sl", ""),
        "tp1": event.get("tp1", ""),
        "tp2": event.get("tp2", ""),
        "tp3": event.get("tp3", ""),
        "rr": event.get("rr", ""),
        "htf_trend": event.get("htf_trend", ""),
        "conf_htf": event.get("c_htf", ""),
        "conf_sweep": event.get("c_sweep", ""),
        "conf_ote": event.get("c_ote", ""),
        "conf_mom": event.get("c_mom", ""),
        "rsi": event.get("rsi", ""),
        # Colonnes laissées vides, à remplir par toi après le trade :
        "resultat": "",   # Win / Loss / BE
        "R_gagne": "",     # ex: +2 ou -1
        "notes": "",
    }
    try:
        requests.post(JOURNAL_URL, json=row, timeout=10)
        return True
    except Exception as e:
        print(f"[journal] échec d'écriture: {e}")
        return False
