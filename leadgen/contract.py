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
    # A lead eredete es a kapcsolat megtalalasanak helye ket kulon adat.
    "lead_source_type",
    "lead_source_url",
    "contact_source_url",
    # Visszamenoleges alias: a `source_url` a lead eredetet jelenti. Uj kodban
    # a fenti, egyertelmu mezoket hasznald.
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

# ═══════════════════════════════════════════════════════════════════════════
# JOVAHAGYOTT KAMPANYOK -- amiknek a SZOVEGET a felhasznalo mar atnezte
#
# MIERT KELL EZ A LISTA: a `templates.py` CAMPAIGNS dict-jebe az agent VAZLAT
# sablonokat tesz (dead_dev, ops_pain), amiket a felhasznalonak at kell irnia
# a sajat hangjara -- ez a `templates.py a felhasznaloe` invarians.
#
# Csakhogy az exportot ez nem erdekelte: ami `ready` allapotu, az kiment.
# Vagyis amint egy uj engine leadet termelt, a VAZLAT szoveg azonnal eles
# levelkent ment volna ki, emberi jovahagyas nelkul.
#
# (Elesben latszott a 10. szakaszban: 2 lead `ready` allapotba kerult
# `ops_pain` kampannyal, es csak azert nem exportalodott, mert meg nem volt
# email cimuk. Az enrichment utan kiment volna.)
#
# ÚJ KAMPANY ELESITESE:
#   1. ird at a szoveget a templates.py-ban
#   2. nezd meg: cd cold-email-starter && python3 preview.py
#   3. vedd fel ide a kampany nevet
APPROVED_CAMPAIGNS = {
    "agency_partner",
    # "dead_dev",   <- a szoveg atirasa utan
    # "ops_pain",   <- a szoveg atirasa utan
}


# A kuldo do-not-contact.csv okai -> a DB suppression.reason ertekei.
# A ket taxonomia nem fedi egymast (INTEGRATION-PLAN.md, 4. ellentmondas):
# a `replied` NEM suppression, hanem allapot -- a valaszolo forro lead lehet,
# csak ember vegye at, ne a robot.
DNC_REASON_MAP = {
    "unsubscribe_request": "unsubscribe",
    "hard_bounce": "hard_bounce",
    "replied": None,  # nem suppression: companies.status = 'replied'
}
