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

# ⚠️ MERVE 2026-08-22, ELES HIVASSAL:
# az `anthropic` SDK 1.0.0 `messages.create()` fuggvenyebol a `temperature`
# parameter TELJESEN ELTUNT. Nem modellfuggo korlat -- a kwarg atadasa
# `TypeError`-t dob, MEG AZELOTT, hogy barmilyen HTTP hivas tortenne.
#
# Ezert az Anthropic ag SOSEM kap temperature-t (lasd `_call_anthropic`),
# es ez a lista mar csak az OPENAI oldalra vonatkozik: a reasoning-modellek
# (o1/o3/o4) csak az alapertelmezett temperature-t fogadjak el.
#
# (A korabbi feltevesem az volt, hogy a claude-haiku-4-5 "meg elfogadja" --
# ezt az elso valodi hivas cafolta meg. Pontosan ezert kell eles teszt.)
_SAMPLING_TILTVA = ("o1", "o3", "o4")

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
    if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    raise LLMConfigError(
        f"ismeretlen modell: {model!r}\n"
        "  A provider a nev elejebol derul ki:\n"
        "    claude-*                  -> Anthropic\n"
        "    gpt-* / o1 / o3 / o4      -> OpenAI\n"
        "    gemini*                   -> Google"
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
    # `temperature` SZANDEKOSAN NINCS: az SDK 1.0.0-bol kikerult (lasd a
    # _SAMPLING_TILTVA melletti magyarazatot). A parameter atadasa TypeError.
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        # A stabil resz kulon blokkban, cache-jelolessel. Ha egyszer atlepi az
        # ~1024 tokenes minimumot, ettol a sortol kezdve ingyen cache-elodik.
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
    }
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
    except TypeError as exc:
        # Az SDK szignaturaja valtozott (mint a temperature eseteben 1.0.0-ban).
        raise LLMConfigError(
            f"az anthropic SDK nem fogadta el a parametereket: {exc}\n"
            f"  Telepitett verzio: {anthropic.__version__}\n"
            "  Ellenorizd a leadgen/llm.py `_call_anthropic` hivasat."
        ) from exc

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


# ─── OpenAI (BULK tier, 2026-08-22 ota ez az alapertelmezes) ───────────────
#
# MIERT httpx ES NEM AZ OPENAI SDK: ugyanaz az indok, mint a Gemininel --
# egyetlen REST hivas nem indokol egy masodik nagy SDK-t a fuggosegek kozt.
# (Az Anthropic oldalon SDK-t hasznalunk, mert ott a hivatalos ajanlas az,
# es a tool use / caching retegek megis kellhetnek kesobb.)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _call_openai(model: str, system: str, user: str,
                 max_tokens: int, temperature: float) -> LLMResult:
    if not config.OPENAI_API_KEY:
        raise LLMConfigError(
            "hianyzik az OPENAI_API_KEY a gyoker .env-bol.\n"
            "  platform.openai.com -> API keys"
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            # A STABIL resz elol, a valtozo hatul -- ugyanaz a szerkezet,
            # mint a masik ket providernel, a caching miatt.
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # Az ujabb modellek `max_tokens` helyett ezt varjak. Ha a modell a
        # regi nevet keri, a lenti hibakezeles atvalt.
        "max_completion_tokens": max_tokens,
        # JSON-mod: a modell garantaltan ervenyes JSON-t ad vissza. A
        # promptjaink amugy is JSON-t kernek, tehat ez csak megerositi.
        "response_format": {"type": "json_object"},
    }
    if not model.startswith(_SAMPLING_TILTVA):
        payload["temperature"] = temperature

    t0 = time.monotonic()
    valasz = _openai_post(payload)

    # ── Parameter-alapu visszaeses ────────────────────────────────────
    # A modellcsaladok kulonbozo parametereket fogadnak el, es a nevek
    # valtoznak (`max_tokens` -> `max_completion_tokens`, temperature-tiltas,
    # JSON-mod tamogatas). Ahelyett, hogy modellenkent tablazatot vezetnenk
    # -- ami elavulna --, a HIBAUZENETBOL tanulunk, egyszer, es ujraprobalunk.
    for _ in range(3):
        if valasz.status_code < 400:
            break
        szoveg = valasz.text[:600]
        modositva = False
        if "max_completion_tokens" in szoveg and "max_tokens" in szoveg:
            payload["max_tokens"] = payload.pop("max_completion_tokens", max_tokens)
            modositva = True
        elif "temperature" in szoveg and "temperature" in payload:
            payload.pop("temperature")
            modositva = True
        elif "response_format" in szoveg and "response_format" in payload:
            payload.pop("response_format")
            modositva = True
        if not modositva:
            break
        valasz = _openai_post(payload)

    r = valasz
    if r.status_code == 401:
        raise LLMConfigError(f"ervenytelen OPENAI_API_KEY: {r.text[:200]}")
    if r.status_code == 404:
        raise LLMConfigError(f"ismeretlen OpenAI modell: {model} ({r.text[:200]})")
    if r.status_code == 429:
        raise LLMError(f"OpenAI rate limit / elfogyott kredit: {r.text[:300]}")
    if r.status_code >= 400:
        raise LLMError(f"OpenAI API hiba {r.status_code}: {r.text[:400]}")

    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise LLMError(f"az OpenAI nem adott valaszt: {json.dumps(data)[:300]}")

    uzenet = choices[0].get("message") or {}
    text = uzenet.get("content") or ""
    # A `length` finish_reason csonka JSON-t jelent -- ezt NEM nyeljuk el,
    # kulonben a parse hibaja utan talalgatnank, mi tortent.
    if choices[0].get("finish_reason") == "length" and not text.rstrip().endswith("}"):
        raise LLMError("a valasz elfogyott a token-keret miatt (novelt max_tokens kell)")

    usage = data.get("usage") or {}
    reszletek = usage.get("prompt_tokens_details") or {}
    return LLMResult(
        text=text,
        model=data.get("model") or model,
        latency_ms=int((time.monotonic() - t0) * 1000),
        input_tokens=usage.get("prompt_tokens", 0) or 0,
        output_tokens=usage.get("completion_tokens", 0) or 0,
        cached_tokens=reszletek.get("cached_tokens", 0) or 0,
    )


def _openai_post(payload: dict):
    try:
        return httpx.post(
            _OPENAI_URL, json=payload, timeout=120.0,
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"halozati hiba (OpenAI): {exc}") from exc


# ─── Kozos belepesi pontok ─────────────────────────────────────────────────

def call(model: str, system: str, user: str, *,
         max_tokens: int = 1500, temperature: float = 0.0) -> LLMResult:
    """Egy hivas a megadott modellre. Hiba eseten DOB, sosem ad defaultot."""
    dispatch = {"anthropic": _call_anthropic, "gemini": _call_gemini,
                "openai": _call_openai}
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


_KULCS = {
    "anthropic": ("ANTHROPIC_API_KEY", "console.anthropic.com -> API keys"),
    "openai": ("OPENAI_API_KEY", "platform.openai.com -> API keys"),
    "gemini": ("GEMINI_API_KEY", "aistudio.google.com -> Get API key"),
}


def kulcs_hianyzik(model: str) -> str:
    """Ures string, ha a modellhez van kulcs. Kulonben beszedes uzenet.

    A PROVIDERBOL vezetjuk le, nem bedrotozott nevbol: igy egy modellvaltas
    (`.env`) utan a hibauzenet is a HELYES kulcsot keri, nem a regit.
    """
    provider = provider_of(model)
    nev, honnan = _KULCS[provider]
    if getattr(config, nev, ""):
        return ""
    return (f"nincs {nev} a gyoker .env-ben (a(z) {model!r} modellhez kell)\n"
            f"  {honnan}")


def available() -> dict[str, bool]:
    """Melyik tier hivhato. A CLI ebbol ad beszedes hibat kulcs nelkul."""
    def ok(model: str) -> bool:
        try:
            return not kulcs_hianyzik(model)
        except LLMConfigError:
            return False
    return {
        "bulk": ok(config.LLM_BULK_MODEL),
        "quality": ok(config.LLM_QUALITY_MODEL),
    }
