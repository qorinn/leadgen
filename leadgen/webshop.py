#!/usr/bin/env python3
"""8.3 "webshop kinoves" -- dobozos platform + magas arbevetel.

    7.5 tech ujjlenyomat -> melyik platformon fut a webshop
    7.1 e-beszamolo      -> mekkora az arbevetel
            ↓
    a ketto metszete = "kinotted a platformot" lead

A terv szerint ez "majdnem ingyen van meg": nincs uj scrapeles, nincs uj
source, nincs AI-hivas. Csak egy szures -- DE nem azon a mezon, amin a terv
gondolta.

════════════════════════════════════════════════════════════════════════════
MIERT NEM HASZNALJUK A MEGLEVO `tech.platform` MEZOT

Az `enrich._tech_fingerprint` a teljes HTML-ben keres kulcsszot
("shoprenter", "woocommerce", ...). Merve a 49 letoltott oldalon
(2026-08-26): 12 talalat, ebbol VALODI SAJAT WEBSHOP 0 db. A tizenketto:

  ndmarketing.hu       partner-logo:  <a href="https://www.shoprenter.hu/">
  thepitch.hu          partner-logo:  img .../partners/shoprenter.png
  futuremanagement.hu  sajat profil:  szakertok.shoprenter.hu/szakerto/...
  growcorp.hu          szolgaltatas:  "webaruhaz fejlesztes woocommerce es
                                       shopify platformon"
  citymarketing.hu     tema-CSS:      .woocommerce a.button { ... }
  ndmarketing.hu       KIKOMMENTELT:  <!-- <link id='trydo-woocommerce-css' -->
  ... es tovabbi 6 marketinges ceg ugyanigy

Ugyanaz a hiba, mint a 8.2-ben: a kulcsszo onmagaban ~85%-ban teved, mert a
ceg SAJAT SZOLGALTATAS-MENUJEBOL vagy egy partner-logobol jon.

A megkulonbozteto itt a MARKER HELYE:

  1. SaaS platform (Shoprenter, Unas, Shopify, Wix)
     -> a platform a betoltott ESZKOZ URL-JENEK A HOSTJABAN van
        (script src / link href / img src), nem a path-jaban es nem <a href>-ben.
        Egy partner-logo a SAJAT domainrol jon -> kiesik.
        Egy <a href="https://shoprenter.hu"> nem eszkoz -> kiesik.

  2. Sajat uzemeltetesu platform (WooCommerce, PrestaShop, Magento)
     -> nincs idegen host, ezert a KONKRET PLUGIN-UTVONAL a marker
        (`wp-content/plugins/woocommerce/`), nem a puszta szo. A tema-CSS-ben
        levo `.woocommerce` szelektor igy kiesik.

  3. Es MINDKET esetben kell BOLT-GEPEZET is: sajat domainre mutato kosar /
     penztar / termek link. Ez zarja ki azt a WordPress-oldalt, amin a plugin
     ott van, de bolt nincs.

A HTML-kommentek problemaja ingyen megoldodik: a HTML-parser nem ad vissza
kikommentelt elemeket, tehat a ndmarketing.hu esete fel sem merul -- de csak
azert, mert PARSZOLUNK, es nem nyers szovegben keresunk. Ezt ne ird vissza
regexre.

════════════════════════════════════════════════════════════════════════════
AMIT A LEVELBE SOHA NE ENGEDJ BE: AZ ARBEVETELT

A kampany hangneme a terv szerint kenyes: "Ne mondd, hogy rossz a
platformjuk." Ehhez hozzajon egy sajat szabaly: a levelben SOHA nem szerepel
a ceg arbevetele. A szam a mi rangsorolasunk bemenete; a cimzettnek azt
uzenne, hogy a penzugyi adatait bogaraszszuk. A personalization mondat ezert
CSAK a platformot emliti, es "ilyen forgalomnal" alakban altalanosit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from . import config, db, labels
from .normalize import normalize_domain

# ─── A platform-markerek ───────────────────────────────────────────────────
# HOST-markerek: a platform sajat kiszolgaloja tolti be az oldal eszkozeit.
# Ez a legerosebb bizonyitek, amit egy oldal adhat magarol.
HOST_MARKEREK = {
    "Shoprenter": ("shoprenter.hu",),
    "Unas": ("unas.hu", "unas.eu"),
    "Shopify": ("cdn.shopify.com", "shopifycdn.com"),
    "Wix": ("static.parastorage.com", "wixstatic.com"),
    "Squarespace": ("squarespace-cdn.com",),
}

# UTVONAL-markerek: sajat uzemeltetesu rendszerek. A plugin/modul KONKRET
# utvonala kell, nem a puszta nev -- kulonben minden tema-CSS talalna.
UTVONAL_MARKEREK = {
    "WooCommerce": ("wp-content/plugins/woocommerce/",),
    "PrestaShop": ("/modules/ps_", "/themes/classic/assets/"),
    "Magento": ("/static/frontend/magento/", "/pub/static/frontend/"),
}

# A `meta[name=generator]` ertekeben szereplo nev. Ez a platform SAJAT
# bejelentese magarol -- olyan eros, mint a host-marker.
GENERATOR_MARKEREK = {
    "Shoprenter": "shoprenter",
    "Unas": "unas",
    "Shopify": "shopify",
    "Wix": "wix.com",
    "WooCommerce": "woocommerce",
    "PrestaShop": "prestashop",
    "Magento": "magento",
    "Squarespace": "squarespace",
}

# A "dobozos" halmaz: a terv 8.3 szerint ezek azok, amiket ki lehet noni.
# A Magento es a PrestaShop SZANDEKOSAN NINCS BENNE: azok nyilt, bovitheto
# rendszerek -- ott a "kinotted" allitas egyszeruen nem igaz.
DOBOZOS = {"Shoprenter", "Unas", "Shopify", "Wix", "Squarespace", "WooCommerce"}

# Bolt-gepezet: kosar / penztar / termeklap link. A lekerdezes-parameteres
# alakok is kellenek: a Shoprenter demo bolt kosar-linkje
# `index.php?route=checkout/cart&...`, tehat a "/cart" mintat nem talalna el.
KOSAR_MINTA = re.compile(
    r"(/kosar|/cart\b|cart\.php|/penztar|/checkout|/termek|/product|/webaruhaz"
    r"|/webshop|add-to-cart|/collections/|/shop/"
    r"|route=(checkout|product)|controller=(cart|product))", re.I)

# Sok webshop MAS HOSTON tartja a boltot, mint a fooldalt: `shop.rossmann.hu`
# a `rossmann.hu` mellett, `demo.myshoprenter.hu` a `demo.shoprenter.hu`
# mellett. Ha a kosar-linket a sajat hosthoz kotnenk, ezek mind kiesnenek --
# ezert a regisztralhato domain szintjen hasonlitunk, es kulon elfogadjuk a
# platformok sajat bolt-hostjait is.
BOLT_HOSTOK = ("myshoprenter.hu", "myshopify.com", "shoprenter.hu",
               "unas.hu", "unas.eu", "wixsite.com", "squarespace.com")

# Eszkoz-hordozo elemek: CSAK ezek attributumaiban keresunk host-markert.
# Az <a href> SZANDEKOSAN nincs itt: az partner-link is lehet.
ESZKOZ_SELECTOR = "script[src], link[href], img[src], iframe[src], source[src]"


@dataclass
class WebshopJel:
    platform: str
    marker: str                 # a szo szerinti bizonyitek (ez megy a DB-be)
    marker_tipus: str           # host | utvonal | generator
    kosar_jel: str = ""

    @property
    def dobozos(self) -> bool:
        return self.platform in DOBOZOS

    def evidence(self) -> str:
        reszek = [f"{self.marker_tipus}: {self.marker}"]
        if self.kosar_jel:
            reszek.append(f"bolt: {self.kosar_jel}")
        return " | ".join(reszek)[:300]


def _hostok_es_utak(tree: HTMLParser) -> tuple[list[str], list[str]]:
    """A betoltott eszkozok hostjai es teljes URL-jei."""
    hostok: list[str] = []
    urlek: list[str] = []
    for node in tree.css(ESZKOZ_SELECTOR):
        for attr in ("src", "href"):
            ertek = (node.attributes.get(attr) or "").strip()
            if not ertek:
                continue
            urlek.append(ertek)
            host = (urlsplit(ertek).hostname or "").lower()
            if host:
                hostok.append(host)
    return hostok, urlek


def _generator(tree: HTMLParser) -> str:
    node = tree.css_first('meta[name="generator"]')
    return ((node.attributes.get("content") or "") if node else "").lower()


def _sajat_link(href: str, sajat_domain: str) -> bool:
    """Sajat boltra mutat-e a link.

    Miert kell egyaltalan szurni: egy blogcikk vagy egy referencia-lista
    linkelhet IDEGEN webshopra -- pontosan az a hiba, amit a 8.2-ben a
    footer-kredit linkjeinel is lattunk.
    """
    host = (urlsplit(href).hostname or "").lower()
    if not host:
        return True                     # relativ link: definicio szerint sajat
    if any(host == b or host.endswith("." + b) for b in BOLT_HOSTOK):
        return True                     # a platform sajat bolt-hostja
    sajat = normalize_domain(sajat_domain) or (sajat_domain or "").lower()
    return (normalize_domain(host) or host) == sajat


def _kosar_jel(tree: HTMLParser, sajat_domain: str) -> str:
    """Bolt-gepezet a sajat bolton. Ures string, ha nincs."""
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if not _sajat_link(href, sajat_domain):
            continue
        if KOSAR_MINTA.search(href):
            return href[:120]
    return ""


def platform_felismeres(html: str, sajat_domain: str) -> WebshopJel | None:
    """Egy letoltott oldalbol: melyik platformon fut a SAJAT webshop.

    None, ha nincs eleg eros bizonyitek. A bizonytalan eset SZANDEKOSAN
    kiesik: a talalat szo szerint bekerul egy levelbe.
    """
    tree = HTMLParser(html)
    hostok, urlek = _hostok_es_utak(tree)
    gen = _generator(tree)
    kosar = _kosar_jel(tree, (sajat_domain or "").lower())

    jel: WebshopJel | None = None

    for platform, minta in GENERATOR_MARKEREK.items():
        if minta in gen:
            jel = WebshopJel(platform, gen[:120], "generator", kosar)
            break

    if jel is None:
        for platform, hostvegek in HOST_MARKEREK.items():
            talalat = next(
                (h for h in hostok if any(h == v or h.endswith("." + v) for v in hostvegek)),
                None)
            if talalat:
                jel = WebshopJel(platform, talalat, "host", kosar)
                break

    if jel is None:
        for platform, utak in UTVONAL_MARKEREK.items():
            talalat = next((u for u in urlek if any(p in u.lower() for p in utak)), None)
            if talalat:
                jel = WebshopJel(platform, talalat[:120], "utvonal", kosar)
                break

    if jel is None:
        return None

    # A generator a platform sajat bejelentese magarol -- az onmagaban is
    # donto. Minden mas markernel kell bolt-gepezet is.
    if jel.marker_tipus != "generator" and not kosar:
        return None
    return jel


# ─── A futas ───────────────────────────────────────────────────────────────

def _cache_htmlek(domain: str) -> list[str]:
    d = config.CACHE_DIR / domain
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.html")):
        try:
            out.append(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return out


@dataclass
class WebshopStats:
    vizsgalt: int = 0
    talalat: int = 0
    dobozos: int = 0
    metszet: int = 0            # dobozos + arbevetel a kuszob felett
    kampany_kapott: int = 0
    nincs_cache: int = 0
    platformok: dict[str, int] = field(default_factory=dict)
    metszet_lista: list[str] = field(default_factory=list)


def run(limit: int = 200, mind: bool = False, dry: bool = False,
        verbose: bool = True) -> WebshopStats:
    """A 8.3 metszet: dobozos platform + arbevetel a kuszob felett.

    KET LEPES EGY PARANCSBAN, mert a masodik ingyen van:
      1. felismeres  -- a mar letoltott HTML-bol, ujra-letoltes nelkul
      2. metszet     -- a penzugyi adattal (7.1)
    """
    stats = WebshopStats()
    szures = "" if mind else "and c.webshop_checked_at is null"
    rows = db.query(f"""
        select c.id, c.company_name, c.normalized_domain, c.campaign,
               c.revenue, c.economic_value, c.signal_score
          from companies c
         where c.normalized_domain is not null
           and c.status not in ('suppressed', 'rejected')
           {szures}
         order by c.signal_score desc nulls last, c.first_seen_at
         limit %s
    """, (limit,))

    if not rows:
        if verbose:
            print("Nincs vizsgalando ceg. (Ujravizsgalas: --all)")
        return stats

    for row in rows:
        stats.vizsgalt += 1
        domain = row["normalized_domain"]
        htmlek = _cache_htmlek(domain)
        if not htmlek:
            stats.nincs_cache += 1
            if not dry:
                _jelold_megvizsgaltnak(row["id"])
            continue

        jel = next(filter(None, (platform_felismeres(h, domain) for h in htmlek)), None)
        if jel is None:
            if not dry:
                _jelold_megvizsgaltnak(row["id"])
            continue

        stats.talalat += 1
        stats.platformok[jel.platform] = stats.platformok.get(jel.platform, 0) + 1
        if jel.dobozos:
            stats.dobozos += 1

        arbevetel = float(row["revenue"] or 0)
        metszet = jel.dobozos and arbevetel >= config.WEBSHOP_REVENUE_MIN_HUF
        if metszet:
            stats.metszet += 1
            stats.metszet_lista.append(
                f"{(row['company_name'] or '')[:38]:<40} {jel.platform:<12} "
                f"{arbevetel / 1_000_000:>8.0f} M Ft")

        if not dry:
            kapott = _atvezet(row, jel, metszet)
            if kapott:
                stats.kampany_kapott += 1

    if verbose:
        _riport(stats, dry)
    return stats


def _jelold_megvizsgaltnak(company_id) -> None:
    db.execute("update companies set webshop_checked_at = now() where id = %s",
               (company_id,))


# A platformnevek magyar toldalekolasa. AZERT KELL KEZI TABLA, mert a
# "{platform}-en" gepies alak minden nevre rossz: a "Shoprenter-en" es a
# "Wix-en" idegen szaghoz vezet, pont abban a mondatban, aminek termeszetesnek
# kell hangzania. Uj platform felvetelekor EZT IS bovitsd.
_RAGOZAS = {
    "Shoprenter": "Shoprenteren",
    "Unas": "Unason",
    "Shopify": "Shopifyon",
    "WooCommerce": "WooCommerce-en",
    "Wix": "Wixen",
    "Squarespace": "Squarespace-en",
    "PrestaShop": "PrestaShopon",
    "Magento": "Magentón",
}


def personalization(jel: WebshopJel) -> str:
    """A 8.3 nyitomondat. NINCS BENNE SZAM, es nincs benne kritika.

    A terv figyelmeztetese: "Ne mondd, hogy rossz a platformjuk. Sokan
    tudatosan es elegedetten hasznaljak." Ez a mondat ezert csak TENYT allit
    (mit lattunk), a kovetkezteteset a kerdes bizza a cimzettre.

    A szoveg EKEZETES: ez nem kommentar, hanem a levelbe kerulo mondat.
    """
    alak = _RAGOZAS.get(jel.platform, f"{jel.platform}-en")
    return f"Láttam, hogy a webshopjuk {alak} fut."


def _atvezet(row, jel: WebshopJel, metszet: bool) -> bool:
    """A felismeres es a metszet atvezetese. True, ha kampanyt is kapott.

    A KAMPANYT CSAK AKKOR ALLITJUK BE, HA MEG NINCS. Ket okbol:

      - a domain lock szerint egy ceg egy kampanyba kerul, es ha egy AI-val
        mar megvalasztott (es esetleg EMBER altal atnezett) kampanyt
        felulirnank, az csendben mas levelet kuldene, mint amit jovahagytak;
      - a megorzo leadmodell szerint a tobbi irany sem vesz el: a 8.3 szog
        `opportunity_angles` sorkent akkor is elmentodik, ha nem o nyer.
    """
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""
            update companies
               set webshop_platform = %s, webshop_evidence = %s,
                   webshop_checked_at = now()
             where id = %s
        """, (jel.platform, jel.evidence(), row["id"]))

        labels.set_label(cur, row["id"], "webshop_platform",
                         {"platform": jel.platform, "marker": jel.marker_tipus,
                          "dobozos": jel.dobozos})

        if not metszet:
            labels.clear_label(cur, row["id"], "webshop_growth")
            _bonusz_ujraszamol(cur, row["id"])
            return False

        labels.set_label(cur, row["id"], "webshop_growth",
                         {"platform": jel.platform,
                          "revenue": float(row["revenue"] or 0)})

        # A szog akkor is elmentodik, ha nem o nyeri a kampanyt.
        cur.execute("""
            insert into opportunity_angles
              (company_id, rank, angle_type, pain, claim, quote, score,
               confidence, selected, model)
            values (%s, %s, 'website', %s, %s, %s, %s, 1.0, %s, 'rule:webshop_8.3')
            on conflict (company_id, rank) do update
               set angle_type = excluded.angle_type, pain = excluded.pain,
                   claim = excluded.claim, quote = excluded.quote,
                   score = excluded.score, model = excluded.model
        """, (row["id"], _szabad_rank(cur, row["id"]),
              "dobozos webshop platform korlatai novekedeskor",
              f"a webshop {jel.platform}-en fut, es a ceg merete mar tulnott rajta",
              jel.marker[:200], 75, not row["campaign"]))

        kapott = False
        if not row["campaign"]:
            # A PERSONALIZATION MONDATOT IS ATIRJUK, nem csak a kampanyt.
            # Elesben latszott (2026-08-26): a ceg megkapta a `webshop_growth`
            # kampanyt, de a `personalization` mezoben egy KORABBI, ugynoksegi
            # szogbol szuletett mondat maradt -- vagyis a level webshopról
            # szolt volna, a nyitomondata viszont masrol. A ket mezo egyutt
            # alkot egy levelet; kulon frissiteni oket nema hiba.
            # A regi mondat nem vesz el: az `opportunity_angles` sorai es az
            # `evidence` jsonb megorzik, mibol keszult.
            cur.execute("""
                update companies
                   set campaign = 'webshop_growth',
                       best_offer = coalesce(best_offer, 'website'),
                       personalization = %s,
                       signal_summary = %s
                 where id = %s
            """, (personalization(jel),
                  f"8.3 webshop kinoves | {jel.platform} | {jel.evidence()}"[:300],
                  row["id"]))
            labels.clear_label(cur, row["id"], "campaign_missing")
            kapott = True

        _bonusz_ujraszamol(cur, row["id"])
        return kapott


def _szabad_rank(cur, company_id) -> int:
    """A kovetkezo szabad rank. A 10. szakasz szogei 1-tol foglaltak."""
    cur.execute("select coalesce(max(rank), 0) + 1 as r from opportunity_angles "
                "where company_id = %s and model <> 'rule:webshop_8.3'", (company_id,))
    return int(cur.fetchone()["r"])


def _bonusz_ujraszamol(cur, company_id) -> None:
    """A penzugyi bonusz ujraszamolasa, ha a webshop-allapot valtozott.

    A `financials.bonus` +25-ot ad a "dobozos webshop + magas arbevetel"
    parosra -- de a webshop-felismeres a penzugyi import UTAN is lefuthat.
    Enelkul az a +25 sosem kerulne be. Ugyanaz az idempotens minta:
    regi bonusz le, uj bonusz fel.
    """
    from . import financials

    cur.execute("""
        select coalesce(financial_bonus, 0) as regi, economic_value, revenue,
               webshop_platform
          from companies where id = %s
    """, (company_id,))
    r = cur.fetchone()
    if not r:
        return
    regi = float(r["regi"] or 0)
    dobozos = r["webshop_platform"] if r["webshop_platform"] in DOBOZOS else None
    uj = financials.bonus(r["economic_value"], r["revenue"], dobozos)
    if uj == regi:
        return
    cur.execute("""
        update companies
           set financial_bonus = %s,
               signal_score = greatest(coalesce(signal_score, 0) - %s + %s, 0)
         where id = %s
    """, (uj, regi, uj, company_id))


def _riport(stats: WebshopStats, dry: bool) -> None:
    print(f"\nvizsgalt: {stats.vizsgalt}   platform-talalat: {stats.talalat}   "
          f"ebbol dobozos: {stats.dobozos}   nincs letoltott oldal: {stats.nincs_cache}")
    if stats.platformok:
        print("  " + "   ".join(f"{k}: {n}" for k, n in sorted(stats.platformok.items())))

    kuszob = config.WEBSHOP_REVENUE_MIN_HUF / 1_000_000
    print(f"\n8.3 METSZET (dobozos platform + arbevetel >= {kuszob:.0f} M Ft): "
          f"{stats.metszet} ceg")
    for sor in stats.metszet_lista[:30]:
        print(f"  {sor}")
    if stats.talalat and not stats.metszet:
        print("  (van dobozos platform, de nincs hozza penzugyi adat vagy tul kicsi)")
        print("  Penzugyi adat: ./leadgen.sh enrich financials")
    if stats.kampany_kapott:
        print(f"\n  {stats.kampany_kapott} ceg kapott `webshop_growth` kampanyt.")
        print("  A SABLON MEG VAZLAT -- amig nincs benne a contract.APPROVED_CAMPAIGNS")
        print("  listaban, ezek a leadek NEM exportalodnak. Lasd: TEENDOK.md")
    if dry:
        print("\n  [SZARAZ FUTAS -- semmit nem irtam a DB-be]")
