"""Az Apify-hivas tesztjei.

MIERT VAN ITT TESZT (CLAUDE.md: "csak a nema hibakra irunk tesztet"):

Ez a fajta hiba HAT NAPIG eszrevetlen maradt (2026-08-29 -- 09-03). A napi
lanc `ingest` lepese minden reggel elbukott egy `httpx.ReadTimeout`-tal, a
lanc pedig -- helyesen -- tovabb ment. Kifele minden rendben volt: a lanc
lefutott, a leadek exportalodtak, levelek mentek ki. Kozben viszont a tolcser
TETEJE volt elzarva: egyetlen uj ceg sem jott be a Google Mapsrol, es a
`ready` leadek utanpotlasa lassan elfogyott (napi 10-11 helyett 6).

Az ilyen hiba nem "elszall a rendszer" tipusu, hanem "lassan kiszarad" --
es pont ezert kell teszt.
"""
from __future__ import annotations

import httpx
import pytest

from leadgen.sources import apify


class _HamisValasz:
    def __init__(self, status_code: int, adat):
        self.status_code = status_code
        self._adat = adat
        self.text = str(adat)

    def json(self):
        return self._adat


class _HamisKliens:
    """A `httpx.Client` helyettesitoje: a valaszokat a hivo adja meg."""

    def __init__(self, valaszok: dict, naplo: list):
        self._valaszok = valaszok
        self._naplo = naplo

    def __call__(self, *args, **kwargs):
        self._naplo.append(("client", kwargs.get("timeout")))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _keres(self, mod, url):
        self._naplo.append((mod, url))
        for minta, valasz in self._valaszok.items():
            if minta in url:
                return valasz
        raise AssertionError(f"varatlan {mod} hivas: {url}")

    def post(self, url, **kw):
        return self._keres("POST", url)

    def get(self, url, **kw):
        return self._keres("GET", url)


@pytest.fixture
def _token(monkeypatch):
    monkeypatch.setattr(apify.config, "APIFY_TOKEN", "teszt-token")


def test_nem_a_szinkron_vegpontot_hasznaljuk():
    """A `run-sync-get-dataset-items` EGYETLEN kapcsolatot tartott nyitva,
    amig az actor vegigfutott -- es ha az beallt a varolistara, a kapcsolat
    kifutott az idobol. A kimenet egy puszta `ReadTimeout` volt, amibol nem
    derult ki, hogy a futas elindult-e es fizettunk-e erte.

    Ha valaha valaki visszairja a szinkron vegpontot, ez a teszt bukjon el.
    """
    import ast
    import inspect

    fa = ast.parse(inspect.getsource(apify))
    # CSAK a valodi kod erdekel: a docstringek epp azt magyarazzak, miert NEM
    # hasznaljuk a szinkron vegpontot -- azokra nem szabad illeszteni.
    docstringek = {
        id(csomopont.body[0].value)
        for csomopont in ast.walk(fa)
        if isinstance(csomopont, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and csomopont.body
        and isinstance(csomopont.body[0], ast.Expr)
        and isinstance(csomopont.body[0].value, ast.Constant)
        and isinstance(csomopont.body[0].value.value, str)
    }
    szoveg_konstansok = [
        csomopont.value for csomopont in ast.walk(fa)
        if isinstance(csomopont, ast.Constant)
        and isinstance(csomopont.value, str)
        and id(csomopont) not in docstringek
    ]
    assert not any("run-sync" in s for s in szoveg_konstansok), \
        "a szinkron vegpont visszakerult a KODBA -- lasd a run_actor() docstringjet"


def test_egyetlen_http_hivas_sem_kaphatja_meg_a_TELJES_idokeretet():
    """A futas hosszat a lekerdezgetes hidalja at, nem egy hosszu kapcsolat.

    Ha egy HTTP-hivas megkapna a teljes (900 mp-es) keretet, egyetlen megakadt
    TCP-kapcsolat ujra elvinne az egesz napi ingestet -- pontosan ugy, ahogy
    a szinkron vegpontnal tortent.
    """
    assert apify._HTTP_TIMEOUT <= 120, \
        "egy HTTP hivas felso ideje maradjon rovid (a futast a polling hidalja at)"


def test_a_futas_INDITASA_utani_hiba_megorzi_az_azonositokat(_token, monkeypatch):
    """MAR FIZETTUNK a futasert -- az azonositok nelkul az adat elveszne.

    Ha a futas elindult, de utana barmi elromlik, a hibauzenetben ott kell
    lennie a futas ES a dataset azonositojanak, kulonben a mar kifizetett
    eredmenyt semmivel nem lehet utolag elhozni.
    """
    naplo: list = []
    valaszok = {
        "/users/me/limits": _HamisValasz(200, {"data": {"current": {"monthlyUsageUsd": 1},
                                                        "limits": {"maxMonthlyUsageUsd": 10}}}),
        "/runs": _HamisValasz(201, {"data": {"id": "RUN123", "defaultDatasetId": "DS456",
                                             "status": "READY"}}),
        "/actor-runs/": _HamisValasz(200, {"data": {"status": "FAILED"}}),
    }
    monkeypatch.setattr(httpx, "Client", _HamisKliens(valaszok, naplo))
    monkeypatch.setattr(apify.time, "sleep", lambda _s: None)

    with pytest.raises(apify.ApifyError) as hiba:
        apify.run_actor("teszt/actor", {}, verbose=False)

    uzenet = str(hiba.value)
    assert "RUN123" in uzenet, "a futas azonositoja hianyzik a hibauzenetbol"
    assert "DS456" in uzenet, "a dataset azonositoja hianyzik a hibauzenetbol"
    assert "FAILED" in uzenet, "a tenyleges Apify-allapot hianyzik"


def test_a_sikeres_futas_a_datasetbol_olvas(_token, monkeypatch):
    """A boldog ut: inditas -> SUCCEEDED -> a dataset tartalma."""
    naplo: list = []
    valaszok = {
        "/users/me/limits": _HamisValasz(200, {"data": {"current": {"monthlyUsageUsd": 1},
                                                        "limits": {"maxMonthlyUsageUsd": 10}}}),
        "/runs": _HamisValasz(201, {"data": {"id": "R1", "defaultDatasetId": "D1",
                                             "status": "RUNNING"}}),
        "/actor-runs/": _HamisValasz(200, {"data": {"status": "SUCCEEDED"}}),
        "/datasets/": _HamisValasz(200, [{"title": "A ceg"}, {"title": "B ceg"}]),
    }
    monkeypatch.setattr(httpx, "Client", _HamisKliens(valaszok, naplo))
    monkeypatch.setattr(apify.time, "sleep", lambda _s: None)

    items = apify.run_actor("teszt/actor", {}, verbose=False)
    assert items == [{"title": "A ceg"}, {"title": "B ceg"}]


def test_a_lekerdezes_halozati_hibaja_nem_szakitja_meg_a_futast(_token, monkeypatch):
    """Egy elvesztett allapot-lekerdezes NEM hiba: a futas tovabb megy.

    Ha minden egyes sikertelen pollra feladnank, egy pillanatnyi halozati
    zavar eldobna egy MAR KIFIZETETT futast.
    """
    naplo: list = []
    allapotok = iter(["RUNNING", "SUCCEEDED"])

    class _Kliens(_HamisKliens):
        def get(self, url, **kw):
            if "/actor-runs/" in url:
                self._naplo.append(("GET", url))
                if len(self._naplo) < 4:      # az elso poll "elszall"
                    raise httpx.ConnectError("halozati zavar")
                return _HamisValasz(200, {"data": {"status": next(allapotok, "SUCCEEDED")}})
            return super().get(url, **kw)

    valaszok = {
        "/users/me/limits": _HamisValasz(200, {"data": {"current": {"monthlyUsageUsd": 1},
                                                        "limits": {"maxMonthlyUsageUsd": 10}}}),
        "/runs": _HamisValasz(201, {"data": {"id": "R1", "defaultDatasetId": "D1",
                                             "status": "RUNNING"}}),
        "/datasets/": _HamisValasz(200, [{"title": "A ceg"}]),
    }
    monkeypatch.setattr(httpx, "Client", _Kliens(valaszok, naplo))
    monkeypatch.setattr(apify.time, "sleep", lambda _s: None)

    items = apify.run_actor("teszt/actor", {}, verbose=False)
    assert items == [{"title": "A ceg"}]
