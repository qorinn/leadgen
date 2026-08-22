#!/usr/bin/env python3
"""8.2 „halott fejleszto" enrichment.

    weboldal footere -> ki keszitette? -> el meg az a fejleszto?

MIERT EZ AZ EGYIK LEGJOBB SIGNAL A TERVBEN:
  - teljesen objektiv (nincs AI-tippeles, nincs hallucinacio)
  - aktualis fajdalom (nincs kihez fordulnia, ha valami elromlik)
  - nulla plusz scrapeles: a footer mar benne van a letoltott HTML-ben
  - a kizart ag INGYEN ad versenytars-terkepet

EZ NEM FORRAS, HANEM ENRICHMENT. Nem kell hozza uj leadforras -- rarakodik
minden mar meglevo leadre, barmelyik engine hozta be oket.

════════════════════════════════════════════════════════════════════════════
A LEGFONTOSABB TERVEZESI DONTES: A KULCSSZO ONMAGABAN NEM ELEG

Merve a 49 letoltott oldalon (2026-08-22): a "keszitette / weboldal keszites /
powered by" mintak 7 oldalon talaltak, de ebbol MINDOSSZE 1 volt valodi
fejleszto-kredit. A tobbi:

  4x  a ceg SAJAT szolgaltatas-menuje  ("Weboldal keszites" menupont)
  1x  stock-foto kredit                 ("Photo design by: Freepik")
  1x  platform + tarhely                ("Powered by WordPress", "Hosting: ...")

Vagyis a puszta kulcsszo ~85%-ban teved. A megkulonbozteto a KIMENO LINK:
egy valodi kredit IDEGEN domainre mutat, a sajat szolgaltatas-menu pedig a
SAJAT domainre. Ezert a felismeres harom feltetelt kot ossze:

    1. a minta illeszkedik a footerben
    2. a minta KOZELEBEN van egy link
    3. a link IDEGEN domainre mutat, es az nem platform/tarhely/stockfoto

A terv kemeny szabalya: "Ha a footer-kredit nem egyertelmu, a lead inkabb
essen ki, mint hogy rossz nevet irj egy emailbe." Ezert minden bizonytalan
eset kimarad.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import httpx
from selectolax.parser import HTMLParser

from . import blocklist, config, db
from .normalize import normalize_domain

# ─── A kredit-mintak ───────────────────────────────────────────────────────
# A terv 8.2 fejezetebol, plusz amit a valos adaton lattunk.
KREDIT_MINTA = re.compile(
    r"(készítette|keszitette|fejlesztette|weboldal\s*készít|weboldalkészít|"
    r"oldalt\s*készít|webdesign|web\s*design|powered\s+by|design\s+by|"
    r"developed\s+by|fejlesztés:|készült\s+a|site\s+by|made\s+by|"
    r"created\s+by|built\s+by)",
    re.I,
)

# A link a minta UTAN, ezen a tavolsagon belul kell alljon.
#
# MIERT IRANYFUGGO: egy kredit mindig ugy nez ki, hogy "Keszitette: <link>" --
# a nev a kifejezes UTAN jon, nem elotte. Ha visszafele is keresnenk, egy
# link-suru footerben barmelyik korabbi link talalna.
#
# MIERT ILYEN SZUK (60 karakter): merve az `onlinemarketing.hu` footeren, ami
# egy tipikus link-suru WordPress-footer. 120 karakteres ablakkal a "Powered
# by" mintara eloszor a tarhelyszolgaltato, majd a `blog.hu` talalt -- egyik
# sem fejleszto. A valodi kreditben a nev KOZVETLENUL a kifejezes utan all.
_LINK_TAVOLSAG = 60

# ─── Amit NEM tekintunk fejlesztonek ───────────────────────────────────────
# Platformok, CMS-ek, tarhelyek, stock-foto oldalak. Ezek nem fejlesztok --
# a 8.3 (webshop kinovés) foglalkozik veluk kulon.
NEM_FEJLESZTO = {
    # CMS / oldalepitok
    "wordpress.org", "wordpress.com", "wix.com", "squarespace.com",
    "webnode.hu", "webnode.com", "ucoz.com", "joomla.org", "drupal.org",
    "shopify.com", "shoprenter.hu", "unas.hu", "woocommerce.com",
    "prestashop.com", "magento.com", "webshopexperts.hu",
    # stock foto / ikon / sablon
    "freepik.com", "flaticon.com", "unsplash.com", "pexels.com",
    "fontawesome.com", "themeforest.net", "envato.com", "elementor.com",
    "divi.space", "elegantthemes.com",
    # tarhely / infrastruktura
    "cloudflare.com", "godaddy.com", "netlify.com", "vercel.com",
    "rackhost.hu", "tarhely.eu", "dotroll.com", "nethely.hu", "evolutionet.hu",
    "forpsi.hu", "mediacenter.hu", "integrity.hu",
    # analitika / egyeb
    "google.com", "gstatic.com", "googleapis.com", "youtube.com",
}

# Parkolt / eladó domain jelei. Ha ezek barmelyike ott van, a fejleszto DEAD.
_PARKOLT = re.compile(
    r"(domain\s+(is\s+)?for\s+sale|buy\s+this\s+domain|eladó\s+a\s+domain|"
    r"a\s+domain\s+eladó|parkolt\s+domain|this\s+domain\s+is\s+parked|"
    r"domain\s+parking|sedoparking|afternic|dan\.com|"
    r"under\s+construction|coming\s+soon|oldal\s+fejlesztés\s+alatt)",
    re.I,
)

# Ha a link KORNYEZETEBEN ez all, akkor nem a fejlesztore mutat, hanem a
# tarhelyszolgaltatora / uzemeltetore. Merve: az `onlinemarketing.hu` footere
# "Powered by WordPress ... Hosting: Smartsector" -- a minta a "Powered by"-ra
# illeszkedett, a legkozelebbi idegen link viszont a TARHELYE volt.
#
# Miert kontextus-vizsgalat es nem bovebb tiltolista: tarhelyszolgaltatobol
# tobb szaz van, es folyamatosan valtoznak. A "Hosting:" szo viszont mindig
# ott all melettuk.
_HOSTING_KONTEXT = re.compile(
    r"(hosting|tárhely|tarhely|szerver|hosted\s+by|üzemelteti|uzemelteti|"
    r"domain\s+regisztr|szolgáltató)", re.I)

UA = "Mozilla/5.0 (compatible; leadgen/1.0; +https://paladi-web.hu)"

# ─── Pontszamok (terv 8.2 "Scoring") ───────────────────────────────────────
PONT = {"DEAD": 35, "DORMANT": 20, "ALIVE": 0}

# Ennyi evnel regebbi copyright + inaktivitas -> DORMANT
_DORMANT_EV = 3


@dataclass
class Kredit:
    """Amit a footerbol kiolvastunk."""
    developer_domain: str
    developer_name: str
    idezet: str                  # a footer szovege a talalat korul -- EMBERI ATNEZESHEZ


@dataclass
class DeadDevStats:
    vizsgalt: int = 0
    kredit_nelkul: int = 0
    talalat: dict[str, int] = field(default_factory=dict)
    versenytars: int = 0
    hibak: list[str] = field(default_factory=list)

    def szamol(self, allapot: str) -> None:
        self.talalat[allapot] = self.talalat.get(allapot, 0) + 1


# ─── 1. lepes: a footer-kredit kinyerese ───────────────────────────────────

def kredit_a_footerbol(html: str, sajat_domain: str) -> Kredit | None:
    """A footer kredit kinyerese. None, ha nincs EGYERTELMU talalat.

    Harom feltetel EGYUTT (lasd a modul tetején, hogy miert):
      1. kredit-minta a footerben
      2. link a minta kozeleben
      3. a link idegen, nem-platform domainre mutat
    """
    try:
        tree = HTMLParser(html)
    except Exception:  # noqa: BLE001
        return None

    footer = tree.css_first("footer")
    if footer is None:
        # Sok magyar oldalon nincs <footer> tag. Ilyenkor az utolso <div>-ek
        # kozt keresnenk -- de az tul zajos, es a terv szabalya szerint a
        # bizonytalan eset inkabb essen ki.
        return None

    for tag in footer.css("script, style, noscript"):
        tag.decompose()

    szoveg = re.sub(r"\s+", " ", footer.text(separator=" "))
    talalat = KREDIT_MINTA.search(szoveg)
    if talalat is None:
        return None

    # A minta kornyeke -- ezt orizzuk meg emberi atnezeshez.
    kezd = max(0, talalat.start() - 40)
    idezet = szoveg[kezd:talalat.end() + 90].strip()

    # A footer linkjei, a szovegbeli helyzetukkel egyutt. A selectolax nem ad
    # karakter-pozíciot, ezert a link SZOVEGE alapjan keressuk meg, hol all.
    for a in footer.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        link_szoveg = re.sub(r"\s+", " ", a.text() or "").strip()
        if not href or not link_szoveg:
            continue

        # Hol all ez a link a footer szovegeben? A minta UTAN kell allnia.
        hely = szoveg.find(link_szoveg)
        if hely < 0 or hely < talalat.start():
            continue
        if hely - talalat.end() > _LINK_TAVOLSAG:
            continue

        # Tarhely-kontextus? Akkor nem fejleszto.
        # A kulcsszo lehet a link ELOTT ("Hosting: <link>") VAGY MAGABAN a
        # link szovegeben ("<a>Hosting: Smartsector</a>") -- merve: az
        # onlinemarketing.hu az utobbit hasznalja. Ezert mindketto szamit.
        kornyezet = szoveg[max(0, hely - 45):hely] + " " + link_szoveg
        if _HOSTING_KONTEXT.search(kornyezet):
            continue

        dev_domain = normalize_domain(href)
        if not dev_domain:
            continue
        # A SAJAT domainre mutato link a ceg sajat szolgaltatas-menuje --
        # ez a leggyakoribb hamis pozitiv (merve: 4 a 7-bol).
        if dev_domain == sajat_domain:
            continue
        if dev_domain in NEM_FEJLESZTO or blocklist.is_platform(href):
            continue

        return Kredit(developer_domain=dev_domain,
                      developer_name=link_szoveg[:80],
                      idezet=idezet)
    return None


# ─── 2. lepes: el-e meg a fejleszto ────────────────────────────────────────

def eletjel(domain: str) -> tuple[str, str]:
    """DEAD | DORMANT | ALIVE, plusz egy rovid indoklas.

    A "nem tudom" itt DEAD-nek szamit? NEM. Ha nem tudjuk eldonteni (timeout,
    halozati hiba), az `ALIVE` -- vagyis a ceg NEM lesz lead. Ez szandekosan
    a szigorubb irany: a terv szabalya szerint inkabb essen ki egy lead, mint
    hogy egy elo fejlesztot halottnak nevezzunk egy emailben.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=12.0,
                          headers={"User-Agent": UA}) as c:
            r = c.get(f"https://{domain}")
    except httpx.ConnectError:
        # A DNS nem oldodik fel, vagy nincs szerver -> a fejleszto eltunt.
        return "DEAD", "a domain nem erheto el (DNS/kapcsolat)"
    except Exception as exc:  # noqa: BLE001
        return "ALIVE", f"nem sikerult eldonteni: {type(exc).__name__}"

    if r.status_code in (404, 410):
        return "DEAD", f"HTTP {r.status_code}"
    if r.status_code >= 500:
        return "ALIVE", f"HTTP {r.status_code} (szerverhiba, nem halal)"

    html = r.text or ""
    if _PARKOLT.search(html[:20000]):
        return "DEAD", "parkolt vagy elado domain"

    # Elo oldal. Elavult-e?
    tree = HTMLParser(html)
    for tag in tree.css("script, style, noscript"):
        tag.decompose()
    szoveg = re.sub(r"\s+", " ", (tree.body or tree).text(separator=" "))

    if len(szoveg) < 200:
        return "DEAD", "gyakorlatilag ures oldal"

    evek = [int(e) for e in re.findall(r"(?:©|&copy;|copyright)\s*(20\d{2})", html, re.I)]
    ev = max(evek) if evek else None
    ha = dt.date.today().year
    if ev and (ha - ev) >= _DORMANT_EV:
        return "DORMANT", f"a copyright {ev}-es ({ha - ev} eve nem frissult)"

    return "ALIVE", "elo, aktiv oldal"


# ─── 3. lepes: a teljes futas ──────────────────────────────────────────────

def _cache_html(domain: str) -> str | None:
    f = config.CACHE_DIR / domain / "index.html"
    if not f.exists():
        return None
    try:
        return f.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def run(limit: int = 200, mind: bool = False, dry: bool = False,
        verbose: bool = True) -> DeadDevStats:
    """Vegigmegy a cegeken, es kiolvassa a fejleszto-kreditet.

    `mind=False` eseten csak azokat nezi, amiknel meg nem futott le.
    A fejleszto-domainek eletjelet CACHE-eljuk a futason belul: sok KKV-t
    ugyanaz a webstudio keszitett, tehat egy domaint egyszer kerdezunk le.
    """
    stats = DeadDevStats()
    felt = "" if mind else "and (c.dev_checked_at is null)"
    rows = db.query(f"""
        select c.id, c.company_name, c.normalized_domain, c.signal_score
          from companies c
         where c.normalized_domain is not null
           and c.status not in ('suppressed', 'rejected')
           {felt}
         order by c.first_seen_at
         limit %s
    """, (limit,))

    if not rows:
        if verbose:
            print("Nincs feldolgozando ceg. (Mindet megneztuk mar? -> --all)")
        return stats

    if verbose:
        print(f"{len(rows)} ceg vizsgalata"
              + ("   [SZARAZ FUTAS]" if dry else ""))

    eletjel_cache: dict[str, tuple[str, str]] = {}

    for row in rows:
        stats.vizsgalt += 1
        domain = row["normalized_domain"]
        html = _cache_html(domain)

        if html is None:
            stats.kredit_nelkul += 1
            if not dry:
                db.execute("update companies set dev_checked_at = now() where id = %s",
                           (row["id"],))
            continue

        kredit = kredit_a_footerbol(html, domain)
        if kredit is None:
            stats.kredit_nelkul += 1
            if not dry:
                db.execute("update companies set dev_checked_at = now() where id = %s",
                           (row["id"],))
            continue

        if kredit.developer_domain not in eletjel_cache:
            eletjel_cache[kredit.developer_domain] = eletjel(kredit.developer_domain)
        allapot, indok = eletjel_cache[kredit.developer_domain]
        stats.szamol(allapot)

        if verbose:
            jel = {"DEAD": "🔥", "DORMANT": "⭐", "ALIVE": "❌"}.get(allapot, " ")
            print(f"  {jel} {allapot:<8} {domain:<26} <- {kredit.developer_domain}")
            print(f"       \"{kredit.idezet[:80]}\"")
            print(f"       {indok}")

        if dry:
            continue

        _atvezet(row, kredit, allapot, indok, stats)

    if verbose:
        _riport(stats, dry)
    return stats


def _atvezet(row, kredit: Kredit, allapot: str, indok: str,
             stats: DeadDevStats) -> None:
    """Az eredmeny bevezetese a DB-be."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            update companies
               set dev_domain = %s, dev_name = %s, dev_state = %s,
                   dev_evidence = %s, dev_checked_at = now()
             where id = %s
        """, (kredit.developer_domain, kredit.developer_name, allapot,
              kredit.idezet[:400], row["id"]))

        # A talalat sourcekent is rogzul: a lecsengesi gorbe a
        # `sources.detected_at`-bol szamol, es a 0.4 jogi minimum szerint
        # minden allitasnak forrasa kell legyen.
        cur.execute("""
            insert into sources (company_id, source_type, source_url, raw_signal)
                 values (%s, 'dead_dev', %s, %s)
            on conflict (source_type, source_url) do update
                    set raw_signal = excluded.raw_signal, detected_at = now()
        """, (row["id"], f"https://{row['normalized_domain']}#footer",
              db.Json({"developer_domain": kredit.developer_domain,
                       "developer_name": kredit.developer_name,
                       "state": allapot, "reason": indok,
                       "quote": kredit.idezet})))

        if allapot == "ALIVE":
            # INGYEN VERSENYTARS-TERKEP. Egy elo webstudio nem lead.
            # A CEG marad lead -- a FEJLESZTO kerul tiltolistara.
            cur.execute("""
                insert into suppression (normalized_domain, reason, note)
                     values (%s, 'competitor', %s)
                on conflict (normalized_domain)
                     where normalized_domain is not null and email is null
                     do nothing
            """, (kredit.developer_domain,
                  f"8.2: elo fejleszto ({row['normalized_domain']} footerebol)"))
            if cur.rowcount:
                stats.versenytars += 1
            return

        # DEAD / DORMANT -> a CEG jobb lead lesz.
        cur.execute("""
            update companies
               set signal_score = coalesce(signal_score, 0) + %s,
                   signal_summary = coalesce(signal_summary || ' | ', '')
                                    || %s
             where id = %s
        """, (PONT[allapot],
              f"halott fejleszto: {kredit.developer_domain} ({allapot})",
              row["id"]))


def _riport(stats: DeadDevStats, dry: bool) -> None:
    print(f"\nvizsgalt: {stats.vizsgalt}   kredit nelkul: {stats.kredit_nelkul}")
    for allapot in ("DEAD", "DORMANT", "ALIVE"):
        if stats.talalat.get(allapot):
            pont = PONT[allapot]
            extra = f"  (+{pont} pont)" if pont else "  (versenytars)"
            print(f"  {allapot:<8} {stats.talalat[allapot]:>3}{extra}")
    if stats.versenytars:
        print(f"\n  {stats.versenytars} uj versenytars a tiltolistan (elo fejlesztok).")
    if stats.talalat.get("DEAD"):
        print(f"\n  >>> {stats.talalat['DEAD']} TOP LEAD: van weboldaluk, de nincs, aki karbantartsa.")
        print("      NEZD AT KEZZEL: ./leadgen.sh report --signal dead_dev")
    if dry:
        print("\n[SZARAZ FUTAS] Semmi nem lett elmentve.")
