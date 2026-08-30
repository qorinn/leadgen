"""A futtatas-kezelo (F6) vedelmi tesztjei.

MIERT VAN ITT TESZT (CLAUDE.md: "csak a nema hibakra irunk tesztet"):

  1. A `sender.py --live` bekerulese a katalogusba NEM DOBNA HIBAT -- csak
     megjelenne egy gomb, amivel egy kattintassal, ketlepcsos megerosites
     nelkul kimennenek a levelek. Pont az a fajta csendes szabalysertes,
     amit kesobb senki nem venne eszre.

  2. Egy elgepelt argv (`--max-result` egy `s` nelkul) csak a FUTAS
     pillanataban derulne ki, exit 2-vel, a naploban -- addigra a
     felhasznalo mar megerositette a koltseget.

  3. Az elo naplo maga: ha a kimenet csak a folyamat vegen jelenne meg, a
     kepernyo tovabbra is "mukodne", csak hasznalhatatlan lenne.

A 3. pontot SZINTETIKUS folyamattal merjuk (egy rovid Python-script, ami
lassan ir), nem valodi CLI-parancssal: a tesztnek nem szabad az ELES
adatbazishoz nyulnia, sem AI- vagy Apify-kreditet koltenie.
"""
from __future__ import annotations

import time

import pytest

from leadgen.cli import build_parser
from webui.api import jobs


# ─── A katalogus ───────────────────────────────────────────────────────────


def test_a_kuldes_nincs_a_katalogusban():
    """WEBUI-TERV.md F6: "a sender.py --live NEM szerepel ebben a katalogusban"."""
    for parancs in jobs.KATALOGUS:
        egesz = " ".join(parancs.argv).lower()
        assert "--live" not in egesz, f"{parancs.kulcs}: eles kuldes a katalogusban"
        assert "sender" not in egesz, f"{parancs.kulcs}: a kuldo a katalogusban"
        assert "deliverability" not in egesz, f"{parancs.kulcs}: az esti jelentes a katalogusban"


def test_a_dev_seed_nincs_a_katalogusban():
    """Invariansok #9: teszt-cegeket szurna az ELES adatbazisba."""
    for parancs in jobs.KATALOGUS:
        assert parancs.argv[0] != "dev", f"{parancs.kulcs}: fejlesztoi eszkoz a katalogusban"


@pytest.mark.parametrize("parancs", jobs.KATALOGUS, ids=lambda p: p.kulcs)
def test_minden_katalogus_parancs_ervenyes_cli_parancs(parancs):
    """Az elgepelt flag kulonben csak futaskor derulne ki -- a koltseg
    megerositese UTAN."""
    argv = jobs.epit_argv(parancs.kulcs)
    # A `parse_args` a hibas argumentumra SystemExittel all meg. Ha lefut,
    # a parancs es minden flagje letezik a CLI-ben.
    build_parser().parse_args(argv)


def test_a_keret_ervenyesitese_a_szerveren_van():
    """A felulet csak felkinalja a hatarokat; betartatni a szerver dolga."""
    with pytest.raises(jobs.ErvenytelenParameter):
        jobs.epit_argv("ingest-maps", {"max_results": 100_000})
    with pytest.raises(jobs.ErvenytelenParameter):
        jobs.epit_argv("ingest-maps", {"nincs_ilyen": 1})
    with pytest.raises(jobs.IsmeretlenParancs):
        jobs.epit_argv("sender-live", {})


def test_az_alapertekek_a_cli_bol_jonnek():
    """Ha valaki atirja a CLI alapertelmezeset, a felulet kovesse -- ne egy
    itteni masolat maradjon ervenyben."""
    ns = build_parser().parse_args(["ingest", "maps"])
    katalogus = {p["kulcs"]: p for p in jobs.katalogus_adat()}
    maps = katalogus["ingest-maps"]
    assert maps["parameterek"][0]["alap"] == ns.max_results


def test_a_koltseg_nem_talalt_szam():
    """WEBUI-TERV.md F6: "ne talalj ki szamot; ha ismeretlen, ird ki, hogy
    ismeretlen"."""
    katalogus = {p["kulcs"]: p for p in jobs.katalogus_adat()}

    # AI: elore nem becsulheto -> NINCS dollarosszeg, csak a jelzes.
    score = katalogus["score"]["koltseg"]
    assert score["ai_tokenenkent"] is True
    assert score["apify_egysegar_usd"] is None

    # Apify: egysegar x darab, es az egysegar a pricing.py-bol jon.
    from leadgen import pricing
    maps = katalogus["ingest-maps"]["koltseg"]
    assert maps["apify_egysegar_usd"] == pricing.APIFY_TALALAT_USD
    assert maps["apify_darab_parametere"] == "max_results"

    # A napi lanc kerete a LANCBOL jon, nem egy itt beirt szambol.
    from leadgen import schedule
    ingest = next(l for l in schedule.lepesek() if l.nev == "ingest")
    varhato = int(ingest.argv[ingest.argv.index("--max-results") + 1])
    assert katalogus["daily"]["koltseg"]["apify_fix_darab"] == varhato


# ─── A futtatas ────────────────────────────────────────────────────────────


@pytest.fixture
def szintetikus(monkeypatch):
    """Egy rovid Python-script CLI-parancs helyett.

    Igy a job-kezelo teljes utja (inditas, elo kimenet, megszakitas,
    sorositas) valodi folyamaton merheto, ANELKUL, hogy az eles adatbazishoz
    nyulnank vagy kreditet koltenenk.
    """
    import sys

    def parancs(argv: list[str]) -> list[str]:
        # A `-u` itt is kell -- pont azt merjuk, hogy a sorok menet kozben
        # erkeznek-e meg.
        return [sys.executable, "-u", "-c", SCRIPT, *argv]

    monkeypatch.setattr(jobs.schedule, "cli_parancs", parancs)
    monkeypatch.setattr(jobs, "_futo", None, raising=False)
    yield
    futo = jobs.futo()
    if futo is not None:
        jobs.megszakit(futo.id)


# A `-c` mod miatt a sys.argv[0] a "-c", utana jonnek a CLI-argumentumok --
# a darabszamot ezert az UTOLSO szambol vesszuk (az a `--limit` erteke).
SCRIPT = """
import sys, time
darab = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 3
for i in range(darab):
    print(f"sor {i}")
    time.sleep(0.3)
"""


def test_a_kimenet_menet_kozben_erkezik(szintetikus, tmp_path, monkeypatch):
    """A FAZIS LENYEGE: a naplonak futas kozben kell frissulnie, nem a vegen.

    Ha ez elromlik, a kepernyo tovabbra is "mukodik" -- csak eppen egy
    beragadt lancnal nem latszik, HOL akadt el.
    """
    monkeypatch.setattr(jobs, "ELOZMENY_PATH", tmp_path / "jobs.jsonl")
    job = jobs.indit("enrich", {"limit": 5})
    time.sleep(0.6)
    kozben, _ = job.sorok_tol(0)
    assert job.fut, "a futas mar veget ert -- emeld a script alvasi idejet"
    assert kozben, "a kimenet csak a futas vegen jelent meg (nincs elo naplo)"

    _var_amig_kesz(job)
    vegso, kurzor = job.sorok_tol(0)
    assert len(vegso) > len(kozben)
    assert kurzor == len(vegso)
    assert job.exit_code == 0


def test_a_kurzor_nem_ismetel_es_nem_hagy_ki(szintetikus, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ELOZMENY_PATH", tmp_path / "jobs.jsonl")
    job = jobs.indit("enrich", {"limit": 4})
    _var_amig_kesz(job)

    mind, veg = job.sorok_tol(0)
    elso_ketto, kurzor = job.sorok_tol(0)
    tovabb, _ = job.sorok_tol(2)
    assert elso_ketto == mind and kurzor == veg
    assert tovabb == mind[2:]


def test_a_masodik_inditas_elutasitva(szintetikus, tmp_path, monkeypatch):
    """Ket parhuzamos futas ugyanazt a cegcsokrot dolgozna fel ketszer -- a
    `flock` az adatsereles ellen ved, a kettos feldolgozas ellen nem."""
    monkeypatch.setattr(jobs, "ELOZMENY_PATH", tmp_path / "jobs.jsonl")
    elso = jobs.indit("enrich", {"limit": 5})
    with pytest.raises(jobs.MarFut) as exc:
        jobs.indit("qualify", {"limit": 5})
    assert exc.value.job.id == elso.id

    jobs.megszakit(elso.id)
    _var_amig_kesz(elso)
    # A futas vege utan ismet indithato.
    masodik = jobs.indit("qualify", {"limit": 2})
    assert masodik.id != elso.id
    jobs.megszakit(masodik.id)
    _var_amig_kesz(masodik)


def test_a_megszakitas_valoban_leallitja(szintetikus, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ELOZMENY_PATH", tmp_path / "jobs.jsonl")
    job = jobs.indit("enrich", {"limit": 100})
    time.sleep(0.4)
    assert job.fut

    jobs.megszakit(job.id)
    _var_amig_kesz(job, masodperc=5)
    assert not job.fut
    assert job.allapot == "cancelled"
    assert job._proc is not None and job._proc.poll() is not None


def test_az_elozmeny_a_futas_utan_megmarad(szintetikus, tmp_path, monkeypatch):
    naplo = tmp_path / "jobs.jsonl"
    monkeypatch.setattr(jobs, "ELOZMENY_PATH", naplo)
    job = jobs.indit("enrich", {"limit": 2})
    _var_amig_kesz(job)

    sorok = jobs.elozmenyek(30)
    assert sorok and sorok[0]["id"] == job.id
    assert sorok[0]["exit_code"] == 0
    assert sorok[0]["seconds"] is not None


def _var_amig_kesz(job, masodperc: float = 15.0) -> None:
    hatarido = time.monotonic() + masodperc
    while job.fut and time.monotonic() < hatarido:
        time.sleep(0.05)
    assert not job.fut, "a futas nem ert veget idoben"
