#!/usr/bin/env python3
"""7.1 e-beszamolo: objektiv meret- es penzszuro.

    arbevetel + letszam  ->  economic_value: LOW / MEDIUM / HIGH
                             (mar nem AI-tipp, hanem TENY)

A terv szerint ez "az egyik legertekesebb kiegeszites": a "nagy arbevetel +
rossz digitalis mukodes" kombinacio a legjobb lead, ami letezik -- van penz,
es van problema. Enelkul ezt nem lehet megkulonboztetni a "kicsi ceg + rossz
weboldal" esettol, ami viszont majdnem ertektelen.

════════════════════════════════════════════════════════════════════════════
MIERT NINCS ITT AUTOMATIKUS LEKERES  --  a 0.3 elotesz eredmenye (2026-08-26)

A terv abbol indult ki, hogy az e-beszamolo.im.gov.hu "kotelezoen publikus es
ingyenesen elerheto", tehat cegenkent egy HTTP-keres. Megneztem a portalt, es
harom dolog derult ki, ami egyutt kizarja az automatikus lekerest:

  1. A kereso ele ALTCHA proof-of-work captcha van kotve
     (`/altcha/api/v1/challenge`). Ez nem "ember-e" teszt, hanem szandekos
     koltseg-korlat a gepi lekerdezes ellen.

  2. A Felhasznalasi Feltetelek meghatarozzak, mi a RENDELTETESSZERU
     hasznalat -- szo szerint: "amennyiben az igenybevevo a Cegtorvenyben
     meghatarozott HITELEZOVEDELMI CELBOL veszi igenybe a szolgaltatast".
     Egy ertekesitesi cellista epitese nem hitelezovedelem.

  3. Ugyanaz a dokumentum kimondja, hogy ha a felhasznalo "kulonfele
     technikai megoldasok igenybevetelevel torekszik a korlatozas
     megkerulesere", a szolgaltato RENDORSEGI FELJELENTEST tesz.

A captcha megkerulese tehat nem szurke zona, hanem a feltetelekben nevesitett
eset. Ezert ez a modul SEMMILYEN keresest nem intez a portal fele.

AMI HELYETTE VAN -- es amit a terv maga is eloir ("legyen manualis fallback a
legjobb 20-30 leadre"):

  worklist  ->  a legjobb N lead egy CSV-ben, kesz keresesi adatokkal
  import    ->  a kitoltott CSV visszaolvasasa
  set       ->  egyetlen ceg adata a parancssorbol (gyors javitashoz)

A HIVATALOS TOMEGES UT IS LETEZIK, es a felhasznalonak erdemes elinditania:
a portal "Beszamolo allomany ertekesitese" oldala szerint a "Csoportos
beszamolo kero lap" kitoltesevel es az e-beszamolo@mkifk.hu cimre kuldesevel
szurt, csoportos lekerdezes IGENYELHETO. Az igy kapott fajl a `--import`
uttal egy lepesben betoltheto. (TEENDOK.md)

════════════════════════════════════════════════════════════════════════════
KET SZABALY, AMIT NE FORDITS MEG

1. EZ NEM KIZARO KAPU. A 2026-08-25-i megorzo leadmodell felulirja a terv
   eredeti "csak MEDIUM+ megy outreachbe" mondatat: a `LOW` ertek CIMKET es
   alacsonyabb rangsorolast jelent, nem elutasitast. Hianyzo penzugyi adat
   pedig vegkepp nem allithat le semmit -- a legtobb cegunkrol egyszeruen
   meg nincs adat.

2. AZ ARBEVETEL FORINTBAN VAN, NEM EZER FORINTBAN. A beszamolo urlapja
   "adatok E Ft-ban" formaban jelenik meg, tehat ez a leggyakoribb elirasi
   hiba: valaki beirja, hogy 350000 (= 350 M Ft a beszamoloban), mi meg
   350 ezer forintkent ertjuk, es a ceg csendben LOW lesz. Az importer
   ezert HANGOSAN figyelmeztet a gyanusan kicsi ertekekre.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from . import config, db, labels

# A kereso urlapja harom kulcsot fogad el (kereses oldal, 2026-08-26):
# cegjegyzekszam, adoszam elso 8 szamjegye, cegnev (min. 4 karakter).
KERESO_URL = "https://e-beszamolo.im.gov.hu/oldal/beszamolo_kereses"

# A worklist CSV oszlopai. Az elso hat MI adjuk (ne ird at), az utolso hat
# a TE dolgod kitolteni.
WORKLIST_HEADER = [
    "company_id", "company_name", "normalized_domain", "city", "tax_number",
    "kereses_url",
    # ── innentol te toltod ki ──
    "revenue_huf", "headcount", "balance_total_huf", "profit_huf",
    "financial_year", "megjegyzes",
]

# Egy mukodo ceg eves arbevetele forintban ritkan van egymillio alatt. Ha egy
# importalt ertek ez alatt van, szinte biztos, hogy EZER FORINTOT irtak be.
GYANUSAN_KICSI_HUF = 1_000_000

WORKLIST_FILE = "financials_worklist.csv"


# ─── A minosites: ket szam -> egy cimke ────────────────────────────────────

def economic_value(revenue: float | None, headcount: int | None) -> str | None:
    """LOW / MEDIUM / HIGH, vagy None, ha egyik szamot sem ismerjuk.

    A KETTO VAGY-KAPCSOLATBAN VAN, nem es-kapcsolatban. Egy 30 fos ceg akkor
    is komoly szervezet, ha alacsony arresen dolgozik; egy 800 M Ft-os
    kereskedocegnek pedig akkor is van penze, ha harman vannak.

    Amit ez a fuggveny SZANDEKOSAN nem tud: megkulonboztetni a valodi
    mukodest a holdingtol vagy az atfolyo-szamlas kereskedotol. Az a
    kalibralas dolga (a kuszobok .env-bol jonnek), nem egy beleegetett
    szabalye.
    """
    if revenue is None and headcount is None:
        return None

    rev = float(revenue or 0)
    fo = int(headcount or 0)

    if rev >= config.REVENUE_HIGH_HUF or fo >= config.HEADCOUNT_HIGH:
        return "HIGH"
    if rev >= config.REVENUE_MEDIUM_HUF or fo >= config.HEADCOUNT_MEDIUM:
        return "MEDIUM"
    return "LOW"


def bonus(ertek: str | None, revenue: float | None,
          webshop_platform: str | None) -> float:
    """A `signal_score` penzugyi bonusza (terv 2512 es 2518).

        +15  magas arbevetel                      [7.1]
        +25  dobozos webshop + magas arbevetel    [8.3]

    A ketto OSSZEADODIK: a "kinotte a platformjat" szog akkor a legerosebb,
    ha a ceg egeszekent is nagy. A 8.3 kuszobe kulon all (es alacsonyabb),
    mert egy 300 M Ft-os webshop mar utkozik a dobozos korlatokba.
    """
    pont = 0.0
    if ertek == "HIGH":
        pont += 15
    if webshop_platform and float(revenue or 0) >= config.WEBSHOP_REVENUE_MIN_HUF:
        pont += 25
    return pont


def kereses_url(row: dict[str, Any]) -> str:
    """A portal keresooldala, elokeszitve az adott ceghez.

    A kereso POST-tal dolgozik, tehat a lekerdezest NEM lehet linkbe tenni --
    ez a link a keresooldalra visz, a beirando kulcsot a worklist sora adja.
    A `q` parameter csak emlekezteto a fajlban, a portal figyelmen kivul hagyja.
    """
    kulcs = (row.get("tax_number") or row.get("company_name") or "").strip()
    return f"{KERESO_URL}?q={quote(kulcs)}" if kulcs else KERESO_URL


# ─── Worklist: kit nezzunk meg kezzel ──────────────────────────────────────

def worklist(limit: int = 20) -> list[dict[str, Any]]:
    """A legjobb N lead, amirol MEG NINCS penzugyi adatunk.

    A terv szerint ez CELZOTT enrichment, nem bulk: "cegenkent egy lekeres,
    de csak a mar megszurt leadekre". Amit a sorrend jelent: a `signal_score`
    szerinti legjobb leadek elol, mert ha a lista vegen fogy el a turelem, a
    fontos cegek akkor is meglegyenek.

    A `rejected`/`suppressed` cegek kimaradnak -- rajuk mar nem koltunk idot.
    Az `error` allapotuak viszont BENT MARADNAK, ha van nevuk: azoknal
    tipikusan csak a domain hianyzik, a cegnev alapjan viszont kereshetok.
    """
    return db.query("""
        select c.id as company_id, c.company_name, c.normalized_domain,
               c.city, c.tax_number, c.signal_score, c.status
          from companies c
         where c.financials_checked_at is null
           and c.status not in ('suppressed', 'rejected')
           and coalesce(c.company_name, '') <> ''
         order by c.signal_score desc nulls last, c.first_seen_at
         limit %s
    """, (limit,))


def worklist_kiir(rows: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WORKLIST_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({
                "company_id": str(r["company_id"]),
                "company_name": r.get("company_name") or "",
                "normalized_domain": r.get("normalized_domain") or "",
                "city": r.get("city") or "",
                "tax_number": r.get("tax_number") or "",
                "kereses_url": kereses_url(r),
                "revenue_huf": "", "headcount": "", "balance_total_huf": "",
                "profit_huf": "", "financial_year": "", "megjegyzes": "",
            })
    return path


# ─── Import: a kitoltott adat vissza a DB-be ───────────────────────────────

@dataclass
class ImportStats:
    olvasott: int = 0
    frissitett: int = 0
    ures: int = 0
    hibas: int = 0
    ismeretlen: int = 0
    ezer_forint_gyanu: list[str] = field(default_factory=list)
    ertekek: dict[str, int] = field(default_factory=dict)


def _szam(ertek: Any) -> float | None:
    """Emberi bepotyogott szam -> float. Ures -> None.

    Elfogadja a szokozzel/ponttal tagolt alakot ("1 234 567", "1.234.567")
    es a tizedesvesszot is. Ami nem ertelmezheto, az hiba, NEM nulla: egy
    csendes nulla ugy nezne ki, mint egy valodi, nullas arbevetel.
    """
    if ertek is None:
        return None
    s = str(ertek).strip().replace(" ", " ")
    if not s:
        return None
    s = s.replace(" ", "").replace("Ft", "").replace("ft", "")
    # Ezres tagolas pontokkal (1.234.567) vs. tizedespont -- ha egynel tobb
    # pont van, biztosan tagolas.
    if s.count(".") > 1:
        s = s.replace(".", "")
    s = s.replace(",", ".")
    return float(s)


def import_csv(path: Path, dry: bool = False, verbose: bool = True) -> ImportStats:
    """Kitoltott worklist (vagy csoportos beszamolo-export) beolvasasa.

    A sor azonositasa harom lepcsos, ebben a sorrendben:
        company_id  ->  tax_number  ->  normalized_domain
    Cegnev szerint SZANDEKOSAN nem parositunk: a magyar cegnevek eleg
    hasonloak ahhoz, hogy egy fuzzy talalat rossz ceghez irjon arbevetelt --
    es onnan az mar egy levelbe kerulo teves allitas.
    """
    stats = ImportStats()
    with path.open(encoding="utf-8-sig", newline="") as f:
        sorok = list(csv.DictReader(f))

    for sor in sorok:
        stats.olvasott += 1
        try:
            revenue = _szam(sor.get("revenue_huf") or sor.get("revenue"))
            balance = _szam(sor.get("balance_total_huf") or sor.get("balance_total"))
            profit = _szam(sor.get("profit_huf") or sor.get("profit"))
            fo_raw = _szam(sor.get("headcount"))
            ev_raw = _szam(sor.get("financial_year"))
        except ValueError:
            stats.hibas += 1
            if verbose:
                print(f"  HIBAS SZAM: {sor.get('company_name') or sor.get('company_id')}")
            continue

        if revenue is None and fo_raw is None:
            stats.ures += 1
            continue

        headcount = int(fo_raw) if fo_raw is not None else None
        ev = int(ev_raw) if ev_raw is not None else None

        if revenue is not None and 0 < revenue < GYANUSAN_KICSI_HUF:
            stats.ezer_forint_gyanu.append(
                f"{sor.get('company_name') or sor.get('company_id')}: {revenue:,.0f} Ft")

        cel = _azonosit(sor)
        if not cel:
            stats.ismeretlen += 1
            if verbose:
                print(f"  NINCS ILYEN CEG: {sor.get('company_name') or sor.get('company_id')}")
            continue

        ertek = economic_value(revenue, headcount)
        stats.ertekek[ertek or "?"] = stats.ertekek.get(ertek or "?", 0) + 1
        if not dry:
            ment(cel, revenue=revenue, headcount=headcount, balance_total=balance,
                 profit=profit, financial_year=ev, forras="csv_import")
        stats.frissitett += 1

    if verbose:
        _import_riport(stats, dry)
    return stats


def _azonosit(sor: dict[str, Any]) -> str | None:
    """A CSV sor -> company_id. None, ha nem talalhato meg egyertelmuen."""
    cid = (sor.get("company_id") or "").strip()
    if cid:
        rows = db.query("select id from companies where id = %s", (cid,))
        if rows:
            return str(rows[0]["id"])

    adoszam = (sor.get("tax_number") or "").strip().replace("-", "")
    if adoszam:
        rows = db.query(
            "select id from companies where replace(tax_number, '-', '') = %s", (adoszam,))
        if len(rows) == 1:
            return str(rows[0]["id"])

    domain = (sor.get("normalized_domain") or "").strip().lower()
    if domain:
        rows = db.query("select id from companies where normalized_domain = %s", (domain,))
        if len(rows) == 1:
            return str(rows[0]["id"])
    return None


# ─── Iras ──────────────────────────────────────────────────────────────────

def ment(company_id: str, *, revenue: float | None, headcount: int | None,
         balance_total: float | None = None, profit: float | None = None,
         financial_year: int | None = None, forras: str = "manual") -> str | None:
    """Egy ceg penzugyi adatanak rogzitese. Visszaadja az uj economic_value-t.

    A `signal_score` frissitese IDEMPOTENS: a korabban adott bonuszt levonjuk,
    az ujat hozzaadjuk. Enelkul minden ujrafuttatas ujra hozzaadna a
    +15/+25 pontot, es a rangsor csendben elromlana (lasd 011_financials.sql).
    """
    ertek = economic_value(revenue, headcount)

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            select coalesce(financial_bonus, 0) as regi_bonusz, webshop_platform
              from companies where id = %s
        """, (company_id,))
        row = cur.fetchone()
        if not row:
            return None
        regi = float(row["regi_bonusz"] or 0)
        uj = bonus(ertek, revenue, row.get("webshop_platform"))

        cur.execute("""
            update companies
               set revenue = %s, headcount = %s, balance_total = %s, profit = %s,
                   financial_year = %s, financial_source = %s,
                   financials_checked_at = now(),
                   economic_value = %s,
                   financial_bonus = %s,
                   signal_score = greatest(coalesce(signal_score, 0) - %s + %s, 0)
             where id = %s
        """, (revenue, headcount, balance_total, profit, financial_year, forras,
              ertek, uj, regi, uj, company_id))

        labels.clear_label(cur, company_id, "financials_missing")
        # A LOW cimke NEM kizaras. Azert kerul fel, hogy a riportban lathato
        # legyen, MIERT all hatul egy lead a sorban -- es hogy a kuszob
        # kalibralasa utan ujraszamolhato legyen.
        if ertek == "LOW":
            labels.set_label(cur, company_id, "low_economic_value",
                             {"revenue": revenue, "headcount": headcount,
                              "financial_year": financial_year})
        else:
            labels.clear_label(cur, company_id, "low_economic_value")
    return ertek


def jelold_hianyzonak(company_id: str, ok: str = "nincs kozzetett beszamolo") -> None:
    """A ceget megneztuk, de nincs (vagy nem talalhato) beszamoloja.

    Ez NEM elutasitas: a `financials_checked_at` csak azt jelenti, hogy a
    kovetkezo worklistben ne jojjon elo ujra. Az `economic_value` marad NULL.
    """
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            update companies
               set financials_checked_at = now(), financial_source = 'manual'
             where id = %s
        """, (company_id,))
        labels.set_label(cur, company_id, "financials_missing", {"reason": ok})


def _import_riport(stats: ImportStats, dry: bool) -> None:
    print(f"\nolvasott sor: {stats.olvasott}   frissitett: {stats.frissitett}   "
          f"ures: {stats.ures}   ismeretlen ceg: {stats.ismeretlen}   "
          f"hibas szam: {stats.hibas}")
    if stats.ertekek:
        print("  " + "   ".join(f"{k}: {n}" for k, n in sorted(stats.ertekek.items())))
    if stats.ezer_forint_gyanu:
        print(f"\n  !!! {len(stats.ezer_forint_gyanu)} arbevetel gyanusan kicsi "
              f"({GYANUSAN_KICSI_HUF:,.0f} Ft alatt).")
        print("      A beszamolo urlapja EZER FORINTBAN jeleniti meg az adatokat --")
        print("      ide viszont FORINT kell. Ellenorizd ezeket:")
        for s in stats.ezer_forint_gyanu[:10]:
            print(f"        {s}")
    if dry:
        print("\n  [SZARAZ FUTAS -- semmit nem irtam a DB-be]")


# ─── A parancs ─────────────────────────────────────────────────────────────

def run(limit: int = 20, verbose: bool = True) -> Path:
    """Worklist keszitese: kit nezzek meg kezzel a portalon."""
    rows = worklist(limit)
    path = config.BASE / "data" / WORKLIST_FILE

    if not rows:
        if verbose:
            print("Minden cegnek megvan a penzugyi adata (vagy meg nincs egy ceg sem).")
        return path

    worklist_kiir(rows, path)
    if verbose:
        print(f"{len(rows)} ceg var penzugyi adatra. A lista kiirva ide:")
        print(f"  {path}\n")
        print("MIT KELL CSINALNI:")
        print(f"  1. nyisd meg: {KERESO_URL}")
        print("  2. keress cegnevre vagy adoszamra, es nyisd meg a beszamolot")
        print("  3. ird be a CSV-be: revenue_huf, headcount, financial_year")
        print("     FIGYELEM: FORINTBAN, nem ezer forintban (a beszamolo E Ft-ban mutatja)")
        print("  4. toltsd vissza:")
        print(f"     ./leadgen.sh enrich financials --import {path}\n")
        print("  Ha egy cegnek nincs kozzetett beszamoloja, hagyd uresen a sort --")
        print("  a kovetkezo worklistben ujra elojon.\n")
        print("  Tomeges ut (ez a hivatalos, es nem kezi munka): a portal")
        print("  \"Beszamolo allomany ertekesitese\" oldalarol a \"Csoportos beszamolo")
        print("  kero lap\" elkuldheto az e-beszamolo@mkifk.hu cimre. Az igy kapott")
        print("  fajl ugyanezzel az --import kapcsoloval betoltheto. Lasd: TEENDOK.md\n")
        for r in rows[:20]:
            nev = (r.get("company_name") or "")[:42]
            dom = r.get("normalized_domain") or "-"
            print(f"  {r['signal_score']:>6.1f}  {nev:<44} {dom}")
    return path
