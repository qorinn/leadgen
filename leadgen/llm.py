#!/usr/bin/env python3
"""LLM-kliens: ket tier, egy felulet.

    bulk(...)     -- olcso, nagy volumen (Gemini). Leadek osztalyozasa.
    quality(...)  -- dragabb, jobb magyar (Claude). Personalization, valaszok.

MIERT VAN KET TIER (a terv "Melyik feladat melyik modellt kapja" fejezete):
napi tobb szaz lead osztalyozasa es napi 5-10 mondat megirasa nem ugyanaz a
feladat. Az elsonel az ar szamit, a masodiknal az, hogy egy magyar cegvezeto
termeszetesnek olvassa-e.

A PROVIDER A MODELLNEVBOL DERUL KI, nem kulon kapcsolobol. Igy a bake-off
ugyanazon a fuggvenyen futtathat barmelyik jelolt modellt (`--model` kapcsolo),
es nem kell tudnia, melyik kihez tartozik.

────────────────────────────────────────────────────────────────────────────
HAROM DOLOG, AMI ITT NEM KOZMETIKA:

1. TEMPERATURE 0 -- DE NEM MINDEN MODELL FOGADJA EL.
   A classifiernel determinisztikus kimenet kell, kulonben nem tudod, hogy a
   ket futas kozti kulonbseg a promptbol vagy a veletlenbol jon. A Claude
   Haiku 4.5 meg elfogadja a `temperature` parametert -- az ujabb Claude
   modellek (Opus 5, Sonnet 5, Fable 5) viszont MAR NEM, es 400-zal
   elutasitjak a kerest. Mivel a modellnev konfigbol jon, egy kesobbi
   modellvaltas eleg lenne ahhoz, hogy minden hivas elszalljon. Ezert a
   `_SAMPLING_TILTVA` lista dontí el, kuldunk-e temperature-t.

2. A STABIL PROMPT ELOL, A VALTOZO ADAT HATUL.
   A prompt caching prefix-egyezesre epul: barmi valtozik elol, minden utana
   levo resz ujraszamolodik. Ezert a rendszer-prompt (stabil) es a lead-adat
   (valtozo) szigoruan kulon parameter -- soha ne fuzd ossze oket egy
   stringbe. FIGYELEM: a cache minimum ~1024 token; a mi rendszer-promptjaink
   ennel rovidebbek, tehat MOST meg nem fognak cache-elodni. A szerkezet
   megis igy helyes: a 9-10. szakasz hosszabb, few-shot promptjainal ez mar
   szamit, es akkor nem kell atirni a hivo oldalakat.

3. A "NEM TUDOM" NEM LEHET EGYENLO A "NINCS"-CSEL.
   Ha egy hivas elszall, ez a modul KIVETELT DOB. Sosem ad vissza ures vagy
   default eredmenyt -- ugyanaz az elv, mint a kuldo mailer.fetch_recent()-
   jenel. Egy csendben default-ra eso classifier a legrosszabb fajta hiba:
   ugy nez ki, mintha dolgozna.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import config

# Ezek a modellek MAR NEM fogadnak el sampling parametert (400-at adnak ra).
# Ha uj modellt veszel fel a configba, ellenorizd, hogy melyik csoportba esik.
_SAMPLING_TILTVA = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
                    "claude-sonnet-5", "claude-fable-5", "claude-mythos-5")

# A JSON-kimenet koruli szemet, amit a modellek neha ravesznek a valaszra.
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


class LLMError(RuntimeError):
    """Az LLM-hivas nem sikerult. A hivo oldal NE essen vissza defaultra."""


class LLMConfigError(LLMError):
    """Hianyzo API kulcs vagy ismeretlen modell -- ember kell hozza."""


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def cache_hit(self) -> bool:
        return self.cached_tokens > 0


# ─── Provider-felismeres ───────────────────────────────────────────────────

def provider_of(model: str) -> str:
    m = (model or "").strip().lower()
    if m.startswith(("claude-", "anthropic.")):
        return "anthropic"
    if m.startswith("gemini"):
        return "gemini"
    raise LLMConfigError(
        f"ismeretlen modell: {model!r}\n"
        "  A provider a nev elejebol derul ki: 'claude-*' vagy 'gemini*'."
    )


# ─── Anthropic (QUALITY tier) ──────────────────────────────────────────────

def _call_anthropic(model: str, system: str, user: str,
                    max_tokens: int, temperature: float) -> LLMResult:
    import anthropic  # lusta import: kulcs nelkuli futasnal ne is kelljen

    if not config.ANTHROPIC_API_KEY:
        raise LLMConfigError(
            "hianyzik az ANTHROPIC_API_KEY a gyoker .env-bol.\n"
            "  console.anthropic.com -> API keys"
        )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        # A stabil resz kulon blokkban, cache-jelolessel. Ha egyszer atlepi az
        # ~1024 tokenes minimumot, ettol a sortol kezdve ingyen cache-elodik.
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
    }
    if not model.startswith(_SAMPLING_TILTVA):
        kwargs["temperature"] = temperature

    t0 = time.monotonic()
    try:
        resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError as exc:
        raise LLMConfigError(f"ervenytelen ANTHROPIC_API_KEY: {exc}") from exc
    except anthropic.NotFoundError as exc:
        raise LLMConfigError(f"ismeretlen modell: {model} ({exc})") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError(f"rate limit (a 3 automatikus ujraprobalas utan): {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Anthropic API hiba {exc.status_code}: {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError(f"halozati hiba: {exc}") from exc

    # A `refusal` HTTP 200-zal jon, nem kivetellel -- kulon kell nezni.
    if getattr(resp, "stop_reason", None) == "refusal":
        raise LLMError("a modell elutasitotta a kerest (stop_reason=refusal)")

    text = "".join(b.text for b in resp.content if b.type == "text")
    u = resp.usage
    return LLMResult(
        text=text,
        model=model,
        latency_ms=int((time.monotonic() - t0) * 1000),
        input_tokens=getattr(u, "input_tokens", 0) or 0,
        output_tokens=getattr(u, "output_tokens", 0) or 0,
        cached_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
    )


# ─── Gemini (BULK tier) ────────────────────────────────────────────────────

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _call_gemini(model: str, system: str, user: str,
                 max_tokens: int, temperature: float) -> LLMResult:
    if not config.GEMINI_API_KEY:
        raise LLMConfigError(
            "hianyzik a GEMINI_API_KEY a gyoker .env-bol.\n"
            "  aistudio.google.com -> Get API key"
        )

    payload = {
        # A rendszer-prompt itt is KULON mezo, nem a user szoveg eleje.
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    t0 = time.monotonic()
    try:
        r = httpx.post(
            _GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": config.GEMINI_API_KEY},
            json=payload, timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"halozati hiba (Gemini): {exc}") from exc

    if r.status_code == 400 and "API key" in r.text:
        raise LLMConfigError(f"ervenytelen GEMINI_API_KEY: {r.text[:200]}")
    if r.status_code == 404:
        raise LLMConfigError(f"ismeretlen Gemini modell: {model}")
    if r.status_code == 429:
        raise LLMError(f"Gemini rate limit: {r.text[:200]}")
    if r.status_code >= 400:
        raise LLMError(f"Gemini API hiba {r.status_code}: {r.text[:300]}")

    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        # Biztonsagi szuro vagy ures valasz -- ez NEM "nincs talalat".
        raise LLMError(f"a Gemini nem adott valaszt: {json.dumps(data)[:300]}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    usage = data.get("usageMetadata") or {}
    return LLMResult(
        text=text,
        model=model,
        latency_ms=int((time.monotonic() - t0) * 1000),
        input_tokens=usage.get("promptTokenCount", 0) or 0,
        output_tokens=usage.get("candidatesTokenCount", 0) or 0,
        cached_tokens=usage.get("cachedContentTokenCount", 0) or 0,
    )


# ─── Kozos belepesi pontok ─────────────────────────────────────────────────

def call(model: str, system: str, user: str, *,
         max_tokens: int = 1500, temperature: float = 0.0) -> LLMResult:
    """Egy hivas a megadott modellre. Hiba eseten DOB, sosem ad defaultot."""
    dispatch = {"anthropic": _call_anthropic, "gemini": _call_gemini}
    return dispatch[provider_of(model)](model, system, user, max_tokens, temperature)


def bulk(system: str, user: str, **kw) -> LLMResult:
    """Nagy volumen, alacsony ar. Lead-osztalyozas, elo-szures."""
    return call(config.LLM_BULK_MODEL, system, user, **kw)


def quality(system: str, user: str, **kw) -> LLMResult:
    """Kis volumen, magas minoseg. Magyar mondat, valasz-osztalyozas."""
    return call(config.LLM_QUALITY_MODEL, system, user, **kw)


# ─── JSON-kimenet ──────────────────────────────────────────────────────────

def parse_json(text: str) -> dict:
    """A modell valaszabol dict. Toleralja a markdown kodblokkot.

    MIERT KELL A FENCE-LEVAGAS, ha a prompt tiltja: mert a prompt betartasa
    valoszinuseg, nem garancia. Egy ```json blokk miatt eldobni egy egyebkent
    helyes valaszt felesleges vesztesegek -- viszont a JAVITAS HATARA itt van:
    a szintaxist nem toldozzuk, azt ujra kell kerni.
    """
    cleaned = _JSON_FENCE.sub("", (text or "").strip())
    # Nemely modell ir egy bevezeto mondatot a JSON ele. Az elso '{'-tol
    # az utolso '}'-ig vagunk -- de csak akkor, ha a nyers parse mar elbukott.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        return json.loads(cleaned[start:end + 1])
    raise json.JSONDecodeError("nem talaltam JSON objektumot", cleaned or "", 0)


def json_call(model: str, system: str, user: str, *,
              max_tokens: int = 1500, retries: int = 1) -> tuple[dict, LLMResult]:
    """Hivas + JSON-parse. Parse-hibara UJRAKERDEZ, aztan feladja.

    A terv eloirasa: "JSON-parse hibara retry egyszer, aztan status='error'".
    Az ujraprobalas nem ugyanaz a keres: a masodik korben a hibat is odaadjuk
    a modellnek. Egy elgepelt zarojel igy jellemzoen egy korben javul.
    """
    last: Exception | None = None
    extra = ""
    for kiserlet in range(retries + 1):
        result = call(model, system, user + extra, max_tokens=max_tokens)
        try:
            return parse_json(result.text), result
        except json.JSONDecodeError as exc:
            last = exc
            extra = (
                "\n\n---\nAZ ELOZO VALASZOD NEM VOLT ERVENYES JSON "
                f"({exc}). Add vissza ugyanazt CSAK ervenyes JSON-kent, "
                "magyarazat es markdown kodblokk nelkul."
            )
    raise LLMError(f"{retries + 1} probalkozas utan sem adott ervenyes JSON-t: {last}")


def available() -> dict[str, bool]:
    """Melyik tier hivhato. A CLI ebbol ad beszedes hibat kulcs nelkul."""
    return {
        "bulk": bool(config.GEMINI_API_KEY),
        "quality": bool(config.ANTHROPIC_API_KEY),
    }
