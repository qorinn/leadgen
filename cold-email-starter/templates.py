#!/usr/bin/env python3
"""Email-sablonok.

EZT A FAJLT KELL ATIRNOD A SAJAT AJANLATODRA. A tobbi modul valtoztatas
nelkul mukodik.

Ket kemenyen megfizetett szabaly van beledrotozva:

1. FAJDALOM ELOSZOR, NE SZOLGALTATAS-LISTA.
   Az elso mondat a CIMZETT problemajarol szoljon, ne rolad. A
   "Bemutatkozom, mi egy X-szel foglalkozo ceg vagyunk" nyito a leggyorsabb
   ut a torlesig.

2. NE IGERJ "UTOLSO LEVELET", HA MEG KULDESZ.
   Ha a 2. follow-up azt irja "utoljara irok", a 3. level pedig megis
   megerkezik, a cimzett joggal haragszik meg. Vagy tartsd be, vagy ne igerd.
   (Ez nalunk valos ugyfelpanaszt eredmenyezett, ezert kulon szabaly.)

Minden sablon plain textet ad vissza. NE kuldj HTML-t cold emailben: rontja
a kezbesitest es sablonosnak nez ki.
"""
from __future__ import annotations

import config


def _greeting(lead: dict) -> str:
    """Ha nincs biztos nev, NE hagyj "[Nev]" placeholdert a szovegben.

    Valos incidens: egy sablonbol nyers "Kedves [Nev]!" ment ki, mert a nev
    csak a kep-alairasban volt. Inkabb semleges megszolitas.
    """
    name = (lead.get("contact_name") or "").strip()
    company = (lead.get("company") or "").strip()
    if name:
        return f"Kedves {name}!"
    if company:
        return f"Tisztelt {company} Csapata!"
    return "Tisztelt Cim!"


def _signature() -> str:
    return (
        f"Udvozlettel,\n"
        f"{config.FROM_NAME or '<A TE NEVED>'}\n"
        f"{config.REPLY_TO or '<EMAIL>'}"
    )


def _unsubscribe() -> str:
    """Kotelezo kilepesi lehetoseg. Ne rejtsd el, ne tedd korulmenyesse.

    Az EU-ban a hideg B2B megkereses jogalapja jellemzoen a jogos erdek
    (GDPR 6(1)(f)), aminek FELTETELE a konnyu tiltakozas. Ez a mondat nem
    opcionalis, es a rendszer automatikusan DNC-be teszi, aki valaszol ra.
    """
    return "Ha nem szeretne tobb levelet, eleg annyit visszairnia, hogy \"nem\", es torlom a listarol."


def cold(lead: dict) -> dict:
    """1. level. Rovid, konkret, egyetlen kerdessel zarul."""
    industry = (lead.get("industry") or "a szakteruleten").strip()
    company = (lead.get("company") or "Onoknel").strip()

    subject = "Kerdes a(z) {c} kapcsan".format(c=company)
    body = f"""{_greeting(lead)}

<IDE IRD A KONKRET FAJDALMAT, amit a(z) {industry} teruleten latsz. Egy-ket
mondat, konkretan, szam nelkul is eleg. Pelda-szerkezet: "Amit ilyenkor a
legtobb {industry} vallalkozasnal latok, hogy X miatt elvesznek erdeklodok.">

<IDE IRD, MIT CSINALSZ EZZEL. Egy mondat, tulzas nelkul.>

Ha erdekli, kuldok egy rovid, konkret peldat arra, hogy {company} eseteben ez
hogy nezne ki. Erdekli?

{_unsubscribe()}

{_signature()}"""
    return {"subject": subject, "body": body, "template": "cold"}


def follow_up_1(lead: dict) -> dict:
    """2. level, az eredeti utan FU1_DELAY_DAYS nappal.

    ONALLO level: NE hivatkozz az elozore ("ahogy irtam"), mert a cimzett
    tobbnyire NEM latta (spam, szures). Ugy fogalmazz, mintha ez lenne az elso.
    """
    company = (lead.get("company") or "Onoknel").strip()
    subject = "Kerdes a(z) {c} kapcsan".format(c=company)
    body = f"""{_greeting(lead)}

<UJ SZOG, ne ismeteld az elso levelet. Pelda: egy rovid, konkret eredmeny
vagy egy gyakori felreertes tisztazasa.>

Ha most nem aktualis, semmi gond, csak jelezze.

{_unsubscribe()}

{_signature()}"""
    return {"subject": subject, "body": body, "template": "follow_up_1"}


def follow_up_2(lead: dict) -> dict:
    """3. level, az EREDETI utan FU2_DELAY_DAYS nappal.

    Ez a szekvencia utolso darabja. FIGYELEM: ha kesobb megis kuldesz
    utankovetest, akkor ITT NE IRD, hogy "utoljara irok". A jelenlegi szoveg
    szandekosan nem igeri ezt.
    """
    subject = "Egy rovid gondolat"
    body = f"""{_greeting(lead)}

<EGY HASZNOS GONDOLAT ELLENSZOLGALTATAS NELKUL. Valami, amit akkor is
hasznalhat, ha sosem lesz ugyfeled. Ez az, ami valaszt szokott hozni.>

Ha barmikor aktualis lesz, keressen nyugodtan.

{_unsubscribe()}

{_signature()}"""
    return {"subject": subject, "body": body, "template": "follow_up_2"}


# A letra sorrendje. Uj fokot ide vegy fel, es allitsd be a napokat a
# config.py-ban. Minden fok az EREDETI cold datumatol szamit.
LADDER = [
    ("cold", 0, cold),
    ("follow_up_1", config.FU1_DELAY_DAYS, follow_up_1),
    ("follow_up_2", config.FU2_DELAY_DAYS, follow_up_2),
]
