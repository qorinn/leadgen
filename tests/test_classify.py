"""Az AI-reteg nema hibainak tesztje.

MIERT PONT EZEKRE IRUNK TESZTET (a repo szabalya: csak oda, ahol a hiba nema):

A valasz-osztalyozas az egyetlen VISSZAFORDITHATATLAN AI-dontes a rendszerben.
Az `unsubscribe` es a `negative` cimke suppressionbe teszi a ceget, ahonnan nem
jon vissza magatol -- es semmi nem dob hibat kozben. Harom nema kimenetel van:

  1. A modell kitalal egy cimket ("leiratkozás", "UNSUBSCRIBE", "no_fit"), es
     az valahogy suppressionne valik.
  2. A modell bizonytalan (confidence 0.3), es megis kizarunk egy ceget.
  3. A JSON-parse elrontja a valaszt, es defaultra esunk vissza.

Egyik sem lathato a naplobol -- csak fel ev mulva, amikor kiderul, hogy a
lista feleannyi, mint kellene.

Az LLM-hivas NINCS mockolva: ezek tiszta fuggvenyek a hivas KORUL. A halozati
resz tesztelese API-kulcsot igenyelne, es azt a bake-off vegzi el elesben.
"""
import json

import pytest

from leadgen import classify, evals, llm, prompts


class TestParseJson:
    """A modellek rendszeresen becsomagoljak a JSON-t, a prompt tiltasa ellenere."""

    def test_tiszta_json(self):
        assert llm.parse_json('{"a": 1}') == {"a": 1}

    def test_markdown_kodblokk(self):
        assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_kodblokk_nyelv_nelkul(self):
        assert llm.parse_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_bevezeto_mondat(self):
        # "Itt a besorolas:" tipusu bevezeto -- a JSON attol meg jo.
        assert llm.parse_json('Itt a valasz:\n{"a": 1}\nRemelem segit!') == {"a": 1}

    def test_ekezetes_ertek(self):
        assert llm.parse_json('{"rationale": "érdeklődik"}')["rationale"] == "érdeklődik"

    @pytest.mark.parametrize("rossz", ["", "semmi json", "{nem json}", "[1,2]{"])
    def test_ervenytelenre_dob(self, rossz):
        # NEM ad vissza ures dictet: a hivo oldal kulonben csendben
        # defaultra esne, es a hibas hivas ugy nezne ki, mint egy sikeres.
        with pytest.raises(json.JSONDecodeError):
            llm.parse_json(rossz)


class TestProviderFelismeres:
    @pytest.mark.parametrize("model,vart", [
        ("claude-haiku-4-5", "anthropic"),
        ("claude-opus-5", "anthropic"),
        ("gpt-5-nano", "openai"),
        ("gpt-4o-mini", "openai"),
        ("o3-mini", "openai"),
        # A Gemini-integracio 2026-08-22-tol nem az alapertelmezes, de
        # ERINTETLENUL MEGMARADT -- egy .env sorral visszakapcsolhato.
        ("gemini-2.5-flash-lite", "gemini"),
        ("gemini-3.7-flash", "gemini"),
    ])
    def test_felismeri(self, model, vart):
        assert llm.provider_of(model) == vart

    @pytest.mark.parametrize("rossz", ["llama-3", "mistral-large", "", "gpt5"])
    def test_ismeretlen_modellre_dob(self, rossz):
        # Elgepelt modellnev ne csendben az egyik providerhez menjen.
        with pytest.raises(llm.LLMConfigError):
            llm.provider_of(rossz)

    def test_a_kulcs_hianyat_a_PROVIDERBOL_vezeti_le(self, monkeypatch):
        """Modellvaltas utan a hibauzenet a HELYES kulcsot kerje.

        Ha bedrotoznank ("nincs GEMINI_API_KEY"), egy OpenAI-ra valtas utan
        a felhasznalo a rossz kulcsot keresne -- es nem ertene, miert nem
        mukodik, miutan beszerezte."""
        monkeypatch.setattr(llm.config, "OPENAI_API_KEY", "")
        monkeypatch.setattr(llm.config, "ANTHROPIC_API_KEY", "")
        assert "OPENAI_API_KEY" in llm.kulcs_hianyzik("gpt-5-nano")
        assert "ANTHROPIC_API_KEY" in llm.kulcs_hianyzik("claude-haiku-4-5")

    def test_meglevo_kulcsnal_nincs_uzenet(self, monkeypatch):
        monkeypatch.setattr(llm.config, "OPENAI_API_KEY", "sk-teszt")
        assert llm.kulcs_hianyzik("gpt-5-nano") == ""


class TestBizalmiKapu:
    """A visszafordithatatlan cimkek vedelme."""

    def test_biztos_unsubscribe_atmegy(self):
        cimke, conf, _ = classify._normalizal(
            {"classification": "unsubscribe", "confidence": 0.95, "rationale": "x"})
        assert cimke == "unsubscribe"
        assert conf == 0.95

    @pytest.mark.parametrize("cimke", ["unsubscribe", "negative"])
    def test_bizonytalan_visszafordithatatlan_other_lesz(self, cimke):
        uj, _, rationale = classify._normalizal(
            {"classification": cimke, "confidence": 0.5, "rationale": "talan"})
        assert uj == "other", "bizonytalan kizaras nem mehet at automatikusan"
        assert "bizalmi kapu" in rationale
        assert cimke in rationale, "az eredeti javaslat maradjon nyomon kovetheto"

    @pytest.mark.parametrize("cimke", ["interested", "not_now", "auto_reply"])
    def test_visszaforditható_cimket_nem_szur(self, cimke):
        # Ezeknel a tevedes olcso: egy 'not_now' 90 nap mulva ujra elojon.
        uj, _, _ = classify._normalizal(
            {"classification": cimke, "confidence": 0.4, "rationale": ""})
        assert uj == cimke

    def test_a_kuszob_pontosan(self):
        alatta, _, _ = classify._normalizal(
            {"classification": "negative", "confidence": classify._MIN_CONFIDENCE - 0.01})
        felette, _, _ = classify._normalizal(
            {"classification": "negative", "confidence": classify._MIN_CONFIDENCE})
        assert alatta == "other" and felette == "negative"


class TestCimkeNormalizalas:
    @pytest.mark.parametrize("rossz", [
        "leiratkozás",      # magyarul adta vissza
        "UNSUBSCRIBED",     # elgepelte
        "no_fit",           # masik feladat cimkeje
        "", None,
    ])
    def test_ismeretlen_cimke_other_lesz(self, rossz):
        cimke, _, rationale = classify._normalizal(
            {"classification": rossz, "confidence": 0.99})
        assert cimke == "other", "ismeretlen cimke SOHA ne valjon suppressionne"
        assert "ismeretlen cimke" in rationale

    def test_nagybetus_cimket_elfogad(self):
        cimke, _, _ = classify._normalizal(
            {"classification": "  INTERESTED  ", "confidence": 0.9})
        assert cimke == "interested"

    @pytest.mark.parametrize("rossz", ["nem szam", None, {}, float("nan")])
    def test_hibas_confidence_nem_dob(self, rossz):
        # Hibas confidence eseten 0.0 -> a bizalmi kapu bezar. Ez a biztonsagos
        # irany: inkabb ember nezze at, mint hogy kizarjunk valakit.
        cimke, conf, _ = classify._normalizal(
            {"classification": "unsubscribe", "confidence": rossz})
        assert cimke == "other"
        assert 0.0 <= conf <= 1.0

    @pytest.mark.parametrize("ertek,vart", [(1.5, 1.0), (-0.2, 0.0)])
    def test_confidence_tartomanyba_szorit(self, ertek, vart):
        _, conf, _ = classify._normalizal(
            {"classification": "other", "confidence": ertek})
        assert conf == vart


class TestKovetkezmenyTabla:
    """A cimke -> kovetkezmeny lekepezes teljes es kizarolagos-e."""

    def test_minden_cimkenek_van_kezelese(self):
        kezelt = (set(classify._COOLDOWN_NAPOK)
                  | set(classify._VISSZAFORDITHATATLAN)
                  | {"interested", "other"})
        assert kezelt == set(prompts.REPLY_CLASSES), (
            "a _kovetkezmeny() nem kezel minden cimket, vagy nem letezo cimket kezel")

    def test_a_cooldown_nem_suppression(self):
        # A 'not_now' es az 'auto_reply' a lead VISSZATERESE, nem kizaras.
        # Ha valaha atkerulnenek a visszafordithatatlanok koze, minden
        # "most nem aktualis" valasz orokre kizarna a ceget.
        assert not (set(classify._COOLDOWN_NAPOK)
                    & set(classify._VISSZAFORDITHATATLAN))

    def test_csak_a_ketto_visszafordithatatlan(self):
        assert set(classify._VISSZAFORDITHATATLAN) == {"unsubscribe", "negative"}


class TestEvidenceGrounding:
    """A hamis idezet a bake-off legsulyosabb hibaja."""

    FORRAS = "Szervizkoordinátort keresünk,\naki a munkalapokat  Excelben vezeti."

    def test_szo_szerinti_idezet_atmegy(self):
        assert evals._foldwhite("a munkalapokat Excelben vezeti") in \
               evals._foldwhite(self.FORRAS)

    def test_sortores_es_dupla_szokoz_nem_szamit(self):
        # Ugyanaz a mondat mas tordelessel -- ez NEM hallucinacio.
        assert evals._foldwhite("keresünk, aki a munkalapokat Excelben") in \
               evals._foldwhite(self.FORRAS)

    def test_kitalalt_idezet_bukik(self):
        assert evals._foldwhite("SAP rendszerben dolgozik") not in \
               evals._foldwhite(self.FORRAS)

    def test_atfogalmazott_idezet_bukik(self):
        # A szabaly "szó szerint" -- az atfogalmazas is hallucinacio.
        assert evals._foldwhite("táblázatban vezeti a munkalapokat") not in \
               evals._foldwhite(self.FORRAS)


class TestKiesesiSzabalyok:
    """A terv A/6 automatikus kiertekelese."""

    def test_egy_ervenytelen_json_kiejt(self):
        r = evals.ModelResult(model="x", osszes=30, talalat=28, ervenytelen_json=1)
        assert "KIESETT" in r.kiesett

    def test_ket_hamis_idezet_meg_bent(self):
        r = evals.ModelResult(model="x", osszes=30, talalat=28, hamis_idezet=2)
        assert r.kiesett == ""

    def test_harom_hamis_idezet_kiejt(self):
        r = evals.ModelResult(model="x", osszes=30, talalat=28, hamis_idezet=3)
        assert "KIESETT" in r.kiesett

    def test_hibatlan_bent_marad(self):
        r = evals.ModelResult(model="x", osszes=30, talalat=27,
                              hatareset_osszes=10, hatareset_talalat=8)
        assert r.kiesett == ""
        assert r.hatareset_arany == 0.8


class TestPromptok:
    def test_a_valasz_szoveg_hatarolva_van(self):
        """A prompt injection vedelem masodik fele: a modell lassa, hol
        kezdodik es hol er veget az IDEGEN szoveg."""
        user = prompts.reply_classifier_user("a@b.hu", "Re: teszt", "barmi")
        assert "<<<VALASZ_SZOVEGE_KEZDETE>>>" in user
        assert "<<<VALASZ_SZOVEGE_VEGE>>>" in user

    def test_a_rendszer_prompt_szol_az_injectionrol(self):
        # A scrapelt es a beerkezo szoveget IDEGENEK irjak.
        assert "ADAT, nem utasítás" in prompts.REPLY_CLASSIFIER_SYSTEM

    def test_a_bizonytalansag_other(self):
        assert "other" in prompts.REPLY_CLASSIFIER_SYSTEM
        assert "kétséges" in prompts.REPLY_CLASSIFIER_SYSTEM

    def test_a_lead_prompt_a_tervbol_valo(self):
        # Szo szerint egyeznie kell a SCRAPER-PLAN fuggelekevel, kulonben a
        # gepi meres nem osszehasonlithato a playgroundos meressel.
        assert "BIZONYÍTÉK-SZABÁLY" in prompts.LEAD_CLASSIFIER_SYSTEM
        assert "webapp_fit" in prompts.LEAD_CLASSIFIER_SYSTEM

    def test_van_prompt_injection_teszteset(self):
        nevek = [n for n, _ in evals.ROBUSZTUSSAG]
        assert "PROMPT INJECTION" in nevek
        assert len(evals.ROBUSZTUSSAG) == 5   # a terv C) pontja 5-ot ir elo


class TestSamplingVedelem:
    """A temperature-kezeles -- ELES HIVASSAL MERVE, 2026-08-22.

    A korabbi feltevesunk az volt, hogy a `claude-haiku-4-5` "meg elfogadja"
    a temperature-t, es csak az ujabb Claude modellek utasitjak el. Az elso
    valodi hivas ezt MEGCAFOLTA: az `anthropic` SDK 1.0.0
    `messages.create()`-jebol a parameter TELJESEN ELTUNT, tehat barmelyik
    modellnel `TypeError`-t dob -- meg azelott, hogy HTTP hivas tortenne.
    """

    def test_az_anthropic_ag_NEM_kuld_temperature_t(self):
        """Ha valaki visszatenne, minden Claude-hivas azonnal elszallna."""
        import inspect
        forras = inspect.getsource(llm._call_anthropic)
        assert '"temperature"' not in forras, (
            "az anthropic SDK 1.0.0 nem fogad el temperature-t -- "
            "a kwarg atadasa TypeError")

    def test_az_sdk_tenyleg_nem_ismeri(self):
        """A feltevest a TELEPITETT SDK-n ellenorizzuk, nem emlekezetbol.

        Ha egy kesobbi SDK visszahozza a parametert, ez a teszt elbukik --
        es akkor ujra lehet gondolni a determinisztikus kimenetet."""
        import anthropic
        import inspect
        sig = inspect.signature(anthropic.Anthropic(api_key="x").messages.create)
        assert "temperature" not in sig.parameters

    def test_az_openai_reasoning_modellek_kimaradnak(self):
        # Az o-sorozat csak az alapertelmezett temperature-t fogadja el.
        for m in ("o1", "o3-mini", "o4-mini"):
            assert m.startswith(llm._SAMPLING_TILTVA)

    def test_a_normal_openai_modell_kap_temperature_t(self):
        # A classifierhez determinisztikus kimenet kell -> temperature 0.
        assert not "gpt-5.6-luna".startswith(llm._SAMPLING_TILTVA)
