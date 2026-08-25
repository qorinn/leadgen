#!/usr/bin/env python3
"""AI-minosites + evidence grounding + offer arbitration (10. szakasz).

    allashirdetes -> BULK modell -> fit pontszam + idezetek
                          |
                          v
                  GROUNDING (ingyen, string-kereses)
                          |
                          v
                  OFFER ARBITRATION -> egy kampany
                          |
                          v
              personalization (QUALITY modell, csak a jo leadekre)

════════════════════════════════════════════════════════════════════════════
NEGY SZABALY, AMI ITT NEM KOZMETIKA

1. A BAKE-OFF PROMPTOT SZO SZERINT HASZNALJUK.
   A `prompts.LEAD_CLASSIFIER_SYSTEM` az, amit a bake-offon mertunk. Ha itt
   "csiszolnank" rajta, a meres ervenytelenne valna: nem tudnank, hogy a
   valasztott modell tenyleg jobb-e, vagy csak mas promptot kapott.

2. A GROUNDING NEM AI-HIVAS.
   Sima string-kereses. Ami nem talalhato meg szo szerint a forrasban, azt
   az ALLITAST eldobjuk. Ha egyetlen alatamasztott allitas sem marad, a lead
   `rejected`. Inkabb menjen ki kevesebb level, mint egy magabiztosan teves.

3. A PERSONALIZATION BUKASA NEM EJTI KI A LEADET.
   Ha a `personalization_quote` nem ellenorizheto, a lead SABLON-emailre esik
   vissza -- nem esik ki. A terv kifejezetten ezt irja elo: a szemelyre szabas
   hianya csak gyengebb level, a teves szemelyre szabas viszont karos.

4. EGY CEG = EGY KAMPANY (offer arbitration).
   Ha egy cegnel tobb ajanlat is indokolt lenne, a LEGERŐSEBB nyer, es a
   tobbi nem megy ki kulon levelben. A terv szo szerint: "Nem kap masnap
   »weboldalt keszitek« emailt is."
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config, db, grounding, llm, pricing, prompts

# A terv A/5 kuszobe: e felett FIT. Ugyanaz a szam, amit a bake-off mer.
FIT_KUSZOB = 70

# A personalization csak a jo leadekre keszul -- ez a QUALITY tier, ami
# dragabb. Nincs ertelme egy 30 pontos leadre magyar mondatot iratni.
PERSONALIZATION_KUSZOB = 70

# Ha a grounding-bukas aranya e folott van, a modell hallucinal.
HALLUCINACIO_RIASZTAS = 0.20


@dataclass
class ScoreStats:
    vizsgalt: int = 0
    fit: int = 0
    nem_fit: int = 0
    grounding_bukas: int = 0        # lead, ami bizonyitek hianyaban esett ki
    eldobott_allitas: int = 0
    megtartott_allitas: int = 0
    personalization: int = 0
    personalization_bukas: int = 0
    hiba: int = 0
    kampanyok: dict[str, int] = field(default_factory=dict)
    # MODELLENKENTI tokenszam es koltseg. A szolgaltatok dashboardja lassan
    # frissul es OSSZEVONJA a modelleket -- ezert vezetjuk mi is.
    konyv: pricing.Konyveles = field(default_factory=pricing.Konyveles)

    @property
    def grounding_arany(self) -> float:
        osszes = self.eldobott_allitas + self.megtartott_allitas
        return self.eldobott_allitas / osszes if osszes else 0.0


# ─── Offer arbitration ─────────────────────────────────────────────────────

# A terv "Offer arbitration" fejezete: harom fit, egy kampany.
# A `mobile_fit` ma mindig 0: az app-store engine nincs megepitve. Nem
# talalgatunk helyette -- a nulla oszinte, egy kitalalt szam nem az.
_AJANLAT_KAMPANY = {
    "webapp": "ops_pain",
    "website": "dead_dev",
    "mobile": "mobile",       # meg nincs sablonja -- lasd `arbitral()`
}


def website_fit(row: dict) -> float:
    """A weboldal-ajanlat erossege. NEM AI -- meglevo, objektiv jelekbol.

    Miert nem kerdezzuk meg az AI-t: mert nem kell. A 8.2 (halott fejleszto)
    es a 7.5 (tech ujjlenyomat) mar megmerte ugyanezt, olcsobban es
    megbizhatobban. Egy LLM-hivas itt penzt egetne ugyanazert az informacioert.
    """
    pont = 0.0
    allapot = (row.get("dev_state") or "").upper()
    if allapot == "DEAD":
        pont += 70          # nincs, aki karbantartsa -> eros weboldal-ajanlat
    elif allapot == "DORMANT":
        pont += 45
    return min(pont, 100.0)


def arbitral(webapp: float, website: float, mobile: float) -> tuple[str, str, float]:
    """A harom fit-bol egy ajanlat es egy kampany. (ajanlat, kampany, pont).

    Dontetlennel a WEBAPP nyer: az a terv legerosebb engine-je, es ott a
    legmagasabb a projekt-ertek.
    """
    jeloltek = [("webapp", webapp or 0.0), ("website", website or 0.0),
                ("mobile", mobile or 0.0)]
    jeloltek.sort(key=lambda x: (-x[1], x[0] != "webapp"))
    ajanlat, pont = jeloltek[0]

    if pont < FIT_KUSZOB:
        return "", "", pont

    kampany = _AJANLAT_KAMPANY.get(ajanlat, "")
    # Ha egy ajanlathoz meg nincs sablonkeszlet, NEM kuldunk levelet vaktaban:
    # a `templates.for_campaign` visszaesne az alapertelmezett (ugynoksegi)
    # sablonra, ami egy KKV-nak teljesen ertelmetlen levelet jelentene.
    if kampany == "mobile":
        return ajanlat, "", pont
    return ajanlat, kampany, pont


# ─── A minosites ───────────────────────────────────────────────────────────

def _forrasszoveg(company_id) -> tuple[str, dict]:
    """A hirdetes szovege -- EZ a grounding forrasa es a prompt bemenete."""
    rows = db.query("""
        select raw_signal from sources
         where company_id = %s and source_type = 'profession'
         order by detected_at desc limit 1
    """, (company_id,))
    if not rows:
        return "", {}
    rs = rows[0]["raw_signal"] or {}
    szoveg = "\n".join(filter(None, (
        rs.get("description"), rs.get("responsibilities"), rs.get("requirements"))))
    return szoveg, rs


def _osztalyoz(rs: dict, szoveg: str) -> tuple[dict, str, object]:
    user = prompts.lead_classifier_user(
        forras="Profession.hu allashirdetes",
        ceg=rs.get("company") or "(ismeretlen)",
        pozicio=rs.get("title") or "(ismeretlen)",
        szoveg=szoveg[:12000],
    )
    model = config.LLM_BULK_MODEL
    data, result = llm.json_call(model, prompts.LEAD_CLASSIFIER_SYSTEM, user,
                                 max_tokens=1500)
    return data, model, result


def _szam(ertek, alap: float = 0.0) -> float:
    try:
        return min(max(float(ertek), 0.0), 100.0)
    except (TypeError, ValueError):
        return alap


def _personalization(rs: dict, evidence: list, szoveg: str,
                     stats: ScoreStats, kampany: str = "") -> str:
    """A QUALITY tier magyar mondata. Bukas eseten URES -> sablon-email.

    A bemenete a MAR GROUNDOLT idezet: olyat adunk a modellnek, amirol mar
    tudjuk, hogy szo szerint szerepel a forrasban. Igy a mondat nem tud
    olyasmire hivatkozni, ami nincs a hirdetesben.
    """
    if not evidence:
        return ""
    idezet = str(evidence[0].get("quote") or "")
    if not idezet:
        return ""
    try:
        magazo = kampany not in prompts.TEGEZO_KAMPANYOK
        r = llm.quality(prompts.personalization_system(magazo, kampany),
                        prompts.personalization_user(
                            rs.get("company") or "", idezet,
                            forras="Profession.hu álláshirdetés"),
                        # 1000, nem 300: a reasoning-modellek (gpt-5.6-*)
                        # a BELSO gondolkodasra is a kimeneti keretbol
                        # fogyasztanak. Merve: a luna 300-nal csonka valaszt
                        # adott egyetlen mondatra. A magasabb plafon nem kerul
                        # semmibe -- csak a TENYLEG hasznalt token szamlazodik.
                        max_tokens=1000)
    except llm.LLMError:
        stats.personalization_bukas += 1
        return ""

    stats.konyv.add_result(r)
    mondat = " ".join((r.text or "").split()).strip().strip('"')
    if not mondat or len(mondat) > 350:
        stats.personalization_bukas += 1
        return ""
    stats.personalization += 1
    return mondat


def run(limit: int = 20, dry: bool = False, verbose: bool = True) -> ScoreStats:
    """A meg nem pontozott ops_pain cegek minositese."""
    stats = ScoreStats()
    rows = db.query("""
        select c.id, c.company_name, c.normalized_domain, c.city,
               c.dev_state, c.signal_score
          from companies c
         where c.campaign = 'ops_pain'
           and c.scored_at is null
           and c.status not in ('suppressed', 'rejected')
           and exists (select 1 from sources s
                        where s.company_id = c.id and s.source_type = 'profession')
         order by c.first_seen_at
         limit %s
    """, (limit,))

    if not rows:
        if verbose:
            print("Nincs minositesre varo ceg.")
            print("  Uj hirdetesek: ./leadgen.sh ingest ops-pain")
        return stats

    if verbose:
        print(f"{len(rows)} ceg minositese (modell: {config.LLM_BULK_MODEL})"
              + ("   [SZARAZ FUTAS -- semmit nem irok]" if dry else ""))
        print()

    for row in rows:
        stats.vizsgalt += 1
        szoveg, rs = _forrasszoveg(row["id"])
        if not szoveg:
            stats.hiba += 1
            continue

        try:
            data, model, result = _osztalyoz(rs, szoveg)
            stats.konyv.add_result(result)
        except llm.LLMConfigError:
            raise                       # kulcs hianyzik -> alljon meg az egesz
        except Exception as exc:  # noqa: BLE001
            stats.hiba += 1
            if verbose:
                print(f"  HIBA {row['company_name'][:30]}: {str(exc)[:70]}")
            continue

        # ─── GROUNDING: ingyen, string-kereses ────────────────────────
        g = grounding.ellenoriz(data.get("evidence"), szoveg)
        stats.megtartott_allitas += len(g.megtartott)
        stats.eldobott_allitas += len(g.eldobott)

        wa = _szam(data.get("webapp_fit"))
        ws = website_fit(row)
        mo = 0.0                        # app-store engine meg nincs

        # KEMENY SZABALY: nincs bizonyitek -> nincs allitas -> nincs email.
        # A `webapp_fit`-et nullazzuk, mert az AI allitasa alatamasztatlan.
        # A `website_fit` MEGMARAD: az nem AI-bol jott, hanem a footer-
        # felismeresbol, aminek sajat bizonyiteka van (`dev_evidence`).
        if not g.van_bizonyitek and wa >= FIT_KUSZOB:
            stats.grounding_bukas += 1
            wa = 0.0

        ajanlat, kampany, pont = arbitral(wa, ws, mo)
        fit = bool(kampany)

        if fit:
            stats.fit += 1
            stats.kampanyok[kampany] = stats.kampanyok.get(kampany, 0) + 1
        else:
            stats.nem_fit += 1

        if verbose:
            jel = "✅" if fit else " ·"
            print(f"  {jel} {row['company_name'][:32]:<34} "
                  f"webapp={wa:.0f} website={ws:.0f} -> "
                  f"{kampany or 'nem fit'}")
            for e in g.eldobott:
                print(f"       ⚠ eldobott allitas: {e['indok']}")
                print(f"         \"{e['quote'][:70]}\"")

        if dry:
            continue

        szemelyre = ""
        if fit and wa >= PERSONALIZATION_KUSZOB:
            szemelyre = _personalization(rs, g.megtartott, szoveg, stats, kampany)

        _atvezet(row, wa, ws, mo, ajanlat, kampany, fit, g, data,
                 model, szemelyre)

    if verbose:
        _riport(stats, dry)
    return stats


def _atvezet(row, wa, ws, mo, ajanlat, kampany, fit, g, data,
             model, szemelyre) -> None:
    osszegzes = "; ".join(
        str(e.get("claim") or "")[:80] for e in g.megtartott[:2])
    db.execute("""
        update companies
           set webapp_fit = %s, website_fit = %s, mobile_fit = %s,
               evidence = %s, grounding_dropped = %s,
               scored_at = now(), score_model = %s,
               best_offer = %s,
               campaign = coalesce(nullif(%s, ''), campaign),
               personalization = nullif(%s, ''),
               signal_summary = coalesce(nullif(%s, ''), signal_summary),
               signal_score = greatest(coalesce(signal_score, 0), %s),
               status = %s,
               status_note = %s
         where id = %s
    """, (wa, ws, mo,
          db.Json({"evidence": g.megtartott, "dropped": g.eldobott,
                   "pain": data.get("pain"),
                   "confidence": data.get("confidence"),
                   "company_size_hint": data.get("company_size_hint")}),
          len(g.eldobott), model, ajanlat or None, kampany, szemelyre,
          osszegzes, max(wa, ws),
          # A `ready` a kesz lead. A `rejected` NEM torles: a ceg bent marad,
          # csak nem kap levelet -- egy kesobbi, mas engine ujra minositheti.
          "ready" if fit else "rejected",
          None if fit else "AI-minosites: nem fit"
          + (" (nincs alatamasztott bizonyitek)" if not g.van_bizonyitek else ""),
          row["id"]))


def _riport(stats: ScoreStats, dry: bool) -> None:
    print(f"\nvizsgalt: {stats.vizsgalt}   fit: {stats.fit}   "
          f"nem fit: {stats.nem_fit}   hiba: {stats.hiba}")
    for kampany, n in sorted(stats.kampanyok.items()):
        print(f"  -> {kampany:<14} {n}")

    print(f"\nEVIDENCE GROUNDING")
    print(f"  megtartott allitas: {stats.megtartott_allitas}")
    print(f"  ELDOBOTT allitas  : {stats.eldobott_allitas} "
          f"({stats.grounding_arany * 100:.0f}%)")
    if stats.grounding_bukas:
        print(f"  {stats.grounding_bukas} lead esett ki, mert egyetlen")
        print("  alatamasztott allitas sem maradt.")

    if stats.grounding_arany > HALLUCINACIO_RIASZTAS:
        print(f"\n  ⚠️  A BUKASI ARANY {HALLUCINACIO_RIASZTAS * 100:.0f}% FELETT VAN.")
        print("  A modell kitalalt idezeteket ad -> hallucinal. Ne menj tovabb:")
        print("  futtasd a bake-offot, es valassz masik modellt.")
        print("    ./leadgen.sh eval bakeoff --model <masik>")

    if stats.personalization or stats.personalization_bukas:
        print(f"\nPERSONALIZATION")
        print(f"  elkeszult: {stats.personalization}")
        if stats.personalization_bukas:
            print(f"  sikertelen: {stats.personalization_bukas} "
                  f"-> ezek SABLON-emailt kapnak, nem esnek ki")

    stats.konyv.riport("TOKENEK ES KOLTSEG (ez a futas)")

    if dry:
        print("\n[SZARAZ FUTAS] Semmi nem lett elmentve.")
    elif stats.fit:
        print(f"\n>>> {stats.fit} uj lead `ready` allapotban.")
        print("    NEZD AT a mondatokat: ./leadgen.sh report --grounding")
