#!/usr/bin/env python3
"""Napi kezbesitesi orjarat. A kuldesi ablak zarasa utan futtasd.

Ket dolgot csinal:
  1. Kiszamolja a napi mutatokat es riaszt, ha baj van.
  2. Meghivja a ramp-ertekelest, ami holnapra be- vagy visszaallitja a keretet.

KET HIBA, AMIT MI ELKOVETTUNK, ES ITT MAR JAVITVA VAN:

(a) A bounce-naplo idobelyege azt mutatja, MIKOR DOLGOZTUK FEL a bounce-t,
    nem azt, mikor ment ki az eredeti level. Amikor egyszer bepotoltunk egy
    tobbnapos bounce-hatralekot, a mero 248%-os bounce-aranyt szamolt es
    hamis riasztast kuldott. Ezert itt a bounce CSAK akkor szamit a mai
    aranyba, ha a cimzettnek MA is kuldtunk.

(b) Nem minden bounce a te hibad. A "nem letezik ez a cim" lista-higienia
    (a lista oregszik), a "policy rejected" viszont reputacio-jelzes. Ha
    mindkettore riasztasz, a riasztas zajja valik es kikapcsolod. Ezert az
    ertesites CSAK a reputacio-relevans reszre nez, a teljes szam a naploban marad.
"""
from __future__ import annotations

import config
import limits
import store

# Ezek a lista oregedesebol fakadnak, nem a kuldo hirnevebol.
LIST_HYGIENE_REASONS = {"soft_bounce"}


def daily_report() -> dict:
    today = store.today()

    sent_today = [r for r in store.sent_rows() if (r.get("ts") or "").startswith(today)]
    recipients_today = {(r.get("email") or "").lower() for r in sent_today}

    real = backlog = reputation = 0
    for row in store.bounce_rows():
        if not (row.get("ts") or "").startswith(today):
            continue
        if (row.get("email") or "").lower() in recipients_today:
            real += 1
            if (row.get("reason") or "") not in LIST_HYGIENE_REASONS:
                reputation += 1
        else:
            backlog += 1

    sent = len(sent_today)
    return {
        "date": today,
        "sent": sent,
        "bounces_same_day": real,
        "bounces_backlog": backlog,
        "bounces_reputation": reputation,
        "bounce_rate": round(real / sent, 4) if sent else 0.0,
        "reputation_bounce_rate": round(reputation / sent, 4) if sent else 0.0,
    }


def main() -> int:
    store.init_all()
    rep = daily_report()

    alert = rep["reputation_bounce_rate"] >= config.BOUNCE_RATE_ALERT

    store.log(
        f"Kezbesites {rep['date']}: kikuldve={rep['sent']} "
        f"bounce={rep['bounces_same_day']} ({rep['bounce_rate'] * 100:.1f}%) "
        f"ebbol reputacio-relevans={rep['bounces_reputation']} "
        f"({rep['reputation_bounce_rate'] * 100:.1f}%)"
        + (f" (+{rep['bounces_backlog']} korabbi, nem szamit bele)" if rep["bounces_backlog"] else "")
    )

    if alert:
        store.log(
            "FIGYELEM: a reputacio-relevans bounce atlepte a kuszobot. "
            "Vedd vissza a napi keretet, es nezd at a lista forrasat. "
            "Ha ez ismetlodik, allitsd le a kampanyt, amig a lista nem tisztult."
        )

    state = limits.evaluate_ramp(
        sent=rep["sent"], bounces=rep["bounces_reputation"], rejects=0,
    )
    store.log(f"Ramp: holnapi keret/fiok = {state.get('cap')} (tiszta napok: {state.get('clean_days')})")
    return 1 if alert else 0


if __name__ == "__main__":
    raise SystemExit(main())
