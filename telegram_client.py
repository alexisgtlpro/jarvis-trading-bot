"""Petit client Telegram (envoi de messages via l'API Bot HTTP)."""
from __future__ import annotations
import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send(text: str, chat_id: str | None = None) -> bool:
    if not TOKEN:
        print("[telegram] TELEGRAM_BOT_TOKEN manquant")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"[telegram] erreur {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[telegram] envoi échoué: {e}")
        return False
