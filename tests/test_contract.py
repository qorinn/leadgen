"""A rendszerhatar vedelme: a ket oldal fejlece ne csusszon el egymastol.

A scraper (Python 3.12, sajat venv) es a kuldo (rendszer 3.9.6, stdlib-only)
NEM importalhatja egymast. Ezert a leads.csv fejlece ket helyen van leirva:

    leadgen/contract.py          LEADS_HEADER   <- az IRO oldal
    cold-email-starter/store.py  LEADS_HEADER   <- az OLVASO oldal

Ha valaki csak az egyiket modositja, az elesben NEM dob hibat: a DictReader
egyszeruen None-t ad a hianyzo mezore, es a level csendben rosszul renderelodik
(pl. minden lead az alapertelmezett kampany sablonjat kapja). Ez a teszt az,
ami ezt eszreveszi -- ezert olvassa be a store.py-t szovegkent es AST-vel.
"""
import ast
from pathlib import Path

import pytest

from leadgen import contract

REPO = Path(__file__).resolve().parent.parent
STORE_PY = REPO / "cold-email-starter" / "store.py"


def _literal_from_store(name: str):
    """A store.py egy modul szintu konstansat olvassa ki, importalas nelkul.

    Importalni nem tudjuk: a kuldo modulja `import config`-ot vegez, ami
    letrehozna a data/ konyvtarat es beolvasna a .env-et. Egy teszt ne
    csinaljon ilyet -- az AST viszont csak elemzi a forrast.
    """
    tree = ast.parse(STORE_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} nem talalhato a store.py-ban")


def test_a_ket_fejlec_azonos():
    assert _literal_from_store("LEADS_HEADER") == contract.LEADS_HEADER


def test_az_email_az_elso_mezo():
    # Nem kotelezo, de minden emberi atnezes ezt felteételezi, es az `email`
    # az EGYETLEN kulcs a kuldo teljes rendszereben.
    assert contract.LEADS_HEADER[0] == "email"


def test_a_kuldo_eredeti_mezoi_megvannak():
    # A templates.py ezekre nev szerint hivatkozik. Ha barmelyik eltunik,
    # a level renderelese csendben romlik el.
    for field in ("email", "company", "contact_name", "industry"):
        assert field in contract.LEADS_HEADER


def test_nincs_ismetlodo_mezo():
    assert len(contract.LEADS_HEADER) == len(set(contract.LEADS_HEADER))


@pytest.mark.parametrize("stage", contract.STAGES)
def test_a_szekvencia_fokok_egyeznek_a_sablonokkal(stage):
    """A sender._stage_of a sent.csv `template` oszlopabol olvassa vissza a
    fokot. Ha egy sablon mas azonositot adna vissza, minden korabbi lead
    visszaesne egy fokra es UJRA kapna levelet."""
    templates_src = (REPO / "cold-email-starter" / "templates.py").read_text(encoding="utf-8")
    assert f'"template": "{stage}"' in templates_src
