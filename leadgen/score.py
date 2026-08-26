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

1. A FUTAS ES AZ OPCIONALIS EVAL UGYANAZT A PROMPTOT HASZNALJA.
   A `prompts.LEAD_CLASSIFIER_SYSTEM` az egyetlen igazsagforras. Modell-
   osszehasonlitasnal minden jelolt pontosan ezt kapja.

2. A GROUNDING NEM AI-HIVAS.
   Sima string-kereses. Ami nem talalhato meg szo szerint a forrasban, azt
   az IRANYT eldobjuk. Ha egyetlen alatamasztott irany sem marad, a ceg
   megmarad `scored` allapotban, de nem kap kitalalt szemelyre szabast.

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

from . import config, db, grounding, labels, llm, pricing, prompts

# Visszamenoleges kompatibilitas az eval-riporttal es a dead-dev pontszammal.
# Ez mar NEM automatikus kizarasi kuszob.
FIT_KUSZOB = 70

# Mar egyetlen groundolt irany is eleg ahhoz, hogy megprobaljuk a ketmondatos
# szemelyre szabast. A kampany jovahagyasa ettol kulon exportkapu.
PERSONALIZATION_KUSZOB = 1

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
    "mobile": "",              # meg nincs jovahagyhato kampanysablon
    "landing_page": "",        # kesobbi kampanyirany
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


def arbitral(webapp: float, website: float, mobile: float,
             landing_page: float = 0.0) -> tuple[str, str, float]:
    """A harom fit-bol egy ajanlat es egy kampany. (ajanlat, kampany, pont).

    Dontetlennel a WEBAPP nyer: az a terv legerosebb engine-je, es ott a
    legmagasabb a projekt-ertek.
    """
    jeloltek = [("webapp", webapp or 0.0), ("website", website or 0.0),
                ("mobile", mobile or 0.0),
                ("landing_page", landing_page or 0.0)]
    jeloltek.sort(key=lambda x: (-x[1], x[0] != "webapp"))
    ajanlat, pont = jeloltek[0]

    if pont <= 0:
        return "", "", pont

    kampany = _AJANLAT_KAMPANY.get(ajanlat, "")
    return ajanlat, kampany, pont


# ─── A minosites ───────────────────────────────────────────────────────────

def _forrasszoveg(company_id) -> tuple[str, dict, object | None]:
    """A hirdetes szovege -- EZ a grounding forrasa es a prompt bemenete."""
    rows = db.query("""
        select id, raw_signal from sources
         where company_id = %s and source_type = 'profession'
         order by detected_at desc limit 1
    """, (company_id,))
    if not rows:
        return "", {}, None
    rs = rows[0]["raw_signal"] or {}
    szoveg = "\n".join(filter(None, (
        rs.get("description"), rs.get("responsibilities"), rs.get("requirements"))))
    return szoveg, rs, rows[0]["id"]


def _osztalyoz(rs: dict, szoveg: str) -> tuple[dict, str, object]:
    user = prompts.lead_classifier_user(
        forras="Profession.hu allashirdetes",
        ceg=rs.get("company") or rs.get("companyName") or "(ismeretlen)",
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


def _szogek(data: dict) -> list[dict]:
    """Az uj tobbiranyu JSON normalizalasa, regi valasz kompatibilitassal."""
    raw = data.get("opportunity_angles")
    if not isinstance(raw, list):
        # A mar futott/atmenetileg regi promptot koveto modell valasza se
        # vesszen el: egyetlen webapp irannya alakitjuk.
        raw = []
        if data.get("evidence"):
            for ev in data.get("evidence") or []:
                if isinstance(ev, dict):
                    raw.append({
                        "type": "webapp", "score": data.get("webapp_fit", 0),
                        "pain": data.get("pain"), "claim": ev.get("claim"),
                        "quote": ev.get("quote"),
                        "confidence": data.get("confidence"),
                    })

    eredmeny: dict[str, dict] = {}
    for angle in raw:
        if not isinstance(angle, dict):
            continue
        tipus = str(angle.get("type") or "").strip().lower()
        if tipus not in _AJANLAT_KAMPANY:
            continue
        normalizalt = {
            "type": tipus,
            "score": _szam(angle.get("score")),
            "pain": str(angle.get("pain") or "")[:200],
            "claim": str(angle.get("claim") or "")[:500],
            "quote": str(angle.get("quote") or "")[:1000],
            "confidence": min(max(_szam(angle.get("confidence"), 0.0), 0.0), 1.0),
        }
        # Hibasan ismetelt type eseten se mentsunk ket versengo webapp- vagy
        # mobile-angle-t. A prompt eleve tiltja; ez a masodik, determinisztikus
        # vedelmi vonal, es a magasabb score a hasznosabb jel.
        elozo = eredmeny.get(tipus)
        if elozo is None or normalizalt["score"] > elozo["score"]:
            eredmeny[tipus] = normalizalt
    return list(eredmeny.values())


def _fit_by_type(angles: list[dict], tipus: str) -> float:
    return max((_szam(a.get("score")) for a in angles
                if a.get("type") == tipus), default=0.0)


def _personalization(rs: dict, evidence: list, szoveg: str,
                     stats: ScoreStats, kampany: str = "") -> str:
    """A QUALITY tier magyar mondata. Bukas eseten URES -> sablon-email.

    A bemenete a MAR GROUNDOLT idezet: olyat adunk a modellnek, amirol mar
    tudjuk, hogy szo szerint szerepel a forrasban. Igy a mondat nem tud
    olyasmire hivatkozni, ami nincs a hirdetesben.
    """
    if not evidence:
        return ""
    # Egy irányhoz több bizonyíték is érkezhet. A legerősebbet adjuk át,
    # különben egy gyengébb, korábban felsorolt idézet elvihetné a mondatot.
    selected = max(evidence, key=lambda e: _szam(e.get("score")))
    idezet = str(selected.get("quote") or "")
    if not idezet:
        return ""
    try:
        magazo = kampany not in prompts.TEGEZO_KAMPANYOK
        r = llm.quality(prompts.personalization_system(
                            magazo, kampany, str(selected.get("type") or "")),
                        prompts.personalization_user(
                            rs.get("company") or rs.get("companyName") or "", idezet,
                            irany=str(selected.get("type") or ""),
                            fajdalom=str(selected.get("pain") or ""),
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
    """A meg nem pontozott, Profession-forrassal rendelkezo cegek minositese."""
    stats = ScoreStats()
    rows = db.query("""
        select c.id, c.company_name, c.normalized_domain, c.city,
               c.dev_state, c.dev_evidence, c.signal_score
          from companies c
         where c.scored_at is null
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
        szoveg, rs, source_id = _forrasszoveg(row["id"])
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
        g = grounding.ellenoriz(_szogek(data), szoveg)
        stats.megtartott_allitas += len(g.megtartott)
        stats.eldobott_allitas += len(g.eldobott)

        angles = list(g.megtartott)
        for angle in angles:
            angle["_source_id"] = source_id
        objektiv_website = website_fit(row)
        if objektiv_website and row.get("dev_evidence"):
            angles.append({
                "type": "website", "score": objektiv_website,
                "pain": "weboldal karbantartasi kockazata",
                "claim": "a korabbi fejleszto elerhetosege bizonytalan",
                "quote": str(row["dev_evidence"])[:1000],
                "confidence": 1.0, "_source_id": None,
            })
        wa = _fit_by_type(angles, "webapp")
        ws = _fit_by_type(angles, "website")
        mo = _fit_by_type(angles, "mobile")
        lp = _fit_by_type(angles, "landing_page")

        if not g.van_bizonyitek:
            stats.grounding_bukas += 1

        ajanlat, kampany, pont = arbitral(wa, ws, mo, lp)
        van_irany = bool(ajanlat)

        if van_irany:
            stats.fit += 1
            if kampany:
                stats.kampanyok[kampany] = stats.kampanyok.get(kampany, 0) + 1
        else:
            stats.nem_fit += 1

        if verbose:
            jel = "✅" if van_irany else " ·"
            print(f"  {jel} {row['company_name'][:32]:<34} "
                  f"webapp={wa:.0f} website={ws:.0f} "
                  f"mobile={mo:.0f} landing_page={lp:.0f} -> "
                  f"{kampany or ajanlat or 'nincs groundolt irany'}")
            for e in g.eldobott:
                print(f"       ⚠ eldobott allitas: {e['indok']}")
                print(f"         \"{e['quote'][:70]}\"")

        if dry:
            continue

        szemelyre = ""
        selected_evidence = [a for a in angles if a.get("type") == ajanlat]
        if selected_evidence and pont >= PERSONALIZATION_KUSZOB:
            szemelyre = _personalization(rs, selected_evidence, szoveg, stats, kampany)

        _atvezet(row, wa, ws, mo, lp, ajanlat, kampany, angles, g, data,
                 model, szemelyre, source_id)

    if verbose:
        _riport(stats, dry)
    return stats


def _atvezet(row, wa, ws, mo, lp, ajanlat, kampany, angles, g, data,
             model, szemelyre, source_id) -> None:
    osszegzes = "; ".join(
        str(e.get("claim") or "")[:80] for e in g.megtartott[:2])
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("delete from opportunity_angles where company_id = %s", (row["id"],))
        rendezett = sorted(
            angles,
            key=lambda a: (-_szam(a.get("score")), a.get("type") != "webapp"),
        )
        for rank, angle in enumerate(rendezett, start=1):
            cur.execute(
                """
                insert into opportunity_angles
                  (company_id, source_id, rank, angle_type, pain, claim, quote,
                   score, confidence, selected, model)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (row["id"], angle.get("_source_id"), rank, angle.get("type"), angle.get("pain"),
                 angle.get("claim"), angle.get("quote"), angle.get("score"),
                 angle.get("confidence"), rank == 1 and bool(ajanlat), model),
            )

        publikus_angles = [
            {k: v for k, v in angle.items() if not k.startswith("_")}
            for angle in angles
        ]
        cur.execute("""
            select count(*) as n from contacts
             where company_id = %s
               and local_check is distinct from 'fail'
               and coalesce(verify_result, '') <> 'invalid'
               and coalesce(bounce_state, '') <> 'hard_bounce'
        """, (row["id"],))
        van_kapcsolat = int(cur.fetchone()["n"]) > 0
        kuldheto = bool(kampany and szemelyre and van_kapcsolat)
        if kuldheto:
            status, note = "ready", None
        elif not van_kapcsolat:
            status, note = "scored", "nincs hasznalhato kapcsolat"
        elif not ajanlat:
            status, note = "scored", "nincs alatamasztott szemelyre szabasi irany"
        elif not kampany:
            status, note = "scored", f"nincs kesz kampany ehhez az iranyhoz: {ajanlat}"
        else:
            status, note = "scored", "a szemelyre szabas nem keszult el"

        cur.execute("""
            update companies
               set webapp_fit = %s, website_fit = %s, mobile_fit = %s,
                   evidence = %s, grounding_dropped = %s,
                   scored_at = now(), score_model = %s,
                   best_offer = %s,
                   campaign = nullif(%s, ''),
                   personalization = nullif(%s, ''),
                   signal_summary = coalesce(nullif(%s, ''), signal_summary),
                   signal_score = greatest(coalesce(signal_score, 0), %s),
                   status = %s, status_note = %s
             where id = %s
        """, (wa, ws, mo,
              db.Json({"angles": publikus_angles, "dropped": g.eldobott,
                       "landing_page_fit": lp,
                       "company_size_hint": data.get("company_size_hint")}),
              len(g.eldobott), model, ajanlat or None, kampany, szemelyre,
              osszegzes, max(wa, ws, mo, lp), status, note, row["id"]))

        if van_kapcsolat:
            labels.clear_label(cur, row["id"], "contact_missing")
        else:
            labels.set_label(cur, row["id"], "contact_missing",
                             {"stage": "scoring"}, source_id)
        if szemelyre:
            labels.clear_label(cur, row["id"], "personalization_missing")
        else:
            labels.set_label(cur, row["id"], "personalization_missing",
                             {"reason": note or "nincs groundolt idezet"}, source_id)
        if ajanlat and not kampany:
            labels.set_label(cur, row["id"], "campaign_missing",
                             {"angle": ajanlat}, source_id)
        else:
            labels.clear_label(cur, row["id"], "campaign_missing")
        if str(data.get("company_size_hint") or "").upper() == "ENTERPRISE":
            labels.set_label(cur, row["id"], "enterprise_hint",
                             {"source": "ai", "automatic_hold": False}, source_id)
        else:
            labels.clear_label(cur, row["id"], "enterprise_hint")


def _riport(stats: ScoreStats, dry: bool) -> None:
    print(f"\nvizsgalt: {stats.vizsgalt}   talalt irany: {stats.fit}   "
          f"nincs groundolt irany: {stats.nem_fit}   hiba: {stats.hiba}")
    for kampany, n in sorted(stats.kampanyok.items()):
        print(f"  -> {kampany:<14} {n}")

    print(f"\nEVIDENCE GROUNDING")
    print(f"  megtartott allitas: {stats.megtartott_allitas}")
    print(f"  ELDOBOTT allitas  : {stats.eldobott_allitas} "
          f"({stats.grounding_arany * 100:.0f}%)")
    if stats.grounding_bukas:
        print(f"  {stats.grounding_bukas} cegnel nem maradt alatamasztott irany;")
        print("  az adat megmaradt, de szemelyre szabott level nem keszult.")

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
        print(f"\n>>> {stats.fit} cegnel talaltunk legalabb egy lehetseges iranyt.")
        print("    Csak a kapcsolattal, szemelyre szabassal es kesz kampannyal")
        print("    rendelkezo cegek kerultek `ready` allapotba.")
        print("    NEZD AT a mondatokat: ./leadgen.sh report --grounding")
