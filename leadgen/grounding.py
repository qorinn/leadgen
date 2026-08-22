#!/usr/bin/env python3
"""Evidence grounding — a rendszer hitelessegi vedoretege.

    NINCS BIZONYITEK  ->  NINCS ALLITAS  ->  NINCS EMAIL

MIERT KULON MODUL EGY STRING-KERESESNEK: mert ez a terv szerint "a
legveszelyesebb pont az egesz pipeline-ban". Ha az AI KITALAL egy tenyt a
cegrol, es az bekerul az emailbe, a hatas nem semleges, hanem NEGATIV:

    AI kimenet:  "Lattam, hogy harom telephelyen dolgoztok..."
    Valosag:     egy telephely van; az AI a "tobb megyeben vallalunk munkat"
                 mondatbol kovetkeztetett

Egy generikus email a rosszabb esetben unalmas. Egy magabiztosan TEVES
szemelyre szabott email hiteltelenne tesz -- es a cimzett azonnal latja,
hogy gepi.

MIERT INGYEN VAN: ez NEM AI-hivas. Sima string-kereses a forrasszovegben.
Nulla plusz koltseg, nulla plusz kesleltetes. A terv szerint "az egyik
legjobb ar/ertek aranyu elem".

────────────────────────────────────────────────────────────────────────────
AMIT NORMALIZALUNK, ES AMIT NEM

Normalizalunk: szokoz (sortores, dupla szokoz), kis/nagybetu.
    Ezek formazasi kulonbsegek -- ugyanaz a mondat maskepp tordelve NEM
    hallucinacio. Ha ezt szigoruan vennenk, minden modell megbukna egy
    sortoresen.

NEM normalizalunk: ekezet, ragozas, szorend, szinonima.
    "tablazatban vezeti" != "Excelben vezeti". Az atfogalmazas mar
    kovetkeztetes, nem idezet -- pontosan az, amit ki akarunk szurni.

A RESZLEGES EGYEZES (az elso 40 karakter) a terv kifejezett engedmenye:
a modellek gyakran hozzatoldanak egy fel tagmondatot az idezet vegehez.
Az ELEJE viszont pontos szokott lenni -- ha az stimmel, a claim megall.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_WS = re.compile(r"\s+")

# A terv engedmenye: ennyi karakternyi eleje-egyezes mar elfogadhato.
RESZLEGES_HOSSZ = 40

# Ennel rovidebb idezet nem bizonyit semmit: egy 8 karakteres toredek
# ("Excelben") szinte barmilyen szovegben megtalalhato, tehat atmenne az
# ellenorzesen anelkul, hogy barmit is alatamasztana.
MIN_IDEZET = 15


def fold(szoveg: str) -> str:
    """Szokoz- es kisbetu-normalizalas. Semmi mas."""
    return _WS.sub(" ", (szoveg or "")).strip().lower()


def idezet_ervenyes(idezet: str, forras: str) -> tuple[bool, str]:
    """Megtalalhato-e az idezet a forrasban? (ervenyes, indok)."""
    q = fold(idezet)
    f = fold(forras)
    if not q:
        return False, "ures idezet"
    if len(q) < MIN_IDEZET:
        # Nem hallucinacio, de nem is bizonyitek.
        return False, f"tul rovid idezet ({len(q)} karakter, minimum {MIN_IDEZET})"
    if not f:
        return False, "nincs forrasszoveg az ellenorzeshez"
    if q in f:
        return True, ""
    eleje = q[:RESZLEGES_HOSSZ]
    if len(q) > RESZLEGES_HOSSZ and eleje in f:
        return True, "reszleges egyezes (az idezet eleje)"
    return False, "NEM SZEREPEL a forrasszovegben"


@dataclass
class GroundingResult:
    megtartott: list[dict] = field(default_factory=list)
    eldobott: list[dict] = field(default_factory=list)
    reszleges: int = 0

    @property
    def van_bizonyitek(self) -> bool:
        return bool(self.megtartott)

    @property
    def bukas_arany(self) -> float:
        osszes = len(self.megtartott) + len(self.eldobott)
        return len(self.eldobott) / osszes if osszes else 0.0


def ellenoriz(evidence: list, forras: str) -> GroundingResult:
    """Az evidence-lista atszurese. Ami nem bizonyithato, azt ELDOBJUK.

    Nem a lead esik ki elsore, hanem az ALLITAS. A lead csak akkor esik ki,
    ha egyetlen alatamasztott allitas sem marad -- ezt a hivo oldal dönti el
    a `van_bizonyitek` alapjan.
    """
    eredmeny = GroundingResult()
    for ev in (evidence or []):
        if not isinstance(ev, dict):
            eredmeny.eldobott.append({"claim": str(ev)[:100],
                                      "quote": "", "indok": "hibas formatum"})
            continue
        idezet = str(ev.get("quote") or "")
        ok, indok = idezet_ervenyes(idezet, forras)
        if ok:
            if indok:
                eredmeny.reszleges += 1
            eredmeny.megtartott.append(ev)
        else:
            eredmeny.eldobott.append({
                "claim": str(ev.get("claim") or "")[:150],
                "quote": idezet[:150],
                "indok": indok,
            })
    return eredmeny
