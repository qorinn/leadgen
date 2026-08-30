"""A webes felulet kontraktusa: az uzleti logika Pythonban marad.

MIERT KELL EZ A TESZT (WEBUI-TERV.md, Invariansok #1):

A frontend a `GET /api/meta`-bol tudja meg, mi engedelyezett -- nem magatol.
Ha valaki egyszer beir egy `const STATUSES = ["new", "ready", ...]` sort egy
komponensbe, az ELESBEN NEM DOB HIBAT: a felulet tovabbra is renderel, csak
csendben MAST mutat, mint amit a rendszer csinal. Pontosan a nema hiba
esete, amiert ebben a repoban egyaltalan van teszt (CLAUDE.md).

Konkret peldak, amiket ez a teszt elkap:
  - egy uj status a 014-es migracioban -> a Python latja, a bedrotozott
    TS-lista nem, es a ceg "ismeretlen allapot"-kent tunik el a szurobol;
  - egy kampany felkerul az APPROVED_CAMPAIGNS-ba -> a felulet tovabbra is
    "VAZLAT"-kent mutatja, es a felhasznalo nem exportal;
  - egy suppression-ok bovites -> a felulet nem kinalja fel, tehat egy
    valodi tiltas nem rogzitheto.

A masik fele: minden endpointnak legyen `response_model`-je. Enelkul az
OpenAPI sema URES objektum, a generalt `api-types.ts` hasznalhatatlan, es a
frontend KENYTELEN kezi tipust irni -- amit ugyanez az invarians tilt.
"""
import ast
import re
from pathlib import Path

import pytest

from leadgen import engines, report
from leadgen.contract import APPROVED_CAMPAIGNS

REPO = Path(__file__).resolve().parent.parent
APP_DIR = REPO / "webui" / "app"
API_DIR = REPO / "webui" / "api"

# A generalt tipusfajl KIVETEL: azt az OpenAPI sema hozza letre, tehat a
# benne szereplo nevek eppen hogy a Pythonbol szarmaznak, nem masolatok.
_GENERALT = {"api-types.ts"}

# A `shadcn add` altal telepitett komponens-konyvtarak KIVETELEK: ezeket nem
# mi irjuk, es egy legkozelebbi `shadcn add` ujra felulirja oket -- tehat egy
# talalat itt nem uzleti-szabaly-atszivargas, hanem veletlen szo-utkozes a
# vendor sajat (uzlettol fuggetlen) szohasznalataval. Peldaul a Bklit
# bar-chart sajat animacios allapotgepe a "ready" es "hold" szavakat hasznalja
# chart-fazisokra -- ez nem a companies.status-t masolja, csak veletlenul
# ugyanaz a ket angol szo (WEBUI-TERV.md F2, 2026-08-30-i dontes).
_VENDOR_KONYVTARAK = {"ui", "charts"}


def _frontend_forrasok() -> list[Path]:
    """A sajat (nem generalt, nem fuggoseg) frontend-forrasok."""
    if not APP_DIR.exists():
        return []
    talalat = []
    for alkonyvtar in ("app", "components", "lib"):
        gyoker = APP_DIR / alkonyvtar
        if not gyoker.exists():
            continue
        for path in gyoker.rglob("*"):
            if path.suffix not in (".ts", ".tsx") or path.name in _GENERALT:
                continue
            if "node_modules" in path.parts:
                continue
            relativ = path.relative_to(gyoker).parts
            if alkonyvtar == "components" and relativ and relativ[0] in _VENDOR_KONYVTARAK:
                continue
            talalat.append(path)
    return talalat


def _tiltott_szavak() -> set[str]:
    """Az uzleti listak ertekei -- ezek egyike sem allhat a frontend kodjaban.

    A forras mindig a Python: ha oda uj ertek kerul, ez a halmaz magatol no,
    tehat a teszt a JOVOBELI bovitesekre is vedelmet ad.
    """
    szavak = set(report.STATUS_ORDER)
    szavak |= set(report._REPLY_ORDER)
    szavak |= set(APPROVED_CAMPAIGNS)
    szavak |= set(engines.ALL_ENGINES)
    szavak |= {e.campaign for e in engines.ALL_ENGINES.values()}
    # A suppression-okok a DB CHECK constraintjebol jonnek (db.suppression_reasons()),
    # de a teszt nem nyithat DB-kapcsolatot -- ezek a ma ervenyes ertekek.
    szavak |= {"unsubscribe", "negative_reply", "manual_block",
               "competitor", "existing_client", "hard_bounce"}
    # A tul altalanos szavak kihagyva: ezek angol koznevkent is elofordulnak
    # egy komponensben (pl. egy `error` valtozo), tehat hamis riasztast adnanak.
    return {s for s in szavak if s not in ("new", "error", "done", "other")}


def test_a_frontend_nem_drotoz_be_uzleti_listat():
    forrasok = _frontend_forrasok()
    assert forrasok, "nem talalhato frontend forrasfajl -- elmozdult a webui/app?"

    tiltott = _tiltott_szavak()
    talalatok = []
    for path in forrasok:
        szoveg = path.read_text(encoding="utf-8")
        for szo in tiltott:
            # Szo hataron keresunk, hogy a `readyState` ne legyen `ready`.
            #
            # (?<!\.)  -- egy `.field` property-access (pl. `daily.review`)
            # NEM talalat: ez egy MAR TIPUSOS API-valaszon (DailyResponse stb.)
            # olvas mezot, amit a `npm run types` general a Pythonbol -- ha a
            # mezo eltunik/atnevezodik, a `tsc` hibat ad, nem csendes
            # elteres (WEBUI-TERV.md F3, 2026-08-30-i dontes).
            #
            # (?<!status=) -- egy `?status=<kulcs>` navigacios link (pl.
            # "/cegek?status=review") sem talalat: ez EGY ISMERT mezonevre
            # (a DailyResponse sajat `review`/`ready`/... mezojere) mutato
            # fix kereszthivatkozas, nem egy masolt lista -- analog azzal,
            # ahogy a Python `report.ACTIONABLE` dict is "review" ->
            # "./leadgen.sh review" parost tarol (WEBUI-TERV.md F3,
            # 2026-08-30-i dontes).
            if re.search(rf"(?<!\.)(?<!status=)\b{re.escape(szo)}\b", szoveg):
                talalatok.append(f"{path.relative_to(REPO)}: {szo!r}")

    assert not talalatok, (
        "Uzleti ertek van bedrotozva a frontendbe. Ezeket a `GET /api/meta`-bol\n"
        "kell kiolvasni, nem TypeScriptben leirni (WEBUI-TERV.md Invariansok #1):\n  "
        + "\n  ".join(sorted(talalatok))
    )


def test_minden_endpointnak_van_response_modelje():
    """Enelkul a generalt TS-tipus ures, es a frontend kezi tipust kenyszerul irni."""
    router_dir = API_DIR / "routers"
    assert router_dir.exists(), "nincs webui/api/routers konyvtar"

    hianyzik = []
    for path in sorted(router_dir.glob("*.py")):
        fa = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(fa):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dek in node.decorator_list:
                if not isinstance(dek, ast.Call):
                    continue
                # @router.get("/api/...") alaku dekoratorok
                if not (isinstance(dek.func, ast.Attribute) and dek.func.attr == "get"):
                    continue
                if not any(kw.arg == "response_model" for kw in dek.keywords):
                    utvonal = dek.args[0].value if dek.args else "?"
                    hianyzik.append(f"{path.name}: {utvonal}")

    assert not hianyzik, (
        "Ezeknek az endpointoknak nincs `response_model`-juk, tehat az OpenAPI\n"
        "semajuk ures, es a `npm run types` hasznalhatatlan tipust general:\n  "
        + "\n  ".join(hianyzik)
    )


def test_a_frontend_csak_localhostra_mutat():
    """WEBUI-TERV.md Invariansok #5: nincs 0.0.0.0, nincs kitett port."""
    for path in _frontend_forrasok():
        szoveg = path.read_text(encoding="utf-8")
        assert "0.0.0.0" not in szoveg, f"{path.relative_to(REPO)}: 0.0.0.0"
        for url in re.findall(r"https?://[^\"'\s`]+", szoveg):
            assert re.match(r"https?://(127\.0\.0\.1|localhost)(:\d+)?", url), (
                f"{path.relative_to(REPO)}: nem-localhost cim: {url}"
            )
