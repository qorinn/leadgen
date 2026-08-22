#!/usr/bin/env python3
"""Lead engine-ek: MIT keresunk, es mi alapjan dontjuk el, hogy jo-e.

═══ EZ A FAJL AZ, AMIT UJ IPARAGHOZ SZERKESZTENI KELL ═══════════════════════

A tervezes vezerelve: az iparag ADAT, nem KOD. Egy uj vertikum felvetele =
egy uj EngineDef blokk itt, plusz a hozza tartozo email-sablonok a
templates.py-ban. A scrapeles, az enrichment, a minosites, az export es a
feedback logikaja VALTOZATLAN marad -- azok forrastol es iparagtol fuggetlenek.

Ami engine-enkent kulonbozik:
  - milyen kifejezesekre keresunk (Google Maps)
  - milyen kulcsszo kell a weboldalon ahhoz, hogy jo lead legyen
  - milyen kulcsszo ZARJA KI (es a kizaras versenytarsat jelent-e)
  - milyen kampany (= melyik sablonkeszlet) rendereli a levelet
  - hogyan all elo a szemelyre szabott mondat

Ami NEM kulonbozik: minden mas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .normalize import strip_accents


def fold(text: str) -> str:
    """Kisbetusites + ekezet-eltavolitas. Minden kulcsszo-illesztes ezen fut.

    A magyar weboldalak ekezetesek, a kulcsszolistak viszont ASCII-ban
    olvashatobbak es kevesbe elgepelhetok. (Ugyanaz a hiba, amit a kuldo
    guards.py-jaban is javitani kellett.)
    """
    return strip_accents((text or "").lower())


# ─── Minosites ─────────────────────────────────────────────────────────────

@dataclass
class QualifyResult:
    ok: bool
    reason: str                       # miert nem, ha nem
    hits: list[str] = field(default_factory=list)        # mely kulcsszavak talaltak
    blockers: list[str] = field(default_factory=list)    # mely kizaro szavak talaltak
    is_competitor: bool = False       # ha igen -> suppression, reason='competitor'
    needs_review: bool = False        # gyenge jel -> ember dontson, ne dobjuk el


@dataclass(frozen=True)
class Qualifier:
    """Kulcsszo-alapu minosites. SZANDEKOSAN NEM AI.

    A terv "Ami NEM igenyel AI-t" fejezete ezt kifejezetten kimondja: az
    ugynokseg-kvalifikacio kulcsszoegyezes. Determinisztikus, ingyenes es
    hibatlan -- ha AI-t hivnank ra, penzt fizetnenk azert, hogy a megbizhato
    lepesunkbe hibalehetoseget epitsunk.
    """
    require_any: tuple[str, ...]
    # ERROS kizaro jel: egyertelmuen sajat fejlesztesi kapacitasra utal.
    # Ezek azonnal versenytars-suppressionbe visznek.
    exclude_hard: tuple[str, ...] = ()
    # GYENGE kizaro jel: gyakran elofordul ugyfel-referenciaban, blogcikkben,
    # vagy kiszervezett szolgaltataskent. Ezek NEM zarnak ki automatikusan,
    # hanem emberi atnezesre allitjak a ceget (`review` statusz).
    exclude_soft: tuple[str, ...] = ()
    exclude_means_competitor: bool = True
    min_hits: int = 1

    def check(self, text: str, strong_context: str = "") -> QualifyResult:
        """`strong_context`: a weboldal cime, meta leirasa es a menu szovege.

        MIERT KULON: egy gyenge kulcsszo (pl. "weboldal keszites") teljesen mast
        jelent aszerint, hogy HOL all. Ha egy ugyfel-velemenyben, az nem az o
        szolgaltatasuk. Ha viszont a CIMBEN vagy a MENUBEN, akkor gyakorlatilag
        biztosan az -- oda a ceg a sajat ajanlatat irja.
        Valos pelda: "aMarketingese Marketing Ugynokseg I PPC hirdeteskezeles,
        Keresomarketing, SEO, weboldal keszites" -- ez a <title>, tehat sajat
        szolgaltatas, nem kell emberi dontes.
        """
        folded = fold(text)
        eros = fold(strong_context)
        hits = [k for k in self.require_any if fold(k) in folded]
        hard = [k for k in self.exclude_hard if fold(k) in folded]
        soft = [k for k in self.exclude_soft if fold(k) in folded]

        # A cimben/menuben allo gyenge jel EROS jelle lep elo.
        cimben = [k for k in soft if fold(k) in eros]
        if cimben:
            hard = hard + cimben
            soft = [k for k in soft if k not in cimben]

        if hard:
            return QualifyResult(
                ok=False,
                reason="sajat fejlesztesi szolgaltatas (stack vagy cim/menu talalat)",
                hits=hits, blockers=hard,
                is_competitor=self.exclude_means_competitor,
            )
        if soft and len(hits) >= self.min_hits:
            return QualifyResult(
                ok=False,
                reason="gyenge kizaro jel -- emberi dontes kell",
                hits=hits, blockers=soft,
                needs_review=True,
            )
        if soft:
            return QualifyResult(
                ok=False, reason="kizaro kulcsszo, es nincs eleg marketing-jel",
                hits=hits, blockers=soft,
                is_competitor=self.exclude_means_competitor,
            )
        if len(hits) < self.min_hits:
            return QualifyResult(
                ok=False,
                reason=f"nincs meg a szukseges {self.min_hits} kulcsszo",
                hits=hits,
            )
        return QualifyResult(ok=True, reason="", hits=hits)


# ─── Forras-definicio ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class MapsSearch:
    """Egy Google Maps lekerdezes. Tobb is tartozhat egy engine-hez.

    MIERT TELEPULESENKENT ES NEM ORSZAGOSAN (merve 2026-08-21):
    a `countryCode: hu` orszagos kereses NEM az orszag legjobb cegeit adja
    vissza, hanem az orszag FOLDRAJZI KOZEPPONTJA koruli talalatokat. Egy
    25 elemu teszt eredmenye: 10 Kecskemet, 2 Dunaujvaros, 1 Budapest, es
    olyan falvak, mint Ballószög, Orgovány, Tiszakécske. Vagyis pont a
    celcsoporton kivuli mikrovallalkozasok.

    Telepulesenkent haladva viszont te dontod el a SORRENDET: eloszor
    Budapest, ahol a 3-30 fos ugynoksegek tobbsege van, es csak utana a
    kisebb varosok. Ez dragabb lekerdezesenkent, de olcsobb HASZNALHATO
    LEADENKENT -- es a folytatolagos ingest miatt egyik lekerdezes sem fut le
    ketszer.
    """
    terms: tuple[str, ...]
    locations: tuple[str, ...]
    max_per_search: int = 50
    # Csak olyan cegek, akiknek VAN weboldala. Akinek nincs, azt nem tudjuk
    # sem enrichmentelni, sem minositeni -- tehat kifizetnenk egy hasznalhatatlan
    # talalatot. Ugynoksegeknel ez csak ~2% (szinte mindnek van oldala), de
    # pl. kivitelezoknel vagy szervizeknel sokkal tobb.
    only_with_website: bool = True


@dataclass(frozen=True)
class EngineDef:
    key: str                 # belso azonosito, ez kerul a sources.source_type-ba
    label: str               # emberi nev a riportokban
    campaign: str            # melyik templates.py sablonkeszlet rendereli
    best_offer: str          # website | webapp | mobile | partner
    qualifier: Qualifier
    personalization: Callable[[QualifyResult, dict], str]
    maps_searches: tuple[MapsSearch, ...] = ()
    base_score: int = 20     # signal_score alapertek, ha bekerul
    enabled: bool = True


# ═══════════════════════════════════════════════════════════════════════════
#  1. UGYNOKSEGI PARTNER  (SCRAPER-PLAN 8.1)
# ═══════════════════════════════════════════════════════════════════════════
# Ez NEM vegfelhasznalo ceget keres, hanem partnert: marketingugynoksegeket,
# akiknek van ugyfeluk fejlesztesi igennyel, de sajat fejlesztojuk nincs.
# 1 lead -> N projekt, es nem kell keresletet teremteni.

_AGENCY_REQUIRE = (
    "ppc", "google ads", "meta ads", "facebook hirdet", "hirdeteskezel",
    "kozossegi media", "social media", "seo", "keresooptimalizal",
    "tartalommarketing", "content marketing", "branding", "arculat",
    "marketing strategia", "marketingstrategia", "kreativ", "kampany",
    "online marketing", "digitalis marketing", "email marketing",
)

# EROS jel: sajat fejlesztoi kapacitas, technologiai stack. Ezek gyakorlatilag
# sosem fordulnak elo veletlenul egy tisztan marketinges oldalon.
_AGENCY_EXCLUDE_HARD = (
    "egyedi fejlesztes", "szoftverfejlesztes", "applikaciofejlesztes",
    "alkalmazasfejlesztes", "mobilfejlesztes", "rendszerfejlesztes",
    "fejleszto csapat", "fejlesztocsapat", "sajat fejleszto",
    "fejlesztoink", "programozoink", "egyedi szoftver",
    "react", "laravel", "node.js", "symfony", "vue.js", "angular",
    "flutter", "kotlin", "swift",
)

# GYENGE jel: gyakran szerepel ugyfel-referenciaban, blogcikkben, vagy
# kiszervezett szolgaltataskent -- vagyis attol meg lehet jo partner.
# Merve: a plus-kreativ.hu-nal a "webfejlesztesi feladatokat" egy UGYFEL
# velemenyeben szerepelt, nem a szolgaltatasaik kozott.
_AGENCY_EXCLUDE_SOFT = (
    "webfejlesztes", "weboldal fejlesztes", "weboldal keszites",
    "webshop keszites", "honlapkeszites", "webdesign",
)


def _agency_personalization(q: QualifyResult, extract: dict) -> str:
    """Tenyszeru mondat a minositesbol. AI NELKUL, ezert nem tud hallucinalni.

    A mondat csak olyan szolgaltatasra utal, amit SZO SZERINT megtalaltunk a
    weboldalukon -- ez maga az evidence grounding, csak ingyen.
    """
    szep = {
        "ppc": "a PPC", "google ads": "a Google Ads", "meta ads": "a Meta Ads",
        "seo": "a SEO", "keresooptimalizal": "a keresőoptimalizálás",
        "kozossegi media": "a közösségi média", "social media": "a közösségi média",
        "tartalommarketing": "a tartalommarketing", "content marketing": "a tartalommarketing",
        "branding": "a branding", "arculat": "az arculattervezés",
        "marketing strategia": "a stratégia", "marketingstrategia": "a stratégia",
        "kreativ": "a kreatív munka", "hirdeteskezel": "a hirdetéskezelés",
        "email marketing": "az email marketing", "kampany": "a kampánykezelés",
    }
    nevek = []
    for h in q.hits:
        n = szep.get(h)
        if n and n not in nevek:
            nevek.append(n)
        if len(nevek) == 2:
            break
    if len(nevek) == 2:
        mit = f"{nevek[0]} és {nevek[1]}"
    elif nevek:
        mit = nevek[0]
    else:
        mit = "a marketing"
    return (f"Körülnéztem nálatok, és {mit} a fő erősségetek — "
            "fejlesztést viszont nem láttam a szolgáltatások közt.")


AGENCY_PARTNER = EngineDef(
    key="agency_partner",
    label="Ügynökségi partner (8.1)",
    campaign="agency_partner",
    best_offer="partner",
    base_score=40,
    qualifier=Qualifier(
        require_any=_AGENCY_REQUIRE,
        exclude_hard=_AGENCY_EXCLUDE_HARD,
        exclude_soft=_AGENCY_EXCLUDE_SOFT,
        exclude_means_competitor=True,
        min_hits=1,
    ),
    personalization=_agency_personalization,
    maps_searches=(
        MapsSearch(
            terms=("marketing ügynökség", "online marketing ügynökség",
                   "reklámügynökség", "PPC ügynökség", "SEO ügynökség",
                   "digitális ügynökség"),
            locations=("Budapest, Hungary", "Debrecen, Hungary",
                       "Szeged, Hungary", "Pécs, Hungary", "Győr, Hungary"),
            max_per_search=50,
        ),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  PELDA: IGY VESZEL FEL EGY UJ IPARAGAT
# ═══════════════════════════════════════════════════════════════════════════
# Ez a definicio KESZ, de `enabled=False`, tehat nem fut. Amikor kell, allitsd
# True-ra, es ird meg hozza a sablonokat a templates.py-ban
# (CAMPAIGNS["field_service"] = (cold, follow_up_1, follow_up_2)).
#
# Semmi mas nem valtozik: az enrichment, a minosites, az export es a feedback
# ugyanaz marad. Ez a lenyeg -- az iparag adat, nem kod.

def _field_service_personalization(q: QualifyResult, extract: dict) -> str:
    return ("Körülnéztem nálatok, és úgy láttam, hogy "
            f"{q.hits[0] if q.hits else 'a szolgáltatás'} a fő profilotok.")


FIELD_SERVICE = EngineDef(
    key="field_service",
    label="Terepi szerviz / kivitelező (1. engine, PELDA)",
    campaign="field_service",
    best_offer="webapp",
    base_score=30,
    enabled=False,                      # ← ITT KAPCSOLD BE
    qualifier=Qualifier(
        require_any=("szerviz", "karbantartas", "kivitelezes", "telepites",
                     "javitas", "klima", "napelem", "gepeszet"),
        # Itt a kizaras NEM versenytarsat jelent, csak azt, hogy nem fit --
        # ezert exclude_means_competitor=False.
        exclude_hard=("aruhaz", "webshop", "kiskereskedelem"),
        exclude_means_competitor=False,
    ),
    personalization=_field_service_personalization,
    maps_searches=(
        MapsSearch(
            terms=("klímaszerelés", "napelem telepítés", "épületgépészet"),
            locations=("Budapest, Hungary",),
            max_per_search=50,
        ),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  3. OPERATIONAL PAIN  (SCRAPER-PLAN 1. engine)  -- allashirdetes-alapu
# ═══════════════════════════════════════════════════════════════════════════
# Ez az EGYETLEN engine, ami nem weboldalrol indul, hanem ALLASHIRDETESBOL.
# A gondolat: ha egy ceg olyan pozíciót hirdet, aminek a munkakore nagyreszt
# adminisztracio es koordinacio, akkor ott egy belso webalkalmazas valodi
# problemat oldana meg.
#
# MIERT MAS A MINOSITES ITT: a tobbi engine a ceg WEBOLDALAN keres kulcsszot.
# Itt a HIRDETES SZOVEGE a bizonyitek -- azt a `sources.raw_signal`-bol
# olvassuk, nem a crawlbol. A `Qualifier` ugyanaz marad, csak mas szoveget kap.
#
# ⚠️ A VEGSO MINOSITES A 10. SZAKASZ AI-CLASSIFIERE LESZ. Az itteni
# kulcsszavak ELOSZURESRE valok: olcson kidobjak a nyilvanvaloan rossz
# talalatokat, mielott egy fizetos LLM-hivast koltenenk rajuk.

# A terv keresoszavai (SCRAPER-PLAN, "Honnan szedd a tesztadatot").
_OPS_PAIN_SEARCHES = (
    "szervizkoordinátor", "diszpécser", "munkairányító",
    "projektkoordinátor", "logisztikai koordinátor",
    "szerviz munkafelvevő", "ügyfélszolgálati koordinátor",
)

# A FAJDALOM jelei a hirdetes szovegeben. Merve a valos adaton (2026-08-22,
# Palla Autojavito Kft.): "Munkalapok felvetele, kezelese es nyomon kovetese",
# "Kapcsolattartas a szerelokkel", "adminisztracio elvegzese" -- ezek szo
# szerint ott vannak egy tipikus hirdetesben.
_OPS_PAIN_REQUIRE = (
    "excel", "tablazat", "munkalap", "adminisztracio", "adminisztrativ",
    "nyilvantartas", "koordinal", "koordinacio", "utemez", "beoszt",
    "diszpecs", "munkairanyit", "kapcsolattartas a szerel",
    "megrendelesek kezelese", "kezi adatbevitel", "papir alapu",
    "tobb telephely", "logisztik",
)

# Ami kizarja. NEM versenytarsat jelent -- csak azt, hogy nem fit.
_OPS_PAIN_EXCLUDE = (
    # Sajat IT/fejlesztoi kapacitas -> nem nekunk valo
    "szoftverfejleszto", "programozo", "rendszergazda", "it osztaly",
    "fejlesztoi csapat", "sajat it",
    # Tul nagy szervezet -> nem KKV
    "multinacionalis", "globalis vallalat", "shared service",
)


def _ops_pain_personalization(q: QualifyResult, row: dict) -> str:
    """VAZLAT -- a 10. szakasz AI-ja fogja megirni a valodi mondatot.

    Addig is legyen valami, ami TENYSZERU es a hirdetes szavaira epul:
    ha a kulcsszo nem a hirdetesben volt, ne allitsuk, hogy ott volt.
    """
    jelek = [h for h in q.hits[:2]]
    if not jelek:
        return ""
    return (f"Láttam a {row.get('city') or 'a'} álláshirdetésüket — a leírásban "
            f"a {' és a '.join(jelek)} is szerepel a feladatok közt.")


OPS_PAIN = EngineDef(
    key="ops_pain",
    label="Operational Pain (állashirdetés-alapú)",
    campaign="ops_pain",
    best_offer="webapp",
    base_score=40,          # a terv legerosebb engine-je
    # ⚠️ KIKAPCSOLVA, amig a 10. szakasz AI-classifiere es a sablonok
    # el nem keszulnek. A forras (ingest) enelkul is futtathato.
    enabled=False,
    qualifier=Qualifier(
        require_any=_OPS_PAIN_REQUIRE,
        exclude_hard=_OPS_PAIN_EXCLUDE,
        exclude_means_competitor=False,
    ),
    personalization=_ops_pain_personalization,
    # Nincs maps_searches: ez a forras a Profession.hu, nem a Google Maps.
    # A Maps csak a DOMAIN FELOLDASARA jon kepbe (lasd sources/profession.py).
)


# ─── Nyilvantartas ─────────────────────────────────────────────────────────

ALL_ENGINES: dict[str, EngineDef] = {
    e.key: e for e in (AGENCY_PARTNER, FIELD_SERVICE, OPS_PAIN)
}


def get(key: str) -> EngineDef:
    engine = ALL_ENGINES.get(key)
    if engine is None:
        elerheto = ", ".join(sorted(ALL_ENGINES))
        raise SystemExit(f"HIBA: ismeretlen engine: {key!r}\n  Elerheto: {elerheto}")
    if not engine.enabled:
        raise SystemExit(
            f"HIBA: a(z) {key!r} engine ki van kapcsolva (enabled=False).\n"
            "  Bekapcsolas: leadgen/engines.py, es ird meg hozza a sablonokat\n"
            "  a cold-email-starter/templates.py CAMPAIGNS dict-jeben."
        )
    return engine
