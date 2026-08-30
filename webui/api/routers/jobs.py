"""A futtatas HTTP-felulete (F6).

Az egesz logika a `webui/api/jobs.py`-ban van (katalogus, sorositas,
megszakitas, elozmeny) -- ez a modul csak HTTP-formara alakit, ahogy a tobbi
router is.

Az SSE-strem (`/api/jobs/{id}/stream`) SOR-KURZORRAL dolgozik, nem
"kuldjuk, ami jott" alapon: igy egy ujratolt oldal onnan folytatja, ahol
abbahagyta, es a naplo sem nem ismetel, sem nem hagy ki.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .. import jobs
from ..schemas import (JobCatalogResponse, JobCurrentResponse, JobHistoryResponse,
                       JobOutputResponse, JobResponse, JobStartBody)

router = APIRouter()

# Ilyen surun nezunk ra, jott-e uj sor. A folyamat kimenete azonnal
# beerkezik (kulon olvaso szal, `-u` a gyerekben) -- ez csak azt szabja meg,
# milyen surun POSTAZZUK ki. 0,25 mp emberi szemmel folyamatos, es nem porgeti
# feleslegesen a CPU-t.
_POLL_MP = 0.25


@router.get("/api/jobs/catalog", response_model=JobCatalogResponse)
def job_catalog() -> dict:
    return {"items": jobs.katalogus_adat()}


@router.get("/api/jobs/current", response_model=JobCurrentResponse)
def job_current() -> dict:
    futo = jobs.futo()
    return {"job": futo.adat() if futo else None}


@router.get("/api/jobs/history", response_model=JobHistoryResponse)
def job_history(limit: int = Query(30, ge=1, le=200)) -> dict:
    return {"items": jobs.elozmenyek(limit)}


@router.post("/api/jobs/start", response_model=JobResponse)
def job_start(body: JobStartBody) -> dict:
    """Elinditja a parancsot.

    409, ha mar fut valami -- a futo job cimkejevel, hogy a felhasznalo lassa,
    MI fut (WEBUI-TERV.md F6). Az egyszerre-egy-futas indoka a jobs.py
    fejleceben all.
    """
    try:
        job = jobs.indit(body.kulcs, body.params)
    except jobs.MarFut as exc:
        raise HTTPException(
            status_code=409,
            detail=f"mar fut egy futas: {exc.job.cimke} ({exc.job.parancs}) "
                   "-- eloszor varj meg vagy szakitsd meg",
        )
    except jobs.IsmeretlenParancs:
        raise HTTPException(status_code=404, detail=f"ismeretlen parancs: {body.kulcs!r}")
    except jobs.ErvenytelenParameter as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job": job.adat()}


@router.post("/api/jobs/{job_id}/cancel", response_model=JobResponse)
def job_cancel(job_id: str) -> dict:
    job = jobs.megszakit(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="nincs ilyen futas")
    return {"job": job.adat()}


@router.get("/api/jobs/{job_id}", response_model=JobOutputResponse)
def job_output(job_id: str, cursor: int = Query(0, ge=0)) -> dict:
    job = jobs.job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="nincs ilyen futas (a szerver ujraindulasa utan a regi "
                   "kimenet mar nem elerheto -- az elozmeny megmarad)",
        )
    sorok, uj_cursor = job.sorok_tol(cursor)
    return {"job": job.adat(), "lines": sorok, "cursor": uj_cursor}


@router.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str, cursor: int = Query(0, ge=0)) -> StreamingResponse:
    """Elo naplo (SSE). Minden esemeny egy JSON: uj sorok + a job allapota.

    A vegen egy utolso esemenyt kuldunk a lezart allapottal, majd lezarjuk a
    stremet -- igy a bongeszo `EventSource`-a nem kezd el ujracsatlakozni egy
    mar befejezett futasra.
    """
    job = jobs.job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="nincs ilyen futas")

    async def esemenyek():
        poz = cursor
        while True:
            sorok, poz = job.sorok_tol(poz)
            kesz = not job.fut
            if sorok or kesz:
                yield "data: " + json.dumps(
                    {"lines": sorok, "cursor": poz, "job": _json_job(job)},
                    ensure_ascii=False) + "\n\n"
            if kesz:
                # Meg egy korre visszaterunk: a folyamat vege es az olvaso
                # szal utolso sorai kozott lehet par ezredmasodperc.
                sorok, poz = job.sorok_tol(poz)
                if sorok:
                    yield "data: " + json.dumps(
                        {"lines": sorok, "cursor": poz, "job": _json_job(job)},
                        ensure_ascii=False) + "\n\n"
                return
            await asyncio.sleep(_POLL_MP)

    return StreamingResponse(
        esemenyek(),
        media_type="text/event-stream",
        # A Next.js dev-proxy es a bongeszo kulonben pufferelne -- pont az
        # elo naplo veszne el, ami a fazis egesz ertelme.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _json_job(job: jobs.Job) -> dict:
    """A job adatai JSON-barat alakban (a datumok stringge alakitva).

    Az SSE-nel nincs Pydantic-sorosito, ezert itt kell megtenni -- de
    UGYANABBOL az `adat()`-bol, mint a tobbi endpoint, hogy a ket uton
    erkezo job objektum mezoi ne csusszanak el.
    """
    adat = job.adat()
    for kulcs in ("started_at", "finished_at"):
        ertek = adat.get(kulcs)
        adat[kulcs] = ertek.isoformat() if ertek else None
    return adat
