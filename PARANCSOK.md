# Parancsok — mit tud a rendszer

> Minden parancs a **repó gyökeréből** futtatandó:
> `/Users/paladibalint/Developer/seo-checker/scraper/scraper`
>
> A `./leadgen.sh` bárhonnan működik — megkeresi a venv-et és a gyökeret.

---

## A napi rutin (ez a rövid válasz)

```bash
./leadgen.sh ingest maps --engine agency_partner --max-results 100   # új cégek
./leadgen.sh enrich                                                  # weboldalak
./leadgen.sh qualify                                                 # minősítés
./leadgen.sh review                                                  # ← TE döntesz
./leadgen.sh export                                                  # átadás a küldőnek

cd cold-email-starter
python3 preview.py                    # ← MI MEGY KI? (teljes levelek)
python3 sender.py --live              # ← éles küldés
python3 deliverability.py             # napi jelentés
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
| `review --reject amarketingese.hu` | versenytárs → `suppressed` |
| `review --suppressed` | **amit a gép automatikusan kizárt** — indoklással |
| `review --approve <domain>` | visszahozza az automatikusan kizártat is |

> Az `--approve` `review`, `suppressed` és `rejected` állapotból is visszahoz.
> Így a rendszer automatikus döntései **nem véglegesek** — bármikor felülbírálhatod.

## Átadás és visszacsatolás

| Parancs | Mit csinál |
|---|---|
| `export --dry` | megmutatja, mi menne a `leads.csv`-be — **nem ír** |
| `export` | kiírja a `leads.csv`-t (domain lock + suppression + cooldown) |
| `export --limit 20` | egyszerre csak ennyi ÚJ leadet ad ki (adagolás) |
| `feedback` | a küldő eredménye (küldés, válasz, bounce) → DB |

> Az `export` **mindig lefuttatja a `feedback`-et először**. Ha az hibára fut,
> az export megáll, és a `leads.csv` érintetlen marad.

## Áttekintés

| Parancs | Mit csinál |
|---|---|
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

**Minden parancs újrafuttatható.** Egyik sem duplikál: az `ingest` a már ismert
cégeket kihagyja, az `enrich` a `status` oszlopból tudja, hol tart, az `export`
ugyanabból az állapotból mindig ugyanazt a fájlt írja.
