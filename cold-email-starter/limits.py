#!/usr/bin/env python3
"""Kuldesi korlatok: idoablak, napi keret es automatikus ramp.

MIERT VAN RA SZUKSEG (draga tapasztalat):
  - Uj domainrol/postafiokbol azonnal sok levelet kuldeni a leggyorsabb ut a
    spam-mappaba. A fogadoszerverek a HIRTELEN volumen-ugrast bunetik.
  - A ramp csak akkor emel, ha az elozo napok kezbesitesi jelei tisztak
    (alacsony bounce, nulla SMTP-elutasitas). Rossz jelnel visszavesz.
  - Az idoablak (munkaido) es a valtozo szunet emberi mintat utanoz.
"""
from __future__ import annotations

import datetime
import json
import random

import config
import store


def in_send_window(now: datetime.datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.datetime.now()
    if not config.SEND_ON_WEEKEND and now.weekday() >= 5:
        return False, "hetvege"
    if not (config.SEND_WINDOW_START <= now.hour < config.SEND_WINDOW_END):
        return False, f"kuldesi ablakon kivul ({config.SEND_WINDOW_START}-{config.SEND_WINDOW_END})"
    return True, "ok"


def _load_state() -> dict:
    if config.RAMP_JSON.exists():
        try:
            return json.loads(config.RAMP_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "cap": config.DAILY_CAP_START,
        "ceiling": config.DAILY_CAP_CEILING,
        "clean_days": 0,
        "last_eval": "",
        "history": [],
    }


def _save_state(state: dict) -> None:
    config.RAMP_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def daily_cap() -> int:
    """Az aznapi teljes keret (osszes postafiokra egyutt)."""
    state = _load_state()
    accounts = max(1, len(config.smtp_accounts()))
    return int(state.get("cap", config.DAILY_CAP_START)) * accounts


def remaining_today() -> int:
    return max(0, daily_cap() - store.sent_today_count())


def send_delay() -> float:
    return random.uniform(config.MIN_DELAY_SECS, config.MAX_DELAY_SECS)


def evaluate_ramp(sent: int, bounces: int, rejects: int) -> dict:
    """Napi egyszer futtasd (a kuldesi ablak zarasa utan).

    Emel, ha RAMP_STEP_DAYS egymast koveto tiszta nap volt.
    Azonnal visszavesz, ha a bounce vagy a reject atlepi a kuszobot.
    """
    state = _load_state()
    today = store.today()
    if state.get("last_eval") == today:
        return state  # ma mar ertekeltunk

    bounce_rate = (bounces / sent) if sent else 0.0
    # A KET NEVEZO SZANDEKOSAN KULONBOZIK:
    #
    #   bounce -- a KIKULDOTT levelek hanyada pattant vissza  -> `sent`
    #   reject -- a MEGKISERELT kuldesek hanyadat utasitottak el -> `sent + rejects`
    #
    # Az elutasitott level ki sem ment, tehat nincs benne a `sent`-ben. Ha
    # itt is `sent`-tel osztanank, 20 kiserletbol 20 elutasitas eseten a
    # nevezo NULLA lenne -- vagyis pont a legsulyosabb esetben adna 0%-ot es
    # hallgatna a riasztas. (Ugyanez a keplet all a deliverability.py
    # `reject_rate` mezojeben; a ketto egy szam, ne csusszon szet.)
    attempted = sent + rejects
    reject_rate = (rejects / attempted) if attempted else 0.0
    cap = int(state.get("cap", config.DAILY_CAP_START))
    action = "hold"

    if bounce_rate >= config.BOUNCE_RATE_ALERT or reject_rate >= config.REJECT_RATE_ALERT:
        cap = max(config.DAILY_CAP_START, cap - config.RAMP_STEP)
        state["clean_days"] = 0
        action = "DOWN"
    elif sent > 0:
        state["clean_days"] = int(state.get("clean_days", 0)) + 1
        if state["clean_days"] >= config.RAMP_STEP_DAYS and cap < state.get("ceiling", config.DAILY_CAP_CEILING):
            cap = min(int(state.get("ceiling", config.DAILY_CAP_CEILING)), cap + config.RAMP_STEP)
            state["clean_days"] = 0
            action = "UP"

    state["cap"] = cap
    state["last_eval"] = today
    state.setdefault("history", []).append({
        "date": today, "sent": sent, "bounces": bounces, "rejects": rejects,
        "bounce_rate": round(bounce_rate, 4), "reject_rate": round(reject_rate, 4),
        "cap_to": cap, "action": action,
    })
    state["history"] = state["history"][-90:]
    _save_state(state)
    return state
