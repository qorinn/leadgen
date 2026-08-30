# Webes felület — végrehajtási terv (13. szakasz)

> **Ez a dokumentum előre megtervezi az egész felületet**, hogy az
> implementáció közben ne kelljen tervezni. Minden fázis megmondja, mit kell
> megépíteni, milyen mezőkkel, és hogyan kell ellenőrizni.
>
> **Ha megvalósítasz egy fázist:** olvasd el a [WEBUI-PROMPT.md](WEBUI-PROMPT.md)
> sablont, és azt másold be Claude Code-nak.
> **Melyik modellel:** [WEBUI-MODELLEK.md](WEBUI-MODELLEK.md).

---

## Miért van szükség erre a dokumentumra

A rendszer ma parancssorból megy. A cél egy teljes felület: **minden adat
látszik, minden funkció gombbal indul.**

Ha a felületet menet közben terveznénk, két baj történne. Egyrészt funkciók
maradnának ki — 19 parancscsoport és 12 adatbázis-tábla van, ezt fejből nem
lehet lefedni. Másrészt minden fázis újratervezéssel kezdődne, ami sokszoros
token-fogyasztás: a megvalósító modellnek ki kellene találnia a képernyőket,
az API-t és a mezőneveket, ahelyett hogy csak megírná őket.

**Ez a dokumentum ezt a tervezést végzi el egyszer, előre.**

---

## A stack — eldöntve

| Réteg | Választás |
|---|---|
| Frontend | **Next.js** (App Router, TypeScript) |
| Komponensek | **shadcn/ui** |
| Chartok | **Bklit UI** (`@bklit/*`) — a shadcn/ui-ra épül, ugyanazzal a `shadcn add` paranccsal telepszik |
| Csomagkezelő | **npm** (a pnpm nincs telepítve a gépen) |
| API | **FastAPI + uvicorn**, a `leadgen` venv-jében (Python 3.12) |
| Indítás | `./leadgen.sh ui` — egy parancs indítja mindkét folyamatot |
| Elérhetőség | **csak `localhost`** |

```
leadgen/ (Python 3.12)  ──►  webui/api (FastAPI)  ──►  webui/app (Next.js)
   AZ ÜZLETI LOGIKA            csak átad                    a felület
```

---

## Invariánsok — ezeket egyik fázis sem törheti el

1. **Az üzleti logika Pythonban marad.** A `contract.APPROVED_CAMPAIGNS`, a
   domain lock, a suppression-okok, a `status` átmenetek és a grounding
   szabályai **soha nem másolódnak TypeScriptbe.** A frontend a
   `GET /api/meta`-ból tudja meg, mi engedélyezett — nem magától.
   *Miért:* két igazság keletkezne ugyanarra a szabályra, és a felület
   csendben mást mutatna, mint amit a rendszer csinál.
2. **A `--live` küldés csak kétlépcsősen indulhat**, és ezt a **szerver**
   kényszeríti ki, nem a gomb.
3. **Nincs megnyitás-követés.** A felület nem mutathat „megnyitási arányt" —
   nincs tracking, és nem is lesz (a küldő invariánsa).
4. **Titok soha nem megy ki API-n.** SMTP-jelszó, `DATABASE_URL`, API-kulcsok
   csak maszkolva (`sk-...abcd`) jelenhetnek meg.
5. **Csak `localhost`.** A DB valódi cég- és személyes adatot tárol (GDPR).
   Nincs kitett port, nincs `0.0.0.0`.
6. **A küldő moduljait csak `subprocess`-en át** szabad hívni. Másik
   interpreteren futnak (rendszer `python3` 3.9.6), lapos importokkal — a venv
   Pythonjából nem importálhatók. Minta: `leadgen/report.py` `_sender_state()`.
7. **A frontend soha nem ír SQL-t**, és nem hív adatbázist közvetlenül.
   Minden írás POST, és a meglévő `leadgen` függvényeket hívja.
8. **Magyar felület, angol azonosítók.** A feliratok ékezetesek; a
   változónevek, API-mezők és fájlnevek angolok — a repó konvenciója szerint
   (`CLAUDE.md`).
9. **A `dev seed` nem kerül fel a felületre.** Teszt-cégeket szúrna az ÉLES
   adatbázisba; ennek nem való gomb.

---

## Könyvtárszerkezet

```
webui/
  api/
    main.py              FastAPI app, router-ek beillesztése
    jobs.py              futtatás-kezelő (egyszerre EGY futás, SSE)
    schemas.py           Pydantic válasz-modellek
    routers/
      health.py  meta.py  report.py  companies.py  review.py
      financials.py  jobs.py  send.py  replies.py  alerts.py
      costs.py  schedule.py  logs.py  settings.py
  app/                   Next.js gyökér
    app/
      page.tsx                  irányítópult
      cegek/page.tsx            cégek listája
      cegek/[id]/page.tsx       cég részletei
      valaszok/page.tsx
      riasztasok/page.tsx
      futtatas/page.tsx
      kuldes/page.tsx
      riportok/page.tsx
      beallitasok/page.tsx
    components/ui/       shadcn komponensek
    components/          saját közös komponensek
    lib/api.ts           fetch-réteg + generált típusok
```

---

# F0 — Alapozás

**Cél:** fusson a két folyamat, és lássuk, hogy él a kapcsolat.

### Fájlok
- `requirements.txt` — új: `fastapi==0.115.*`, `uvicorn[standard]==0.32.*`
- `webui/api/main.py`, `webui/api/routers/health.py`
- `webui/app/` — `npx create-next-app@latest` (TypeScript, Tailwind, App Router,
  `src/` nélkül), majd `npx shadcn@latest init`
- `leadgen.sh` — új `ui` parancs
- `.gitignore` — `webui/app/node_modules/`, `webui/app/.next/`

### `GET /api/health`
```json
{ "db": {"ok": true, "tablak": 12},
  "sender_dir": {"ok": true, "ut": "..."},
  "migraciok": {"alkalmazott": 13, "utolso": "013_rejects.sql"},
  "verzio": "0.1.0" }
```
A `db.check()` és a `db.migrate` naplótáblája már megvan — **ezeket hívd, ne
írj új lekérdezést.**

### `./leadgen.sh ui`
Elindítja az uvicorn-t (8000) és a Next.js-t (3000), megnyitja a böngészőt.
Ctrl+C mindkettőt leállítja. **Csak `127.0.0.1`-re kötve.**

### Ellenőrzés
```bash
./leadgen.sh ui          # böngésző megnyílik
curl -s localhost:8000/api/health | head
```
**Kész, ha:** a kezdőlap zöld állapotjelzőt mutat (DB, küldő könyvtár,
migrációk), és a `curl` valós számokat ad.

---

# F1 — Olvasó API és a `/api/meta` kontraktus

**Ez a legfontosabb fázis.** Minden későbbi erre épül.

### Előfeltétel: a `report.py` refaktor

A `leadgen/report.py` függvényei ma **kiírnak** (`print`), nem adatot adnak
vissza. Az API-nak adat kell.

**Amit tenni kell:** minden riport-függvényt bonts ketté — egy `*_adat()`
függvény, ami dict-et ad vissza, és a meglévő kiíró függvény, ami **ezt
hívja**. A CLI kimenete nem változhat.

*Miért így:* ha az API külön lekérdezéseket írna, két igazság lenne ugyanarra
a számra — pontosan az a hiba, amit a `_sender_state()` elkerül azzal, hogy
megkérdezi a küldőt, nem újraszámolja.

⚠️ A `report.py` `_STATUSES` modul-szintű gyorsítótárat használ. Egy hosszan
futó API-folyamatban ez **beragadna**. A refaktor során ezt kérésenkénti
hatókörre kell vinni.

### `GET /api/meta` — a kontraktus

Ez akadályozza meg, hogy a szabályok átszivárogjanak a frontendbe:

```json
{ "statuszok":      [{"kulcs":"ready","cimke":"kész (exportálható)","sorrend":5}],
  "kampanyok":      [{"kulcs":"agency_partner","jovahagyott":true}],
  "engine_ek":      [{"kulcs":"agency_partner","cimke":"...","aktiv":true}],
  "suppression_okok":["unsubscribe","hard_bounce","competitor","..."],
  "valasz_osztalyok":[{"kulcs":"interested","cimke":"ÉRDEKLŐDIK — válaszolj neki"}],
  "cimkek":         ["contact_missing","domain_missing","..."],
  "kuszobok":       {"revenue_medium":100000000,"bounce_alert":0.04,"...":0} }
```

Forrás: `report.STATUS_ORDER` / `STATUS_LABEL`, `contract.APPROVED_CAMPAIGNS`,
`engines.ALL_ENGINES`, `report._REPLY_LABEL`, `config.*` küszöbök.
**Egyiket se írd újra — importáld.**

### További GET-ek

| Útvonal | Tartalom |
|---|---|
| `/api/report/daily` | keret, kiküldve, maradék, bounce, reject, sorbanállás, „hány napra elég", rád vár |
| `/api/report/funnel` | státusz-számlálók, kapcsolatok, suppression, címkék, outreach |
| `/api/companies` | szűrés: `status`, `campaign`, `engine`, `economic_value`, `label`, `q` (név/domain); rendezés: `signal_score`, `company_name`, `updated_at`; lapozás: `page`, `per_page` (alap 50) |
| `/api/companies/{id}` | **minden**: cég + `sources` (raw_signal) + `contacts` + `opportunity_angles` + `company_labels` + `outreach` + `suppression` |
| `/api/replies` | `reply_events`, szűrés osztályra |
| `/api/alerts` | aktív és lezárt |
| `/api/costs` | `llm_usage.csv` modellenként + `source_runs` |
| `/api/runs` | `source_runs` előzmények |
| `/api/schedule/status` | `schedule.allapot()` adatai |
| `/api/logs/{nev}` | `sender`, `alerts`, `daily` — utolsó N sor |

**Lapozás kötelező** a `/api/companies`-on: ma 100 cég van, de ez nőni fog.

### TypeScript típusok
`npm run types` — az OpenAPI sémából generál (`openapi-typescript`).
**A frontend soha nem definiál kézzel API-típust.**

### Ellenőrzés
```bash
.venv/bin/pytest                                    # 376 teszt zöld marad
.venv/bin/python -m leadgen.cli report --daily      # a CLI kimenete VÁLTOZATLAN
curl -s localhost:8000/api/meta | python3 -m json.tool | head -30
curl -s "localhost:8000/api/companies?status=ready&per_page=5"
```
**Kész, ha:** a CLI kimenete bitre ugyanaz, mint a refaktor előtt, és minden
endpoint valós adatot ad.

---

# F2 — Váz, navigáció, közös komponensek

**Cél:** meglegyen minden újrahasznált elem, amire a többi fázis épül.

### Navigáció (bal oldali sáv)
Irányítópult · Cégek · Válaszok · Riasztások · Futtatás · Küldés · Riportok ·
Beállítások

### Közös komponensek
| Komponens | Mit tud |
|---|---|
| `AdatTabla` | szerver-oldali szűrés, rendezés, lapozás; oszlopválasztó |
| `StatusBadge` | **a `/api/meta`-ból** veszi a címkét és a színt — soha nem bedrótozva |
| `UresAllapot` | „Nincs átnézendő cég" + a következő lépés parancsa |
| `HibaAllapot` | a hiba szövege + „Újra" gomb |
| `Betoltes` | skeleton, nem pörgő ikon |
| `KoltsegJelveny` | „~$0,22" — fizetős műveletek mellé |
| `MegerositoDialog` | veszélyes műveletekhez, a következmény kiírásával |
| `JsonNezo` | összecsukható JSON (a `raw_signal`-hoz) |

### Téma
Világos/sötét, rendszerkövetéssel. shadcn alapértelmezett paletta.

### Ellenőrzés
Minden útvonal megnyílik (üres tartalommal is), a téma vált, és egy Bklit
chart megjelenik teszt-adattal.

---

# F3 — Irányítópult

**Cél:** a napi rutin első képernyője. Ez váltja ki a `report --daily`-t.

### Felülről lefelé
1. **Riasztás-sáv** — ha van aktív riasztás, ez van legfelül, kiemelve.
   Típusonként eltérő hangsúly; a megválaszolatlan érdeklődő a legerősebb.
   Üres állapotban **nem** foglal helyet.
2. **Ma** — napi keret · ma kiküldve · még kiküldhető · `leads.csv` sorai ·
   bounce · SMTP-elutasítás. *A bounce és a reject **csak akkor jelenik meg,
   ha nem nulla** — egy állandó „0" három nap alatt láthatatlanná válik.*
3. **Sorbanállás** — sorban áll / kész, még nincs exportálva / „~N napra elég".
   5 nap fölött figyelmeztetés az adagolásra (`export --limit`).
4. **Rád vár** — válaszolt cégek, átnézendők; kattintásra a megfelelő oldalra.
5. **Gyorsgombok** — napi lánc, export, feedback, küldés-előnézet.
   **F6-ig letiltva**, „hamarosan" jelöléssel.

### Ellenőrzés
Az oldal számai **egyezzenek** a `./leadgen.sh report --daily` kimenetével.
Ha eltérnek, az API vagy a refaktor hibás.

---

# F4 — Cégek: lista és részletnézet

**Cél:** minden cégadat látható legyen. Ez a legnagyobb adatfelület.

### Lista
Szűrők: státusz · kampány · engine · gazdasági érték · címke · szabadszavas
keresés (név, domain). Rendezés: pontszám, név, frissítés. Lapozás.
Alap oszlopok: név · domain · státusz · kampány · pontszám · gazdasági érték ·
email · frissítve.

### Részletnézet — minden adat, szekciókban

| Szekció | Mezők |
|---|---|
| Fejléc | név, domain (kattintható), státusz, kampány, pontszám, `status_note` |
| **A levélbe menő mondat** | `personalization` + `personalization_quote` |
| **AI-szögek** | `opportunity_angles`: típus, pontszám, `pain`, `claim`, **`quote` szó szerint**, `selected` jelölés, modell |
| Kapcsolatok | email, típus, `local_check`, `verify_result`, `bounce_state`, **`send_reject_count` + `send_error`**, forrás-URL |
| Pénzügy | `revenue` (Ft), `headcount`, `balance_total`, `profit`, `financial_year`, `financial_source`, `economic_value`, `financial_bonus` |
| Fejlesztő (8.2) | `dev_name`, `dev_domain`, `dev_state`, **`dev_evidence` szó szerint** |
| Webshop (8.3) | `webshop_platform`, **`webshop_evidence`** |
| Címkék | `company_labels` + `details` JSON |
| Outreach | idővonal: `queued_at` → `sent_at` → `replied_at`, `stage`, `sender_account` |
| Suppression | ha van: ok, megjegyzés, dátum |
| **Nyers források** | `sources`: típus, URL, `detected_at`, és a **`raw_signal` teljes JSON** összecsukva |

**A szó szerinti idézetek kiemelten jelenjenek meg.** Ezek az emberi átnézés
tárgyai: a `dev_evidence` és a `webshop_evidence` a levélbe kerülő állítás
bizonyítéka, és ha téves, az kínos. Ne rövidítsd le őket.

### Ellenőrzés
Nyiss meg egy `ready` céget és egy `suppressed` céget. Vesd össze:
```bash
.venv/bin/python -m leadgen.cli report --grounding
```
Minden mező, ami a DB-ben nem `null`, jelenjen meg valahol az oldalon.

---

# F5 — Emberi döntések (az első írási műveletek)

**Cél:** az írási minta rögzítése + a három emberi folyamat.

### Az írási minta (ezt követi minden későbbi fázis)
- Minden írás **POST**, és a meglévő `leadgen` függvényt hívja.
- **Nincs optimista frissítés** — írás után újratöltés, hogy a szerver
  igazsága látszódjon.
- Minden visszafordíthatatlan művelet előtt `MegerositoDialog`, ami **kiírja a
  következményt** („a cég tiltólistára kerül, és a következő export kiveszi a
  `leads.csv`-ből").

### 1. Review
`POST /api/review/{id}/approve` · `POST /api/review/{id}/reject {reason}` ·
`GET /api/review/suppressed` (automatikusan kizárt versenytársak,
felülbírálhatók).

A `reject` okai a `/api/meta`-ból jönnek (`manual_block`, `competitor`,
`existing_client`, `negative_reply`, `unsubscribe`) — **nem bedrótozva**.

⚠️ A `reject` **már exportált (`queued`) leadre is működik**, és lezárja az
outreach sort. A megerősítő szövegnek ezt ki kell mondania.

### 2. Pénzügyi adat kézi bevitele
A portál lekérdezése jogi okból tiltott (`financials.py`), ezért ez
szándékosan kézi:
- `GET /api/financials/worklist` — a kitöltendő CSV letöltése
- `POST /api/financials/import` — a kitöltött CSV **feltöltése** (előbb
  `--dry` nézet: mit írna be)
- `POST /api/companies/{id}/financials` — cégenkénti űrlap

**Az űrlap forintban kér értéket**, és 1 M Ft alatt hangosan figyelmeztet: a
beszámoló „adatok E Ft-ban" formában mutat, és ez a leggyakoribb hiba.
Külön kapcsoló: „nincs közzétett beszámoló".

### 3. Kampány-jóváhagyás — csak megjelenítés
Látszik, melyik kampány vázlat még. **A felület nem írhatja az
`APPROVED_CAMPAIGNS`-t** — az a `contract.py`-ban marad, mert emberi
szövegátírás előzi meg. A felület a lépéseket írja ki.

### Ellenőrzés
```bash
# egy teszt-domainen, majd vissza:
.venv/bin/python -m leadgen.cli review --reject <domain> --reason manual_block
.venv/bin/python -m leadgen.cli review --approve <domain>
```
A felületről végzett művelet **ugyanazt az adatbázis-állapotot** eredményezze,
mint a CLI.

---

# F6 — Futtatások és élő napló

**Cél:** minden parancs indítható, és látszik, mit csinál.

### Job-kezelő (`webui/api/jobs.py`)
- **Egyszerre EGY futás.** *Miért:* két `daily` egymásra futna, és a
  `store` CSV-fájljaiért versenyeznének. A `flock` véd a sérüléstől, de a
  kettős feldolgozástól nem. Ha fut valami, a második indítás **elutasítva**,
  a futó job megjelölésével.
- **SSE-stream** soronként. Erre már van alap: a `schedule._futtat()`
  `PYTHONUNBUFFERED`-del indít, tehát van mit streamelni.
- **Megszakítás** — a folyamat leállítása.
- **Előzmények** — mikor, mi, meddig futott, mi lett a kilépési kód.

### Indítható parancsok (katalógus a `/api/jobs/catalog`-ból)
| Parancs | Fizetős? | Becslés |
|---|---|---|
| `daily` (teljes lánc) | 💰 igen (ingest) | ~$0,22 |
| `daily --skip-ingest` | nem | — |
| `enrich`, `qualify`, `feedback`, `export`, `alert`, `webshop-growth` | nem | — |
| `enrich dead-dev` | nem | — |
| `score` | 💰 AI | tokenenként |
| `classify-replies` | 💰 AI | tokenenként |
| `ingest maps`, `ingest ops-pain` | 💰 Apify | ~$0,005/találat |
| `resolve-domains` | 💰 Apify | ~$0,005/cég |

**Fizetős parancs csak megerősítés után indul**, és a párbeszéd **kiírja a
becsült költséget** és a keretet (`--max-results`, `--limit`). A becslés
forrása a `leadgen/pricing.py`, illetve az Apify egységár — **ne találj ki
számot**; ha ismeretlen, írd ki, hogy ismeretlen.

⚠️ **A `sender.py --live` NEM szerepel ebben a katalógusban.** A küldés az
F7 külön útján megy, kétlépcsős megerősítéssel.

### Naplók
`sender.log` · `alerts.log` · `leadgen_daily.log` — megtekintés, követés,
szűrés.

### Ellenőrzés
```bash
# a felületről indítsd:  daily --skip-ingest
# közben a naplónak FOLYAMATOSAN kell frissülnie, nem a végén egyben
```
**Kész, ha:** a kimenet menet közben látszik, a második indítás elutasításra
kerül, és a megszakítás valóban leállítja a folyamatot.

---

# F7 — Küldés (kétlépcsős) — a legkockázatosabb fázis

**Cél:** a kiküldés a felületről is indítható legyen, de az emberi kapu
maradjon meg.

### `POST /api/send/preview`
A **teljes renderelt levelek** — nem az első 400 karakter. Mintája a
`cold-email-starter/preview.py`, ami már pontosan ezt csinálja.
**Subprocess a rendszer `python3`-mal** (3.9.6), a `SENDER_DIR`-ből.

Válasz:
```json
{ "token": "<a terv hash-e>",
  "lejar": "2026-08-29T10:15:00",
  "levelek": [{"cimzett":"...","ceg":"...","fok":"cold",
               "targy":"...","torzs":"a TELJES szöveg"}],
  "mai_keret": 20, "terv_meret": 10 }
```

### `POST /api/send/live`
**Csak érvényes tokennel indul.** A token a terv tartalmi hash-e (címzettek +
fokok + tárgyak). Ha a terv közben megváltozott — mert lefutott egy export,
vagy valaki elutasított egy leadet —, a hash **nem egyezik**, a szerver
elutasítja, és új előnézetet kér.

**Ezt a szerver kényszeríti ki, nem a gomb.** *Miért:* egy gomb letiltása
frontend-állapot; egy elgépelt `fetch`, egy visszafelé-gomb vagy egy
újratöltés megkerülheti. A kiküldés visszafordíthatatlan, tehát a védelemnek
a szerveren kell lennie.

További szabályok:
- a token **rövid életű** (10 perc) és **egyszer használatos**;
- a `--live` a job-kezelőn megy, élő kimenettel;
- a felületen a küldés előtt látszik: mai keret, terv mérete, és hogy a
  guards le fog futni.

### Mintalevél magadnak
A `preview.py --send-to` megfelelője: minta a saját címedre. **Nem ír a
`sent.csv`-be**, tehát a valódi lead szekvenciája érintetlen marad.

### Ellenőrzés
```bash
# 1. előnézet a felületen -> hasonlítsd össze:
cd cold-email-starter && python3 sender.py --dry
# 2. próbáld meg a /send/live-ot ÉRVÉNYTELEN tokennel -> 409 Conflict
# 3. kérj előnézetet, majd futtass egy exportot, majd küldj -> ELUTASÍTVA
```
**Kész, ha:** a 2. és 3. eset is elutasításra kerül, és az előnézet szövege
karakterre egyezik a `sender.py --dry` kimenetével.

---

# F8 — Válaszok és riasztások

### Válaszok (`reply_events`)
Lista: cég · cím · tárgy · besorolás · **bizonyosság** · modell · dátum.
Részletek: a **teljes szöveg** és az AI **indoklása** (`rationale`).

Kiemelve:
- **`interested`** — 24 órás óra, meddig van hátra a válaszra;
- **`other`** — bizonytalan, emberi átnézést kér;
- az `error` mezős sorok külön (az osztályozás hibára futott).

*A `not_now` és az `auto_reply` **nem** suppression, hanem cooldown (90 / 14
nap) — a felület ezt írja ki, ne keltse azt a látszatot, hogy a cég kiesett.*

### Riasztások (`alerts`)
Aktív és lezárt. Mezők: típus, üzenet, `first_seen` („3 napja tart"),
`last_notified`, `resolved_at`. Az `alerts.log` is megnézhető.

### Ellenőrzés
```bash
.venv/bin/python -m leadgen.cli report --replies
.venv/bin/python -m leadgen.cli alert --dry --skip-deliverability
```
A felület ugyanazokat a sorokat mutassa.

---

# F9 — Riportok és chartok

### Nézetek
| Nézet | Tartalom | Chart |
|---|---|---|
| Tölcsér | státuszok életciklus-sorrendben | oszlop (Bklit) |
| **Grounding** | a levélbe menő mondat **és a forrásidézet egymás mellett** | — |
| Gazdasági érték | LOW/MEDIUM/HIGH, árbevétel-lista | oszlop |
| Kampány | cégek kampányonként, jóváhagyási állapottal | — |
| **Költségek** | `llm_usage.csv` modellenként + `source_runs` (Apify) | vonal (napi) |

### Költségek — fontos részlet
A tokenszámot **mi** számoljuk (`pricing.py`), mert a szolgáltatók
dashboardja lassan frissül és összevonja a modelleket. Ismeretlen modellnél a
tokenszám pontos, de az ár helyén **„ISMERETLEN ÁR"** áll — a felület ezt így
is írja ki. **Soha ne találj ki árat.**

### Mérőeszközök — csak olvashatóan
A bake-off (`eval`) és az `llm-check` **eredménye** megjelenik, de **gomb
nélkül** (felhasználói döntés). Ha még nem futott, írd ki, melyik paranccsal
indítható terminálból.

### Nyers naplók
`sent.csv`, `do-not-contact.csv`, `bounces.csv`, `rejects.csv`, `replies.csv`
— táblázatos nézet. Az értelmezett adat a DB-ből jön; ez a nyers ellenőrzés.

---

# F10 — Ütemezés és beállítások

### Ütemezés
`schedule status` adatai: telepítve van-e, betöltve van-e, mikor futott
utoljára, mi volt a kilépési kód. Gombok: telepítés / eltávolítás.
A `leadgen_daily.log` utolsó sorai.

### Beállítások — **maszkolva**
A `.env` értékei úgy, hogy **a titkok soha ne menjenek ki**:
- ami titok (`DATABASE_URL`, API-kulcsok, SMTP-jelszó): csak `be van állítva` /
  `HIÁNYZIK`, esetleg utolsó 4 karakter;
- ami nem titok (küszöbök, modellnevek, `EMAIL_VALIDATION`, `ALERT_EMAIL`):
  teljes érték.

**A felület nem írja a `.env`-et.** Kézi szerkesztés marad — egy elrontott
`DATABASE_URL` az egész rendszert megállítaná.

### Diagnosztika (olvasható)
Engine-ek (`engines.ALL_ENGINES`, aktív/kikapcsolt) · jóváhagyott kampányok ·
migrációk (`schema_migrations`) · `feedback_watermark` állása.

---

# F11 — Lezárás

### Teendők
1. **Hibaállapotok végigvitele** — minden oldal viselkedjen értelmesen, ha az
   API nem elérhető, ha üres az adat, és ha lassú a válasz.
2. **API-szerződés tesztek** (`tests/test_webui.py`):
   - a `/api/meta` tartalmazza a `contract.APPROVED_CAMPAIGNS` **aktuális**
     tartalmát (ne legyen bedrótozott másolat);
   - a `/api/send/live` **érvénytelen tokennel elutasít**;
   - egyetlen API-válasz sem tartalmaz titkot (kulcs, jelszó, `DATABASE_URL`);
   - a job-katalógusban **nincs** `--live`.
3. **Dokumentáció**: `HOGYAN-HASZNALD.md` új „17. folyamat — A felület",
   `PARANCSOK.md` (`ui` parancs), `CLAUDE.md` (a `webui/` réteg leírása),
   `INTEGRATION-PLAN.md` 13. szakasz → kész.
4. **Teljes végigjátszás**: napi lánc → átnézés → export → küldés-előnézet,
   végig a felületen.

---

## Lefedettség — 19/19 parancscsoport, 12/12 tábla

*Ellenőrizve a tényleges `--help` kimenetből és a DB sémából (2026-08-29).*

| Parancscsoport | Hol |
|---|---|
| `report`, `alert` | F3, F8, F9 |
| `daily`, `export`, `feedback`, `enrich`, `score`, `qualify`, `webshop-growth` | F6 |
| `ingest`, `resolve-domains` | F6 — fizetős, megerősítéssel |
| `review` | F5 |
| `enrich financials` | F5 (worklist, import, űrlap) |
| `classify-replies` | F6 (futtatás) + F8 (eredmény) |
| `schedule`, `engines`, `db` | F10 |
| `eval`, `llm-check` | F9 — csak eredmény, gomb nélkül |
| `dev` | **szándékosan kimarad** (teszt-adat az éles DB-be) |

| Tábla | Hol |
|---|---|
| `companies`, `sources`, `contacts`, `company_labels`, `opportunity_angles`, `outreach` | F4 |
| `suppression` | F4 + F5 |
| `reply_events`, `alerts` | F8 |
| `source_runs` | F9 |
| `schema_migrations`, `feedback_watermark` | F10 |

Fájlok: `leads.csv` → F7 · `llm_usage.csv` → F9 · `financials_worklist.csv` →
F5 · naplók → F6 · küldő CSV-k → F9.
