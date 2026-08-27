# Parancsok — mit tud a rendszer

> Minden parancs a **repó gyökeréből** futtatandó:
> `/Users/paladibalint/Developer/seo-checker/scraper/scraper`
>
> A `./leadgen.sh` bárhonnan működik — megkeresi a venv-et és a gyökeret.

---

## A napi rutin (ez a rövid válasz)

```bash
./leadgen.sh report                   # ← hol tartunk, mi vár rám
./leadgen.sh review                   # ← TE döntesz (ha van átnézendő)
./leadgen.sh export                   # átadás a küldőnek (feedback-et is futtat)

cd cold-email-starter
python3 sender.py --dry               # ← MI MEGY KI MA? (utolsó ellenőrzés)
python3 sender.py --live              # ← éles küldés

# este, a küldési ablak (17:00) után:
python3 deliverability.py             # napi jelentés + a holnapi keret
cd .. && ./leadgen.sh feedback        # a nap eredménye vissza a DB-be
```

**Új cégek gyűjtése** nem napi feladat — akkor futtasd, ha a `report` azt
mutatja, hogy fogy a sor:

```bash
./leadgen.sh ingest maps --engine agency_partner --max-results 100
./leadgen.sh enrich
./leadgen.sh qualify
```

---

# 1. SCRAPER — `./leadgen.sh ...`

## Leadek gyűjtése

| Parancs | Mit csinál |
|---|---|
| `ingest maps --engine agency_partner` | Google Maps → új cégek a DB-be |
| `ingest maps --max-results 100` | **költség-korlát** (~$0.005/találat) |
| `ingest maps --dry` | megmutatja, mit keresne — **nem költ** |
| `ingest maps --force` | a már lefuttatott lekérdezéseket is újra futtatja |
| `ingest maps --refresh-days 60` | ennyi napnál régebbi lekérdezés futhat újra (0 = soha) |

> **Az `ingest` folytatólagos.** Megjegyzi, melyik (kifejezés + település) párost
> futtatta már le, és legközelebb a következővel folytatja. Ha a `--max-results`
> keret elfogy, egyszerűen futtasd le újra ugyanazt a parancsot — onnan folytatja.
> Így soha nem fizetsz kétszer ugyanazokért a cégekért.
| `enrich` | letölti a weboldalakat (`new` → `enriched`) |
| `enrich --limit 10` | csak ennyit dolgoz fel egy futásban |
| `qualify` | minősít (`enriched` → `ready` / `review` / `suppressed`) |

## Emberi döntés

| Parancs | Mit csinál |
|---|---|
| `review` | kilistázza a bizonytalan cégeket, domainnel és indokkal |
| `review --approve bda.hu` | jó lead → `ready` |
| `review --reject amarketingese.hu` | ne keressük meg → `suppressed` |
| `review --reject mito.group --reason competitor` | ugyanaz, megadott okkal |
| `review --suppressed` | **amit a gép automatikusan kizárt** — indoklással |
| `review --approve <domain>` | visszahozza az automatikusan kizártat is |

> Az `--approve` `review`, `suppressed` és `rejected` állapotból is visszahoz.
> Így a rendszer automatikus döntései **nem véglegesek** — bármikor felülbírálhatod.

> A `--reject` **már exportált (`queued`) és megkeresett (`sent`) leadre is
> működik.** Ez az 5. szakasz óta fontos: az utolsó visszafordítható pont a
> `sender.py --dry` kimenete, és amit ott meglátsz, azt innen tudod kihúzni.
> A parancs lezárja a folyamatban lévő outreach sort is, a `leads.csv`-ből
> pedig a következő `export` veszi ki. `sent` állapotú leadnél ez a még
> hátralévő follow-upokat állítja le.
>
> A `--reason` értékei: `manual_block` (alapértelmezés), `competitor`,
> `existing_client`, `negative_reply`, `unsubscribe`.

## Átadás és visszacsatolás

| Parancs | Mit csinál |
|---|---|
| `export --dry` | megmutatja, mi menne a `leads.csv`-be — **nem ír** |
| `export` | kiírja a `leads.csv`-t (domain lock + suppression + cooldown) |
| `export --limit 20` | egyszerre csak ennyi ÚJ leadet ad ki (adagolás) |
| `feedback` | a küldő eredménye (küldés, válasz, bounce) → DB |

> Az `export` **mindig lefuttatja a `feedback`-et először**. Ha az hibára fut,
> az export megáll, és a `leads.csv` érintetlen marad.

## Modell-összehasonlítás

| Parancs | Mit mér |
|---|---|
| `eval sentences --limit 9 --model A --model B` | **a magyar mondatok minősége — VAKON** |
| `eval bakeoff --model A --model B` | a hirdetés-minősítés pontossága (30 teszteset kell) |
| `eval robustness --model A` | átverhető-e (prompt injection) |

> **Az `eval sentences` vakon dolgozik:** minden mondatnál más sorrendben
> keveri a modelleket, és a megfejtés a fájl végén, lenyitható blokkban van.
> Ha látnád, melyiket melyik írta, a drágábbtól önkéntelenül jobbat várnál.
>
> A terv szerint érdemes **másnap** elolvasni. A kritérium egyetlen kérdés:
> **kiküldenéd a saját neveddel?**

> Kiírja a **skálázott költséget** is: mit jelentene napi 333 új leadnél
> (= napi ~1000 levél, mert egy lead 3 levelet kap).

## Költségmérés — token- és árszámolás

| Parancs | Mit csinál |
|---|---|
| `llm-check --dry` | **becsült** költség — nem hív API-t |
| `llm-check` | éles teszt: működik-e a kulcs + mennyibe került |
| `llm-check --model gpt-5.6-luna --model claude-sonnet-5` | több modell egymás mellett |
| `llm-check --repeat 5` | ennyi hívás modellenként (pontosabb átlag) |
| `llm-check --budget 2.00` | költségfék USD-ben — e felett **el sem indul** |
| `llm-check --summary` | az eddigi összes mérés, modellenként |

> **Miért számolunk mi:** a szolgáltatók dashboardja lassan frissül és
> **összevonja a modelleket** — egy összehasonlítás ettől értelmetlen lenne.
> Minden hívás tokenjeit külön vezetjük: `data/llm_usage.csv`.

> A `score` és a `classify-replies` is kiírja a saját futása token- és
> költségbontását, modellenként.

> ⚠️ Ez **számítás, nem számla.** Az árak a `leadgen/pricing.py` táblájából
> jönnek, forrással és dátummal. Ismeretlen árú modellnél a tokenszám pontos,
> az ár helyén „ISMERETLEN AR" áll — nem talál ki számot.

## AI-szolgáltató váltása

Egyetlen sor a gyökér `.env`-ben — a **provider a modellnévből** derül ki:

```
LLM_BULK_MODEL=gpt-5.6-luna            # gpt-*/o1/o3/o4 → OpenAI
LLM_QUALITY_MODEL=claude-haiku-4-5     # claude-*       → Anthropic
                                       # gemini*        → Google
```

> Mindhárom integráció megvan és megmarad. A Geminire visszatérni ennyi:
> `LLM_BULK_MODEL=gemini-2.5-flash-lite` + `GEMINI_API_KEY=...`

> Kulcshiánynál a program megmondja, **melyik** kulcs kell — a modellnévből
> vezeti le, nem bedrótozva.

## AI-minősítés + evidence grounding (10. szakasz)

| Parancs | Mit csinál |
|---|---|
| `score --dry` | megmutatja a minősítést — **semmit nem ír** |
| `score --limit 20` | élesben, batch-elve |
| `report --grounding` | mit állított az AI, és milyen idézetből |

> **Bizonyíték-szabály:** minden AI-állításhoz szó szerinti idézet kell a
> forrásszövegből. Ami nem található meg, azt a rendszer eldobja. Ha nem marad
> alátámasztott állítás, a lead `rejected`. Ez **ingyen** van — nem AI-hívás.

> **Ha a grounding-bukás 20% felett van**, a modell hallucinál → bake-off,
> másik modell.

> **Offer arbitration:** egy cég egy kampányba kerül. A legerősebb ajánlat nyer.

> 🔒 **Vázlat sablonnal nem megy ki levél.** Az `APPROVED_CAMPAIGNS`
> ([leadgen/contract.py](leadgen/contract.py)) a kapu — csak az ott felsorolt
> kampányok exportálódnak.

## Álláshirdetés-forrás — Profession.hu (9. szakasz)

| Parancs | Mit csinál |
|---|---|
| `ingest ops-pain --dry` | megmutatja, mit keresne — **nem költ** |
| `ingest ops-pain --max-results 50` | hirdetések letöltése (költségfék) |
| `ingest ops-pain --location Budapest` | csak erre a településre |
| `resolve-domains --limit 20` | **FIZETŐS**: a beragadt cégek domainje Maps-ből |
| `resolve-domains --dry` | megmutatja, kiket kérdezne le |

| `ingest ops-pain --force` | a ma már lefuttatott kereséseket is újra futtatja |
| `ingest ops-pain --refresh-days 0` | soha ne hagyjon ki keresést |

> **Két szinten véd az ismétlődés ellen, és a kettő más:**
>
> | Szint | Mit véd | Mit spórol |
> |---|---|---|
> | **hirdetés** (`sources`) | ugyanaz a hirdetés nem kerül be kétszer | nincs duplikált cég, nem fut le kétszer a drága feldolgozás |
> | **keresés** (`source_runs`) | ugyanaz a keresés nem fut le újra aznap | **az Apify-lekérdezés árát** |
>
> A második nélkül a napon belül megismételt futás újra kifizetné a keresést,
> hiába nem hozna egyetlen új hirdetést sem. Mérve: `$0.01` egy olyan futásért,
> ami 0 új hirdetést hozott. Alapértelmezés: naponta egyszer futhat le egy
> keresés — álláshirdetés naponta jelenik meg új.

> **Miért külön a `resolve-domains`:** az ingest a HIRDETÉSEKBŐL indul, és a
> már látottakat kiejti — a korábban beragadt cégeket tehát nem érné utol.
> Ez a parancs a CÉGEKBŐL indul.

> A Profession.hu **nem adja meg a cég weboldalát** (mérve: 12 hirdetésből 0).
> A feloldás ~$0,005/cég, mért találati arány 4/3.

## Halott fejlesztő — 8.2 (8. szakasz)

| Parancs | Mit csinál |
|---|---|
| `enrich dead-dev --dry` | megmutatja a találatokat — **nem ír** |
| `enrich dead-dev` | élesben: pontozás + versenytárs-suppression |
| `enrich dead-dev --all` | a már megvizsgáltakat is újra nézi |
| `report --signal dead_dev` | DEAD / DORMANT / ALIVE bontás + a footer szövege |

> **A DEAD találatokat ember nézze át.** A fejlesztő neve szó szerint bekerül
> a levélbe — ha téves, az kínos. A riport ezért kiírja a footer eredeti
> szövegét is.

> Nem kell hozzá új scrapelés: a footer már benne van a letöltött HTML-ben.

## Árbevétel és létszám — 7.1 (11. szakasz)

**A portált NEM kérdezzük le géppel** (captcha + a Felhasználási Feltételek
hitelezővédelmi célt írnak elő). Kézi vagy importált adat.

| Parancs | Mit csinál |
|---|---|
| `enrich financials --limit 20` | listát ír `data/financials_worklist.csv`-be, kitöltésre |
| `enrich financials --import FAJL` | a kitöltött lista (vagy csoportos beszámoló-export) beolvasása |
| `enrich financials --import FAJL --dry` | csak megmutatja, mit írna be |
| `enrich financials --set DOMAIN --revenue FT --headcount FO --year EV` | egyetlen cég |
| `enrich financials --set DOMAIN --missing` | nincs közzétett beszámolója |
| `report --economic` | LOW / MEDIUM / HIGH bontás + a számok |

> **FORINTBAN, nem ezer forintban.** A beszámoló űrlapja „adatok E Ft-ban"
> formában mutat. Az importer minden 1 M Ft alatti árbevételre hangosan szól —
> az szinte biztosan elírás.

> **A LOW nem kizárás.** A pénzügyi érték **rangsorol**, nem szűr; a hiányzó
> adat végképp nem állít le semmit.

> **A küszöbök a gyökér `.env`-ben:** `REVENUE_MEDIUM_HUF` (100 M),
> `REVENUE_HIGH_HUF` (500 M), `HEADCOUNT_MEDIUM` (5), `HEADCOUNT_HIGH` (25),
> `WEBSHOP_REVENUE_MIN_HUF` (300 M). Ez üzleti döntés — kalibráld.

> **Ez a lépés opcionális**, és nem kell minden céget lekérni: napi 20 levélnél
> a sor tetején lévő 20-30 cégről elég adat.

> **A tömeges, hivatalos út FIZETŐS:** „Csoportos beszámoló kérő lap" →
> `e-beszamolo@mkifk.hu`, költségtérítéssel (az űrlap számlázási adatot kér).
> A kapott fájl ugyanezzel az `--import`-tal megy be. Kérd bele az **adószámot**
> is — a párosítás `company_id → adószám → domain` sorrendben megy, cégnév
> szerint soha.

## Webshop kinövés — 8.3 (11. szakasz)

| Parancs | Mit csinál |
|---|---|
| `webshop-growth --dry` | megmutatja a találatokat — **nem ír** |
| `webshop-growth` | élesben: platform + metszet az árbevétellel |
| `webshop-growth --all` | a már megvizsgáltakat is újra nézi |
| `report --campaign webshop_growth` | a kampány cégei + a jóváhagyási állapot |

> **A kulcsszó nem elég.** Az `enrich` `tech.platform` mezője a 49 mért oldalon
> **12-ből 12-szer tévedett** (partner-logó, szolgáltatás-szöveg, téma-CSS).
> A 8.3 ezért a betöltött **eszköz hostját** vagy a **plugin-útvonalat** nézi,
> és kosár-linket is kér mellé.

> **Nem írja felül a meglévő kampányt.** Ha a cég már kampányban van, a
> webshop-irány `opportunity_angles` sorként mentődik el.

> **A `webshop_growth` sablon VÁZLAT** — amíg nincs az `APPROVED_CAMPAIGNS`
> listában, ezek a leadek nem exportálódnak.

## Email-ellenőrzés (7. szakasz)

Nincs külön parancsa — **az exportnál automatikusan lefut**. A gyökér `.env`
kapcsolója vezérli:

| Beállítás | Mit csinál |
|---|---|
| `EMAIL_VALIDATION=off` | semmit |
| `EMAIL_VALIDATION=local_only` | ingyenes szűrő: formátum, MX-rekord, eldobható domain |
| `EMAIL_VALIDATION=full` | + Reoon a túlélőkre (fizetős, `REOON_API_KEY` kell) |

```bash
EMAIL_VALIDATION=full ./leadgen.sh export --dry   # egy futásra felülvezérelve
```

> **A cache pénzt véd:** ugyanarra a címre `VERIFY_CACHE_DAYS` (90) napon belül
> nem kérdez rá kétszer. Két egymás utáni `export --dry` közül a másodiknak
> **0 lekérdezést** kell mutatnia. Ha nem így van, állítsd vissza `local_only`-ra.

> **API-hiba nem zár ki senkit.** Minden hiba `unknown`, soha nem `invalid`.

## AI réteg (6. szakasz)

| Parancs | Mit csinál |
|---|---|
| `classify-replies --dry` | megmutatja a besorolást — **semmit nem ír** |
| `classify-replies` | besorol és átvezeti a következményeket |
| `classify-replies --limit 20` | egyszerre csak ennyit |
| `eval bakeoff --model <modell>` | a 30 teszteset végigfuttatása |
| `eval bakeoff --model A --model B` | két modell egymás mellett, egy táblázatban |
| `eval robustness --model <modell>` | támadó bemenetek (üres, hosszú, angol, HTML, **prompt injection**) |
| `report --replies` | a válaszok besorolás szerint + akire lépned kell |

> **A `--dry` itt nem formalitás.** Az `unsubscribe` és a `negative` címke
> véglegesen kizárja a céget. Első futtatáskor és minden prompt-módosítás
> után nézd át szárazon.

> **Bizalmi kapu:** ha a modell `unsubscribe`-ot vagy `negative`-ot javasol
> **0.70 alatti** bizonyossággal, a rendszer `other`-re teszi, és ember dönt.
> A modell eredeti javaslata megmarad a `rationale` mezőben.

> A `bakeoff` tesztkészlet **emberi munka**: [evals/README.md](evals/README.md).
> A 10 határeset kézi címkéje a te üzleti döntésed — a könnyű eseteken minden
> modell jó lesz.

## Automatikus futás és riasztás (12. szakasz)

| Parancs | Mit csinál |
|---|---|
| `schedule install` | a napi lánc **minden reggel 7:30-kor** fut (launchd) |
| `schedule status` | fut-e az ütemezés, és mikor futott utoljára |
| `schedule uninstall` | az ütemezés kikapcsolása |
| `schedule install --dry` | csak megmutatja a telepítendő beállítást |
| `daily` | a **teljes napi lánc** most, kézzel |
| `daily --dry` | mit futtatna? — semmit nem hajt végre |
| `daily --skip-ingest` | a lánc a **fizetős** gyűjtés nélkül |
| `daily --limit 20` | export-adagolás: ennyi új leadnél többet ne állítson sorba |
| `alert` | riasztás-ellenőrzés + értesítés |
| `alert --dry` | csak megmutatja — nem ír és nem küld emailt |
| `alert --skip-deliverability` | a küldő kézbesítési körje nélkül (az IMAP-ot igényel) |

**A lánc SOHA nem küld élesben.** A `sender.py --live` és a
`deliverability.py` szándékosan kimarad belőle — azokat ember indítja.
Tesztsor őrzi, hogy ez így is maradjon.

**Az `alert` és a `deliverability.py` 1-es kilépési kódja jelzés, nem hiba:**
azt jelenti, hogy *van* riasztás. Cronban ezt ne értelmezd programhibának.

## Áttekintés

| Parancs | Mit csinál |
|---|---|
| `report` | **a teljes tölcsér** + a mai kép egyben |
| `report --daily` | csak a mai kép: **riasztások**, napi keret vs. sorbanállás |
| `report --replies` | a válaszok besorolás szerint |
| `engines` | milyen iparágak vannak, melyik aktív |
| `db check` | táblák és sorszámok |
| `db info` | kapcsolódási adatok (jelszó nélkül) |
| `db migrate` | séma frissítése (idempotens) |

## Fejlesztői

| Parancs | Mit csinál |
|---|---|
| `dev seed` | 3 teszt-cég `.invalid` címekkel (nem küldhető ki valódi levél) |
| `dev clear-seed` | teszt-cégek törlése |

---

# 2. KÜLDŐ — `cd cold-email-starter && python3 ...`

## Mielőtt bármit kiküldenél

| Parancs | Mit csinál |
|---|---|
| `python3 preview.py` | **a TELJES levelek**, címzettenként |
| `python3 preview.py --stage follow_up_1` | a 2. levél előnézete |
| `python3 preview.py --limit 3` | csak az első 3 |
| `python3 preview.py --send-to en@cimem.hu --limit 2` | **mintát küld MAGADNAK** |
| `python3 sender.py --dry --skip-guards` | a mai terv, rövidítve |
| `python3 sender.py --dry` | ugyanaz, de a guards is lefut (IMAP kell) |

## Küldés

| Parancs | Mit csinál |
|---|---|
| `python3 sender.py --live` | **ÉLES küldés**, a napi keretig |
| `python3 sender.py --live --limit 5` | csak 5 levél ebben a futásban |

## Figyelés

| Parancs | Mit csinál |
|---|---|
| `python3 guards.py` | válasz / leiratkozás / bounce beolvasás (IMAP) |
| `python3 deliverability.py` | napi jelentés + a holnapi keret |
| `python3 -c "import mailer; mailer.check_accounts()"` | SMTP bejelentkezés-teszt |

---

# 3. Amit érdemes tudni

**A `--dry` mindenhol biztonságos.** Sem a `sender.py`, sem az `export` nem ír
semmit `--dry` mellett. Az éles küldéshez **explicit `--live`** kell.

**A `preview.py --send-to` nem írja a `sent.csv`-t.** Tehát ha magadnak küldesz
mintát, a valódi lead attól még várakozik, és később megkapja a rendes levelét.

**A napi keret a `sent.csv`-ből számol.** Amit a `preview.py --send-to` küld,
az a mi rendszerünkben **nem számít bele** — a Google viszont valódi levélnek
számolja (a Workspace napi limitje ~2000 külső címzett, tehát pár teszt-levél
érdektelen).

**A `report` megmondja, hány napra elég a sor.** Ha ez 5 nap fölé megy,
adagolj (`export --limit 20`): a follow-up **mindig veri** a friss cold-ot
ugyanabban a napi keretben, tehát egy nagy export nem gyorsítja a kiküldést,
csak várakozó sort épít. A napi keret a kézbesítési jelekből emelkedik
(`deliverability.py`), nem a leadek számától.

**A leiratkozó link csak akkor jelenik meg a levélben, ha az `UNSUB_BASE_URL`
be van állítva** a gyökér `.env`-ben. Amíg nincs, a levél a *„írd vissza, hogy
stop"* mondattal megy ki — az is működik. **Csak akkor állítsd be, ha a
leiratkozó oldal már él**: egy 404-re mutató link rosszabb, mint a mondat.

**A `preview.py --send-to` teszt-levelében a leiratkozó link szándékosan nem
működik.** Enélkül a saját tesztelésed egy valódi céget iratna le.

**Minden parancs újrafuttatható.** Egyik sem duplikál: az `ingest` a már ismert
cégeket kihagyja, az `enrich` a `status` oszlopból tudja, hol tart, az `export`
ugyanabból az állapotból mindig ugyanazt a fájlt írja.

**Az automatikus lánc egy hibás lépés után is tovább megy** — kivéve a
`feedback`-et. Ha az elszáll, az `export` **nem fut le**: visszajelzés nélkül
exportálni annyi, mint újra levelet küldeni annak, aki tegnap nemet mondott.
Egy elszállt `ingest` viszont nem állítja meg a napot, mert a többi lépésnek
van mit feldolgoznia a tegnapi cégekből.

**A napi lánc naplója:** `cold-email-starter/data/leadgen_daily.log`.
Ha egy reggel nem történt semmi, ez az első hely, ahova nézni kell.

**Ugyanarról a riasztásról naponta csak egyszer megy email.** A fájl-napló
(`data/alerts.log`) és a `report --daily` viszont mindig mutatja, amíg fennáll.
