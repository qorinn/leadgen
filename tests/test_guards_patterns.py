"""A leiratkozas-felismeres mintainak tesztje.

MIERT ITT VAN, ES MIERT NEM IMPORTALJA A guards.py-t: a kuldo modulja
`import config`-ot vegez, ami beolvassa a .env-et es letrehozza a data/
konyvtarat. Egy teszt ne csinaljon ilyet. Ezert a mintakat AST-vel olvassuk
ki a forrasbol, es a leadgen sajat strip_accents-evel hajtogatunk -- ami
egyben azt is ellenorzi, hogy a ket oldal ekezet-kezelese egyezik.

MIERT ER EZ TESZTET: ez a kod dont arrol, hogy valakit VEGLEGESEN kizarunk-e.
Mindket iranyu hiba draga:
  - hamis pozitiv -> egy erdeklodo lead veglegesen suppressionbe kerul;
  - hamis negativ -> egy valodi leiratkozas rossz okkal naplozodik.
Mindketto NEMA hiba: semmi nem dob kivetelt.
"""
import ast
import re
from pathlib import Path

import pytest

from leadgen import normalize

REPO = Path(__file__).resolve().parent.parent
GUARDS_PY = REPO / "cold-email-starter" / "guards.py"


def _unsub_patterns() -> tuple:
    tree = ast.parse(GUARDS_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "UNSUB_PATTERNS":
                    return ast.literal_eval(node.value)
    raise AssertionError("UNSUB_PATTERNS nem talalhato a guards.py-ban")


PATTERNS = _unsub_patterns()


def _matches(text: str) -> bool:
    folded = normalize.strip_accents(text.lower())[:600]
    return any(re.search(p, folded) for p in PATTERNS)


# Valodi leiratkozasi szandek -- ezeket EL KELL kapni.
@pytest.mark.parametrize("valasz", [
    "Kérlek távolíts el a listáról",
    "Kérem töröljenek a listáról",
    "Leiratkozom",
    "stop",
    "Ne küldjetek több levelet",
    "Ne írj többet",
    "unsubscribe",
])
def test_leiratkozast_felismeri(valasz):
    assert _matches(valasz), f"nem ismerte fel: {valasz!r}"


# ELUTASITAS, NEM LEIRATKOZAS. 2026-08-21-tol szandekosan NEM illeszkedik.
#
# A ketto nem ugyanaz, es a kulonbseg penzben merheto: az elutasito valasz
# fel ev mulva, mas ajanlattal ujra megkeresheto, a leiratkozas viszont
# VEGLEGES. Amig a ket eset egy okba folyt ossze, minden "koszonom, nem"
# orokre kizarta a ceget.
#
# Senki nem esik ki a vedelmi halon: aki valaszol, azt a guards.run() vegen
# levo `replied` szabaly amugy is DNC-be teszi -- csak "valaszolt" okkal,
# nem "leiratkozott" okkal. A szetvalasztast a 6. szakasz AI-osztalyozoja
# vegzi majd el rendesen.
@pytest.mark.parametrize("valasz", [
    "Köszönöm, nem érdekel.",
    "Nem kérem a leveleket",
    "Jelenleg nem kívánunk élni a lehetőséggel.",
    "Not interested, thanks.",
])
def test_elutasitas_nem_leiratkozas(valasz):
    assert not _matches(valasz), (
        f"elutasitaskent kellene kezelni, nem leiratkozaskent: {valasz!r}"
    )


# NEM leiratkozas -- ezekre TILOS illeszkednie.
# Mindegyik olyan valasz, amit egy erdeklodo vagy semleges cimzett ir.
@pytest.mark.parametrize("valasz", [
    "Most nem aktuális, de jövőre kérdezz rá!",
    "Nem tudom, kivel dolgozunk, megkérdezem a kollégát.",
    "Igen, érdekel! Mikor tudnánk beszélni?",
    "Köszönjük a megkeresést, továbbítom az ügyvezetőnek.",
    "Jelenleg nem keresünk új partnert, de tartsuk a kapcsolatot.",
])
def test_erdeklodo_valaszra_nem_illeszkedik(valasz):
    assert not _matches(valasz), f"HAMIS POZITIV: {valasz!r}"


def test_a_nyers_nem_minta_nincs_bent():
    """A r"\\bnem\\b" volt a legdragabb hamis pozitiv forras.

    Magyar szovegben a "nem" szo szinte minden valaszban elofordul, tehat
    ez a minta gyakorlatilag MINDEN valaszolot leiratkozokent kezelt volna.
    """
    assert r"\bnem\b" not in PATTERNS


def test_a_sajat_leiratkozasi_hivoszavunk_illeszkedik():
    """A templates.py FALLBACK aga azt keri, hogy irjak vissza: "stop".

    2026-08-21 ota az alap ut a leiratkozo LINK, de a fallback mondat
    megmaradt arra az esetre, ha egy leadhez nincs `unsub_url` (kezzel
    felvett sor, vagy nincs beallitva az UNSUB_BASE_URL). Amig a sablon
    ezt a szot keri, a mintanak illeszkednie KELL ra -- kulonben a sajat
    utasitasunkra erkezo valaszt nem ismernenk fel.
    """
    templates_src = (REPO / "cold-email-starter" / "templates.py").read_text(encoding="utf-8")
    assert "„stop" in templates_src, "a sablon mar nem a 'stop' szot keri"
    assert _matches("stop")


def test_a_link_es_a_fallback_is_letezik_a_sablonban():
    """A leiratkozas KET uton mehet, es MINDKETTONEK bent kell lennie.

    Ha valaki kiveszi a fallback agat, egy `unsub_url` nelkuli lead ugy
    kapna levelet, hogy NINCS BENNE kilepesi lehetoseg -- ez a GDPR 6(1)(f)
    jogalap feltetelet sertene, es nemán tortenne.
    """
    src = (REPO / "cold-email-starter" / "templates.py").read_text(encoding="utf-8")
    assert "unsub_url" in src, "a sablon nem hasznalja a leiratkozo linket"
    assert "itt tudsz leiratkozni" in src, "hianyzik a link-valtozat"
    assert "„stop" in src, "hianyzik a fallback mondat"
