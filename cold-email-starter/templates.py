#!/usr/bin/env python3
"""Email-sablonok.

EZT A FAJLT KELL ATIRNOD A SAJAT AJANLATODRA. A tobbi modul valtoztatas
nelkul mukodik.

Jelenlegi allapot: az UGYNOKSEGI PARTNER (8.1) kampany szovegei aktivak.
Az integracios terv 2. szakaszaban ezek egy CAMPAIGNS dict-be kerulnek, es
mellejuk jonnek a tobbi kampany sablonjai (dead_dev, ops_pain, ...). Addig
a `cold` / `follow_up_1` / `follow_up_2` nev az ugynoksegi valtozatra mutat.

FIGYELEM a `template` azonositokra: a "cold" / "follow_up_1" / "follow_up_2"
sztringeket NE nevezd at. A sender._stage_of ezekbol vezeti le, hol tart a
szekvencia; atnevezes utan minden korabban megkeresett lead visszaesik egy
fokra es UJRA KAP levelet.

Ket kemenyen megfizetett szabaly van beledrotozva:

1. FAJDALOM ELOSZOR, NE SZOLGALTATAS-LISTA.
   Az elso mondat a CIMZETT problemajarol szoljon, ne rolad. A
   "Bemutatkozom, mi egy X-szel foglalkozo ceg vagyunk" nyito a leggyorsabb
   ut a torlesig.
   (Az ugynoksegi kampanyban egyetlen tagmondat mondja meg, mi vagy -- e
   nelkul a zaro kerdes ertelmezhetetlen. Utana azonnal roluk szol.)

2. NE IGERJ "UTOLSO LEVELET", HA MEG KULDESZ.
   Ha a 2. follow-up azt irja "utoljara irok", a 3. level pedig megis
   megerkezik, a cimzett joggal haragszik meg. Vagy tartsd be, vagy ne igerd.
   (Ez nalunk valos ugyfelpanaszt eredmenyezett, ezert kulon szabaly.)

Minden sablon plain textet ad vissza. NE kuldj HTML-t cold emailben: rontja
a kezbesitest es sablonosnak nez ki.

A LEVELEK SZOVEGE EKEZETES -- ez szandekos elteres a kod-konvenciotol.
A kommentek es a docstringek ASCII-ban maradnak, de a cimzettnek meno
szoveg ekezet nelkul igenytelen es gepies benyomast keltene. Ellenorizve:
az EmailMessage a targyat RFC 2047-tel kodolja, a torzset UTF-8-cal kuldi.
"""
from __future__ import annotations

import config


def _greeting(lead: dict) -> str:
    """Formalis megszolitas. Ha nincs biztos nev, NE hagyj "[Nev]" placeholdert.

    Valos incidens: egy sablonbol nyers "Kedves [Nev]!" ment ki, mert a nev
    csak a kep-alairasban volt. Inkabb semleges megszolitas.
    """
    name = (lead.get("contact_name") or "").strip()
    company = (lead.get("company") or "").strip()
    if name:
        return f"Kedves {name}!"
    if company:
        return f"Tisztelt {company} Csapata!"
    return "Tisztelt Cím!"


def _greeting_informal(lead: dict) -> str:
    """Szakmai, tegezo megszolitas (ugynoksegek, fejlesztok).

    Ugyanaz a vedelem, mint a _greeting()-nel: nev nelkul semleges tobbes
    szamu megszolitas, soha nem marad nyers placeholder a szovegben.
    """
    name = (lead.get("contact_name") or "").strip()
    if name:
        first = name.split()[-1] if "," not in name else name.split(",")[0]
        return f"Szia {first}!"
    return "Sziasztok!"


def _personalization(lead: dict, fallback: str) -> str:
    """A scraper altal generalt, bizonyitekhoz kotott nyitomondat.

    Ha a mezo ures vagy meg nem letezik (a 2. szakasz elott igy van), a
    sablon a fallback mondatra esik vissza -- soha nem marad ures bekezdes.
    """
    text = (lead.get("personalization") or "").strip()
    return text or fallback


def _signature() -> str:
    return (
        f"Üdvözlettel,\n"
        f"{config.FROM_NAME or '<A TE NEVED>'}\n"
        f"{config.REPLY_TO or '<EMAIL>'}"
    )


def _signature_informal() -> str:
    return (
        f"Üdv,\n"
        f"{config.FROM_NAME or '<A TE NEVED>'}\n"
        f"{config.REPLY_TO or '<EMAIL>'}"
    )


def _unsubscribe() -> str:
    """Kotelezo kilepesi lehetoseg. Ne rejtsd el, ne tedd korulmenyesse.

    Az EU-ban a hideg B2B megkereses jogalapja jellemzoen a jogos erdek
    (GDPR 6(1)(f)), aminek FELTETELE a konnyu tiltakozas. Ez a mondat nem
    opcionalis, es a rendszer automatikusan DNC-be teszi, aki valaszol ra.

    MIERT "stop" ES NEM "nem": a guards.UNSUB_PATTERNS a valasz szovegen
    illeszt. A puszta "nem" szo magyar szovegben szinte minden valaszban
    elofordul, ezert egy erdeklodo valasz is veglegesen leiratkozaskent
    kerulne suppressionbe. A "stop" egyertelmu es ritka -- a leiratkozas
    ugyanolyan konnyu marad, de a jelzes nem tevesztheto ossze mas
    tartalommal. (Integracios terv, 5. ellentmondas.)
    """
    return "Ha nem szeretnél több levelet, írd vissza, hogy „stop”, és töröllek a listáról."


# ─── Ugynoksegi partner kampany (8.1) ──────────────────────────────────────
# Hangnem: kollegialis, nem ertekesitoi. Ez NEM ugyfelszerzes, hanem
# partnerkereses. Mindharom level KERDESSEL zarul, nem ajanlattal: egy
# kerdesre konnyu valaszolni, egy ajanlatra donteni kell.

def agency_cold(lead: dict) -> dict:
    """1. level. Egy tagmondat rolad, utana rolunk, a vegen egy kerdes."""
    body = f"""{_greeting_informal(lead)}

Webes és mobilfejlesztéssel foglalkozom, jellemzően ügynökségek mögött dolgozom kivitelezőként.

{_personalization(lead, "Láttam, hogy nálatok a hirdetés és a stratégia az erősség, fejlesztést viszont nem hirdettek szolgáltatásként.")}

Kivel dolgoztok most, ha egy ügyfélnek weboldal vagy egyedi fejlesztés kell?

{_unsubscribe()}

{_signature_informal()}"""
    return {"subject": "Kivel fejlesztetek?", "body": body, "template": "cold"}


def agency_follow_up_1(lead: dict) -> dict:
    """2. level, az eredeti utan FU1_DELAY_DAYS nappal.

    ONALLO level: NE hivatkozz az elozore ("ahogy irtam"), mert a cimzett
    tobbnyire NEM latta (spam, szures). Ugy fogalmazz, mintha ez lenne az elso.
    Uj szog: nem a partner LETE a kerdes, hanem a kapacitasa.
    """
    body = f"""{_greeting_informal(lead)}

A legtöbb ügynökségnél nem az a kérdés, van-e fejlesztő partner, hanem hogy éppen ráér-e. Amikor nem, az ügyfél vagy vár, vagy elviszi a munkát máshova.

Előfordul ez nálatok?

{_unsubscribe()}

{_signature_informal()}"""
    return {"subject": "Amikor nincs szabad fejlesztő", "body": body, "template": "follow_up_1"}


def agency_follow_up_2(lead: dict) -> dict:
    """3. level, az EREDETI utan FU2_DELAY_DAYS nappal.

    Ez a szekvencia utolso darabja. FIGYELEM: ha kesobb megis kuldesz
    utankovetest, akkor ITT NE IRD, hogy "utoljara irok". A jelenlegi szoveg
    szandekosan nem igeri ezt.

    Hasznos gondolat ellenszolgaltatas nelkul: valami, amit akkor is
    hasznalhat, ha sosem lesz belole kozos munka. Ez az, ami valaszt hoz.
    """
    body = f"""{_greeting_informal(lead)}

Egy tapasztalat ügynökségi projektekből, ami akkor is hasznos, ha sosem dolgozunk együtt: a fejlesztések nálam a leggyakrabban nem technikai okból csúsznak, hanem azért, mert a tartalom (szövegek, képek, adatlisták) később készül el, mint a felület.

Ha az ügyfélnek már a projekt legelején adtok egy konkrét tartalomlistát határidővel, az általában többet ment a határidőből, mint bármelyik technikai döntés.

Ha bármikor aktuális lesz egy fejlesztő partner, keressetek nyugodtan.

{_unsubscribe()}

{_signature_informal()}"""
    return {"subject": "Egy tapasztalat ügynökségi projektekről", "body": body, "template": "follow_up_2"}


# ─── Az aktiv keszlet ──────────────────────────────────────────────────────
# A 2. szakaszban ezek helyere egy CAMPAIGNS dict kerul, es a sender a lead
# `campaign` mezoje alapjan valaszt. Addig az ugynoksegi kampany az aktiv.
cold = agency_cold
follow_up_1 = agency_follow_up_1
follow_up_2 = agency_follow_up_2


# A letra sorrendje. Uj fokot ide vegy fel, es allitsd be a napokat a
# config.py-ban. Minden fok az EREDETI cold datumatol szamit.
LADDER = [
    ("cold", 0, cold),
    ("follow_up_1", config.FU1_DELAY_DAYS, follow_up_1),
    ("follow_up_2", config.FU2_DELAY_DAYS, follow_up_2),
]
