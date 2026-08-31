# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mi ez a repó

A repó két rendszert tartalmaz, amiket össze kell hangolni:

- `cold-email-starter/` — a kész, működő cold email küldő motor (stdlib-only, a gépen
  a rendszer `python3` 3.9.6-ján fut).
- `leadgen/` — a **lead-scraper**, épül. Saját venv (Python 3.12), Supabase Postgres.
  Az 1. szakasz (alapozás) 2026-08-19-én elkészült: séma, migrációk, normalizáló réteg.
  Üzleti logika még nincs benne.
- `webui/` — a **webes felület** (13. szakasz, 2026-08-30-án lezárva): FastAPI
  backend + Next.js frontend, csak `localhost`-on. Lásd lent „A webes felület
  (`webui/`)" szakaszt.
- [HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) — **a felhasználói útmutató**: a valódi
  folyamatok, hogyan kell futtatni őket, mi opcionális bennük, és mi nincs még kész.
  Laikusnak írva, rövid mondatokkal. **Lásd lent a karbantartási kötelezettséget.**
- [TEENDOK.md](TEENDOK.md) — **amit a felhasználónak kell elvégeznie**, fázisokon
  átívelően. Ha egy szakasz emberi feladatot termel, ide is vedd fel.
- [OPCIONALIS.md](OPCIONALIS.md) — elhalasztott és felmerült módosítási ötletek,
  becsléssel. Nem TODO: innen a felhasználó választ.
- [DOMAIN-BEMELEGITES.md](DOMAIN-BEMELEGITES.md) — hogyan kell egy új küldő
  domaint előkészíteni és bemelegíteni. **Tartalmaz egy rendszer-specifikus
  korlátot:** a `daily_cap()` a fiókok számával szoroz, a `next_account()` pedig
  egyenletesen oszt — ezért egy második `SMTP_ACCOUNTS` bejegyzés a hideg
  postafiókot azonnal napi 20 levéllel indítaná. A bemelegítés ezért külön
  példányban fut, nem második fiókként.
- [INTEGRATION-PLAN.md](INTEGRATION-PLAN.md) — **a végrehajtási terv**: a két rendszer
  közti kontraktus, az eldöntött integrációs kérdések, a szakaszok és az állapotuk.
  Egy új session ezzel kezdjen — a tetején lévő állapot-blokk megmondja, hol tartunk.
- [WEBUI-TERV.md](WEBUI-TERV.md) — **a webes felület (13. szakasz) végrehajtási terve**,
  12 fázisra bontva (F0–F11), fázisonkénti ellenőrzéssel. Mellette
  [WEBUI-MODELLEK.md](WEBUI-MODELLEK.md) (melyik fázis melyik modellel) és
  [WEBUI-PROMPT.md](WEBUI-PROMPT.md) (a bemásolható fázis-prompt).
  **A felület megépült** (F0–F11 kész, 2026-08-30) — indítás: `./leadgen.sh ui`.
  A felhasználói leírás: [HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) „17. folyamat".
- [SCRAPER-PLAN.md](SCRAPER-PLAN.md) — **a repó elsődleges követelményrendszere**, 3258 sor.
  Ne olvastasd végig egy sessionben; célzottan olvasd `sed -n`-nel. A load-bearing fejezetek:

  | Fejezet | Sorok | Miért kell |
  |---|---|---|
  | `0.4 Jogi minimum` | 190–225 | a `suppression` tábla és a forrás-rögzítés kötelezettsége |
  | `Validation` | 2088–2155 | kétlépcsős validáció, `EMAIL_VALIDATION = off\|local_only\|full` |
  | adatbázis-séma | 2156–2311 | `companies` / `sources` / `contacts` / `suppression` / `outreach` |
  | `Az aranyszabály` | 2312–2341 | **domain lock**: egy domain = egy aktív sequence |
  | `Offer arbitration` + `Cooldown` | 2342–2405 | egy cég egy kampányba kerül; cooldown-szabályok |
  | `Fontos: mi fut hol` | 2645–2711 | `status` lifecycle, batch-elt rövid futások |
  | `Építési sorrend` | 2837–2980 | határidőre optimalizált sorrend, és amit NEM építünk |
  | `Függelék: bake-off` | 2981–3258 | a modellváltás evalja |

- `ignore/` — munkaanyagok. Az
  [ignore/AI-model-teszteles-manualisan.md](ignore/AI-model-teszteles-manualisan.md) a
  bake-off protokoll **korábbi, rövidebb változata**; a mérvadó verzió a `SCRAPER-PLAN.md`
  függeléke. A könyvtár a neve ellenére **be van commitolva** (`git ls-files`).

A scraper feladata: **jelölt** leadeket termelni a `cold-email-starter/data/leads.csv`-be.
A döntést, hogy tényleg megy-e levél, minden futásnál újra a küldő védelmi rétege hozza meg.
A küldő részletes rendszerleírása:
[cold-email-starter/SCRAPER_INTEGRATION.md](cold-email-starter/SCRAPER_INTEGRATION.md)
(a benne felsorolt „nyitott kérdések" azóta eldőltek — lásd az INTEGRATION-PLAN.md 2. részét).

A `cold-email-starter/AGENTS.md` a küldő motorra vonatkozó kemény szabályokat tartalmazza —
ezek a lenti "Invariánsok" szakaszban is szerepelnek, és érvényesek maradnak.

## A határidő mint tervezési kényszer

**2026. október 12., legalább 1 ügyfél.** Egy fejlesztő, Claude Code-dal. A terv vezérelve
szó szerint: *„Az első emaileknek a 2. héten ki kell menniük, nem a 6. héten."* Egy félkész
pipeline, ami küld, többet ér, mint egy tökéletes, ami még nem.

- **Tudatosan feláldozva:** VPS / saját infra, teljes source-lefedettség, kézi
  üzenet-validáció kiküldés előtt, deliverability finomhangolás.
- **NEM áldozható fel** (olcsó most, utólag napokba kerül): `suppression` tábla, platform
  blocklist, evidence grounding, `status` oszlop.
- **Volumen-korlát:** `DAILY_CAP_START=20`, `RAMP_STEP=20` / 3 tiszta nap, `ceiling=200`
  **postafiókonként** → egy postafiókkal ~7 hét a plafonig. A határidőig nem a leadhiány
  a szűk keresztmetszet, hanem a küldési keret. Ezzel tervezz.

## Parancsok

Nincs test suite, nincs linter, nincs csomagkezelő (szándékosan nulla külső függőség).
A "tesztelés" ezek a smoke-futtatások, mind a `cold-email-starter/` könyvtárból:

```bash
cp .env.example .env && cp data/leads.example.csv data/leads.csv   # első beállítás
python3 -c "import mailer; mailer.check_accounts()"   # SMTP bejelentkezés-teszt
python3 sender.py --dry --skip-guards                 # fejlesztés közben EZ a fő ellenőrzés
python3 sender.py --dry                               # dry, de IMAP-ot igényel (guards lefut)
python3 sender.py --live                              # éles küldés
python3 guards.py                                     # csak a védelmi kör (IMAP)
python3 deliverability.py                             # napi jelentés + ramp értékelés
```

`--skip-guards` nélkül a `--dry` is IMAP-kapcsolatot nyit, és guards-hiba esetén exit 1-gyel
áll le, mielőtt bármit kiírna. (Beállított `SMTP_ACCOUNTS` nélkül a `sender.py` már ez előtt
kilép.) Bármilyen küldési-logika módosítás után a `--dry --skip-guards` kimenetét
(terv + renderelt levelek) kell átnézni.

`sender.py --limit N` levágja az adott futás tervét; `deliverability.py` **exit 1-et ad,
ha riasztás van** — cronban ezt ne értelmezd hibának.

### A scraper parancsai — a repó gyökeréből

> **Teljes parancs-referencia: [PARANCSOK.md](PARANCSOK.md)** — ott minden
> funkció szerepel, magyarázattal. Az alábbi csak a leggyakoribbak.
>
> A `./leadgen.sh` indító bárhonnan működik (megkeresi a venv-et és a gyökeret).

A scraper **külön interpreteren fut**: saját venv Python 3.12-vel. A `python3` a gépen
3.9.6, azon a küldő fut. Ne keverd őket.

```bash
.venv/bin/python -m leadgen.cli db info        # kapcsolódási adatok, jelszó nélkül
.venv/bin/python -m leadgen.cli db migrate     # idempotens, bármikor újrafuttatható
.venv/bin/python -m leadgen.cli db check       # táblák és sorszámok
.venv/bin/python -m leadgen.cli report         # hol tart a tölcsér + a mai keret
.venv/bin/python -m leadgen.cli daily          # a teljes napi lánc (12. szakasz)
.venv/bin/python -m leadgen.cli alert --dry    # riasztás-ellenőrzés, írás nélkül
.venv/bin/python -m leadgen.cli schedule status  # fut-e az ütemezés
.venv/bin/pytest                               # a normalizáló réteg tesztjei
```

## A napi rutin — 5. szakasz óta ez a rendszer üzemmódja

**A 12. szakasz óta a scraper-oldal futhat magától** (`./leadgen.sh schedule
install` → launchd, minden reggel 7:30). A küldés szándékosan kézi maradt.
Minden lépés rövid, batch-elt és újrafuttatható, tehát egy kihagyott nap nem
borít fel semmit — a következő futás onnan folytatja.

```bash
# ── reggel, 5 perc ────────────────────────────────────────────────────────
# (ütemezett futásnál a report/export lépést a lánc már elvégezte 7:30-kor)
./leadgen.sh report --daily           # riasztások + mi fér a mai keretbe
./leadgen.sh review                   # ha van átnézendő: TE döntesz
./leadgen.sh export                   # feedback-import + leads.csv újraírás

cd cold-email-starter
python3 sender.py --dry               # a mai terv, guards-szal (utolsó ellenőrzés)
python3 sender.py --live              # ÉLES — ezt EMBER indítja, agent soha

# ── este, a küldési ablak (17:00) után ────────────────────────────────────
python3 deliverability.py             # napi jelentés + a holnapi keret
cd .. && ./leadgen.sh feedback        # a nap eredménye vissza a DB-be
```

**Amit egy agentnek tudnia kell erről a rutinról:**

- **A `--live` futást soha nem az agent indítja.** Ez nem technikai korlát,
  hanem munkamegosztás: a kiküldés visszafordíthatatlan, és a levél a
  felhasználó nevében megy ki. Az agent előkészít és ellenőriz.
- **A `deliverability.py` exit 1-et ad, ha riasztás van** — ez nem hiba,
  ez a jelzés. A `--live` után futtatva a ramp-értékelést is elvégzi, és az
  a `last_eval` mező miatt **naponta csak egyszer** hat.
- **A sorrend nem cserélhető fel:** az `export` maga futtatja a `feedback`-et
  első lépésként, és ha az elszáll, nem ír semmit. Az esti `feedback` külön
  futtatása azért kell, hogy a nap eredménye (kiment levelek, válaszok,
  bounce-ok) még aznap átvezetődjön — nem másnap reggel derüljön ki.
- **A `report --daily` a „hány napra elég a sor" számot mutatja.** Ha ez 5 nap
  fölé megy, adagolni kell (`export --limit 20`): a follow-up mindig veri a
  friss cold-ot ugyanabban a napi keretben, tehát egy nagy export nem gyorsít,
  csak várakozó sort épít.
- **A `--live` NEM kerülhet be az ütemezett láncba.** A `leadgen/schedule.py`
  szándékosan csak a scraper-oldalt futtatja; tesztsor őrzi
  (`test_a_lanc_soha_nem_kuld_eles_levelet`). Ez felhasználói döntés
  (2026-08-27), nem technikai korlát — ha valaha megváltozik, az legyen
  kimondott döntés, ne egy „beteszem a láncba is" módosítás mellékhatása.
- **Az utolsó visszafordítható pont a `sender.py --dry`.** Amit ott látsz, az
  megy ki. Ha egy lead mégsem kell, `./leadgen.sh review --reject <domain>` —
  ez már exportált (`queued`) leadre is működik, lezárja az outreach sort, és
  a következő export kiveszi a `leads.csv`-ből.

## Architektúra

### Adatmodell: négy CSV, nincs adatbázis
Minden állapot `cold-email-starter/data/` alatt, `store.py` kezeli. Fejlécek a `store.py`
tetején (`LEADS_HEADER` stb.):

| Fájl | Ki írja | Szerep |
|---|---|---|
| `leads.csv` | a scraper / a felhasználó | bemenet; `email` az **egyetlen kulcs** az egész rendszerben |
| `sent.csv` | csak `sender.py` | igazságforrás a napi volumenre ÉS a szekvencia-fokra |
| `do-not-contact.csv` | csak `guards.py` | suppression; ide kerül a válaszoló, leiratkozó, hard bounce |
| `bounces.csv` | csak `guards.py` | bounce-napló |

`store._append` sima fájl-append: **nincs tranzakció, nincs lock**. Ha bármi (scraper, cron)
párhuzamosan írhat, `flock` kell.

### Futási ciklus (`sender.py:main`)
`guards.run()` → `limits.in_send_window()` → `limits.remaining_today()` →
`build_plan()` → `mailer.send()` → `store.record_send()`.

### Amit csak több fájl elolvasásából lehet tudni

- **A `template` mező a `sent.csv`-ben load-bearing.** A `sender._stage_of` a leadhez tartozó
  `sent.csv` sorok `template` értékeiből (`"cold"` / `"follow_up_1"` / `"follow_up_2"`)
  vezeti le, hol tart a szekvencia. Ha átnevezel egy sablon-azonosítót a `templates.py`-ban,
  minden korábban kiküldött lead visszaesik egy korábbi fokra és **újra kap levelet**.
  A `templates.LADDER` konstans jelenleg deklaratív: a `build_plan` nem olvassa.
- **A follow-up mindig veri a friss cold-ot ugyanabban a napi keretben** (`build_plan`:
  `followups + fresh`, aztán `[:limit]`). Sok új lead betöltése nem gyorsítja a kiküldést,
  csak várakozó sort épít.
- **A napi keret nem a lead-mennyiségtől függ.** `limits.daily_cap()` = a rampelt
  per-fiók keret × a `SMTP_ACCOUNTS` fiókok száma. `evaluate_ramp()` kizárólag
  kézbesítési jelekből (bounce/reject) emel vagy csökkent, és a `last_eval` mező miatt
  **naponta csak egyszer** hat — többszöri hívás csendben nem csinál semmit.
- **Az időablak dry-run alatt nincs kikényszerítve** (`if live and not open_now`), így
  bármikor tesztelhető.
- **`config._load_dotenv` `os.environ.setdefault`-ot használ**: a már beállított valódi
  környezeti változó felülírja a `.env` értékét, nem fordítva.
- **A `LEADS_HEADER` biztonságosan bővíthető** (pl. `source_url`, `scraped_at`,
  `status`), mert minden olvasás/írás `csv.DictReader`/`DictWriter`, tehát név szerinti,
  nem pozíció szerinti — amíg az `email` mező megvan, más modul nem törik el.
- **`verify.py` az egyetlen hely, ahol opcionális külső csomag felmerül**: `dns.resolver`,
  ha telepítve van, különben a rendszer `dig` parancsa. Nem kötelező függőség.
- **`verify.probe_mailbox` "unknown" értéke SOHA nem jelent rossz címet** — csak `dead`-re
  szabad címet véglegesen kizárni. Sok felhőszolgáltató blokkolja a kimenő 25-ös portot,
  ilyenkor minden cím "unknown" lenne.
- **`deliverability.daily_report` csak azokat a bounce-okat számolja a mai arányba, akiknek
  MA is küldtünk** — a `bounces.csv` timestampje a feldolgozás, nem a kiküldés ideje.
  A riasztás pedig csak a reputáció-releváns (nem soft) bounce-okra néz.

## ⚠️ Ahol a terv és a küldő ellentmond egymásnak

A `SCRAPER-PLAN.md` feltételezései és a `cold-email-starter/` tényleges viselkedése között
hat ellenőrzött eltérés van. Egyik sem látszik egyetlen fájlból. Ha ezek ismerete nélkül
kezdesz integrációt építeni, csendben rossz rendszert építesz.

| # | A terv feltételezi | A küldő valójában | Következmény |
|---|---|---|---|
| 1 | **Domain lock** — egy domain egyszerre egy sequence-ben (`Az aranyszabály`) | `sender.build_plan` `dict[email] -> lead`-et épít, a domain fogalmát nem ismeri | Ha egy cégről két cím kerül be (`info@` + `nev@`), **mindkettő kap külön levelet**. A terv legfontosabb szabálya sérül. A domain lockot az exportáló oldalon kell kikényszeríteni — a küldő nem tudja kifejezni. |
| 2 | AI-generált **personalization mondat** megy az emailbe (Tier A/B) | `templates.py` csak `contact_name` / `company` / `industry` mezőt renderel | A terv teljes personalization rétegének **nincs hova landolnia**. `LEADS_HEADER` bővítés + `templates.py` módosítás kell. |
| 3 | **Offer arbitration** + engine-enként külön CTA (webapp / website / mobil) | egyetlen sablonkészlet: `cold` / `follow_up_1` / `follow_up_2` | Négy engine nem szolgálható ki egy sablonnal; `campaign` mező + sablonválasztás kell. |
| 4 | `suppression` **domain- vagy email-szintű**, okok: `unsubscribe`, `negative_reply`, `manual_block`, `competitor`, `existing_client` | `do-not-contact.csv` **csak email-szintű**, okok: `replied`, `unsubscribe_request`, `hard_bounce` | A két taxonómia nem fedi egymást, és a küldő nem ismer domain-szintű tiltást. A 8.1 engine melléktermékként `competitor` sorokat termel — ezeknek nincs helyük a DNC-ben. |
| 5 | AI válasz-osztályozás tölti a suppressiont (AI-feladat #5) | `guards.UNSUB_PATTERNS` tartalmazza a `r"\bnem\b"` mintát, és a válasz **első 600 karakterén** illeszt | Magyar szövegben a „nem" szó szinte biztosan előfordul → **tömeges hamis `unsubscribe_request`**. Egy érdeklődő válasz is véglegesként kerülhet suppressionbe. |
| 6 | Validation kiszűri: `noreply@`, `webmaster@`, `admin@`, `privacy@`, `gdpr@` | `verify.ROLE_PREFIXES` = `abuse, postmaster, noreply, no-reply, donotreply, spam, webmaster, hostmaster, root` — **nincs benne** `admin`, `privacy`, `gdpr` | A két szűrőlista eltér. (`info@` **mindkettőben átmegy** — szándékosan: magyar KKV-nál gyakran ez az egyetlen cím, és a `data/leads.example.csv` is ilyet használ.) |

Az 5. pont javítása **nem gyengíti** a védelmi réteget: minden válaszoló a `replied`
szabály miatt amúgy is DNC-be kerül, tehát az `UNSUB_PATTERNS` szűkítése nem enged ki
senkit, csak az *okot* pontosítja.

## A scraper (`leadgen/`) — 1. szakasz óta létezik

Külön rendszer, saját függőségekkel. A teljes terv: [INTEGRATION-PLAN.md](INTEGRATION-PLAN.md).

| | |
|---|---|
| Futtatás | `.venv/bin/python -m leadgen.cli ...` a **repó gyökeréből** |
| Python | 3.12 (Homebrew), saját `.venv`. A küldő a rendszer 3.9.6-ján fut. |
| Függőségek | `psycopg[binary]`, `httpx`, `selectolax`, `pytest` (`requirements.txt`) |
| Adatbázis | Supabase Postgres 17, **session pooler** (5432). A 6543-as transaction pooleren a migrációk elhasalnának. |
| Titkok | a **gyökér** `.env`-ben (`DATABASE_URL`, ...). A küldőé külön: `cold-email-starter/.env`. |

**Modulok és a felelősségük:**

- `leadgen/db.py` — **az egyetlen hely, ahol `psycopg`-t hívunk.** Ha a DB valaha
  költözik, egy fájl változik. Máshol ne olvasd a connection stringet.
- `leadgen/normalize.py` — domain / cégnév / telefon / email, tiszta függvények.
  A `.hu` másodszintű suffixek (`shop.hu`, `co.hu`, ...) be vannak drótozva:
  e nélkül minden `*.shop.hu` cég egyetlen `shop.hu` kulcsra esne össze.
- `leadgen/blocklist.py` — platform-domainek + a cégkulcs feloldása
  (domain → adószám → cégnév+település → telefon).
- `leadgen/migrations/*.sql` — sima SQL, névsorrendben. **Egy már lefuttatott
  migrációt soha ne írj át** (checksum védi): vegyél fel újat.

**Miért van itt pytest, ha a küldőben nincs test suite:** a normalizálás hibái némák —
két cég összeolvad, vagy egy cég kétszer kap levelet, és semmi nem dob hibát. Csak
ide írunk tesztet, máshova nem.

**Az iparág adat, nem kód.** A [leadgen/engines.py](leadgen/engines.py) `EngineDef`
blokkjai írják le, hogy egy vertikum mit keres a Google Mapsen, milyen kulcsszó
minősít, mi zár ki, és melyik kampány sablonjai renderelnek. Új iparág = új blokk
ott + sablonok a `templates.py`-ban. **A scrapelés, enrichment, export és feedback
kódja változatlan marad** — azok forrástól és iparágtól függetlenek. Van egy kész,
`enabled=False` példa-definíció (`field_service`), ami megmutatja a mintát.

**A kizárás két szintű** (`exclude_hard` / `exclude_soft`): az erős jel azonnal
versenytárs-suppressionbe visz, a gyenge jel `review` állapotba, emberi döntésre.
Ez azért van, mert a kulcsszó gyakran ügyfél-referenciából vagy blogcikkből jön,
nem a cég saját szolgáltatás-listájából — és egy jó lead elvesztése drágább, mint
egy félrement levél.

**Vázlat sablonnal nem mehet ki levél: `contract.APPROVED_CAMPAIGNS` a kapu.**
Az agent VÁZLAT sablonokat tesz a `templates.py`-ba (`dead_dev`, `ops_pain`),
amiket a felhasználónak át kell írnia — de az exportot ez korábban nem
érdekelte: ami `ready`, az kiment. Élesben látszott a 10. szakaszban: 2 lead
`ready` lett `ops_pain` kampánnyal, és csak azért nem exportálódott, mert még
nem volt email címük. Az `enrich` után kiment volna, jóváhagyás nélkül.
**Új kampány élesítése: szöveg átírása → `preview.py` → felvétel az
`APPROVED_CAMPAIGNS`-ba.** Tesztsor őrzi, hogy a vázlatok ne legyenek benne.

**Az evidence grounding NEM AI-hívás.** [leadgen/grounding.py](leadgen/grounding.py):
szóköz- és kisbetű-normalizálás, majd string-keresés a forrásszövegben, 40
karakteres részleges egyezéssel. Amit **nem** normalizálunk: ékezet, ragozás,
szórend, szinonima — az átfogalmazás már következtetés, nem idézet, és pont
azt szűrjük. A `MIN_IDEZET` (15 karakter) azért kell, mert egy rövid töredék
szinte bármely szövegben megtalálható, tehát átmenne anélkül, hogy bizonyítana.

**A Profession.hu NEM adja meg a cég weboldalát.** Mérve (2026-08-22, 12
hirdetés): a `description` teljes szöveggel megvan — **de csak
`includeDetails=True` mellett** —, a cég domainje viszont sehol, még a
profession.hu profiloldalán sem. Ezért a domain-feloldás három lépcsős
([leadgen/sources/profession.py](leadgen/sources/profession.py)), és a
harmadik (Google Maps, ~$0,005/cég) **külön parancs**: az `ingest`
inkrementális, tehát a már látott hirdetéseket a feloldás előtt kiejti — egy
`--resolve-maps`-szel megismételt ingest sosem érné utol a beragadt cégeket.
Ezt az éles teszt találta meg. Domain nélkül a cég `status='error'`-ban vár,
**nem vész el**.

**A 8.2 footer-felismerésben a kulcsszó önmagában ~85%-ban téved.** Mérve a 49
letöltött oldalon: a „készítette / weboldal készítés / powered by" minták 7
helyen találtak, de csak **1** volt valódi fejlesztő-kredit — a többi a cég
saját szolgáltatás-menüje, egy stock-fotó kredit és a WordPress/tárhely volt.
A [leadgen/deadev.py](leadgen/deadev.py) ezért három feltételt köt össze:
minta a footerben + link **a minta UTÁN, 60 karakteren belül** + a link idegen,
nem-platform, nem-tárhely domainre mutat. A hosting-kontextust a link
**szövegében is** nézi (`<a>Hosting: Smartsector</a>`). Mindegyik szűkítést
valós hamis pozitív indokolta, és tesztsor őrzi.

**Az email-validáció kétlépcsős, és a `role_account` NEM érvénytelen cím.**
A [leadgen/validate.py](leadgen/validate.py) `_STATUS_MAP`-jában a legfontosabb
sor a `role_account → valid`: a Reoon külön státusszal jelzi a szerepkörös
címeket (`info@`, `office@`), és ha ezt `invalid`-nak vennénk, **a magyar
KKV-lista nagy része csendben eltűnne** (a 46 kapcsolatból 31 `generic`,
túlnyomórészt `info@`). Ugyanígy load-bearing: **minden API-hiba `unknown`,
soha nem `invalid`** — egy Reoon-kimaradás nem törölheti a listát.
A cache (90 nap) nem optimalizáció, hanem költségvédelem; kötelező teszt védi.

**Az AI réteg két tieres, és a provider a modellnévből derül ki.**
Három provider van bekötve: `gpt-*`/`o1`/`o3`/`o4` → OpenAI, `claude-*` →
Anthropic, `gemini*` → Google. **Providert váltani = egy sort átírni a
`.env`-ben** (`LLM_BULK_MODEL`), a hívó oldalak nem változnak — ez 2026-08-22-én
élesben bizonyult, amikor a BULK tier Geminiről OpenAI-ra váltott. A
Gemini-integráció szándékosan **megmaradt**, nincs törölve.
**Kulcshiány-üzenet: soha ne drótozd be a provider nevét** — az
`llm.kulcs_hianyzik()` a modellnévből vezeti le, különben egy modellváltás után
a rossz kulcsot kérnénk a felhasználótól. Tesztsor védi.
A [leadgen/llm.py](leadgen/llm.py) `bulk()` (olcsó, nagy volumen) és
`quality()` (jobb magyar) függvényt ad; a `call(model, ...)` bármelyik
modellel megy, ezért tud a bake-off ugyanazon a kódon több modellt mérni.
A promptok egy helyen vannak ([leadgen/prompts.py](leadgen/prompts.py)), mert a
prompt caching **stabil prefixet** kíván — a változó lead-adat mindig külön
paraméter, sosem a rendszer-prompthoz fűzve.

**A leadadat és a megkereshetőség két külön réteg.** Minden scraper-találatot
előbb teljes nyers payloadként ments a `sources` táblába; a `company_id` lehet
NULL, ha még nincs stabil cégazonosító. Gyenge vagy hiányzó szolgáltatási jel,
domain, kontakt vagy personalization miatt új kód **nem állíthat `rejected`-et**:
használj `scored`/`review`/`hold` státuszt és `company_labels` címkét. Az AI
`opportunity_angles` listát ad, a pontszám rangsorol, nem kizár. Suppression csak
leiratkozás, negatív válasz, hard bounce, meglévő ügyfél, kézi tiltás vagy
bizonyítható közvetlen versenytárs. Az export továbbra is csak `ready` +
használható kontakt + jóváhagyott kampány esetén enged, és külön viszi a lead
eredetét (`lead_source_*`) és a kontakt forrását (`contact_source_url`).

**A prompt few-shot példái SABLONNÁ válnak — ezt hat kimenet együtt látszik.**
Mérve 2026-08-25: a personalization mind a 6 mondata ugyanúgy folytatódott
(*„Ilyenkor szokott segíteni egy közös webes felület, ahol…"*), mert a prompt
JÓ példái pont ezt a fordulatot használták. Egyetlen kimeneten ez nem
látszik. Javítva: a példák **szerkezetileg különböznek** egymástól, a prompt
kimondja, hogy a példák a szerkezetet mutatják és nem a szövegezést, és
felsorol tiltott sablon-fordulatokat. **Prompt-módosítás után mindig
6+ kimenetet nézz egyszerre**, ne egyet.

**Ellentmondó hossz-utasítás = a modell találgat.** Ugyanabban a promptban
egyszerre szerepelt *„egyetlen mondat"*, *„KÉT-HÁROM MONDAT"* és *„három
mondat, maximum 70 szó"* — a bővítések rétegződtek egymásra. A modell
ilyenkor nem hibázik hangosan, csak kiszámíthatatlan hosszúságút ad.
Prompt bővítésekor **a régi utasítást is javítsd**, ne csak told hozzá az újat.

**Minden LLM-hívás tokenjeit MI számoljuk** ([leadgen/pricing.py](leadgen/pricing.py)),
mert a szolgáltatók dashboardja lassan frissül és **összevonja a modelleket** —
egy bake-off ettől értelmetlen lenne. A `score`, a `classify-replies` és az
`llm-check` mind modellenkénti bontást ír ki, és a `data/llm_usage.csv` napló
összeadható. Az árak kézzel karbantartott tábla, forrással és dátummal;
ismeretlen modellnél a tokenszám pontos, az ár helyén „ISMERETLEN AR" áll —
**soha ne találj ki árat**.

**Az `anthropic` SDK 1.0.0 `messages.create()`-je NEM fogad el `temperature`-t.**
A paraméter teljesen eltűnt: az átadása `TypeError`, még HTTP-hívás előtt. Ez
nem modellfüggő korlát — a korábbi feltevés („a Haiku még elfogadja") téves
volt, és az első valódi hívás cáfolta meg. Tesztsor ellenőrzi a **telepített**
SDK szignatúráját, nem emlékezetből.

**A `temperature` nem küldhető minden modellnek.** A `claude-haiku-4-5` még
elfogadja, az Opus 5 / Sonnet 5 / Fable 5 viszont **400-zal elutasítja**. Mivel
a modellnév `.env`-ből jön, egy modellváltás enélkül minden hívást eltörne —
ezért van az `llm._SAMPLING_TILTVA` lista. Új modell felvételekor ellenőrizd.

**A válasz-osztályozás az egyetlen visszafordíthatatlan AI-döntés.**
Az `unsubscribe` és a `negative` címke suppressionbe teszi a céget. Három
védelmi réteg van egymáson, és **mindhárom kell**: (1) a prompt bizonytalanság
esetén `other`-t kér; (2) a **bizalmi kapu** — 0.70 alatti bizonyosságnál a
visszafordíthatatlan címke `other` lesz; (3) a `--dry` az alapértelmezett
munkamódszer. A `not_now` és az `auto_reply` **nem** suppression, hanem
cooldown (90 / 14 nap) — ezeket soha ne told át a visszafordíthatatlanok közé.

**A leiratkozás linken keresztül megy, és a link nem ír a küldő fájljaiba.**
A `contacts.unsub_token` a címhez tartozik (nem a kampányhoz), tehát egy régi
levélben lévő link egy év múlva is működik. A weboldal két `security definer`
függvényt hívhat (`unsub_lookup` / `unsub_confirm`), semmi mást — **a táblákon
RLS van, nulla policy-vel**, mert a Supabase `anon` szerep alapból mindenre
kapna jogot, az anon kulcs pedig szándékosan publikus. A scrapert ez nem
érinti: `postgres` szerepkörrel csatlakozik, ami a táblák tulajdonosa.
A leiratkozás érvényesítése az exportnál történik (a lead kimarad a
`leads.csv`-ből, az `outreach` sora `stopped` lesz) — **a `do-not-contact.csv`
marad a `guards.py` tulajdona.**

**Az e-beszámoló portált NEM kérdezzük le géppel — ez jogi, nem technikai
korlát.** A 0.3 előteszt (2026-08-26) három dolgot talált: Altcha
proof-of-work captchát a kereső előtt; a Felhasználási Feltételekben a
rendeltetésszerű használat definícióját (*„a Cégtörvényben meghatározott
**hitelezővédelmi célból**"* — egy értékesítési céllista nem az); és azt, hogy
a *„különféle technikai megoldások igénybevételével"* történő megkerülés
**rendőrségi feljelentéssel** jár. A [leadgen/financials.py](leadgen/financials.py)
ezért worklist + `--import` + `--set` úton dolgozik, és **tesztsor tiltja,
hogy bárki HTTP-klienst hozzon be a modulba**. A hivatalos tömeges út létezik:
„Csoportos beszámoló kérő lap" → `e-beszamolo@mkifk.hu` (TEENDOK.md 4.5).

**Az `economic_value` rangsorol, nem szűr, és a `signal_score` bónusz
idempotens.** A terv eredeti *„csak MEDIUM+ megy outreachbe"* mondatát a
2026-08-25-i megőrző leadmodell felülírja: a `LOW` címke, nem elutasítás. A
bónusz (`+15` magas árbevétel, `+25` dobozos webshop + magas árbevétel) azért
külön `financial_bonus` oszlopban tárolódik, mert a `signal_score` kumulatív —
`signal_score + 15` alakban írva minden újrafuttatás újra hozzáadná, és a
rangsor csendben elromlana. Minden újraszámolás `régi le, új fel`.
**Az árbevétel FORINTBAN van**: a beszámoló űrlapja „adatok E Ft-ban" formában
mutat, ezért az importer minden 1 M Ft alatti értékre hangosan szól.

**A 8.3-ban a `tech.platform` mező 100%-ban tévedett.** Mérve a 49 letöltött
oldalon (2026-08-26): 12 találat, **0 valódi saját webshop** — partner-logók,
egy `partners/shoprenter.png` képfájl, egy `szakertok.shoprenter.hu` link,
szolgáltatás-szövegek, egy téma-CSS `.woocommerce` szelektora és egy
**kikommentelt** stylesheet. A [leadgen/webshop.py](leadgen/webshop.py) ezért
három feltételt köt össze: a marker a betöltött **eszköz URL-jének hostjában**
(SaaS platform) vagy a **konkrét plugin-útvonalban** (saját üzemeltetésű) van +
van **bolt-gépezet** (kosár/termék link) + **parszolunk, nem regexelünk** (a
kikommentelt elem így fel sem merül — ezt ne írd vissza regexre). Mérve: 0
hamis pozitív a 49 oldalon, 3/3 valódi webshop felismerve. **A Magento és a
PrestaShop szándékosan nincs a „dobozos" halmazban** — azok nyílt, bővíthető
rendszerek, ott a „kinőtted" állítás nem igaz.

**A kampány és a personalization mondat együtt alkot egy levelet.** Élesben
látszott: a cég megkapta a `webshop_growth` kampányt, de a `personalization`
mezőben egy korábbi, **ügynökségi** szögből született mondat maradt — a levél
webshopról szólt volna, a nyitómondata viszont másról. Kampányváltáskor
mindkettőt frissítsd. A 8.3 emellett **nem írja felül a meglévő kampányt** (a
domain lock miatt, és mert egy ember által átnézett kampányt nem cserélhet le
csendben); a szög ilyenkor `opportunity_angles` sorként akkor is elmentődik.
**Az árbevétel soha nem kerülhet a levélbe** — tesztsor őrzi, hogy a 8.3
mondata ne tartalmazzon számjegyet.

**Az ütemezett futás három dolgot tör el, ami kézi futtatásnál nem
látszik.** (12. szakasz) (1) **A `store._append` lock nélkül nem biztonságos**:
a 12. szakasz óta két folyamat ír a `data/` alá (a launchd lánca és a kézzel
indított küldő), és egy félig kiírt `sent.csv` sor csendben rossz napi keretet
vagy rossz szekvencia-fokot okoz — ezért `flock` van minden íráson **és**
olvasáson. (2) **A Python fájlba irányítva blokkosan pufferel**: élesben mérve
50 másodperc futás után a launchd naplója még teljesen üres volt, tehát egy
beragadt láncnál pont az nem látszana, hol akadt el. A plist ezért
`PYTHONUNBUFFERED=1`-et ad az egész folyamatfának. (3) **A launchd nagyon szűk
környezettel indít** — a `PATH`-ban nincs benne a Homebrew, ahol a venv
Pythonja van. Mindhárom hibát csak éles launchd-futás mutatta meg, kézi
futtatás soha.

**A riasztás akkor ér valamit, ha ritka.** A feltételek napokig fennállnak
(„3 napja nincs `ready` lead"), tehát fékezés nélkül ugyanaz a mondat menne ki
minden reggel — három nap múlva a felhasználó szűrőt tenne rá, és onnantól a
*valódi* riasztást sem látná. Ezért van az `alerts` tábla `last_notified`
oszlopa és a 24 órás cooldown. A dedup kulcsa a riasztás **tárgyát** is
tartalmazza (`unanswered_interested:<email>`), különben a második érdeklődő
elnyomva maradna, amíg az elsőt meg nem válaszolod.

**A riasztási email best-effort, a fájl az igazságforrás.** Egy SMTP-kimaradás
pontosan az a helyzet, amikor a riasztás a legfontosabb — és pont akkor nem
működik az email út. Ezért az `alerts._emailben()` **soha nem dob kivételt**,
hanem a hibaszöveget adja vissza, ami maga is bekerül a naplóba. A sorrend
kötött: fájl → DB → email.

**A `deliverability.py` fixen nullát adott át a rampnak.** Emiatt a
`REJECT_RATE_ALERT` küszöb **soha nem sült el**, és a ramp csak a
visszapattanásokból tanult — nem látta, ha a Google *elutasítja* a küldést. A
`sender.py` már számolta a sikertelen küldéseket, csak nem mentette gépi
olvasásra alkalmas formában; most `rejects.csv`. A két arány **nevezője
szándékosan különbözik**: a bounce a kiküldött (`sent`), a reject a
megkísérelt (`sent + rejects`) levelekre vetül — utóbbi nélkül 20 kísérletből
20 elutasítás esetén a nevező nulla lenne, és pont a legsúlyosabb eset adna
0%-ot.

**A napi lánc egy hibás lépés után tovább megy — a `feedback` kivételével.**
Egy elszállt `ingest` (Apify-kimaradás) nem eshet ki egy egész napot: a többi
lépésnek van mit feldolgoznia tegnapról. A `feedback` viszont `kotelezo=True`,
és utána a lánc megáll: visszajelzés nélkül exportálni annyi, mint újra
levelet küldeni annak, aki tegnap nemet mondott. Tesztsor őrzi a sorrendet is.

**A Profession jogi cégnevet ad, a Maps márkanevet.** Mérve a 100 cégen: a
Profession-leadek 75%-ánál (30/40) szerepel a jogi forma a névben, a
Maps-leadeknél 22%-ánál (13/60) — a cégjegyzék viszont jogi néven keres.
A DB-ben jelenleg **0 cégnek van adószáma**, ezért a pénzügyi import
párosítása `company_id → adószám → domain` sorrendben megy; **cégnév szerint
szándékosan soha**, mert egy téves névegyezés rossz céghez írna árbevételt.

**A domain lock adatbázis-szinten él:** részleges UNIQUE index az
`outreach (company_id) WHERE status IN ('queued','sent')` feltétellel. A küldő ezt
nem tudja kifejezni (`build_plan` email szerint kulcsol), ezért itt kell kikényszeríteni.

## A webes felület (`webui/`) — 13. szakasz óta létezik

Harmadik réteg a scraper és a küldő mellett, de **nem harmadik igazságforrás**:
csak megjelenít és gombot nyom, dönteni nem dönt. A teljes végrehajtási terv
(fázisonként, ellenőrzéssel): [WEBUI-TERV.md](WEBUI-TERV.md). A felhasználói
nézet: [HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) „17. folyamat — A felület".

| | |
|---|---|
| Indítás | `./leadgen.sh ui` — a `leadgen` venv-jéből fut, **nem** a `python3` 3.9.6-on |
| Backend | `webui/api/` — FastAPI, csak `127.0.0.1`-en, `leadgen` függvényeket importál |
| Frontend | `webui/app/` — Next.js + shadcn/ui + Bklit UI (chartok), TypeScript |
| Kontraktus | `GET /api/meta` — innen tudja a felület, mi a jóváhagyott kampány, mi a suppression-ok, mi a státusz-sorrend |

**A legfontosabb szabály: az üzleti logika soha nem másolódik TypeScriptbe.**
Egy `tests/test_webui_contract.py` teszt (`test_a_frontend_nem_drotoz_be_uzleti_listat`)
ezt automatikusan ellenőrzi is — string-literálként keresi a frontend
forrásaiban a `report.STATUS_ORDER`, `contract.APPROVED_CAMPAIGNS` és hasonló
Python-listák elemeit, és elbukik, ha bármelyik előfordul. Ha egy jövőbeli
fázis egy Python-oldali listát akar a frontenden megjeleníteni, a helyes út
egy új mező a `/api/meta` válaszban, nem egy bedrótozott TS-tömb.

**A küldő (`cold-email-starter/`) moduljait a webui is csak subprocess-en át
hívja** — ugyanaz az ok, mint a `leadgen/report.py`-nál (`_sender_state()`):
másik interpreteren futnak. A `webui/api/routers/send.py` és a `jobs.py` ezt
a mintát követi.

**Minden riport-jellegű Python-függvénynek van egy `*_adat()` ikertestvére**
(pl. `report.funnel_adat()` a `report.funnel()` mellett): az `*_adat()`
dict-et ad vissza, amit a CLI kiíró függvénye ÉS a webui router is hív. Ha
egy új API-végpont közvetlenül `db.query()`-t írna a router fájlba a meglévő
`leadgen`-függvény megkerülésével, két igazság lenne ugyanarra a számra — ez
az, amit a fázis-promptok „ne írj új lekérdezést, ha van már függvény"
szabálya elkerül.

**A titkok maszkolása Pythonban dől el, nem a routerben.** A `.env` értékeit
a `leadgen.config.settings_adat()` maszkolja (`webui/api/routers/settings.py`
csak hívja) — egy `tests/test_webui_contract.py` teszt (`test_egyetlen_valasz_sem_tartalmaz_titkot`)
minden GET-végpontot végigmegy, és a MA beállított titkok egyikét sem szabad
megtalálnia egyetlen válaszban sem.

## 📌 Dokumentáció-karbantartás — kötelező, nem opcionális

**Ha egy szakasz új folyamatot vagy új parancsot ad a rendszerhez, a
[HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) frissítése a szakasz része** — nem
külön feladat, és nem a felhasználó kérésére történik. A felhasználó
kifejezetten ezt kérte (2026-08-22): az útmutató maradjon együtt a kóddal.

Amit frissíteni kell:

| Ha ez történt | Ezt kell frissíteni |
|---|---|
| új folyamat (pl. ütemezés, új leadforrás) | új számozott szakasz a folyamatok közt |
| új CLI parancs | a megfelelő folyamatba + [PARANCSOK.md](PARANCSOK.md) |
| **egy hiányzó funkció elkészült** | ki a „Mi nincs még kész" táblából |
| új gyakori hibaüzenet | a „Ha valami baj van" táblába |
| új emberi feladat keletkezett | [TEENDOK.md](TEENDOK.md) |
| felmerült, de elhalasztott ötlet | [OPCIONALIS.md](OPCIONALIS.md) |

**A stílus kötelező része a tartalomnak:** rövid mondatok, szakzsargon csak
magyarázattal, laikus olvasónak. Ne told bele a tervezési indoklásokat — azok
az INTEGRATION-PLAN.md-be valók.

## Invariánsok — ezeket ne törd el

1. **Dry-run az alapértelmezés.** Csak `--live` küld. Ezt a védelmet ne fordítsd meg;
   ha éles-szerű kimenet kell teszthez, a `--dry` print-jéből dolgozz.
2. **Guards hiba = nem küldünk semmit.** `mailer.fetch_recent` hiba esetén *kivételt dob*,
   sosem ad vissza üres listát; a `sender.py` ilyenkor exit 1-gyel megáll. "Nem tudom"
   soha nem lehet egyenlő azzal, hogy "senki nem válaszolt".
3. **A DNC-lista szent.** Aki rajta van, annak semmilyen körülmények között nem megy levél.
4. **Titok sosem kerül kódba** — minden a `.env`-ből. A `data/*.csv` valódi felhasználói
   adat: ne commitold, ne másold ki, ne küldd el sehova. **Figyelem: a repó gyökerében
   nincs `.gitignore`** — csak `cold-email-starter/.gitignore` van, ami kizárólag azon a
   könyvtáron belül védi a `.env`-et és a `data/*.csv`-t. Ha a scraper a gyökérbe vagy
   máshova ír titkot/nyers adatot, ahhoz új `.gitignore`-bejegyzés kell. A
   `.claude/settings.json` `deny` blokkja tiltja a `Read(.env)` és
   `Read(**/*credentials*)` hívásokat — ez nem hiba, hanem szándékos.
5. **Nincs követőpixel, nincs nyitás-követés, nincs HTML levél.** Plain text only.
6. **`templates.py` a felhasználóé.** A szöveget csak kifejezett kérésre írd át. A benne
   drótozott szabályok (fájdalom először; nincs hamis "utoljára írok" ígéret; nincs nyers
   `[Nev]` placeholder — `_greeting()` üres névnél semleges megszólítást ad) valós
   incidensekből származnak.
7. **Stdlib-only a küldő modulokban** (`config`, `store`, `mailer`, `guards`, `limits`,
   `verify`, `templates`, `sender`, `deliverability`). A scraper hozhat saját függőséget
   (`requests`, `beautifulsoup4`, `playwright`), de ne szivárogtasd be a küldő oldalra —
   ha mégis muszáj, dokumentáld a döntést a kódban.

## Konvenciók

- **A dokumentáció és a kód-kommentek magyarul vannak.** A `.py` fájlokban a magyar szöveg
  **ékezet nélkül** (ASCII-transzliterálva) szerepel, a `.md` fájlokban ékezettel. Kövesd ezt.
- Azonosítók, CSV-fejlécek, log-kulcsok angolul.
- Email-normalizálás mindenhol `.strip().lower()` — a dedup erre épül.
- A modulok lapos, egy szintű importokkal hivatkoznak egymásra (`import store`), nincs
  csomag-struktúra; a scripteket a `cold-email-starter/` könyvtárból kell futtatni.

## A két rendszer határa, és ami még nyitott

**A határ egyetlen fájl:** `cold-email-starter/data/leads.csv`. Minden más a küldőben az
ő saját állapota.

**Két külön állapotgép, ne mosd össze őket:**

- a terv `status` lifecycle-je (`new → enriched → scored → ready → sent`) a **lead**
  életciklusa, és a scraper adatbázisáé;
- a küldő szekvencia-foka (`cold` / `follow_up_1` / `follow_up_2` / `done`) az **üzenet**
  állapota, és a `sent.csv`-ből származtatott.

**Ezek a kérdések 2026-08-19-én eldőltek** — a válaszok és az indoklásuk az
[INTEGRATION-PLAN.md](INTEGRATION-PLAN.md) 2. részében (A–F pont) vannak. Röviden:

- **Két tároló, koncernenként egy birtokos.** Supabase = ki a jelölt; CSV = mi ment ki.
- **Írási jogok:** a scraper a DB-t és a `leads.csv`-t írja; a küldő a `sent.csv`-t,
  DNC-t, bounce-okat. Egyik sem nyúl a másikéhoz.
- **Az export teljesen újraírja a `leads.csv`-t** (atomikusan), és tartalmazza a
  folyamatban lévő leadeket is — különben elmaradnának a follow-upjaik.
- **A feedback-import kötelező az export előtt**; ha hibára fut, az export exit 1-gyel
  megáll. Ez a küldő „guards hiba = nem küldünk" invariánsának a párja.
- **Validáció:** ingyenes szűrő enrichmentkor, Reoon az export kapujában, 90 napos cache.
- **Válasz-osztályozás a scraperben**, de előbb a `guards.py`-nak meg kell őriznie a
  válaszok szövegét (`replies.csv`) — ma eldobja őket.

Amiről a küldő oldaláról már most tudni kell: a `leads.csv`-n belül **nincs** dedup (a
`build_plan` csendben az utolsó sort veszi ismétlődő email esetén), és **nincs** upsert a
`store.py`-ban — csak append és teljes újraolvasás. Jogalap: B2B jogos érdek
(GDPR 6(1)(f)) — publikus, üzleti kontextusú forrásokból gyűjts.
