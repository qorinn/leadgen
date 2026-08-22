#!/usr/bin/env python3
"""Idofuggo signal-pontszam: a lecsengesi gorbe.

A terv "Lecsenges" fejezete (2560-2620). A gondolat egyszeru:

    egy 3 honapos allashirdetes mar nem fajdalom -- betoltottek
    egy 3 honapos elavult weboldal viszont MEG MINDIG elavult

Vagyis nem minden signal romlik egyforma sebesseggel. Ket gorbe van:

  MEREDEK -- ami gyorsan avul: allashirdetes, hirdetesi kampany,
             friss negativ ertekeles, kiallitas
  LAPOS   -- ami nem avul: elavult weboldal (7.5), webshop platform (7.5),
             arbevetel (7.1), halott fejleszto (8.2)

MIERT SZAMIT EZ A GYAKORLATBAN (a terv szo szerint):
"A napi futas nem »a legjobb leadeket« adja vissza, hanem A MOST
LEGIDOSZERUBB leadeket. Ez sokkal jobb outreach utemezes: minden nap van
nehany friss, indokolt megkereses, ahelyett hogy egyszer kikuldenel 500
levelet es utana nem lenne semmi."

════════════════════════════════════════════════════════════════════════════
MA MIERT NEM VALTOZTAT SEMMIT

A jelenlegi ket signalunk -- 8.1 (ugynokseg) es 8.2 (halott fejleszto) --
MINDKETTO a lapos gorben van, tehat 180 napig 1.0 a szorzo. A lecsenges
gyakorlati hatasa most nulla.

Akkor miert epult meg most? Mert a 9. szakasz elso signalja az ALLASHIRDETES,
ami a meredek gorben van -- es akkor mar nem lehet visszamenoleg atrendezni
a sorrendet. A szerkezet most keszen all, kesobb csak fel kell venni az uj
forrast a `MEREDEK` halmazba.
"""
from __future__ import annotations

# ─── A meredek gorbe (terv 2560-2570) ──────────────────────────────────────
# (napok felso hatara, szorzo). Az elso illeszkedo sor nyer.
MEREDEK_GORBE = (
    (7, 1.0),
    (30, 0.8),
    (90, 0.5),
    (180, 0.2),
)

# ─── A lapos gorbe ─────────────────────────────────────────────────────────
# Ami strukturalis, az sokaig igaz marad. Fel evig teljes ertek, utana
# lassu csokkenés -- de sosem nullazodik, mert egy elavult weboldal
# tegnap es ma is ugyanolyan elavult.
LAPOS_GORBE = (
    (180, 1.0),
    (365, 0.9),
    (730, 0.7),
)
LAPOS_MINIMUM = 0.5

# Melyik `sources.source_type` melyik gorbén van.
# Ami nem szerepel itt, az a LAPOS gorbet kapja -- ez a biztonsagos
# alapertelmezes: inkabb tartsuk meg a leadet, mint hogy csendben eltunjon.
MEREDEK_FORRASOK = {
    "profession",        # allashirdetes (9. szakasz)
    "job_ad",
    "meta_ads",          # aktiv hirdetesi kampany
    "review",            # friss negativ ertekeles
    "expo",              # kiallitas
}


def szorzo(kor_napokban: float, source_type: str = "") -> float:
    """A signal eletkorabol a pontszam-szorzo."""
    if kor_napokban < 0:
        kor_napokban = 0.0

    if source_type in MEREDEK_FORRASOK:
        for hatar, ertek in MEREDEK_GORBE:
            if kor_napokban <= hatar:
                return ertek
        return 0.0          # 180 nap felett a gyors signal ertektelen

    for hatar, ertek in LAPOS_GORBE:
        if kor_napokban <= hatar:
            return ertek
    return LAPOS_MINIMUM    # a strukturalis signal sosem nullazodik


def aktualis_pont(alappont: float, kor_napokban: float,
                  source_type: str = "") -> float:
    return round(float(alappont or 0) * szorzo(kor_napokban, source_type), 2)


# ─── SQL-oldali valtozat ───────────────────────────────────────────────────
# Az export a `signal_score` szerint rendez, es a rendezes SQL-ben tortenik.
# Ha a lecsengest Pythonban szamolnank, at kellene rendezni az egesz
# lekerdezest -- ezert ugyanaz a gorbe SQL-kifejezeskent is megvan.
#
# FIGYELEM: ha a fenti tablazatokat modositod, EZT IS modositsd. A
# tests/test_scoring.py osszehasonlitja a ket oldalt, tehat elcsuszas eseten
# a teszt elhasal -- nem az eles futas.

def sql_szorzo(kor_kifejezes: str, forras_kifejezes: str) -> str:
    """A szorzo SQL-kifejezeskent.

    `kor_kifejezes`   -- ami napokban adja a signal korat
    `forras_kifejezes`-- ami a source_type-ot adja
    """
    meredek = " ".join(
        f"when {kor_kifejezes} <= {hatar} then {ertek}" for hatar, ertek in MEREDEK_GORBE)
    lapos = " ".join(
        f"when {kor_kifejezes} <= {hatar} then {ertek}" for hatar, ertek in LAPOS_GORBE)
    forrasok = ", ".join(f"'{f}'" for f in sorted(MEREDEK_FORRASOK))
    return (
        f"case when {forras_kifejezes} in ({forrasok}) "
        f"then (case {meredek} else 0.0 end) "
        f"else (case {lapos} else {LAPOS_MINIMUM} end) end"
    )
