#!/usr/bin/env python3
"""Eles API-teszt: mukodik-e a kulcs, es MENNYIBE KERUL.

    ./leadgen.sh llm-check                    # a beallitott ket modell
    ./leadgen.sh llm-check --model gpt-5.6-luna --model claude-haiku-4-5

MIERT VAN ERRE KULON PARANCS:

1. AZ INTEGRACIO ELLENORZESE. A modellcsaladok kulonbozo parametereket
   fogadnak el (`temperature`, `max_tokens` vs `max_completion_tokens`,
   JSON-mod), es a nevek valtoznak. Amig nem futott le egy VALODI hivas,
   az integracio feltetelezes marad, nem teny.

2. A KOLTSEG MERESE MODELLENKENT. A szolgaltatok dashboardja lassan frissul
   es OSSZEVONJA a modelleket -- egy bake-off ettol ertelmetlen lenne.
   Ez a parancs minden hivas tokenjeit kulon szamolja.

3. KOLTSEGFEK. Minden futas elott kiirja a BECSULT koltseget, es ha az
   atlepi a keretet, meg sem probalja. Egy elgepelt `--repeat 1000` igy nem
   tud szamlat csinalni.

A naplo (`data/llm_usage.csv`) sorai osszeadhatok: tobb futas utan is latszik,
mennyit koltottel osszesen, modellenkent.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from . import config, llm, pricing, prompts

NAPLO = config.BASE / "data" / "llm_usage.csv"
NAPLO_FEJLEC = ["ts", "parancs", "model", "hivasok", "be", "ki", "cache", "usd"]

# Rovid, de VALODI feladat -- ugyanaz a prompt, amit elesben hasznalunk.
# Igy a merés a valodi terhelest kozeliti, nem egy "mondj szia"-t.
_MINTA_HIRDETES = """\
Szervizkoordinátort keresünk budapesti telephelyünkre.

Főbb feladatok:
- Ügyfelekkel telefonos és e-mailes kapcsolattartás
- Munkalapok felvétele, kezelése és nyomon követése Excelben
- Kapcsolattartás a szerelőkkel a javítások menetéről
- Árajánlatok előkészítése, számlázási feladatok
- Beérkező alkatrészek átvétele és nyilvántartása

Elvárások: 1-3 év tapasztalat, jó szervezőkészség, felhasználói
szintű számítógépes ismeretek."""


def _becsult_koltseg(model: str, ismetles: int) -> float | None:
    """Elozetes becsles a fekhez. Tapasztalati tokenszamok a mi promptunkra."""
    return pricing.cost_usd(model, 1400 * ismetles, 400 * ismetles)


def _naplo_ir(parancs: str, konyv: pricing.Konyveles) -> None:
    NAPLO.parent.mkdir(parents=True, exist_ok=True)
    uj = not NAPLO.exists()
    with NAPLO.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NAPLO_FEJLEC)
        if uj:
            w.writeheader()
        ts = dt.datetime.now().isoformat(timespec="seconds")
        for model, t in sorted(konyv.tetelek.items()):
            k = konyv.koltseg(model)
            w.writerow({"ts": ts, "parancs": parancs, "model": model,
                        "hivasok": t["hivasok"], "be": t["be"], "ki": t["ki"],
                        "cache": t["cache"],
                        "usd": f"{k:.6f}" if k is not None else ""})


def osszesites_adat() -> dict:
    """A naplo osszegzese modellenkent, dict-kent (`/api/costs`, F1).

    A `*_adat()` / kiiro fuggveny szetvalasztasa ugyanaz a mintazat, mint a
    `report.py`-ban: az API-nak adat kell, nem szoveg, es ket kulon
    implementacio ket kulon igazsagot adna ugyanarra a szamra.
    """
    if not NAPLO.exists():
        return {"has_data": False, "by_model": {}, "total_usd": 0.0,
                "first_ts": None, "last_ts": None}
    with NAPLO.open(encoding="utf-8-sig", newline="") as f:
        sorok = list(csv.DictReader(f))
    if not sorok:
        return {"has_data": False, "by_model": {}, "total_usd": 0.0,
                "first_ts": None, "last_ts": None}

    ossz: dict[str, dict] = {}
    for s in sorok:
        t = ossz.setdefault(s["model"], {"hivasok": 0, "be": 0, "ki": 0, "usd": 0.0})
        t["hivasok"] += int(s["hivasok"] or 0)
        t["be"] += int(s["be"] or 0)
        t["ki"] += int(s["ki"] or 0)
        t["usd"] += float(s["usd"] or 0)

    return {
        "has_data": True,
        "by_model": ossz,
        "total_usd": sum(t["usd"] for t in ossz.values()),
        "first_ts": sorok[0]["ts"],
        "last_ts": sorok[-1]["ts"],
    }


def napi_koltseg_adat() -> dict:
    """A naplo osszegzese naponkent, dict-kent (webui F9 -- 'Koltsegek'
    chart, napi vonal). A modellenkenti bontas az `osszesites_adat()`-e --
    ez ugyanazt a naplot nezi, csak a masik tengely menten osszesit."""
    if not NAPLO.exists():
        return {"has_data": False, "days": []}
    with NAPLO.open(encoding="utf-8-sig", newline="") as f:
        sorok = list(csv.DictReader(f))
    if not sorok:
        return {"has_data": False, "days": []}

    by_day: dict[str, float] = {}
    for s in sorok:
        nap = (s["ts"] or "")[:10]
        if not nap:
            continue
        by_day[nap] = by_day.get(nap, 0.0) + float(s["usd"] or 0)

    return {
        "has_data": True,
        "days": [{"date": nap, "usd": osszeg} for nap, osszeg in sorted(by_day.items())],
    }


def osszesites() -> None:
    """A naplo osszegzese modellenkent -- ezt add ossze a dashboarddal."""
    adat = osszesites_adat()
    if not adat["has_data"]:
        if not NAPLO.exists():
            print("Meg nem futott egyetlen mert LLM-hivas sem.")
        else:
            print("A naplo ures.")
        return

    print(f"EDDIGI LLM-KOLTSEG (a {NAPLO.name} alapjan)")
    print(f"  {'modell':<24} {'hívás':>6} {'be':>10} {'ki':>9} {'$':>12}")
    print("  " + "-" * 66)
    for model in sorted(adat["by_model"]):
        t = adat["by_model"][model]
        print(f"  {model:<24} {t['hivasok']:>6} {t['be']:>10,} {t['ki']:>9,} "
              f"${t['usd']:>11.6f}")
    print("  " + "-" * 66)
    print(f"  {'OSSZESEN':<24} {'':>6} {'':>10} {'':>9} "
          f"${adat['total_usd']:>11.6f}")
    print(f"\n  elso merés: {adat['first_ts']}   utolso: {adat['last_ts']}")


def run(models: list[str], ismetles: int = 1, keret_usd: float = 0.50,
        dry: bool = False) -> int:
    """Egy valodi hivas modellenkent, tokenszamlalassal."""
    konyv = pricing.Konyveles()

    # ─── KOLTSEGFEK ──────────────────────────────────────────────────
    print("BECSULT KOLTSEG (a futas ELOTT)")
    becsult_ossz = 0.0
    ismeretlen = []
    for m in models:
        b = _becsult_koltseg(m, ismetles)
        if b is None:
            ismeretlen.append(m)
            print(f"  {m:<24} ISMERETLEN AR -- nem tudom elore becsulni")
        else:
            becsult_ossz += b
            print(f"  {m:<24} ~${b:.6f}")
    print(f"  {'osszesen':<24} ~${becsult_ossz:.6f}   (keret: ${keret_usd:.2f})")

    if becsult_ossz > keret_usd:
        print(f"\nHIBA: a becsult koltseg atlepi a keretet. NEM INDULOK EL.")
        print(f"  Ha tenyleg ennyit szansz ra: --budget {becsult_ossz * 1.5:.2f}")
        return 1
    if ismeretlen and not dry:
        print(f"\n  ⚠ {len(ismeretlen)} modell ara ismeretlen -- a fek NEM ved rajuk.")

    if dry:
        print("\n[SZARAZ FUTAS] Nem hivtam meg egyetlen API-t sem.")
        return 0

    # ─── A VALODI HIVASOK ────────────────────────────────────────────
    print()
    hibas = 0
    for model in models:
        print(f"── {model}")
        try:
            hiany = llm.kulcs_hianyzik(model)
        except llm.LLMConfigError as exc:
            print(f"   HIBA: {exc}")
            hibas += 1
            continue
        if hiany:
            print(f"   KIHAGYVA: {hiany}")
            continue

        for i in range(ismetles):
            user = prompts.lead_classifier_user(
                forras="Profession.hu allashirdetes", ceg="Teszt Szerviz Kft.",
                pozicio="Szervizkoordinátor", szoveg=_MINTA_HIRDETES)
            try:
                data, result = llm.json_call(
                    model, prompts.LEAD_CLASSIFIER_SYSTEM, user,
                    max_tokens=1500, retries=0)
            except Exception as exc:  # noqa: BLE001
                print(f"   ✗ HIBA: {type(exc).__name__}: {str(exc)[:200]}")
                hibas += 1
                break

            konyv.add_result(result)
            k = pricing.cost_usd(model, result.input_tokens,
                                 result.output_tokens, result.cached_tokens)
            angles = [a for a in (data.get("opportunity_angles") or [])
                      if isinstance(a, dict)]
            print(f"   ✓ {len(angles)} lehetseges irany  "
                  f"{result.latency_ms} ms  "
                  f"be={result.input_tokens} ki={result.output_tokens}"
                  + (f"  ${k:.6f}" if k is not None else "  ar ismeretlen"))
            if i == 0:
                # Az ELSO valasz tartalmat is megmutatjuk: enelkul csak azt
                # tudnank, hogy "valaszolt", nem azt, hogy ERTELMESET valaszolt.
                for angle in angles[:1]:
                    print(f"     {angle.get('type')}: "
                          f"{str(angle.get('pain'))[:60]}")
                    print(f"     idezet: \"{str(angle.get('quote'))[:70]}\"")

    konyv.riport()
    if konyv.tetelek:
        _naplo_ir("llm-check", konyv)
        print(f"\n  Naplozva: {NAPLO}")
        print("  Osszesites tobb futasra: ./leadgen.sh llm-check --summary")
    return 1 if hibas else 0
