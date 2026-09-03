#!/usr/bin/env python3
"""Vedelmi reteg: valasz-figyeles, leiratkozas es bounce-feldolgozas.

Mindharom ugyanabbol a postafiokbol olvas, ezert egy IMAP-korben intezzuk.
Orankenti/napi futtatasra valo, a kuldes ELOTT.

A harom szabaly, amit soha ne kapcsolj ki:
  1. Aki valaszolt, annak nem megy tobb automatikus level.
  2. Aki leiratkozott, az azonnal es vegleg DNC-be kerul.
  3. Aki visszapattant (nem letezo cim), az azonnal DNC-be kerul.
     Egy nem letezo cimre valo ujra-kuldes duplan bunteti a reputaciot.
"""
from __future__ import annotations

import re
import unicodedata

import config
import mailer
import store

# Bounce-uzenetek jellemzo feladoi es targyai
NDR_SENDERS = ("mailer-daemon", "postmaster@", "mail-daemon")
NDR_SUBJECTS = (
    "undelivered mail", "delivery status notification", "returned to sender",
    "delivery has failed", "kezbesitesi hiba", "failure notice", "mail delivery failed",
)

# Vegleges (hard) bounce mintak. CSAK ezekre teszunk DNC-t.
# A "mailbox full" es a hasonlo atmeneti hibak NEM tartoznak ide.
HARD_BOUNCE_PATTERNS = (
    r"550[ -]", r"551[ -]", r"553[ -]", r"5\.1\.1", r"5\.1\.[0-9]",
    r"user unknown", r"no such user", r"recipient not found",
    r"address rejected", r"does not exist", r"mailbox unavailable",
    r"nincs ilyen felhasznalo",
)
SOFT_BOUNCE_PATTERNS = (r"mailbox full", r"quota", r"4\.2\.2", r"over quota", r"try again")

# Leiratkozasi szandek.
#
# KET JAVITAS TORTENT ITT, MERT A MINTAK KETIRANYBAN IS HIBAZTAK (merve):
#
# 1. HAMIS POZITIV -- torolve a nyers r"\bnem\b" minta.
#    Magyar szovegben a "nem" szo szinte minden valaszban elofordul. A
#    "Most nem aktualis, de jovore kerdezz ra!" valasz emiatt VEGLEGESEN
#    leiratkozaskent kerult volna suppressionbe -- vagyis pont egy erdeklodo
#    lead veszett volna el, csendben.
#    Ez NEM gyengiti a vedelmet: aki valaszol, az a lenti `replied` szabaly
#    miatt amugy is DNC-be kerul. Csak az OK lesz pontos.
#
# 2. HAMIS NEGATIV -- a mintak ASCII-ban vannak, a magyar valaszok viszont
#    ekezetesek. A "Kerlek tavolits el a listarol" illeszkedett, a
#    "Kerlek tavolits el a listarol" ekezetes valtozata NEM. Ugyanigy halott
#    volt a `nem erdekel` es a `torol.*listar` minden ekezetes szovegre.
#    Ezert a _fold() ekezet-hajtogatast vegez az illesztes ELOTT.
#
# 2026-08-21: A LISTA LESZUKITVE, amikor a leveleket atallitottuk leiratkozo
# LINKRE. Innentol ez a szabaly a masodlagos ut -- aki kattint, az mar nem is
# jut el idaig.
#
# Ami kikerult: "not interested", "koszonom, nem", "nem erdekel", "nem kerem",
# "nem kivanok". Ezek NEM leiratkozasi kerelmek, hanem ELUTASITASOK, es a
# kettot kar osszemosni: az elutasito valasz kesobb ujra megkeresheto (mas
# ajanlattal, fel ev mulva), a leiratkozas viszont VEGLEGES.
#
# A szukites SENKIT nem enged ki: aki valaszol, azt a fuggveny vegen levo
# `replied` szabaly amugy is DNC-be teszi. Csak az OK lesz pontosabb -- es a
# 6. szakasz AI-osztalyozoja ezt fogja rendesen szetvalasztani.
#
# Ami bent maradt: csak az EGYERTELMU keresek. A lista itt szandekosan
# szigoru, mert a hamis pozitiv ara nagy (egy erdeklodo veglegesen kiesik).
UNSUB_PATTERNS = (
    r"\bne kuldj", r"\bne kuldjon", r"\bne irj", r"leiratkoz", r"tavolits",
    r"torol.*listar", r"\bunsubscribe\b", r"remove me", r"\bstop\b",
    r"kerem.*torol",
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _fold(text: str) -> str:
    """Kisbetusites + ekezet-eltavolitas, a mintaillesztes elott.

    "Kerlek tavolits el a listarol" es a ekezetes valtozata igy ugyanarra a
    szovegre illeszkedik. E nelkul az osszes ASCII-ban irt minta halott volt
    minden ekezetes magyar valaszra -- es magyar valaszok jellemzoen ekezetesek.
    """
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _extract_email(raw_from: str) -> str:
    m = re.search(r"<([^>]+)>", raw_from or "")
    if m:
        return m.group(1).strip().lower()
    m = EMAIL_RE.search(raw_from or "")
    return m.group(0).strip().lower() if m else ""


def _is_ndr(msg: dict) -> bool:
    sender = (msg.get("from") or "").lower()
    subject = (msg.get("subject") or "").lower()
    return any(s in sender for s in NDR_SENDERS) or any(s in subject for s in NDR_SUBJECTS)


def _bounced_address(msg: dict) -> tuple[str, str] | None:
    """A bounce torzsebol kiszedi az EREDETI cimzettet es a hiba tipusat.

    Fontos: a bounce feladoja a MAILER-DAEMON, nem a cimzett. A valodi cimet
    a torzsbol kell kibanyaszni, kulonben a daemon cime kerulne DNC-be.
    """
    body = (msg.get("body") or "") + " " + (msg.get("subject") or "")
    low = _fold(body)   # a "nincs ilyen felhasznalo" minta is ASCII-ban van

    kind = ""
    if any(re.search(p, low) for p in HARD_BOUNCE_PATTERNS):
        kind = "hard_bounce"
    elif any(re.search(p, low) for p in SOFT_BOUNCE_PATTERNS):
        kind = "soft_bounce"
    else:
        return None

    known = store.already_contacted()
    for candidate in EMAIL_RE.findall(body):
        candidate = candidate.lower()
        if candidate in known:
            return candidate, kind
    return None


# Kozismert freemail-szolgaltatok. A DOMAIN-alapu parositas ezeknel NEM
# ervenyes: ha egy leadnek `valaki@gmail.com` cimere kuldtunk, attol meg egy
# TETSZOLEGES gmail-cimrol jovo level nem az o valasza.
_FREEMAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.hu", "hotmail.com",
    "hotmail.hu", "yahoo.com", "yahoo.hu", "icloud.com", "freemail.hu",
    "citromail.hu", "t-online.hu", "upcmail.hu", "vipmail.hu", "indamail.hu",
    "chello.hu", "externet.hu", "invitel.hu", "protonmail.com", "gmx.com", "gmx.net",
}

# A valasz-targy jellegzetes elotagjai. A DOMAIN-alapu parositasnal kotelezo:
# e nelkul egy ceges hirlevel (`hirlevel@ceg.hu`) is "valasznak" szamitana, es
# csendben tiltolistara tenne egy jo leadet.
#
# NEM A TARGY ELEJEHEZ KOTVE (`search`, nem `match`): az automatikus
# tavollet-valaszok ele sajat szoveget tesznek. Valos pelda a postafiokbol:
# "Szabadsagon vagyok Re: Gyors kerdes a fejlesztesrol". Ha csak a targy
# elejen keresnenk, pont ezek maradnanak ki -- pedig ezeket erdemes a
# LEGJOBBAN elkapni: nem elutasitas, hanem "most nem er ra", amire a
# valasz-osztalyozo 14 napos cooldownt ad, follow-up helyett.
#
# A `\s*:` miatt a szo utan KOZVETLENUL kettospont kell, tehat egy
# "Regisztralj most:" targyu hirlevel nem illeszkedik.
_VALASZ_TARGY = re.compile(
    r"(?:^|\s)(re|válasz|valasz|aw|fwd?|továbbítás|tovabbitas)\s*:",
    re.IGNORECASE)


def _is_reply_from_lead(sender: str, msg: dict, contacted: set[str],
                        contacted_domains: set[str]) -> bool:
    """Ez a level egy megkeresett lead valasza-e?

    KET UTON ISMERUNK FEL EGY VALASZT, es a masodik nelkul valaszok vesznek el:

    1. PONTOS CIM-EGYEZES. Arrol a cimrol jott, amire irtunk. Ez a biztos eset,
       itt nem kerunk semmilyen tovabbi jelet.

    2. AZONOS CEG-DOMAIN, "Re:" targgyal. Az ember ritkan arrol a cimrol
       valaszol, amire irtunk: az `info@ceg.hu`-ra kuldott levelre a sajat
       cimerol jon a valasz. Merve (2026-09-03): ket valodi valasz --
       koztuk egy erdeklodo -- maradt lathatatlan pontosan emiatt, es a
       rendszer 2 nap mulva follow-upot kuldott volna nekik.

    A 2. ut KET SZUKITESSEL biztonsagos:
      - freemail domain KIZARVA (egy tetszoleges gmail-cim nem a lead valasza)
      - a targynak valasz-elotaggal kell kezdodnie (kulonben egy ceges
        hirlevel is tiltolistara tenne egy jo leadet)

    A tevedes iranya itt szandekosan az ovatossag fele dol: egy hamis talalat
    annyit jelent, hogy nem kuldunk tovabbi levelet valakinek. Egy KIMARADT
    valasz viszont azt, hogy follow-upot kuldunk annak, aki mar valaszolt.
    """
    if sender in contacted:
        return True

    domain = sender.split("@")[-1].strip().lower()
    if not domain or domain in _FREEMAIL or domain not in contacted_domains:
        return False
    return bool(_VALASZ_TARGY.search(msg.get("subject") or ""))


def run(days: int = 14) -> dict:
    """Vegigmegy a postafiokokon. Visszaadja az osszesitest.

    Ha BARMELYIK postafiok olvasasa hibara fut, kivetelt dob. A hivo oldal
    ilyenkor NE kuldjon follow-upot (lasd mailer.fetch_recent doksijat).
    """
    replied: set[str] = set()
    stats = {"scanned": 0, "replies": 0, "replies_logged": 0,
             "unsubscribes": 0, "hard_bounces": 0, "soft_bounces": 0}
    # Egyszer olvassuk be, nem valaszonkent -- kulonben O(n^2) fajlolvasas.
    seen_replies = store.reply_msg_ids()

    accounts = config.smtp_accounts()
    if not accounts:
        raise RuntimeError("Nincs beallitva SMTP_ACCOUNTS.")

    contacted = store.already_contacted()
    contacted_domains = store.contacted_domains()

    for acc in accounts:
        messages = mailer.fetch_recent(acc, days=days)  # hiba eseten dob
        stats["scanned"] += len(messages)

        for msg in messages:
            if _is_ndr(msg):
                found = _bounced_address(msg)
                if found:
                    addr, kind = found
                    store.record_bounce(addr, kind, msg.get("subject", ""))
                    if kind == "hard_bounce":
                        if store.add_to_dnc(addr, "hard_bounce", "automatikus: nem letezo cim"):
                            stats["hard_bounces"] += 1
                    else:
                        stats["soft_bounces"] += 1
                continue

            sender = _extract_email(msg.get("from", ""))
            if not sender or not _is_reply_from_lead(sender, msg, contacted,
                                                     contacted_domains):
                continue

            replied.add(sender)
            stats["replies"] += 1

            # A valasz SZOVEGET is megorizzuk. Eddig itt eldobtuk: csak egy
            # DNC-sor maradt belole, tehat az AI valasz-osztalyozasnak
            # (erdeklodik / nem / leiratkozas / automatikus valasz) nem volt
            # bemenete. A dedup a Message-ID-n all, mert ez a fuggveny minden
            # futasnal ujraolvassa a teljes 14 napos ablakot.
            msg_id = (msg.get("message_id") or "").strip()
            dedup_key = msg_id or f"{sender}|{msg.get('subject', '')[:120]}"
            if dedup_key not in seen_replies:
                store.record_reply(dedup_key, sender, msg.get("subject", ""),
                                   msg.get("body", ""))
                seen_replies.add(dedup_key)
                stats["replies_logged"] += 1

            body_low = _fold(msg.get("body") or "")[:600]
            if any(re.search(p, body_low) for p in UNSUB_PATTERNS):
                if store.add_to_dnc(sender, "unsubscribe_request", "automatikus: valaszban jelezte"):
                    stats["unsubscribes"] += 1

    # A valaszolokat is suppressionbe tesszuk az automatikus letra szempontjabol.
    # Kulon reason, hogy kesobb meg tudd kulonboztetni oket a leiratkozoktol:
    # egy valaszolo lehet forro lead, csak EMBER valaszoljon neki, ne a robot.
    for addr in replied:
        store.add_to_dnc(addr, "replied", "valaszolt, kezi kovetes szukseges")

    return stats


if __name__ == "__main__":
    store.init_all()
    try:
        result = run()
        store.log(f"Guards: {result}")
    except Exception as exc:  # noqa: BLE001
        store.log(f"Guards HIBA (a kuldes ilyenkor NE induljon): {exc}")
        raise SystemExit(1)
