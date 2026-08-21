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


def run_actor(actor: str, payload: dict, timeout: int = 900,
              verbose: bool = True) -> list[dict[str, Any]]:
    """Actor futtatasa es a dataset visszaadasa.

    Az actor azonositoja `felhasznalo~actor-nev` alakban kell (a `/` helyett `~`).
    Szinkron vegpontot hasznalunk: a scrapelesi futasaink rovidek (nehany szaz
    talalat), es igy nem kell allapotot tarolni ket hivas kozott.
    """
    before = usage()["used_usd"] if verbose else None
    url = f"{API}/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"

    if verbose:
        print(f"  Apify actor: {actor}")
    started = time.monotonic()
    with httpx.Client(timeout=timeout) as c:
        r = c.post(url, params={"token": _token()}, json=payload)

    if r.status_code >= 300:
        raise ApifyError(f"{actor} -> HTTP {r.status_code}: {r.text[:400]}")

    items = r.json()
    if not isinstance(items, list):
        raise ApifyError(f"{actor}: varatlan valasz-formatum: {type(items)}")

    if verbose:
        after = usage()["used_usd"]
        print(f"  -> {len(items)} talalat, {time.monotonic() - started:.0f} mp, "
              f"koltseg ~${after - (before or 0):.4f} "
              f"(havi osszesen ${after:.4f})")
    return items
