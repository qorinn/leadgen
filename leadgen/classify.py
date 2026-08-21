#!/usr/bin/env python3
"""Valasz-osztalyozas: reply_events -> suppression / cooldown / 'replied'.

    reply_events (osztalyozatlan)  ->  LLM  ->  cimke + kovetkezmeny

EZ A RENDSZER EGYETLEN VISSZAFORDITHATATLAN AI-DONTESE. Az `unsubscribe` es a
`negative` cimke suppressionbe teszi a ceget, ahonnan nem jon vissza magatol.
Ezert harom vedelmi reteg van egymas utan, es mindharom kell:

  1. A PROMPT bizonytalansag eseten `other`-t ker (lasd prompts.py).
  2. A BIZALMI KAPU (`_MIN_CONFIDENCE`): ha a modell maga sem biztos,
     a visszafordithatatlan cimke `other`-re esik vissza -- ember dont.
  3. A --dry MOD az alapertelmezett munkamodszer: eloszor mindig nezd meg.

MIERT NEM SZIMMETRIKUS A KET HIBA:

    tul szigoru -> egy erdeklodo lead ORÖKRE elveszik      (draga, es NEMA)
    tul enyhe   -> egy nemet mondo ceg meg egy levelet kap  (kellemetlen)

A celcsoport veges (100-300 ugynokseg), tehat egy jo lead elvesztese tobbe
kerul, mint egy felrement level. Ezert dolt el minden hatareset a
megengedobb irany fele.

MIT CSINAL A HAT CIMKE (a terv 3. pontja szerint):

  interested   -> companies.status='replied' + KULON RIPORT-SOR (ez a lenyeg)
  not_now      -> cooldown +90 nap, NINCS suppression
  negative     -> suppression (email szinten), reason='negative_reply'
  unsubscribe  -> suppression (DOMAIN szinten), reason='unsubscribe'
  auto_reply   -> cooldown +14 nap, a lead visszater a sorba
  other        -> semmi automatikus lepes, emberi atnezes
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from . import config, db, llm, prompts
from .normalize import email_domain

# Ez alatt a modell sajat bizonytalansaga miatt NEM hajtunk vegre
# visszafordithatatlan lepest. A cimke ilyenkor `other` lesz, es a
# `rationale` megorzi az eredeti javaslatot -- tehat latszik, mit gondolt
# a modell, csak nem lett belole automatikus kizaras.
_MIN_CONFIDENCE = 0.70

# Csak ez a ket cimke visszafordithatatlan. A tobbinel a bizalmi kapu nem
# szol bele: egy tevesen `not_now`-ra tett valasz 90 nap mulva ujra elojon,
# egy tevesen `interested` pedig csak annyi, hogy ranezel.
_VISSZAFORDITHATATLAN = ("unsubscribe", "negative")

_COOLDOWN_NAPOK = {"not_now": 90, "auto_reply": 14}


@dataclass
class ClassifyStats:
    feldolgozva: int = 0
    hiba: int = 0
    bizalmi_kapu: int = 0          # visszafordithatatlanbol `other` lett
    ismeretlen_cim: int = 0        # nincs ilyen kapcsolat a DB-ben
    cimkek: dict[str, int] = field(default_factory=dict)
    erdeklodok: list[dict] = field(default_factory=list)

    def szamol(self, cimke: str) -> None:
        self.cimkek[cimke] = self.cimkek.get(cimke, 0) + 1


def _osztalyoz(row: dict) -> tuple[dict, str]:
    """Egy valasz besorolasa. (eredmeny_dict, modellnev). Hiba eseten dob."""
    user = prompts.reply_classifier_user(
        felado=row.get("email") or "",
        targy=row.get("subject") or "",
        # A torzs mar 2000 karakterre van vagva a guards oldalan. Itt is
        # vagunk, mert egy kezzel bemasolt sor barmilyen hosszu lehet.
        szoveg=(row.get("body") or "")[:4000],
    )
    model = config.LLM_QUALITY_MODEL
    data, _ = llm.json_call(
        model, prompts.REPLY_CLASSIFIER_SYSTEM, user, max_tokens=500,
    )
    return data, model


def _normalizal(data: dict) -> tuple[str, float, str]:
    """A modell kimenetet ervenyes ertekekre szoritja.

    Ha a modell kitalal egy kategoriat vagy elgepeli, NEM talalgatunk:
    `other` lesz belole, es a rationale megorzi az eredetit. Egy ismeretlen
    cimke soha ne valjon veletlenul suppressionne.
    """
    cimke = str(data.get("classification") or "").strip().lower()
    rationale = str(data.get("rationale") or "").strip()[:500]
    # A NaN KULON KEZELENDO, es ez nem elmeleti: a json.loads Python-
    # kiterjeszteskent ELFOGADJA a `NaN` literalt, tehat egy modell
    # visszaadhatja. NaN-nal MINDEN osszehasonlitas hamis -- vagyis a lenti
    # bizalmi kapu (`confidence < _MIN_CONFIDENCE`) sem lepne be, es egy
    # bizonytalan `unsubscribe` csendben kizarna a ceget. Ezt a tesztkeszlet
    # talalta meg (tests/test_classify.py).
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    if not math.isfinite(confidence):
        confidence = 0.0
    confidence = min(max(confidence, 0.0), 1.0)

    if cimke not in prompts.REPLY_CLASSES:
        rationale = f"[ismeretlen cimke: {cimke!r}] {rationale}"
        cimke = "other"

    # ─── A BIZALMI KAPU ────────────────────────────────────────────────
    if cimke in _VISSZAFORDITHATATLAN and confidence < _MIN_CONFIDENCE:
        rationale = (f"[bizalmi kapu: a modell '{cimke}'-t javasolt "
                     f"{confidence:.2f} bizonyossaggal, ember dontsen] {rationale}")
        cimke = "other"

    return cimke, confidence, rationale


def _kovetkezmeny(cur, cimke: str, email: str, stats: ClassifyStats) -> None:
    """A cimke atvezetese a cegre. A `contacts` a kapocs email -> ceg."""
    cur.execute("select id, company_id from contacts where email = %s", (email,))
    contact = cur.fetchone()
    if contact is None:
        # Kezzel felvett cim, torolt ceg, vagy sajat teszt-level. Nem hiba:
        # a besorolas megmarad, csak nincs kire alkalmazni.
        stats.ismeretlen_cim += 1
        return

    company_id = contact["company_id"]

    if cimke == "interested":
        # A LEGFONTOSABB KIMENET. Nincs automatikus lepes azon kivul, hogy a
        # robot innentol nem ir neki -- a valaszt EMBER irja meg.
        cur.execute(
            "update companies set status = 'replied' where id = %s and status <> 'suppressed'",
            (company_id,))
        cur.execute(
            """update outreach set status = 'replied',
                                   replied_at = coalesce(replied_at, now())
                where contact_id = %s and status in ('queued','sent')""",
            (contact["id"],))
        cur.execute("select company_name, normalized_domain from companies where id = %s",
                    (company_id,))
        ceg = cur.fetchone()
        stats.erdeklodok.append({"email": email, **(ceg or {})})
        return

    if cimke in _COOLDOWN_NAPOK:
        # NINCS suppression. A ceg visszater a sorba, csak kesobb.
        # Az outreach sort le KELL zarni, kulonben a domain lock reszleges
        # indexe szerint a sequence orokre "aktiv" marad, es a ceg soha nem
        # kaphatna uj megkeresest a cooldown lejarta utan sem.
        napok = _COOLDOWN_NAPOK[cimke]
        cur.execute(
            f"""update companies
                   set status = 'ready',
                       cooldown_until = now() + interval '{napok} days',
                       status_note = %s
                 where id = %s and status not in ('suppressed','rejected')""",
            (f"valasz: {cimke} -- {napok} nap cooldown", company_id))
        cur.execute(
            "update outreach set status = 'stopped' where contact_id = %s "
            "and status in ('queued','sent')", (contact["id"],))
        return

    if cimke == "negative":
        # EMAIL szinten tiltunk: egy ember nemet mondott, de a cegnel mas
        # dontéshozo mas valaszt adhat egy masik ajanlatra.
        cur.execute(
            """insert into suppression (email, reason, note)
                    values (%s, 'negative_reply', 'AI valasz-osztalyozas')
               on conflict (email) where email is not null do nothing""",
            (email,))
        _lezar(cur, contact["id"], company_id, "elutasito valasz")
        return

    if cimke == "unsubscribe":
        # DOMAIN szinten tiltunk (a terv eloirasa). Aki leiratkozast ker, az
        # a ceg neveben beszel -- egy masik cimre kuldott level ugyanoda
        # erkezne, es pontosan azt a panaszt valtana ki, amit kerult.
        domain = email_domain(email)
        if domain:
            cur.execute(
                """insert into suppression (normalized_domain, reason, note)
                        values (%s, 'unsubscribe', 'AI valasz-osztalyozas')
                   on conflict (normalized_domain)
                        where normalized_domain is not null and email is null
                        do nothing""",
                (domain,))
        cur.execute(
            """insert into suppression (email, reason, note)
                    values (%s, 'unsubscribe', 'AI valasz-osztalyozas')
               on conflict (email) where email is not null do nothing""",
            (email,))
        _lezar(cur, contact["id"], company_id, "leiratkozas keres a valaszban")
        return

    # `other` -> semmi automatikus lepes. Szandekosan.


def _lezar(cur, contact_id, company_id, indok: str) -> None:
    cur.execute(
        "update outreach set status = 'stopped' where contact_id = %s "
        "and status in ('queued','sent')", (contact_id,))
    cur.execute(
        "update companies set status = 'suppressed', status_note = %s where id = %s",
        (indok, company_id))


def run(limit: int = 50, dry: bool = False, verbose: bool = True) -> ClassifyStats:
    """Az osztalyozatlan valaszok feldolgozasa. Batch-elve, ujraindithatoan."""
    stats = ClassifyStats()

    rows = db.query(
        """select id, email, subject, body, received_at
             from reply_events
            where classified_at is null
            order by created_at
            limit %s""", (limit,))

    if not rows:
        if verbose:
            print("Nincs osztalyozatlan valasz.")
        return stats

    if verbose:
        print(f"{len(rows)} valasz vár osztalyozasra "
              f"(modell: {config.LLM_QUALITY_MODEL})"
              + ("   [SZARAZ FUTAS -- semmit nem irok]" if dry else ""))
        print()

    for row in rows:
        try:
            data, model = _osztalyoz(row)
        except llm.LLMConfigError:
            raise                       # kulcs hianyzik -> az egesz futas alljon meg
        except (llm.LLMError, json.JSONDecodeError) as exc:
            stats.hiba += 1
            if verbose:
                print(f"  HIBA {row['email']}: {exc}")
            if not dry:
                # Az `error` kitoltese nelkul ez a sor ugy nezne ki, mint egy
                # meg fel nem dolgozott valasz, es minden futas ujra nekimenne.
                db.execute(
                    "update reply_events set error = %s, classified_at = now() "
                    "where id = %s", (str(exc)[:500], row["id"]))
            continue

        eredeti = str(data.get("classification") or "?")
        cimke, confidence, rationale = _normalizal(data)
        if cimke != eredeti and eredeti in _VISSZAFORDITHATATLAN:
            stats.bizalmi_kapu += 1

        stats.feldolgozva += 1
        stats.szamol(cimke)

        if verbose:
            jel = "!" if cimke == "interested" else " "
            print(f" {jel} {cimke:<12} {confidence:.2f}  {row['email']}")
            if rationale:
                print(f"      {rationale[:110]}")

        if dry:
            continue

        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """update reply_events
                      set classification = %s, confidence = %s, model = %s,
                          rationale = %s, error = null, classified_at = now()
                    where id = %s""",
                (cimke, confidence, model, rationale, row["id"]))
            _kovetkezmeny(cur, cimke, (row["email"] or "").strip().lower(), stats)

    if verbose:
        _riport(stats, dry)
    return stats


def _riport(stats: ClassifyStats, dry: bool) -> None:
    print()
    print(f"feldolgozva: {stats.feldolgozva}   hiba: {stats.hiba}")
    for cimke in prompts.REPLY_CLASSES:
        if stats.cimkek.get(cimke):
            print(f"  {cimke:<12} {stats.cimkek[cimke]:>3}")

    if stats.bizalmi_kapu:
        print(f"\n  {stats.bizalmi_kapu} esetben a bizalmi kapu lepett kozbe: a modell")
        print(f"  visszafordithatatlan cimket javasolt {_MIN_CONFIDENCE} alatti")
        print("  bizonyossaggal, ezert 'other' lett. Nezd at oket.")

    if stats.ismeretlen_cim:
        print(f"\n  {stats.ismeretlen_cim} valasz olyan cimrol jott, ami nincs a DB-ben")
        print("  (kezzel felvett lead vagy sajat teszt-level). Besorolva, de nincs kire alkalmazni.")

    if stats.erdeklodok:
        print(f"\n{'=' * 66}")
        print(f">>> {len(stats.erdeklodok)} ERDEKLODO VALASZ -- EZEKRE TE VALASZOLJ, 24 ORAN BELUL")
        print(f"{'=' * 66}")
        for e in stats.erdeklodok:
            print(f"  {e.get('company_name') or '?'}  <{e['email']}>")
            if e.get("normalized_domain"):
                print(f"    https://{e['normalized_domain']}")

    if dry:
        print("\n[SZARAZ FUTAS] Semmi nem lett elmentve. Eles futas: a --dry nelkul.")
