#!/usr/bin/env python3
"""Apify Actor futtatas. Vekony reteg a HTTP API folott.

MIERT APIFY ES NEM SAJAT SCRAPER: a terv "Apifyt hogyan hasznalnam?" fejezete
szerint ott hasznalunk kesz Actort, ahol a platform bonyolult. Merve (2026-08-21):
a cylex.hu Cloudflare-challenge-et ad meg a robots.txt-re is, a LinkedIn
robots.txt-je pedig kifejezetten tiltja az automatizalt hozzaferest. A Google
Maps sajat kezbol szinten blokkolt. Az Apify ezt a reteget uzemelteti -- ez az
uzleti modelljuk, es olcsobb, mint sajat proxy-infrastrukturat epiteni.

KOLTSEG: minden futas utan naplozzuk a felhasznalast, hogy ne meglepetes legyen.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from .. import config

API = "https://api.apify.com/v2"


class ApifyError(RuntimeError):
    pass


def _token() -> str:
    if not config.APIFY_TOKEN:
        raise ApifyError(
            "nincs beallitva az APIFY_TOKEN.\n"
            f"  Varom itt: {config.BASE / '.env'}\n"
            "  Apify -> Settings -> API & Integrations -> Personal API token"
        )
    return config.APIFY_TOKEN


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


def usage() -> dict[str, Any]:
    """Havi felhasznalas es keret. Minden futas elott/utan erdemes megnezni."""
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{API}/users/me/limits", headers=_headers())
        r.raise_for_status()
        d = r.json()["data"]
    return {
        "used_usd": float(d.get("current", {}).get("monthlyUsageUsd", 0) or 0),
        "max_usd": d.get("limits", {}).get("maxMonthlyUsageUsd"),
    }


# Egy-egy HTTP hivas felso ideje. SZANDEKOSAN ROVID: a futas hosszat a
# lekerdezgetes (polling) hidalja at, nem egyetlen orakig nyitva tartott
# kapcsolat. Igy egy megakadt TCP-kapcsolat legfeljebb ennyi idot visz el,
# nem az egesz napi keretet.
_HTTP_TIMEOUT = 60.0

# A lekerdezes-koz: rovidrol indul (a legtobb futas gyors), aztan lassul, hogy
# egy hosszu futas alatt ne kerdezgessunk feleslegesen ezerszer.
_POLL_MIN, _POLL_MAX = 3.0, 15.0

# Az Apify vegallapotai. Barmi mas azt jelenti: meg dolgozik.
_KESZ = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMING-OUT"}


def dataset_items(dataset_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Egy mar lefutott Apify-futas eredmenye. KULON FUGGVENY, mert ezzel
    lehet UTOLAG elhozni egy olyan futas adatait, amirol a halozat leszakadt --
    a futasert ugyanis MAR FIZETTUNK."""
    with httpx.Client(timeout=_HTTP_TIMEOUT) as c:
        r = c.get(f"{API}/datasets/{dataset_id}/items",
                  headers=_headers(), params={"clean": "true", "limit": limit})
    if r.status_code >= 300:
        raise ApifyError(f"dataset {dataset_id} -> HTTP {r.status_code}: {r.text[:300]}")
    items = r.json()
    if not isinstance(items, list):
        raise ApifyError(f"dataset {dataset_id}: varatlan valasz-formatum: {type(items)}")
    return items


def run_actor(actor: str, payload: dict, timeout: int = 900,
              verbose: bool = True) -> list[dict[str, Any]]:
    """Actor futtatasa es a dataset visszaadasa.

    Az actor azonositoja `felhasznalo~actor-nev` alakban kell (a `/` helyett `~`).

    ────────────────────────────────────────────────────────────────────────
    MIERT NEM A SZINKRON VEGPONT (`run-sync-get-dataset-items`):

    Az egyetlen HTTP-kapcsolatot tartott nyitva, amig az actor vegigfutott. Ha
    az actor beallt az Apify varolistajara vagy lassan futott, a kapcsolat
    kifutott az idobol -- es a kimenet egy puszta `httpx.ReadTimeout` volt,
    amibol NEM DERULT KI, hogy a futas elindult-e, meddig jutott, es
    fizettunk-e erte.

    Elesben merve: a napi lanc `ingest` lepese HAT egymast koveto napon
    bukott el igy (2026-08-29 -- 09-03), vagyis hat napig EGYETLEN uj ceg sem
    jott be a Google Mapsrol. A tolcser teteje csendben el volt zarva: a lanc
    "csak" egy lepesre irt hibat, a `ready` leadek utanpotlasa viszont
    elfogyott, es ez csak hetekkel kesobb latszott volna a kuldesen.

    A helyes minta harom rovid hivas:
      1. futas INDITASA        -> azonnal visszaterul a futas azonositoja
      2. allapot LEKERDEZESE   -> ismetelve, amig vegallapotba nem er
      3. eredmeny ELHOZASA     -> a dataset tartalma

    Igy egyetlen HTTP-hivas sem tart tovabb `_HTTP_TIMEOUT`-nal, a futas
    hosszat pedig a lekerdezgetes hidalja at.

    KOLTSEGVEDELEM: ha barmi elromlik azutan, hogy a futas MAR ELINDULT,
    kiirjuk a futas es a dataset azonositojat -- azert MAR FIZETTUNK, es
    ezekkel utolag elhozhato (`dataset_items(...)`), nem kell ujra futtatni.
    """
    before = usage()["used_usd"] if verbose else None
    started = time.monotonic()
    if verbose:
        print(f"  Apify actor: {actor}")

    # ── 1. A futas INDITASA ──────────────────────────────────────────────
    with httpx.Client(timeout=_HTTP_TIMEOUT) as c:
        r = c.post(f"{API}/acts/{actor.replace('/', '~')}/runs",
                   headers=_headers(), json=payload)
    if r.status_code >= 300:
        raise ApifyError(f"{actor} inditas -> HTTP {r.status_code}: {r.text[:400]}")
    futas = (r.json() or {}).get("data") or {}
    run_id = futas.get("id")
    dataset_id = futas.get("defaultDatasetId")
    if not run_id or not dataset_id:
        raise ApifyError(f"{actor}: az inditas nem adott futas-azonositot: {str(futas)[:200]}")

    # Innentol MAR FIZETUNK a futasert -- minden hibauzenetben ott kell
    # lennie a ket azonositonak, kulonben elveszik a mar kifizetett adat.
    nyom = f"(run={run_id} dataset={dataset_id})"
    if verbose:
        print(f"  futas elindult {nyom}")

    # ── 2. Az allapot LEKERDEZESE, amig vegallapotba nem er ──────────────
    varakozas = _POLL_MIN
    statusz = futas.get("status") or "READY"
    while statusz not in _KESZ:
        if time.monotonic() - started > timeout:
            raise ApifyError(
                f"{actor}: a futas {timeout} mp utan sem fejezodott be "
                f"(utolso allapot: {statusz}) {nyom}\n"
                f"  A futas az Apify-on TOVABB MEGY. Ha lefut, az eredmeny "
                f"utolag elhozhato a dataset azonositoval.")
        time.sleep(varakozas)
        varakozas = min(_POLL_MAX, varakozas * 1.5)
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as c:
                rr = c.get(f"{API}/actor-runs/{run_id}", headers=_headers())
            if rr.status_code < 300:
                statusz = ((rr.json() or {}).get("data") or {}).get("status") or statusz
        except httpx.HTTPError:
            # Egy elvesztett lekerdezes nem hiba: a futas tovabb megy, es a
            # kovetkezo korben ujra megkerdezzuk. A teljes idokeretet a fenti
            # `timeout` vedi.
            pass

    if statusz != "SUCCEEDED":
        raise ApifyError(f"{actor}: a futas {statusz} allapotban vegzodott {nyom}")

    # ── 3. Az eredmeny ELHOZASA ──────────────────────────────────────────
    try:
        items = dataset_items(dataset_id)
    except Exception as exc:  # noqa: BLE001
        raise ApifyError(
            f"{actor}: a futas SIKERES volt, de az eredmenyt nem sikerult "
            f"elhozni: {exc} {nyom}\n"
            f"  MAR FIZETTUNK erte -- az adat a dataset azonositoval elhozhato.")

    if verbose:
        after = usage()["used_usd"]
        print(f"  -> {len(items)} talalat, {time.monotonic() - started:.0f} mp, "
              f"koltseg ~${after - (before or 0):.4f} "
              f"(havi osszesen ${after:.4f})")
    return items
