#!/usr/bin/env python3
"""Modell-arak es koltsegszamitas.

MIERT SZAMOLUNK MI, ES NEM A SZOLGALTATO DASHBOARDJARA HAGYATKOZUNK
(felhasznaloi keres, 2026-08-22):

  1. A dashboard LASSAN FRISSUL -- egy teszt utan percekig/orakig nem latszik.
  2. OSSZEVONJA A MODELLEKET. Egy bake-off pont arrol szol, hogy ket modellt
     hasonlitunk ossze; ha a szamla egyben latszik, a merés ertelmetlen.

Ezert MINDEN hivas utan sajat tokenszamot es sajat koltseget vezetunk, es a
riportok modellenkent bontva mutatjak.

⚠️ EZ BECSLES, NEM SZAMLA. Az itteni arak kezzel karbantartott tablabol
jonnek. Ha egy modell arat valtoztat, vagy uj modellt hasznalsz, a szam
elcsuszik -- ezert van minden sornal a forras es a datum, es ezert irja ki a
riport, hogy "szamitott". A vegso igazsag mindig a szolgaltato szamlaja.

AMIT AZ ARAK NEM TARTALMAZNAK: a nagyon hosszu promptok felarat (az OpenAI
272K token felett 2x input / 1.5x output arat szamol), es a cache-iras
1.25x felarat. A mi promptjaink nagysagrendekkel rovidebbek, tehat ez a
gyakorlatban nem szamit -- de ha valaha hosszu dokumentumokat kuldenenk,
ezt a modult kell bovíteni.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# (input $/1M, output $/1M, cached input $/1M vagy None)
#
# FORRAS ES DATUM soronkent -- enelkul fel ev mulva senki nem tudna, honnan
# jott a szam, es hogy elavult-e.
ARAK: dict[str, tuple[float, float, float | None]] = {
    # developers.openai.com/api/docs/models/gpt-5.6-luna  (ellenorizve 2026-08-22)
    "gpt-5.6-luna": (0.20, 1.20, 0.02),
    # A Claude-arak a claude-api referenciabol (cache: 2026-06-24).
    "claude-haiku-4-5": (1.00, 5.00, None),
    "claude-sonnet-5": (3.00, 15.00, None),
    "claude-opus-5": (5.00, 25.00, None),
    # Terv-tablazatbol, NEM ellenorzott friss forrasbol -- ha ezeket
    # hasznalod, ellenorizd az arat.
    "gemini-2.5-flash-lite": (0.10, 0.40, None),
}

# Anthropicnal a cache-olvasas ~0.1x az input ar, ha nincs kulon megadva.
_CACHE_SZORZO = 0.1


def ismeretlen(model: str) -> bool:
    return model not in ARAK


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             cached_tokens: int = 0) -> float | None:
    """Egy hivas becsult koltsege. None, ha a modell ara ismeretlen.

    A None SZANDEKOS: ha nem tudjuk az arat, NEM talalunk ki egy szamot.
    A riport ilyenkor kiirja a tokeneket es azt, hogy az ar ismeretlen --
    abbol a felhasznalo maga tud szamolni.
    """
    if ismeretlen(model):
        return None
    be, ki, cache = ARAK[model]
    cache_ar = cache if cache is not None else be * _CACHE_SZORZO
    # A cache-elt tokenek NEM szamitanak bele a teljes arba: azokat kulon,
    # olcsobban szamoljuk.
    friss_be = max(0, (input_tokens or 0) - (cached_tokens or 0))
    return (friss_be * be + (cached_tokens or 0) * cache_ar
            + (output_tokens or 0) * ki) / 1_000_000


@dataclass
class Konyveles:
    """Modellenkenti tokenszam es koltseg egy futason belul.

    A `hivasok` szamot is vezetjuk: abbol derul ki, ha egy retry vagy egy
    ujraprobalas tobbszor hivott, mint amennyit vartunk.
    """
    tetelek: dict[str, dict] = field(default_factory=dict)

    def add(self, model: str, input_tokens: int, output_tokens: int,
            cached_tokens: int = 0) -> None:
        t = self.tetelek.setdefault(model, {
            "hivasok": 0, "be": 0, "ki": 0, "cache": 0})
        t["hivasok"] += 1
        t["be"] += input_tokens or 0
        t["ki"] += output_tokens or 0
        t["cache"] += cached_tokens or 0

    def add_result(self, result) -> None:
        """Kenyelmi valtozat egy llm.LLMResult-hoz."""
        self.add(result.model, result.input_tokens,
                 result.output_tokens, result.cached_tokens)

    def koltseg(self, model: str) -> float | None:
        t = self.tetelek.get(model)
        if not t:
            return None
        return cost_usd(model, t["be"], t["ki"], t["cache"])

    @property
    def osszes_koltseg(self) -> float:
        """A ISMERT aru modellek osszege. Az ismeretlenek kimaradnak --
        ezert irja ki a riport oket kulon."""
        return sum(k for m in self.tetelek
                   if (k := self.koltseg(m)) is not None)

    @property
    def ismeretlen_arak(self) -> list[str]:
        return sorted(m for m in self.tetelek if ismeretlen(m))

    def riport(self, cim: str = "TOKENEK ES KOLTSEG") -> None:
        if not self.tetelek:
            return
        print(f"\n{cim}")
        print(f"  {'modell':<24} {'hívás':>6} {'be':>9} {'ki':>8} "
              f"{'cache':>7} {'$ (számított)':>15}")
        print("  " + "-" * 74)
        for model in sorted(self.tetelek):
            t = self.tetelek[model]
            k = self.koltseg(model)
            ar = f"${k:.6f}" if k is not None else "ISMERETLEN AR"
            print(f"  {model:<24} {t['hivasok']:>6} {t['be']:>9,} {t['ki']:>8,} "
                  f"{t['cache']:>7,} {ar:>15}")
        print("  " + "-" * 74)
        print(f"  {'OSSZESEN':<24} {'':<6} {'':<9} {'':<8} {'':<7} "
              f"${self.osszes_koltseg:.6f}".replace(",", " "))

        if self.ismeretlen_arak:
            print(f"\n  ⚠ Ismeretlen aru modell: {', '.join(self.ismeretlen_arak)}")
            print("    A tokenszam pontos, az ar nem szerepel a leadgen/pricing.py")
            print("    tablajaban -- szamold ki a szolgaltato arlistajabol.")

        print("\n  (Sajat szamitas, NEM a szolgaltato szamlaja. A dashboard")
        print("   lassan frissul es osszevonja a modelleket -- ezert szamolunk.)")
