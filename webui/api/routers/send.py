"""A kuldes ketlepcsos utja (F7) -- a rendszer legkockazatosabb endpointja.

    POST /api/send/preview   a mai terv, TELJES levelekkel + egy token
    POST /api/send/live      eles kuldes -- CSAK ervenyes tokennel
    POST /api/send/sample    mintalevel a sajat cimedre (nem ir a sent.csv-be)

MIERT NINCS ITT UZLETI LOGIKA: a terv felepitese a kuldo dolga
(`sender.build_plan`), a token-kapu szabalyai a `leadgen/send.py`-ban vannak.
Ez a modul csak HTTP-formara alakit -- ugyanaz a felallas, mint a tobbi
routernel.

A KAPU HELYE. Az eles kuldes elott a szerver UJRA lekerdezi a tervet, es
ujra hasheli. Nem a frontend mondja meg, hogy a terv valtozatlan -- a
szerver ellenorzi. Egy letiltott gomb megkerulheto (elgepelt `fetch`,
vissza-gomb, ujratoltes); ez nem (WEBUI-TERV.md Invariansok #2).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from leadgen import send

from .. import jobs
from ..schemas import (JobResponse, SendKontaktBody, SendLiveBody,
                       SendPreviewResponse, SendSampleBody, SendSampleResponse)

router = APIRouter()


def _terv() -> send.Terv:
    """A mai terv, vagy 503, ha a kuldot nem tudtuk megkerdezni.

    A "nem tudom" SOHA nem lehet egyenlo a "nincs mit kuldeni"-vel: egy ures
    terv azt jelentene, hogy ma senkit nem kell megkeresni. Ez a kuldo
    `guards`-invariansanak a parja (CLAUDE.md Invariansok #2).
    """
    terv = send.terv()
    if not terv.ok:
        raise HTTPException(
            status_code=503,
            detail=f"a kuldo nem valaszolt: {terv.error} "
                   "(fut a rendszer python3, es megvan a cold-email-starter/.env?)",
        )
    return terv


@router.post("/api/send/preview", response_model=SendPreviewResponse)
def send_preview() -> dict:
    """A mai terv teljes leveleivel, es egy 10 percig ervenyes token.

    A TERV GUARDS NELKUL keszul. A `sender.py --dry` alapbol lefuttatja a
    guardsot, de az IMAP-ot nyit ES IR (DNC, bounce-naplo) -- egy elonezet
    nem irhat. A guards a kuldeskor fut le, es a tervet csak SZUKITENI tudja
    (aki kozben valaszolt vagy leiratkozott, kimarad). A felulet ezt kiirja.
    """
    terv = _terv()
    token, lejar = send.token_kiad(terv.levelek)
    # A cimet CSAK a `cold` fokon szabad cserelni -- a szabaly es az indoka a
    # `leadgen.send.CSEREHETO_FOK`-nal van. A szures itt tortenik, hogy a
    # frontend ne ismerje a fok-neveket.
    cserehetok = [lv.cimzett for lv in terv.levelek if lv.fok == send.CSEREHETO_FOK]
    return {
        "token": token,
        "lejar": lejar,
        "levelek": [vars(lv) for lv in terv.levelek],
        "mai_keret": terv.mai_keret,
        "terv_meret": terv.terv_meret,
        "ablak_nyitva": terv.ablak_nyitva,
        "ablak_ok": terv.ablak_ok,
        "valaszthato": send.kontakt_valasztek(cserehetok),
    }


@router.post("/api/send/kontakt", response_model=JobResponse)
def send_kontakt(body: SendKontaktBody) -> dict:
    """Cimzett-csere egy cegnel, majd a `leads.csv` ujrairasa.

    MIERT INDIT EXPORTOT: a kuldo a `leads.csv`-bol dolgozik, nem a DB-bol.
    A DB-ben elmentett valasztas onmagaban nem valtoztatna meg a mai tervet --
    a fajlt is ujra kell irni. Az export ezert nem "extra" lepes, hanem a
    csere befejezese.

    A tokent ez SZANDEKOSAN ervenytelenne teszi: a terv tartalma megvaltozott,
    tehat a felhasznalonak uj elonezetet kell kernie, es azt jova kell
    hagynia. (Ugyanaz a kapu, mint a `/api/send/live`-nal.)
    """
    futo = jobs.futo()
    if futo is not None:
        raise HTTPException(
            status_code=409,
            detail=f"mar fut egy futas: {futo.cimke} -- eloszor varj meg",
        )

    eredmeny = send.kontakt_csere(body.regi_email, body.uj_email)
    if not eredmeny.ok:
        raise HTTPException(status_code=400, detail=eredmeny.hiba)

    try:
        job = jobs.indit("export")
    except jobs.MarFut as exc:
        raise HTTPException(status_code=409, detail=f"mar fut egy futas: {exc.job.cimke}")
    return {"job": job.adat()}


@router.post("/api/send/live", response_model=JobResponse)
def send_live(body: SendLiveBody) -> dict:
    """ELES KULDES. Csak ervenyes, fel nem hasznalt, friss tokennel indul.

    A sorrend nem cserelheto fel:
      1. ujra lekerdezzuk a tervet a kuldotol,
      2. a token ellenorzese ES elhasznalasa EGY lepesben (dupla kattintas),
      3. csak ezutan indul barmilyen folyamat.

    Ha a 2. lepes elutasit, semmi nem indult el.
    """
    mostani = _terv()
    try:
        send.token_beval(body.token, mostani.levelek)
    except send.TokenErvenytelen as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    try:
        job = jobs.indit_kuldes()
    except jobs.MarFut as exc:
        # A token mar elhasznalodott -- szandekosan. Egy futas kozbeni
        # masodik kuldes-inditas ugyis uj elonezetet erdemel.
        raise HTTPException(
            status_code=409,
            detail=f"mar fut egy futas: {exc.job.cimke} ({exc.job.parancs}) "
                   "-- eloszor varj meg vagy szakitsd meg, majd kerj uj elonezetet",
        )
    return {"job": job.adat()}


@router.post("/api/send/sample", response_model=SendSampleResponse)
def send_sample(body: SendSampleBody) -> dict:
    """Mintalevel a SAJAT cimedre (`preview.py --send-to`).

    VALODI SMTP-kuldes, de a valodi cimzettek nem kapnak semmit, es a
    `sent.csv` sem valtozik -- a lead szekvenciaja erintetlen marad.
    """
    cim = (body.cim or "").strip()
    if "@" not in cim:
        raise HTTPException(status_code=400, detail="adj meg egy ervenyes email cimet")
    if not (1 <= body.limit <= 10):
        raise HTTPException(status_code=400, detail="a minta-darabszam 1 es 10 kozott lehet")
    if body.fok not in send.FOKOK:
        raise HTTPException(
            status_code=400,
            detail=f"ismeretlen fok: {body.fok!r} (valaszthato: {', '.join(send.FOKOK)})",
        )
    # Nem kuldunk mintat, amig egy masik futas dolgozik: az eles kuldes es a
    # minta ugyanazt az SMTP-fiokot hasznalna, es a Google napi limitje is
    # kozos.
    futo = jobs.futo()
    if futo is not None:
        raise HTTPException(
            status_code=409,
            detail=f"mar fut egy futas: {futo.cimke} -- eloszor varj meg",
        )

    eredmeny = send.mintalevel(cim, limit=body.limit, fok=body.fok)
    return {"ok": eredmeny.ok, "sorok": eredmeny.sorok,
            "error": eredmeny.error or None}
