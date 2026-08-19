# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mi ez a repó

A repó gyökere (`scraper/scraper`) egy **még meg nem írt lead-scraper** munkatere. Jelenleg:

- `cold-email-starter/` — a kész, működő cold email küldő motor (Python 3.10+, stdlib-only).
  Ez az egyetlen kód a repóban; a scraperből még egy sor sem létezik.
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
A részletes rendszerleírás és a nyitott integrációs kérdések:
[cold-email-starter/SCRAPER_INTEGRATION.md](cold-email-starter/SCRAPER_INTEGRATION.md).

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

**Még nyitott integrációs kérdések** (a fenti ellentmondás-tábla a bemenetük, és külön
integrációs tervben dőlnek el): egy vagy két igazságforrás; hol fut az email-validáció és
mi az újravalidálási küszöb; hogyan jut vissza a bounce / leiratkozás / válasz a
scraperhez és milyen gyakran; ki írhatja a `status`-t; mi a pontos átadási mezőlista és
melyik oldal indítja a folyamatot; hol fut a válasz-osztályozás.

Amiről a küldő oldaláról már most tudni kell: a `leads.csv`-n belül **nincs** dedup (a
`build_plan` csendben az utolsó sort veszi ismétlődő email esetén), és **nincs** upsert a
`store.py`-ban — csak append és teljes újraolvasás. Jogalap: B2B jogos érdek
(GDPR 6(1)(f)) — publikus, üzleti kontextusú forrásokból gyűjts.
