"""
Couche d'analyse : transforme un événement SMC brut en lecture
acheteur / vendeur lisible, avec un niveau de confiance simple.

NB : ce n'est pas un conseil financier. C'est une aide à la décision qui
structure ce que l'indicateur a détecté. La décision reste 100% humaine.
"""
from __future__ import annotations

# Décrit chaque type d'événement côté acheteur/vendeur
EVENT_MEANING = {
    ("BOS", "bull"): (
        "🟢 BOS haussier",
        "Cassure de structure vers le haut : la tendance haussière se "
        "confirme. Biais ACHETEUR. On cherche des achats sur repli (retour "
        "dans un FVG ou un Order Block haussier).",
        "acheteur", 3,
    ),
    ("BOS", "bear"): (
        "🔴 BOS baissier",
        "Cassure de structure vers le bas : la tendance baissière se "
        "confirme. Biais VENDEUR. On cherche des ventes sur rebond (retour "
        "dans un FVG ou un Order Block baissier).",
        "vendeur", 3,
    ),
    ("CHOCH", "bull"): (
        "🟢 CHOCH haussier",
        "Changement de caractère vers le haut : possible retournement de "
        "baissier à haussier. Biais ACHETEUR naissant, à confirmer par un "
        "BOS. Prudence, c'est un signal précoce.",
        "acheteur", 2,
    ),
    ("CHOCH", "bear"): (
        "🔴 CHOCH baissier",
        "Changement de caractère vers le bas : possible retournement de "
        "haussier à baissier. Biais VENDEUR naissant, à confirmer par un "
        "BOS. Prudence, c'est un signal précoce.",
        "vendeur", 2,
    ),
    ("FVG", "bull"): (
        "🔵 FVG haussier",
        "Zone d'inefficience (Fair Value Gap) laissée par une impulsion "
        "haussière. Souvent rejouée : le prix peut y revenir avant de "
        "repartir à la hausse. Zone d'achat potentielle.",
        "acheteur", 1,
    ),
    ("FVG", "bear"): (
        "🟣 FVG baissier",
        "Zone d'inefficience laissée par une impulsion baissière. Le prix "
        "peut y revenir avant de repartir à la baisse. Zone de vente "
        "potentielle.",
        "vendeur", 1,
    ),
    ("LIQUIDITY_EQH", "bear"): (
        "🟠 Liquidité au-dessus (EQH)",
        "Sommets égaux : de la liquidité (stops acheteurs) s'accumule "
        "au-dessus. Le prix va souvent la chasser avant de se retourner à la "
        "baisse. Surveille un balayage puis un CHOCH baissier.",
        "vendeur", 2,
    ),
    ("LIQUIDITY_EQL", "bull"): (
        "🟠 Liquidité en dessous (EQL)",
        "Creux égaux : de la liquidité (stops vendeurs) s'accumule en "
        "dessous. Le prix va souvent la chasser avant de se retourner à la "
        "hausse. Surveille un balayage puis un CHOCH haussier.",
        "acheteur", 2,
    ),
}


def confidence_bar(level: int) -> str:
    full = "●" * level
    empty = "○" * (3 - level)
    return full + empty


def _format_rr(rr: str) -> str:
    # "1/2/3" -> "TP1 1:1 · TP2 1:2 · TP3 1:3"
    try:
        parts = [p.strip() for p in rr.split("/")]
        return " · ".join(f"TP{i+1} 1:{p}" for i, p in enumerate(parts))
    except Exception:
        return rr


def _has_levels(event: dict) -> bool:
    return all(event.get(k) for k in ("entry_low", "entry_high", "sl",
                                      "tp1", "tp2", "tp3"))


def build_message(event: dict, news_warning: str | None = None) -> str:
    etype = event.get("event", "?")
    bias = event.get("bias", "?")
    ticker = event.get("ticker", "XAUUSD")
    tf = event.get("tf", "?")
    price = event.get("price", "?")
    trend = event.get("trend", "none")
    direction = event.get("dir") or ("BUY" if bias == "bull" else "SELL")

    title, desc, side, conf = EVENT_MEANING.get(
        (etype, bias),
        (f"Signal {etype}", "Événement détecté.", "neutre", 1),
    )

    is_buy = direction == "BUY"
    dir_emoji = "🟢🔼" if is_buy else "🔴🔽"
    trend_txt = {"bull": "haussière 🟢", "bear": "baissière 🔴",
                 "none": "indéterminée ⚪"}.get(trend, "indéterminée ⚪")

    grade = event.get("grade", "")
    score = event.get("score", "")
    sess = event.get("sess", "")
    grade_badge = {"A+": "🏆 A+", "A": "🥈 A", "B": "🥉 B"}.get(grade, grade)

    conf_txt = confidence_bar(conf)

    header = f"{dir_emoji} *{ticker} {direction}*"
    if grade:
        header += f"  ·  {grade_badge}"
    lines = [
        header,
        f"_Signal : {title} · `{tf}`_",
    ]
    meta = []
    if score:
        meta.append(f"Score confluence : *{score}/100*")
    if sess:
        meta.append(f"Session : {sess}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append("")

    if _has_levels(event):
        if event.get("price"):
            lines.append(f"Prix au signal : *{event['price']}*")
        lines += [
            f"🎯 *Entry Zone :* {event['entry_low']} – {event['entry_high']}",
            f"🛑 *Stop Loss :* {event['sl']}",
            f"🥇 *Take Profit 1 :* {event['tp1']}   _(1R)_",
            f"🥈 *Take Profit 2 :* {event['tp2']}   _(2R)_",
            f"🥉 *Take Profit 3 :* {event['tp3']}   _(3R)_",
        ]
        if event.get("dol"):
            lines.append(f"🧲 *Cible liquidité (DOL) :* {event['dol']}  "
                         f"_(là où le prix est probablement 'tiré')_")
        lines.append("")
    else:
        lines += [f"Prix actuel : *{price}*", ""]

    # ---- Confluences (ce qui a validé le setup) ----
    def _chk(ok: str | None) -> str:
        return "✅" if str(ok) == "1" else "❌"

    htf_trend = event.get("htf_trend", "")
    htf_txt = {"bull": "haussier", "bear": "baissier"}.get(htf_trend, "neutre")
    if any(k in event for k in ("c_htf", "c_sweep", "c_ote", "c_mom")):
        lines += [
            "🧩 *Confluences*",
            f"{_chk('1' if sess and sess != 'Hors killzone' else '0')} "
            f"Session active ({sess or 'n/a'})",
            f"{_chk(event.get('c_htf'))} Biais H4 aligné (H4 {htf_txt})",
            f"{_chk(event.get('c_sweep'))} Balayage de liquidité + MSS",
            f"{_chk(event.get('c_smt'))} Divergence SMT (NQ/ES)",
            f"{_chk(event.get('c_vol'))} Volume + displacement (CME)",
            f"{_chk(event.get('c_ote'))} Zone Premium/Discount "
            f"({event.get('c_pd', 'n/a')})",
            f"{_chk(event.get('c_vwap'))} VWAP institutionnel aligné",
            f"{_chk(event.get('c_sb'))} Fenêtre Silver Bullet",
            f"{_chk(event.get('c_mom'))} Momentum (EMA200 + RSI "
            f"{event.get('rsi', '?')})",
            "",
        ]

    # ---- Analyse complète ----
    lines += [
        "📊 *Analyse*",
        desc,
        "",
        f"*Contexte :* tendance de fond {trend_txt}. "
        f"Setup noté *{grade or '?'}* ({score or '?'}/100).",
        f"*Confiance du signal :* {conf_txt}",
    ]

    if _has_levels(event):
        invalid_word = ("sous le Stop Loss (structure cassée)"
                        if is_buy else "au-dessus du Stop Loss (structure cassée)")
        lines += [
            "",
            "*Plan d'exécution :*",
            "• Entrée : la zone est proche du prix actuel. Entre au marché ou "
            "sur un léger repli dans la zone. Si le prix s'est déjà trop "
            "éloigné de la zone, laisse passer.",
            f"• Invalidation : le scénario est faux si le prix clôture "
            f"{invalid_word}. Respecte le Stop Loss, toujours.",
            "• Sortie : sécurise une partie à TP1, puis remonte le Stop Loss "
            "à ton prix d'entrée (break-even) pour un trade sans risque, et "
            "laisse courir vers TP2 / TP3.",
            f"• Ratio risque/rendement : {_format_rr(event.get('rr', '1/2/3'))} "
            "(R = distance entrée → stop).",
            "*Risque conseillé :* 1% de ton capital maximum sur ce trade.",
        ]

    if news_warning:
        lines += ["", news_warning]

    lines += [
        "",
        "_Aide à la décision automatisée, pas un conseil financier. Les "
        "niveaux sont calculés sur l'ATR et la structure : à vérifier avec ton "
        "propre jugement. Ne trade jamais sans stop._",
    ]
    return "\n".join(lines)
