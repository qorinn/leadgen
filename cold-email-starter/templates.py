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


def _signature_lines(greeting: str) -> str:
    """Alairas a .env-bol. Ami nincs beallitva, az a SORAVAL EGYUTT kimarad.

    Miert nem drotozzuk be: a nev, a cim, a telefonszam es a weboldal
    peldany-specifikus adat. A .env-ben van a helyuk (az nincs commitolva),
    nem egy verziokezelt forrasfajlban.

    A telefonszam es a weboldal 2026-08-21-en kerult be, felhasznaloi kerésre:
    egy elerheto ember levele hitelesebb, mint egy ceg nevtelen megkeresese.
    """
    lines = [
        greeting,
        config.FROM_NAME or "<A TE NEVED>",
        config.REPLY_TO or "<EMAIL>",
    ]
    if config.SIGNATURE_PHONE:
        lines.append(config.SIGNATURE_PHONE)
    if config.SIGNATURE_URL:
        # Sema nelkul: a levelezok igy is kattinthatova teszik, viszont a
        # "https://" nelkuli alak emberi alairasnak nez ki, nem hirdetesnek.
        lines.append(config.SIGNATURE_URL.replace("https://", "").replace("http://", "").rstrip("/"))
    return "\n".join(lines)


def _signature() -> str:
    return _signature_lines("Üdvözlettel,")


def _signature_informal() -> str:
    return _signature_lines("Üdv,")


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
    """1. level. Egy tagmondat rolad, utana rolunk, a vegen egy kerdes.

    A mondatok kotoszoval es gondolatjellel fuznek ossze (nem kulon
    bekezdesenkent kijelentes), mert ember igy ir egy idegennek -- a
    felsorolas-szeru, izolalt mondatok a leggyorsabb ut a robot-benyomashoz.
    """
    body = f"""{_greeting_informal(lead)}

Fejlesztő vagyok, és sokat dolgozom ügynökségek mögött alvállalkozóként — ők viszik a stratégiát, a hirdetést, a kreatívot, én meg a kódot.

{_personalization(lead, "Körülnéztem nálatok, és a hirdetéskezelés meg a stratégia a fő erősségetek — fejlesztést viszont nem láttam a szolgáltatások közt.")}

Szóval inkább csak rákérdeznék: van most olyan fejlesztő partneretek, akit be tudtok vonni, ha egy ügyfélnek weboldal vagy egyedi rendszer kell?

{_unsubscribe()}

{_signature_informal()}"""
    return {"subject": "Kivel fejlesztetek?", "body": body, "template": "cold"}


def agency_follow_up_1(lead: dict) -> dict:
    """2. level, az eredeti utan FU1_DELAY_DAYS nappal.

    ONALLO level: NE hivatkozz az elozore ("ahogy irtam"), mert a cimzett
    tobbnyire NEM latta (spam, szures). Ugy fogalmazz, mintha ez lenne az elso
    -- ezert van ujra bemutatkozas, nem "megint en vagyok" nyitas.
    Uj szog: nem a partner LETE a kerdes, hanem a kapacitasa. A "nem X, hanem Y"
    szembeallitas helyett szemelyes megfigyeleskent fogalmazva ("amit latok"),
    mert a puszta ellentetpar tipikus copywriter-minta, nem elo beszed.
    """
    body = f"""{_greeting_informal(lead)}

Fejlesztő vagyok, és gyakran találkozom ezzel a helyzettel ügynökségeknél: nem az a baj, hogy nincs fejlesztő partnerük, hanem hogy épp nem ér rá senki. Ilyenkor az ügyfél vagy vár, vagy máshova viszi a projektet.

Nálatok is előfordul ez?

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

Fejlesztőként ez a leggyakoribb tapasztalatom ügynökségi projekteknél: a munka szinte sosem technikai okból csúszik, hanem mert a tartalom — szövegek, képek, adatok — mindig később készül el, mint maga a felület.

Ha ezt előre jelzitek az ügyfeleknek, és kértek tőlük egy konkrét tartalomlistát határidővel már a projekt legelején, azzal többet nyertek, mint bármelyik technikai döntéssel.

Ha valaha aktuális lesz egy fejlesztő partner, szóljatok nyugodtan.

{_unsubscribe()}

{_signature_informal()}"""
    return {"subject": "Egy tapasztalat ügynökségi projektekről", "body": body, "template": "follow_up_2"}


# ─── Kampanyok ─────────────────────────────────────────────────────────────
# A terv "Offer arbitration" fejezete szerint egy ceg EGYETLEN kampanyba kerul,
# es engine-enkent mas a CTA. A sender.build_plan a lead `campaign` mezoje
# alapjan valaszt innen sablonkeszletet.
#
# FONTOS: minden kampany ugyanazt a harom `template` azonositot adja vissza
# ("cold" / "follow_up_1" / "follow_up_2"), mert a sender._stage_of ezekbol
# vezeti le a szekvencia-fokot. Ez helyes: egy cim egy kampanyhoz tartozik,
# tehat nincs utkozes. Uj kampanyhoz UJ FUGGVENYEK kellenek, nem uj azonositok.
#
# Uj kampany felvetele: irj harom fuggvenyt, es vedd fel ide egy sorral.
CAMPAIGNS: dict[str, tuple] = {
    "agency_partner": (agency_cold, agency_follow_up_1, agency_follow_up_2),
}

DEFAULT_CAMPAIGN = "agency_partner"


def for_campaign(name: str | None) -> tuple:
    """(cold, follow_up_1, follow_up_2) az adott kampanyhoz.

    Ismeretlen vagy ures ertek eseten a DEFAULT_CAMPAIGN-re esik vissza --
    NEM dob hibat. Indok: egy elgepelt kampanynev miatt ne alljon meg a
    kikuldes, es ne maradjon ki egy lead. A visszaeses a naploban latszik
    (a sender kiirja, melyik sablont hasznalja).
    """
    return CAMPAIGNS.get((name or "").strip(), CAMPAIGNS[DEFAULT_CAMPAIGN])


# Visszafele kompatibilitas: a modul szintu nevek az alapertelmezett kampanyra
# mutatnak, hogy a LADDER es barmely kulso hivas valtozatlanul mukodjon.
cold, follow_up_1, follow_up_2 = CAMPAIGNS[DEFAULT_CAMPAIGN]


# A letra sorrendje. Uj fokot ide vegy fel, es allitsd be a napokat a
# config.py-ban. Minden fok az EREDETI cold datumatol szamit.
LADDER = [
    ("cold", 0, cold),
    ("follow_up_1", config.FU1_DELAY_DAYS, follow_up_1),
    ("follow_up_2", config.FU2_DELAY_DAYS, follow_up_2),
]
