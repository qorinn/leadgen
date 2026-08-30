"""GET /api/financials/worklist (CSV letoltes), POST /api/financials/import
(kitoltott CSV feltoltese), POST /api/companies/{id}/financials (cegenkenti
urlap).

Csupa meglevo `leadgen.financials` fuggveny hivasa (WEBUI-TERV.md F5) -- ez a
modul csak a HTTP be-/kimenetet alakitja. A portal lekerdezese jogi okbol
tiltott (lasd leadgen/financials.py fejlecet), ezert ez a folyamat
szandekosan kezi marad.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from leadgen import config, db, financials

from ..schemas import CompanyFinancialsBody, FinancialsImportResponse, FinancialsSaveResponse

router = APIRouter()


@router.get("/api/financials/worklist")
def financials_worklist(limit: int = Query(20, ge=1, le=200)) -> PlainTextResponse:
    """A legjobb N lead, amirol meg nincs penzugyi adat -- CSV letoltes.

    Mindig valid CSV-t ad vissza (ures listanal is csak a fejlecsor), hogy a
    letoltes soha ne akadjon el egy hianyzo fajlon.
    """
    rows = financials.worklist(limit)
    path = config.BASE / "data" / financials.WORKLIST_FILE
    financials.worklist_kiir(rows, path)
    tartalom = path.read_text(encoding="utf-8")
    return PlainTextResponse(
        tartalom,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{financials.WORKLIST_FILE}"'},
    )


@router.post("/api/financials/import", response_model=FinancialsImportResponse)
async def financials_import(
    file: UploadFile = File(...),
    dry: bool = Form(True),
) -> dict:
    """A kitoltott worklist (vagy csoportos beszamolo-export) feltoltese.

    `dry` alapertelmezetten igaz (a repo altalanos dry-run-eloszor elve,
    CLAUDE.md Invariansok #1) -- a frontend elobb egy elonezetet mutat, a
    tenyleges iras kulon, kifejezett megerositessel tortenik.
    """
    tartalom = await file.read()
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, dir=config.BASE / "data"
    ) as tmp:
        tmp.write(tartalom)
        tmp_path = Path(tmp.name)
    try:
        stats = financials.import_csv(tmp_path, dry=dry, verbose=False)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "olvasott": stats.olvasott,
        "frissitett": stats.frissitett,
        "ures": stats.ures,
        "hibas": stats.hibas,
        "ismeretlen": stats.ismeretlen,
        "ezer_forint_gyanu": stats.ezer_forint_gyanu,
        "ertekek": stats.ertekek,
        "dry": dry,
    }


@router.post("/api/companies/{company_id}/financials", response_model=FinancialsSaveResponse)
def company_financials_save(company_id: str, body: CompanyFinancialsBody) -> dict:
    rows = db.query("select id from companies where id = %s", (company_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="nincs ilyen ceg")

    if body.missing:
        financials.jelold_hianyzonak(company_id)
        return {"economic_value": None, "figyelmeztetes": None}

    if body.revenue is None and body.headcount is None:
        raise HTTPException(
            status_code=400,
            detail="adj meg legalabb arbevetelt vagy letszamot "
                   "(vagy jelold: nincs kozzetett beszamolo)",
        )

    figyelmeztetes = None
    if body.revenue is not None and 0 < body.revenue < financials.GYANUSAN_KICSI_HUF:
        figyelmeztetes = (
            f"{body.revenue:,.0f} Ft gyanusan kicsi arbevetel -- a beszamolo "
            "urlapja \"adatok E Ft-ban\" formaban mutat, ez a leggyakoribb elirasi hiba."
        )

    ertek = financials.ment(
        company_id,
        revenue=body.revenue,
        headcount=body.headcount,
        financial_year=body.financial_year,
        forras="manual",
    )
    return {"economic_value": ertek, "figyelmeztetes": figyelmeztetes}
