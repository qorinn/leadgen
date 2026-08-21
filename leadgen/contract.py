#!/usr/bin/env python3
"""A KET RENDSZER KOZTI KONTRAKTUS. Egyetlen fajl a hatar: leads.csv.

Miert van kulon modul egy listanak: a scraper Python 3.12-n fut sajat venv-ben,
a kuldo a rendszer 3.9.6-jan, stdlib-only. A ket oldal NEM importalhatja
egymast. Ezert a fejlec ket helyen van leirva:

    itt                          -> leadgen/contract.py  (az iro oldal)
    cold-email-starter/store.py  -> LEADS_HEADER         (az olvaso oldal)

Ket masolat = elcsuszas-kockazat, ezert a tests/test_contract.py beolvassa a
store.py-t es osszehasonlitja ezzel. Ha valaki csak az egyik oldalt modositja,
a teszt elhasal -- nem az eles futas.
"""
from __future__ import annotations

# A kuldo eredeti mezoi. EZEKET NE NEVEZD AT: a templates.py nev szerint olvassa.
_ORIGINAL = ["email", "company", "contact_name", "website", "industry", "city", "notes"]

# A scraper altal hozzaadott mezok.
_ADDED = [
    # Melyik sablonkeszlet rendereljen. A sender.build_plan ebbol valaszt.
    # Ures / ismeretlen ertek -> a templates.DEFAULT_CAMPAIGN.
    "campaign",
    # Az evidence-groundolt nyitomondat. URES -> a sablon sajat mondatara esik
    # vissza, tehat a lead NEM vesz el, csak nem lesz szemelyre szabva.
    "personalization",
    # 0.4 JOGI MINIMUM: honnan van az adat. Ha valaki rakerdez, meg kell tudni
    # mondani. Ezert az exportalo NEM ir ki olyan sort, ahol ez ures.
    "source_url",
    # Signal-frissesseg (ISO datum). Emberi atnezeshez es hibakereseshez.
    "scraped_at",
    # A DB UUID-je. A kuldo nem hasznalja; a feedback email szerint joinol.
    # Hibakereseshez viszont aranyat er: egy leads.csv sorbol azonnal
    # megtalalhato a ceg a DB-ben.
    "company_id",
    # A szemelyre szolo leiratkozo link, TELJES URL-kent (nem csak token).
    # Miert a teljes URL: igy a templates.py-nak nem kell tudnia sem a
    # domaint, sem az utvonalat -- egyszeruen kiirja, amit kap. Ha a mezo
    # URES, a sablon a "valaszolj, hogy stop" mondatra esik vissza.
    "unsub_url",
]

LEADS_HEADER = _ORIGINAL + _ADDED

# A kuldo szekvencia-fokai. Ezeket a sender._stage_of a sent.csv `template`
# oszlopabol olvassa vissza -- ATNEVEZESUK MINDEN KORABBI LEADET VISSZAVET
# egy fokra, es ujra kikuldene nekik a levelet.
STAGES = ("cold", "follow_up_1", "follow_up_2")

# A kuldo do-not-contact.csv okai -> a DB suppression.reason ertekei.
# A ket taxonomia nem fedi egymast (INTEGRATION-PLAN.md, 4. ellentmondas):
# a `replied` NEM suppression, hanem allapot -- a valaszolo forro lead lehet,
# csak ember vegye at, ne a robot.
DNC_REASON_MAP = {
    "unsubscribe_request": "unsubscribe",
    "hard_bounce": "manual_block",
    "replied": None,  # nem suppression: companies.status = 'replied'
}
