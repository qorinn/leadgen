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

(c) 12. SZAKASZ -- A RAMP VAK FOLTJA. Ez a fajl korabban FIXEN NULLAT adott at
    az elutasitasoknak:  evaluate_ramp(..., rejects=0). Emiatt a
    REJECT_RATE_ALERT kuszob soha nem sult el, es a ramp kizarolag a
    visszapattanasokbol tanult. Nem latta, ha a Google elkezdi ELUTASITANI a
    kuldeseket (rate limit, policy reject) -- pedig pont ez az a jel, ami
    idoben szolna. A sender.py mar szamolta a sikertelen kuldeseket, csak nem
    mentette gepi olvasasra alkalmas formaban; most a rejects.csv-be irja.

    A BOUNCE ES A REJECT KET KULON JELENSEG, ezert ket kulon kuszob:
      bounce -- a cimlista oregszik      -> BOUNCE_RATE_ALERT (0.04)
      reject -- a KULDO oldalan van baj  -> REJECT_RATE_ALERT (0.03)
    A reject kuszobe alacsonyabb, mert a rossz cim a mi hibank nelkul is
    elofordul, egy policy-elutasitas viszont soha.
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
    # Az elutasitasok a KULDES pillanataban keletkeznek, tehat a ts mindig a
    # valodi esemeny ideje -- itt nincs a bounce-nal latott "hatralek"
    # problema, es nem kell a mai cimzettekhez szurni.
    rejects = store.rejects_today_count()
    # A nevezo a MEGKISERELT kuldes, nem a sikeres: 20 kiserletbol 20
    # elutasitas 100%, nem osztas-nullaval. A `sent` onmagaban csak a
    # sikereseket szamolja, tehat pont a legrosszabb esetben lenne 0.
    attempted = sent + rejects
    return {
        "date": today,
        "sent": sent,
        "rejects": rejects,
        "attempted": attempted,
        "reject_rate": round(rejects / attempted, 4) if attempted else 0.0,
        "bounces_same_day": real,
        "bounces_backlog": backlog,
        "bounces_reputation": reputation,
        "bounce_rate": round(real / sent, 4) if sent else 0.0,
        "reputation_bounce_rate": round(reputation / sent, 4) if sent else 0.0,
    }


def main() -> int:
    store.init_all()
    rep = daily_report()

    bounce_alert = rep["reputation_bounce_rate"] >= config.BOUNCE_RATE_ALERT
    reject_alert = rep["reject_rate"] >= config.REJECT_RATE_ALERT
    alert = bounce_alert or reject_alert

    store.log(
        f"Kezbesites {rep['date']}: kikuldve={rep['sent']} "
        f"bounce={rep['bounces_same_day']} ({rep['bounce_rate'] * 100:.1f}%) "
        f"ebbol reputacio-relevans={rep['bounces_reputation']} "
        f"({rep['reputation_bounce_rate'] * 100:.1f}%)"
        + (f" (+{rep['bounces_backlog']} korabbi, nem szamit bele)" if rep["bounces_backlog"] else "")
    )
    if rep["rejects"]:
        store.log(
            f"SMTP-elutasitas: {rep['rejects']} / {rep['attempted']} kiserlet "
            f"({rep['reject_rate'] * 100:.1f}%). Az okok: data/rejects.csv"
        )

    if bounce_alert:
        store.log(
            "FIGYELEM: a reputacio-relevans bounce atlepte a kuszobot. "
            "Vedd vissza a napi keretet, es nezd at a lista forrasat. "
            "Ha ez ismetlodik, allitsd le a kampanyt, amig a lista nem tisztult."
        )
    if reject_alert:
        # MAS A TEENDO, MINT BOUNCE-NAL: a bounce a listarol szol, a reject
        # rolunk. Itt nem a lista forrasat kell nezni, hanem azt, hogy a
        # kuldo fiok/domain nem utkozik-e limitbe vagy policy-ba.
        store.log(
            "FIGYELEM: az SMTP-elutasitasok aranya atlepte a kuszobot. "
            "Ez NEM a lista hibaja, hanem a kuldo oldale: rate limit vagy "
            "policy-elutasitas. Nezd meg a data/rejects.csv hibauzeneteit, "
            "es ma ne inditsd ujra a kuldest."
        )

    state = limits.evaluate_ramp(
        sent=rep["sent"], bounces=rep["bounces_reputation"], rejects=rep["rejects"],
    )
    store.log(f"Ramp: holnapi keret/fiok = {state.get('cap')} (tiszta napok: {state.get('clean_days')})")
    return 1 if alert else 0


if __name__ == "__main__":
    raise SystemExit(main())
