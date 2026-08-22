"""Az email-validacio tesztje.

MIERT ER EZ TESZTET (a repo szabalya: csak a NEMA hibak helyere irunk):

1. A CACHE PENZ. Ha elromlik, nem hibat dob, hanem SZAMLAT: ugyanazokra a
   cimekre fizetunk ujra es ujra. A terv kifejezetten kotelezove teszi ezt a
   tesztet ("Kotelezo unit-teszt erre, mert ez penz").

2. A STATUSZ-LEKEPEZES CSENDBEN TUD LISTAT IRTANI. Ha a `role_account`
   valaha `invalid`-ra kepzodne le, a magyar KKV-lista nagy resze eltunne --
   a jelenlegi 46 kapcsolatbol 31 `generic` (tulnyomorészt `info@`).
   Semmi nem dobna hibat: az export egyszeruen keveseb sort irna.

3. A "NEM TUDOM" NEM LEHET "ROSSZ". Egy Reoon-kimaradas nem jelolheti
   ervenytelennek a listat.
"""
import datetime as dt

import pytest

from leadgen import validate


class TestStatuszLekepezes:
    """A Reoon statuszai -> a mi negy ertekunk."""

    @pytest.mark.parametrize("reoon,vart", [
        ("safe", "valid"),
        ("valid", "valid"),
        ("catch_all", "catch_all"),
        ("invalid", "invalid"),
        ("disabled", "invalid"),
        ("disposable", "invalid"),
        ("spamtrap", "invalid"),
        ("inbox_full", "unknown"),
        ("unknown", "unknown"),
    ])
    def test_lekepezes(self, reoon, vart):
        assert validate._STATUS_MAP[reoon] == vart

    def test_a_role_account_ERVENYES(self):
        """A LEGFONTOSABB TESZT EBBEN A FAJLBAN.

        A magyar kisvallalkozasoknal az `info@` gyakran az EGYETLEN letezo
        cim. Ha a Reoon `role_account` statuszat ervenytelennek vennenk, a
        lista nagy resze csendben eltunne -- hiba nelkul.
        """
        assert validate._STATUS_MAP["role_account"] == "valid"

    def test_a_spamtrap_mindig_ervenytelen(self):
        # Spamcsapdara kuldeni a leggyorsabb ut a blokklistara.
        assert validate._STATUS_MAP["spamtrap"] == "invalid"

    def test_ismeretlen_statusz_unknown_lesz(self):
        # Ha a Reoon uj statuszt vezet be, az NEM lehet automatikusan
        # `invalid` -- inkabb ne dontsunk, mint rosszul dontsunk.
        assert validate._STATUS_MAP.get("valami_uj_statusz", "unknown") == "unknown"


class TestCache:
    """Ez a teszt penzt ved."""

    def test_hianyzo_idobelyeg_lejartnak_szamit(self):
        assert validate._lejart(None) is True

    def test_friss_eredmenyt_nem_kerdez_ujra(self):
        tegnap = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        assert validate._lejart(tegnap) is False

    def test_regi_eredmenyt_ujrakerdez(self):
        regen = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=200)
        assert validate._lejart(regen) is True

    def test_pontosan_a_hataron(self):
        from leadgen import config
        alatta = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            days=config.VERIFY_CACHE_DAYS - 1)
        felette = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            days=config.VERIFY_CACHE_DAYS + 1)
        assert validate._lejart(alatta) is False
        assert validate._lejart(felette) is True

    def test_idozona_nelkuli_idobelyeget_is_kezel(self):
        # A psycopg timezone-aware erteket ad, de egy kezi teszt-beszuras
        # naiv datetime-ot hagyhat. Ez ne dobjon TypeError-t.
        naiv = dt.datetime.now() - dt.timedelta(days=1)
        assert validate._lejart(naiv) is False


class TestHelyiSzuro:
    """Az ingyenes lepcso. Ami itt kiesik, arra nem koltunk."""

    @pytest.mark.parametrize("cim,indok_resz", [
        ("nincs-kukac", "formatum"),
        ("teszt@zoldnyil.invalid", "teszt-domain"),
        ("valaki@mailinator.com", "eldobhato"),
    ])
    def test_kizarja(self, cim, indok_resz):
        eredmeny, indok = validate.helyi_ellenorzes(cim)
        assert eredmeny == "fail"
        assert indok_resz in indok

    def test_a_dev_seed_cimei_kiesnek(self):
        # A `.invalid` TLD garantaltan nem letezik (RFC 2606). Ha ez atmenne,
        # egy veletlen eles futas hard bounce-t termelne.
        for cim in ("hello@zoldnyil.invalid", "info@kapocskreativ.invalid"):
            assert validate.helyi_ellenorzes(cim)[0] == "fail"

    def test_mx_hiany_eseten_nem_dol_el(self, monkeypatch):
        # Ha a DNS-lekerdezes maga hibazik (nincs `dig`, nincs halozat),
        # NEM zarunk ki senkit: "nem tudom" != "rossz".
        monkeypatch.setattr(validate, "_mx_cache", {})
        monkeypatch.setattr(validate, "van_mx", lambda d: True)
        assert validate.helyi_ellenorzes("info@pelda.hu")[0] == "pass"


class TestTierSzabaly:
    """A terv 2136-2141 catch-all szabalya."""

    def test_tier_savok(self):
        assert validate.tier_of(85) == "A"
        assert validate.tier_of(55) == "B"
        assert validate.tier_of(20) == "C"
        assert validate.tier_of(None) == "C"

    def test_valid_mindenhova_mehet(self):
        for pont in (10, 50, 90):
            assert validate.kikuldheto("valid", pont)[0] is True

    def test_invalid_sehova(self):
        for pont in (10, 50, 90):
            assert validate.kikuldheto("invalid", pont)[0] is False

    def test_catch_all_csak_A_es_B(self):
        assert validate.kikuldheto("catch_all", 90)[0] is True    # A
        assert validate.kikuldheto("catch_all", 55)[0] is True    # B
        assert validate.kikuldheto("catch_all", 20)[0] is False   # C

    def test_unknown_csak_A(self):
        assert validate.kikuldheto("unknown", 90)[0] is True
        assert validate.kikuldheto("unknown", 55)[0] is False
        assert validate.kikuldheto("unknown", 20)[0] is False

    def test_hianyzo_eredmeny_unknownkent_viselkedik(self):
        # Egy meg nem validalt cim ne csusszon at "ervenyeskent".
        assert validate.kikuldheto(None, 55)[0] is False
        assert validate.kikuldheto("", 55)[0] is False

    def test_a_kizarasnak_mindig_van_indoka(self):
        # Nema kizaras nem megengedett: az exportnak ki kell tudnia irni,
        # miert maradt ki egy lead.
        for eredmeny, pont in (("invalid", 90), ("catch_all", 20), ("unknown", 20)):
            mehet, indok = validate.kikuldheto(eredmeny, pont)
            assert mehet is False
            assert indok, f"nincs indok: {eredmeny}/{pont}"


class TestHibaturés:
    """API-hiba SOHA nem lehet 'invalid'."""

    @pytest.mark.parametrize("hiba", [
        ("halozati hiba", "ConnectError"),
        ("HTTP 500", None),
        ("HTTP 402", None),          # elfogyott a kredit
        ("olvashatatlan valasz", None),
    ])
    def test_minden_hibaag_unknownt_ad(self, hiba, monkeypatch):
        """A `_reoon_egy` minden hibaaga `unknown`-t ad vissza."""
        import httpx

        def dobj(*a, **kw):
            raise httpx.ConnectError("nincs halozat")

        monkeypatch.setattr(validate.httpx, "get", dobj)
        ertek, _ = validate._reoon_egy("info@pelda.hu")
        assert ertek == "unknown", "API-hiba nem jelolhet ervenytelennek egy cimet"

    def test_hibas_http_statusz_unknown(self, monkeypatch):
        class FakeResp:
            status_code = 500
            def json(self): return {}

        monkeypatch.setattr(validate.httpx, "get", lambda *a, **kw: FakeResp())
        assert validate._reoon_egy("info@pelda.hu")[0] == "unknown"

    def test_ervenyes_valasz_atmegy(self, monkeypatch):
        class FakeResp:
            status_code = 200
            def json(self): return {"status": "safe"}

        monkeypatch.setattr(validate.httpx, "get", lambda *a, **kw: FakeResp())
        assert validate._reoon_egy("info@pelda.hu")[0] == "valid"


class TestParhuzamossag:
    def test_nem_lepi_tul_a_reoon_korlatjat(self):
        # A Reoon egy vegponton max 5 parhuzamos szalat enged.
        assert validate._MAX_PARHUZAM <= 5
