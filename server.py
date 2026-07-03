"""
Serveur webhook Jarvis Trading.

Reçoit les alertes de TradingView (indicateur Jarvis SMC), les analyse,
vérifie le calendrier économique, et envoie une synthèse sur Telegram.

Lancer :  python server.py
Endpoints :
  POST /webhook?key=SECRET   -> reçoit les alertes TradingView (+ journal)
  GET  /health               -> test de vie
  GET  /agenda?key=SECRET    -> brief éco du matin + battement de coeur
  GET  /status               -> état machine (JSON, sans notification)
"""
from __future__ import annotations
import os
import json
import datetime as dt
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo("Europe/Paris")
except Exception:  # sécurité si tzdata absent
    PARIS = dt.timezone.utc
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify

import telegram_client as tg
import analysis
import economic_calendar as cal
import journal

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
NEWS_WARN_MINUTES = int(os.getenv("NEWS_WARN_MINUTES", "60"))
ALERT_EXPIRY = os.getenv("ALERT_EXPIRY", "")  # ex: 2026-08-03
PORT = int(os.getenv("PORT", "5000"))

app = Flask(__name__)


def _expiry_warning() -> str | None:
    """Prévient si l'alerte TradingView approche de son expiration."""
    if not ALERT_EXPIRY:
        return None
    try:
        exp = dt.datetime.strptime(ALERT_EXPIRY, "%Y-%m-%d").date()
    except Exception:
        return None
    days = (exp - dt.datetime.now(PARIS).date()).days
    if days < 0:
        return ("🔴 *Ton alerte TradingView a EXPIRÉ* le "
                f"{ALERT_EXPIRY}. Recrée-la pour recevoir des signaux.")
    if days <= 5:
        return (f"⚠️ Ton alerte TradingView expire dans *{days} jour(s)* "
                f"({ALERT_EXPIRY}). Pense à la recréer.")
    return None


def _news_warning() -> str | None:
    """Renvoie un avertissement si une annonce éco arrive bientôt."""
    events = cal.upcoming(within_minutes=NEWS_WARN_MINUTES)
    if not events:
        return None
    parts = ["⚠️ *Annonce éco imminente* (volatilité sur les indices US) :"]
    for e in events:
        hhmm = e["when"].strftime("%H:%M UTC")
        parts.append(f"• {hhmm} — {e['currency']} {e['title']}")
    parts.append("_Prudence : évite d'entrer juste avant la publication._")
    return "\n".join(parts)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/webhook")
def webhook():
    if WEBHOOK_SECRET and request.args.get("key") != WEBHOOK_SECRET:
        return jsonify(error="unauthorized"), 401

    # TradingView envoie parfois du texte brut, parfois du JSON
    raw = request.get_data(as_text=True) or ""
    event = None
    try:
        event = json.loads(raw)
    except Exception:
        # message texte simple : on l'envoie tel quel
        if raw.strip():
            tg.send(f"📩 Alerte TradingView :\n{raw.strip()}")
            return jsonify(status="forwarded")
        return jsonify(error="empty"), 400

    if event.get("source") != "jarvis_smc":
        tg.send(f"📩 Alerte :\n```\n{raw}\n```")
        return jsonify(status="forwarded")

    warn = _news_warning()
    msg = analysis.build_message(event, news_warning=warn)
    ok = tg.send(msg)
    # Journal : on enregistre les vrais setups directionnels (avec niveaux)
    logged = False
    if event.get("dir") and event.get("sl"):
        logged = journal.log_signal(event)
    return jsonify(status="sent" if ok else "telegram_error", journaled=logged)


@app.get("/agenda")
def agenda():
    if WEBHOOK_SECRET and request.args.get("key") != WEBHOOK_SECRET:
        return jsonify(error="unauthorized"), 401
    _now = dt.datetime.now(PARIS)
    _jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    _mois = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]
    today_fr = f"{_jours[_now.weekday()]} {_now.day} {_mois[_now.month]}"
    events = cal.today_agenda()
    # Le brief du matin sert aussi de battement de coeur : s'il arrive,
    # c'est que tout le système (bot + Telegram + cron) fonctionne.
    header = f"☀️ *Brief éco du matin* — {today_fr}\n✅ Système actif et à l'écoute."
    if not events:
        lines = [header, "\nPas d'annonce US à fort impact aujourd'hui. "
                 "Journée technique : fie-toi à la structure (BOS/CHOCH)."]
    else:
        lines = [header, "\nAnnonces à surveiller (heure de Paris) :"]
        for e in events:
            hhmm = e["when"].astimezone(PARIS).strftime("%H:%M")
            fc = f" | prév {e['forecast']}" if e.get("forecast") else ""
            prev = f" | préc {e['previous']}" if e.get("previous") else ""
            lines.append(f"• *{hhmm}* — {e['currency']} {e['title']}{fc}{prev}")
        lines.append("\n_Prudence autour de ces horaires : volatilité et faux "
                     "signaux fréquents sur les indices._")
    exp = _expiry_warning()
    if exp:
        lines.append("\n" + exp)
    tg.send("\n".join(lines))
    return jsonify(count=len(events), diag=cal.LAST)


@app.get("/status")
def status():
    """État machine (sans notification), pour un check rapide."""
    cal._fetch()
    return jsonify(
        bot="ok",
        calendar_status=cal.LAST.get("status"),
        calendar_error=cal.LAST.get("error"),
        journal_configured=bool(os.getenv("JOURNAL_WEBHOOK_URL")),
        alert_expiry=ALERT_EXPIRY or None,
    )


if __name__ == "__main__":
    print(f"Jarvis Trading Bot en écoute sur le port {PORT}")
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("⚠️  TELEGRAM_BOT_TOKEN manquant dans .env")
    app.run(host="0.0.0.0", port=PORT)
