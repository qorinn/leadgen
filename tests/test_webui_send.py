"""A ketlepcsos kuldes-kapu (F7) vedelmi tesztjei.

MIERT VAN ITT TESZT (CLAUDE.md: "csak a nema hibakra irunk tesztet"):

A kikuldes VISSZAFORDITHATATLAN, es a level a felhasznalo neveben megy ki.
Minden itteni hiba nema lenne:

  1. Ha a `send-live` bekerul a job-katalogusba, a `/api/jobs/start` egyetlen
     kattintassal, elonezet es token nelkul inditana kuldest. A felulet
     tovabbra is "mukodne".

  2. Ha a token-ellenorzes csak a token LETEZESET nezne (nem a terv
     tartalmat), akkor egy kozben lefutott export utan a regi tokennel MAS
     leveleket kuldenenk ki, mint amit az ember jovahagyott -- es semmi nem
     jelezne.

  3. Ha a token nem lenne egyszer hasznalatos, egy dupla kattintas ket
     kuldest inditana.

A tesztek NEM inditanak valodi kuldest es NEM nyulnak a kuldo fajljaihoz:
szintetikus `Level` listakon merik a kaput, illetve a katalogus alakjat.
"""
from __future__ import annotations

import datetime as dt

import pytest

from leadgen import send
from webui.api import jobs


def _levelek(*cimzettek: str) -> list[send.Level]:
    return [
        send.Level(cimzett=c, ceg=c.split("@")[-1], fok="cold",
                   targy="Kivel fejlesztetek?", torzs=f"Sziasztok! ({c})")
        for c in cimzettek
    ]


# ─── A kapu ────────────────────────────────────────────────────────────────


def test_ervenyes_token_valtozatlan_tervre_atmegy():
    levelek = _levelek("a@pelda.hu", "b@pelda.hu")
    token, lejar = send.token_kiad(levelek)
    assert lejar > dt.datetime.now()
    send.token_beval(token, levelek)  # nem dob


def test_ismeretlen_token_elutasitva():
    with pytest.raises(send.TokenErvenytelen):
        send.token_beval("nincs-ilyen-token", _levelek("a@pelda.hu"))


def test_a_token_egyszer_hasznalatos():
    """Dupla kattintas nem indithat ket kuldest."""
    levelek = _levelek("a@pelda.hu")
    token, _ = send.token_kiad(levelek)
    send.token_beval(token, levelek)
    with pytest.raises(send.TokenErvenytelen) as exc:
        send.token_beval(token, levelek)
    assert "elhasznaltuk" in str(exc.value)


def test_a_lejart_token_elutasitva(monkeypatch):
    monkeypatch.setattr(send, "TOKEN_ELETTARTAM_PERC", -1)
    levelek = _levelek("a@pelda.hu")
    token, _ = send.token_kiad(levelek)
    with pytest.raises(send.TokenErvenytelen):
        send.token_beval(token, levelek)


@pytest.mark.parametrize("valtozas, leiras", [
    (lambda lv: _levelek("a@pelda.hu"), "elfogyott egy cimzett (export futott)"),
    (lambda lv: _levelek("a@pelda.hu", "c@pelda.hu"), "mas cimzett kerult be"),
])
def test_a_megvaltozott_terv_elutasitva(valtozas, leiras):
    """A LENYEGI ELLENORZES: nem a token romlott el, a TERV mas."""
    eredeti = _levelek("a@pelda.hu", "b@pelda.hu")
    token, _ = send.token_kiad(eredeti)
    with pytest.raises(send.TokenErvenytelen) as exc:
        send.token_beval(token, valtozas(eredeti))
    assert "megvaltozott" in str(exc.value), leiras


def test_a_hash_a_torzset_is_fedi():
    """A `templates.py` a felhasznaloe, es az elonezet ota atirhatta. Targy-
    valtozas nelkul is MAS szoveg menne ki, mint amit jovahagyott."""
    eredeti = _levelek("a@pelda.hu")
    token, _ = send.token_kiad(eredeti)
    atirt = _levelek("a@pelda.hu")
    atirt[0].torzs = "Teljesen mas szoveg."
    with pytest.raises(send.TokenErvenytelen):
        send.token_beval(token, atirt)


def test_a_fok_valtozasa_is_elutasitva():
    """Ugyanaz a cimzett, de mar a follow-up fokon -- mas level menne ki."""
    eredeti = _levelek("a@pelda.hu")
    token, _ = send.token_kiad(eredeti)
    masik_fok = _levelek("a@pelda.hu")
    masik_fok[0].fok = "follow_up_1"
    with pytest.raises(send.TokenErvenytelen):
        send.token_beval(token, masik_fok)


def test_a_sorrend_is_resze_a_tervnek():
    """A terv RANGSOROLT es LEVAGOTT lista: a `build_plan` a follow-upokat
    teszi elore, es a mai keretnel elvagja (`(followups + fresh)[:limit]`).
    Ket kulonbozo sorrend tehat ket kulonbozo terv -- mas menne ki, ha a
    keret kisebb, mint a lista. Ezert a hash sorrend-erzekeny.

    (A gyakorlatban ez nem ad hamis elutasitast: a sorrend ugyanabbol a
    `leads.csv`-bol determinisztikusan all elo.)"""
    a, b = _levelek("a@pelda.hu", "b@pelda.hu")
    token, _ = send.token_kiad([a, b])
    with pytest.raises(send.TokenErvenytelen):
        send.token_beval(token, [b, a])


# ─── A kuldes nem szivaroghat be a job-katalogusba ─────────────────────────


def test_a_kuldes_nincs_a_katalogusban():
    """WEBUI-TERV.md F6: a `sender.py --live` NEM szerepel a katalogusban."""
    assert jobs.KULDES_KULCS not in {p.kulcs for p in jobs.KATALOGUS}


def test_a_jobs_start_nem_tudja_elinditani_a_kuldest():
    """A `/api/jobs/start` csak katalogus-kulcsot fogad el. Ez az az ut, amit
    egy elgepelt `fetch` vagy egy kivancsi felhasznalo elerne."""
    with pytest.raises(jobs.IsmeretlenParancs):
        jobs.indit(jobs.KULDES_KULCS)
    with pytest.raises(jobs.IsmeretlenParancs):
        jobs.epit_argv(jobs.KULDES_KULCS, {})


def test_a_kuldes_a_kuldo_interpreteren_es_konyvtarabol_indul():
    """A kuldo lapos importokkal, a rendszer python3-jan (3.9.6) fut -- a venv
    Pythonjabol nem importalhato (CLAUDE.md). Ezt a parancs ALAKJAN merjuk,
    futtatas nelkul."""
    import inspect
    forras = inspect.getsource(jobs.indit_kuldes)
    assert '"python3"' in forras, "nem a rendszer python3-jat hivja"
    assert '"-u"' in forras, "a `-u` nelkul a kimenet csak a futas vegen jelenne meg"
    assert "config.SENDER_DIR" in forras, "nem a kuldo konyvtarabol indul"


def test_a_kuldes_ugyanazt_a_sorosito_kaput_hasznalja():
    """Egy export NEM futhat kikuldes kozben: a `leads.csv`-t irna at a kuldo
    labai alatt. Mindket ut a `_inditas()`-on megy at."""
    import inspect
    for fuggveny in (jobs.indit, jobs.indit_kuldes):
        assert "_inditas(" in inspect.getsource(fuggveny), fuggveny.__name__


# ─── A router alakja ───────────────────────────────────────────────────────


def test_az_eles_kuldes_csak_tokennel_hivhato():
    """A `/api/send/live` kotelezo mezoje a token. Ha valaha opcionalissa
    valna, a kapu csendben kinyilna."""
    from webui.api.schemas import SendLiveBody
    assert SendLiveBody.model_fields["token"].is_required()


def test_a_kuldes_router_ujra_lekerdezi_a_tervet():
    """A hash-ellenorzes csak akkor er valamit, ha a FRISS tervre fut. Ha a
    router a kliens altal kuldott tervet hasonlitana ossze, a kapu nem
    vedene semmit."""
    import inspect
    from webui.api.routers import send as send_router
    forras = inspect.getsource(send_router.send_live)
    assert "_terv()" in forras, "nem kerdezi ujra a tervet a kuldotol"
    # A token beallitasa ELOTT nem indulhat folyamat.
    assert forras.index("token_beval") < forras.index("indit_kuldes")
