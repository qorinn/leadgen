#!/usr/bin/env python3
"""CSV-alapu tarolas. Szandekosan nincs adatbazis: igy barmikor kezzel is
megnyithato, verziokezelheto es athelyezheto.

Hat fajl:
  leads.csv          - a lead-lista (a scraper irja)
  sent.csv           - minden kimeno level egy sor (igazsagforras a volumenre)
  do-not-contact.csv - suppression. Aki itt van, annak SOHA nem megy level.
  bounces.csv        - visszapattant cimek naploja
  replies.csv        - a beerkezett valaszok szovege (az AI-osztalyozas bemenete)
  rejects.csv        - SMTP-elutasitasok (a ramp ebbol tanul, 12. szakasz)

FAJL-ZAROLAS (12. szakasz) -- MIERT VALT KOTELEZOVE:
Amig ember inditott minden futast, egyszerre egy folyamat irt ide. A 12.
szakasz utan a leadgen lanca cronbol/launchd-bol fut, es a kuldot te
inditod kezzel -- tehat KET folyamat irhat ugyanabba a konyvtarba,
egymastol fuggetlenul utemezve. Az `_append` sima szoveges hozzafuzes:
lock nelkul ket egyideju iras egymasba csuszhat, es egy FELIG kiirt CSV-sor
keletkezik. Az a sor ettol kezdve minden olvasasnal hibas -- es mivel a
sent.csv az igazsagforras a napi volumenre ES a szekvencia-fokra, egy serult
sor csendben rossz levelet kuld ki, vagy rossz keretet szamol.

Ezert MINDEN iras es MINDEN olvasas `flock`-ot ker (`_locked`). A zar
folyamatok kozott mukodik, es a fajl bezarasakor automatikusan felszabadul --
tehat egy osszeomlott folyamat nem hagy beragadt zarat maga utan.
"""
from __future__ import annotations

import contextlib
import csv
import datetime
import fcntl
from pathlib import Path

import config

# A scraper altal irt mezok is itt vannak. Biztonsagos bovites: minden olvasas
# es iras csv.DictReader/DictWriter, tehat NEV szerinti, nem pozicio szerinti --
# amig az `email` mezo megvan, egyik modul sem torik el.
#
# FIGYELEM: ennek a listanak egyeznie kell a leadgen/contract.py LEADS_HEADER-evel.
# Ha csak az egyik oldalt irod at, a tests/test_contract.py elhasal.
LEADS_HEADER = [
    "email", "company", "contact_name", "website", "industry", "city", "notes",
    "campaign", "personalization", "lead_source_type", "lead_source_url",
    "contact_source_url", "source_url", "scraped_at", "company_id", "unsub_url",
]
SENT_HEADER = ["ts", "email", "domain", "stage", "template", "subject", "account"]
DNC_HEADER = ["ts", "email", "reason", "notes"]
BOUNCE_HEADER = ["ts", "email", "reason", "raw_subject"]
# `msg_id`: a level Message-ID fejlece. EZ A DEDUP KULCS -- a guards minden
# futasnal ujraolvassa a teljes 14 napos postafiokot, tehat ugyanaz a valasz
# tobbszor is elenk kerul. Message-ID nelkul minden futas duplikalna.
# `classified`: a scraper (6. szakasz) tolti ki, a kuldo nem nyul hozza.
REPLIES_HEADER = ["ts", "msg_id", "email", "subject", "body", "classified"]
# `error`: a nyers SMTP hibauzenet. AZ OK SZO SZERINT KELL, nem csak a tenye --
# egy "rate limit exceeded" mast jelent, mint egy "policy rejected": az elso
# atmeneti, a masodik reputacio-jelzes. Ha csak szamolnank az elutasitasokat,
# a ramp visszavenne a keretbol, de nem tudnad, MIERT.
REJECTS_HEADER = ["ts", "email", "account", "error"]


# ─── Fajl-zarolas ──────────────────────────────────────────────────────────
# A zar MAGAN A MEGNYITOTT FAJLON van, nem egy kulon .lock fajlon. Igy nem
# maradhat arva zar-fajl a konyvtarban, es nincs olyan allapot, hogy a zar
# letezik, de a vedett fajl mar nem.
#
# HAROM DOLOG, AMI ITT SZANDEKOS:
#
# 1. Az OLVASAS is zarol (megosztott, LOCK_SH). Enelkul egy olvaso pont egy
#    felig kiirt sorra futhatna ra. Tobb olvaso egyszerre fut -- csak az iro
#    (LOCK_EX) zarja ki oket.
#
# 2. A zar BLOKKOL, nem hibazik (nincs LOCK_NB). Egy CSV-sor kiirasa
#    ezredmasodperc; ha kozben varni kell a masik folyamatra, az helyes
#    viselkedes. Hibaval visszaterni itt azt jelentene, hogy egy kikuldott
#    level NEM kerul be a sent.csv-be -- a rendszer legsulyosabb hibaja,
#    mert a kovetkezo futas ujra kikuldene ugyanazt.
#
# 3. NEM helyettesiti a tranzakciot. Egyetlen `_append` hivast tesz atomiva,
#    tobb fajlon atnyulo muveletet nem. A rendszernek erre nincs is szuksege:
#    minden iras egyetlen sor egyetlen naploba.


@contextlib.contextmanager
def _locked(path: Path, mode: str, lock_type: int):
    """Megnyitott es zarolt fajl. A zar a bezarassal automatikusan felszabadul.

    Ha a folyamat osszeomlik, az operacios rendszer engedi el a zarat -- ezert
    nem tud beragadni. (Egy kulon .lock fajl eseten ez nem lenne igaz.)
    """
    with path.open(mode, encoding="utf-8-sig" if "r" in mode else "utf-8",
                   newline="") as f:
        fcntl.flock(f.fileno(), lock_type)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _ensure(path: Path, header: list[str]) -> None:
    """Letrehozza a fajlt a fejleccel, ha meg nincs.

    Az "x" mod az atomikus resz: ha ket folyamat egyszerre jut ide, az egyik
    letrehozza, a masik FileExistsError-t kap es tovabbmegy. Egy `exists()`
    ellenorzes utani `open("w")` ezt nem tudna -- a ket ellenorzes koze
    beferne a masik folyamat, es a masodik iras FELULIRNA a mar meglevo
    fajlt, fejlecre csonkitva. Vagyis pont az egesz naplot torolne.
    """
    try:
        with path.open("x", encoding="utf-8", newline="") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            csv.writer(f).writerow(header)
    except FileExistsError:
        pass


def init_all() -> None:
    _ensure(config.LEADS_CSV, LEADS_HEADER)
    _ensure(config.SENT_CSV, SENT_HEADER)
    _ensure(config.DNC_CSV, DNC_HEADER)
    _ensure(config.BOUNCE_CSV, BOUNCE_HEADER)
    _ensure(config.REPLIES_CSV, REPLIES_HEADER)
    _ensure(config.REJECTS_CSV, REJECTS_HEADER)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with _locked(path, "r", fcntl.LOCK_SH) as f:
        return list(csv.DictReader(f))


def _append(path: Path, header: list[str], row: dict) -> None:
    _ensure(path, header)
    with _locked(path, "a", fcntl.LOCK_EX) as f:
        csv.DictWriter(f, fieldnames=header).writerow(row)


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.date.today().isoformat()


# ─── Leadek ────────────────────────────────────────────────────────────────

def leads() -> list[dict]:
    return _read(config.LEADS_CSV)


# ─── Kuldes-naplo ──────────────────────────────────────────────────────────

def sent_rows() -> list[dict]:
    return _read(config.SENT_CSV)


def record_send(email: str, stage: str, template: str, subject: str, account: str) -> None:
    email = email.strip().lower()
    _append(config.SENT_CSV, SENT_HEADER, {
        "ts": now(),
        "email": email,
        "domain": email.split("@")[-1] if "@" in email else "",
        "stage": stage,
        "template": template,
        "subject": subject,
        "account": account,
    })


def sent_today_count() -> int:
    d = today()
    return sum(1 for r in sent_rows() if (r.get("ts") or "").startswith(d))


def already_contacted() -> set[str]:
    """Minden cim, akinek valaha kuldtunk barmit."""
    return {(r.get("email") or "").strip().lower() for r in sent_rows()}


def contacted_domains() -> set[str]:
    """Minden CEG-domain, ahova valaha kuldtunk levelet.

    MIERT KELL A CIMEK MELLE A DOMAIN IS: az ember ritkan arrol a cimrol
    valaszol, amire irtunk. Egy `info@ceg.hu`-ra kuldott levelre tipikusan a
    sajat cimerol jon a valasz (`nagy.eszter@ceg.hu`) -- a `guards` viszont
    pontos cim-egyezest keresett, tehat az ilyen valaszt NEM LATTA.
    Kovetkezmeny: a rendszer follow-upot kuldott volna annak, aki mar
    valaszolt (merve 2026-09-03: ket valodi valasz maradt eszreveletlen).
    """
    return {(r.get("domain") or "").strip().lower()
            for r in sent_rows() if (r.get("domain") or "").strip()}


# ─── Suppression (DNC) ─────────────────────────────────────────────────────

def dnc_emails() -> set[str]:
    return {(r.get("email") or "").strip().lower() for r in _read(config.DNC_CSV)}


def add_to_dnc(email: str, reason: str, notes: str = "") -> bool:
    """Idempotens: ha mar bent van, nem duplikal. True, ha most kerult be."""
    email = email.strip().lower()
    if not email or email in dnc_emails():
        return False
    _append(config.DNC_CSV, DNC_HEADER, {
        "ts": now(), "email": email, "reason": reason, "notes": notes,
    })
    return True


# ─── Bounce-naplo ──────────────────────────────────────────────────────────

def bounce_rows() -> list[dict]:
    return _read(config.BOUNCE_CSV)


def record_bounce(email: str, reason: str, raw_subject: str = "") -> None:
    _append(config.BOUNCE_CSV, BOUNCE_HEADER, {
        "ts": now(), "email": email.strip().lower(),
        "reason": reason, "raw_subject": raw_subject[:200],
    })


# ─── SMTP-elutasitasok (a ramp bemenete) ───────────────────────────────────
# A `sender.py` eddig szamolta a sikertelen kuldeseket (`failed += 1`), de
# csak a sender.log-ba irta -- gepi olvasasra alkalmatlan formaban. A
# `deliverability.py` ezert fixen nullat adott at a rampnak, es a
# REJECT_RATE_ALERT kuszob soha nem sult el.
#
# MIERT SZAMIT: a bounce a cimlista oregedeserol szol, a reject viszont
# ROLUNK -- a Google rate limitje vagy policy-elutasitasa. Ez az a jel, ami
# IDOBEN szol, mielott komoly baj lesz. Napi 20 levelnel egy elutasitas meg
# latszik a logban; a 12. szakasz utan viszont mar nem olvassa ember a
# kimenetet, tehat gepi jelre van szukseg.

def reject_rows() -> list[dict]:
    return _read(config.REJECTS_CSV)


def record_reject(email: str, account: str, error: str) -> None:
    _append(config.REJECTS_CSV, REJECTS_HEADER, {
        "ts": now(), "email": email.strip().lower(),
        "account": account, "error": (error or "")[:300],
    })


def rejects_today_count() -> int:
    d = today()
    return sum(1 for r in reject_rows() if (r.get("ts") or "").startswith(d))


# ─── Valasz-naplo ──────────────────────────────────────────────────────────
# MIERT VAN ERRE SZUKSEG: a guards.py eddig beolvasta a valasz szoveget,
# mintat illesztett ra, majd ELDOBTA. Csak egy DNC-sor maradt belole. Emiatt
# a tervezett AI valasz-osztalyozasnak (ami a suppression tablat toltene)
# egyszeruen nem volt bemenete. Ez a fajl az a bemenet.
#
# A kuldo csak IR ide. Az osztalyozast a scraper vegzi, es a `classified`
# oszlopot is o tolti -- a kuldo sosem olvassa vissza.

def reply_rows() -> list[dict]:
    return _read(config.REPLIES_CSV)


def reply_msg_ids() -> set[str]:
    """A mar naplozott valaszok Message-ID-jai (dedup a guards ujrafutasa ellen)."""
    return {(r.get("msg_id") or "").strip() for r in reply_rows() if (r.get("msg_id") or "").strip()}


def record_reply(msg_id: str, email: str, subject: str, body: str) -> None:
    _append(config.REPLIES_CSV, REPLIES_HEADER, {
        "ts": now(),
        "msg_id": (msg_id or "").strip(),
        "email": email.strip().lower(),
        "subject": (subject or "")[:300],
        # 2000 karakter boven eleg az osztalyozashoz, es igy a fajl nem hizik
        # el az idezett elozmenyektol (a valaszok gyakran tartalmazzak a mi
        # sajat levelunket is, teljes egeszeben).
        "body": (body or "")[:2000],
        "classified": "",
    })


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)
    with _locked(config.LOG_FILE, "a", fcntl.LOCK_EX) as f:
        f.write(line + "\n")
