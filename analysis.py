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


def build_message(event: dict, news_warning: str | None = None) -> str:
    etype = event.get("event", "?")
    bias = event.get("bias", "?")
    ticker = event.get("ticker", "XAUUSD")
    tf = event.get("tf", "?")
    price = event.get("price", "?")
    trend = event.get("trend", "none")

    title, desc, side, conf = EVENT_MEANING.get(
        (etype, bias),
        (f"Signal {etype}", "Événement détecté.", "neutre", 1),
    )

    trend_txt = {"bull": "haussière 🟢", "bear": "baissière 🔴",
                 "none": "indéterminée ⚪"}.get(trend, "indéterminée ⚪")

    lines = [
        f"*{title}*  —  `{ticker}` en `{tf}`",
        f"Prix : *{price}*",
        f"Tendance de fond : {trend_txt}",
        f"Confiance : {confidence_bar(conf)}",
        "",
        desc,
    ]

    if news_warning:
        lines += ["", news_warning]

    lines += [
        "",
        "_Aide à la décision, pas un conseil. Vérifie le contexte avant "
        "d'agir et gère ton risque._",
    ]
    return "\n".join(lines)
