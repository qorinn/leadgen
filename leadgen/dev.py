#!/usr/bin/env python3
"""Fejlesztoi teszt-adat. NEM eles adat, es sosem szabad kikuldeni.

Miert van ra szukseg: a 2. es 3. szakasz (a rendszerhatar mindket iranya) a
scrapeles ELOTT keszul el, mert az integracio a kockazatos resz, nem a
scrapeles. Kezzel beszurt sorokkal viszont teljes egeszeben tesztelheto.

BIZTONSAG: minden teszt-cim `.invalid` vegzodesu. Ez az RFC 2606 altal
fenntartott TLD, ami garantaltan sosem letezik -- tehat egy velelten `--live`
futas sem tudna valakinek tenylegesen levelet kuldeni. Az exportalo ezen
kivul hangosan figyelmeztet, ha ilyen cim van a listaban.
"""
from __future__ import annotations

from . import db

SEED_SOURCE_TYPE = "dev_seed"

_SEEDS = [
    {
        "company_name": "Zöld Nyíl Marketing Kft.",
        "name_key": "zold nyil marketing",
        "domain": "https://zoldnyil.invalid",
        "normalized_domain": "zoldnyil.invalid",
        "industry": "online marketing",
        "city": "Budapest",
        "signal_summary": "PPC + social, fejlesztést nem hirdet; 8 fős csapat",
        "personalization": "A hirdetéskezelés és a közösségi média nálatok saját "
                           "csapattal megy, fejlesztést viszont nem hirdettek.",
        "signal_score": 45,
        "contacts": [
            ("hello@zoldnyil.invalid", None, "generic", "https://zoldnyil.invalid/kapcsolat"),
        ],
    },
    {
        "company_name": "Kapocs Kreatív Bt.",
        "name_key": "kapocs kreativ",
        "domain": "https://www.kapocskreativ.invalid",
        "normalized_domain": "kapocskreativ.invalid",
        "industry": "reklámügynökség",
        "city": "Szeged",
        "signal_summary": "Branding + kreatív; portfólióban weboldalak, de fejlesztést nem árul",
        "personalization": "A portfóliótokban több weboldal is szerepel, "
                           "fejlesztést viszont nem hirdettek szolgáltatásként.",
        "signal_score": 60,
        # KET kapcsolat szandekosan: a domain lock miatt csak EGY mehet ki,
        # es a `personal` tipusnak kell nyernie a `generic` felett.
        "contacts": [
            ("info@kapocskreativ.invalid", None, "generic", "https://kapocskreativ.invalid/kapcsolat"),
            ("nagy.eszter@kapocskreativ.invalid", "Nagy Eszter", "personal", "https://kapocskreativ.invalid/csapat"),
        ],
    },
    {
        "company_name": "Delta PPC Ügynökség Kft.",
        "name_key": "delta ppc ugynokseg",
        "domain": "deltappc.invalid",
        "normalized_domain": "deltappc.invalid",
        "industry": "PPC ügynökség",
        "city": "Debrecen",
        "signal_summary": "Google Ads fókusz; fejlesztő pozíciót hirdet ← erős bónusz signal",
        "personalization": "",   # SZANDEKOSAN URES: a sablon-fallbacket teszteli
        "signal_score": 70,
        "contacts": [
            ("info@deltappc.invalid", None, "generic", "https://deltappc.invalid/impresszum"),
        ],
    },
]


def seed() -> int:
    """Idempotens: ujra futtatva nem duplikal (a normalized_domain UNIQUE)."""
    created = 0
    with db.connect() as conn, conn.cursor() as cur:
        for item in _SEEDS:
            cur.execute(
                """
                insert into companies (company_name, name_key, domain, normalized_domain,
                                       industry, city, signal_summary, personalization,
                                       signal_score, campaign, best_offer, status)
                     values (%(company_name)s, %(name_key)s, %(domain)s, %(normalized_domain)s,
                             %(industry)s, %(city)s, %(signal_summary)s, %(personalization)s,
                             %(signal_score)s, 'agency_partner', 'partner', 'ready')
                -- A companies_domain_uniq RESZLEGES index (`where normalized_domain
                -- is not null`), ezert az ON CONFLICT celnak meg kell ismetelnie
                -- ugyanazt a feltetelt -- kulonben a Postgres nem talalja az indexet.
                -- Minden jovobeli companies-upsertnel ugyanez a szabaly.
                on conflict (normalized_domain) where normalized_domain is not null do nothing
                  returning id
                """,
                item,
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("select id from companies where normalized_domain = %s",
                            (item["normalized_domain"],))
                row = cur.fetchone()
            else:
                created += 1
            company_id = row["id"]

            cur.execute(
                """
                insert into sources (company_id, source_type, source_url, raw_signal)
                     values (%s, %s, %s, '{"note": "fejlesztoi teszt-adat"}'::jsonb)
                on conflict (source_type, source_url) do nothing
                """,
                (company_id, SEED_SOURCE_TYPE, item["domain"]),
            )
            for email, name, email_type, source_url in item["contacts"]:
                cur.execute(
                    """
                    insert into contacts (company_id, email, name, email_type,
                                          local_check, source_url)
                         values (%s, %s, %s, %s, 'pass', %s)
                    on conflict (email) do nothing
                    """,
                    (company_id, email, name, email_type, source_url),
                )
    return created


def clear_seed() -> int:
    """Minden teszt-ceg torlese. A kapcsolodo sorok ON DELETE CASCADE-del mennek."""
    return db.execute(
        """
        delete from companies
         where id in (select company_id from sources where source_type = %s)
        """,
        (SEED_SOURCE_TYPE,),
    )
