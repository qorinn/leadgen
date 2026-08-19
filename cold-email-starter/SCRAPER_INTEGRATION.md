# Cold email rendszer — teljes működési leírás AI agenteknek

Ez a dokumentum AI agenteknek szól, akiknek **scrapert kell építeniük és a
meglévő cold email rendszerhez kapcsolniuk**. Nem a felhasználónak szóló
összefoglaló, hanem munkaanyag: minden itt van, ami a rendszer jelenlegi
működéséről, invariánsairól és korlátairól szükséges ahhoz, hogy az
integráció során megalapozott döntés szülessen arról, mit lehet
változtatás nélkül hagyni, és mihez kell hozzányúlni.

**A terv jelenlegi állása:** a meglévő küldési logika alapjai (dry-run
default, guards, DNC, ramp) megmaradnak, de **a rendszer módosítható**, ha a
scraper-integráció ezt indokolja. Nem cél a változtatás elkerülése — cél,
hogy a változtatás tudatos legyen, ne törje el a lent felsorolt
invariánsokat ok nélkül.

---

## 1. A rendszer célja és nem-céljai

Python 3.10+, **stdlib-only** (szándékos: nincs külső függőség, bárhol
elindul). Ez a tervezési döntés eddig kőbe vésett volt; ha a scraper miatt
külső csomag kellene (pl. `requests`, `beautifulsoup4`, `playwright`), az a
scraper saját függősége lehet, de az email-küldő modulok (`config`, `store`,
`mailer`, `guards`, `limits`, `verify`, `templates`, `sender`,
`deliverability`) függőség-mentességét ne törd meg feltétlenül csak azért,
mert kényelmes lenne — ha mégis szükséges, dokumentáld a döntést a kódban.

A rendszer **nem** "küldj ki mindenkinek" script. A logika nagy része arról
szól, kinek NE küldjünk. A scraper ebbe a modellbe illeszkedik: a scraper
**jelölteket** termel, a döntést, hogy tényleg megy-e neki levél, a meglévő
védelmi réteg hozza meg minden egyes futásnál újra (nem egyszeri szűrés
feltöltéskor).

A rendszer eddig **nem tartalmazott lead-gyűjtést** — ez volt a szándékos
hiány, amit most a scraper tölt be. Ez azt jelenti, hogy nincs meglévő
scraper-kontraktus, amit be kéne tartani — a kontraktust most alakítjuk ki,
és szabadon tervezhető úgy, ahogy a scraper architektúrája megkívánja.

---

## 2. Adatmodell — 4 CSV fájl, nincs adatbázis

Minden állapot `data/` alatt, sima CSV-ben (`store.py`). Szándékosan nincs
DB, hogy a fájlok kézzel is átláthatók, verziózhatók, hordozhatók legyenek.
Ez a döntés a scraper miatt sem feltétlenül szent — ha a lead-volumen vagy a
scraper igényei (pl. gyakori upsert, státusz-mezők, source-tracking)
indokolják, áttérés SQLite-ra vagy máshova ésszerű módosítás, amíg a négy
alapfájl *szemantikája* (lásd lent) megmarad valamilyen formában.

### `leads.csv` — a lead-lista (eddig: a felhasználó töltötte fel kézzel)
```
email,company,contact_name,website,industry,city,notes
```
- `email`: **az egyetlen kulcs** a teljes rendszerben. Minden modul
  (`sender.py`, `guards.py`, `limits.py`) email-cím alapján azonosít,
  dedupol, dönt DNC-ről.
- `contact_name`, `company`, `industry`: közvetlenül a levél törzsébe
  kerülnek (`templates.py`), nyersen, szűrés nélkül. Ha `contact_name`
  üres, a rendszer semleges megszólítást használ ("Tisztelt Cím!") — SOHA
  nem hagy nyers `[Nev]` placeholdert (ez valós incidensből ered).
- `website`, `city`, `notes`: jelenleg csak emberi átnézésre, a küldési
  logika nem olvassa őket. Ha a scraper extra mezőket akar tárolni (pl.
  `source_url`, `scraped_at`, `confidence_score`), a `LEADS_HEADER`-t
  (`store.py` 19. sor) bővíteni kell — ez biztonságos módosítás, mert
  `csv.DictReader`/`DictWriter` néven hivatkozik a mezőkre, nem pozíció
  szerint, tehát a többi modul nem törik el, amíg az `email` mező megvan.

### `sent.csv` — küldési napló (igazságforrás a volumenre és a stádiumra)
```
ts,email,domain,stage,template,subject,account
```
Csak a `sender.py` ír bele (`store.record_send`), minden sikeres küldés után
egy sor. A `sender.build_plan()` ebből olvassa ki, hogy egy lead melyik
fokon áll (cold / follow_up_1 / follow_up_2 / done) — l. 4. pont.

### `do-not-contact.csv` (DNC) — suppression lista
```
ts,email,reason,notes
```
Aki itt szerepel, annak **soha, semmilyen körülmények között** nem megy
levél — ezt a `sender.build_plan()` minden futásnál ellenőrzi
(`store.dnc_emails()`). Ide kerül automatikusan: aki válaszolt (`replied`),
aki leiratkozott (`unsubscribe_request`), akinek a címe hard bounce-olt
(`hard_bounce`) — mind a `guards.py`-ból. Idempotens írás
(`store.add_to_dnc`): ha már bent van, nem duplikál.

### `bounces.csv` — visszapattanások naplója
```
ts,email,reason,raw_subject
```
Csak a `guards.py` ír bele. **A timestamp azt jelzi, mikor DOLGOZTUK FEL a
bounce-t, nem mikor ment ki az eredeti levél** — ez fontos, mert a
`deliverability.py` emiatt csak a "ma is küldtünk neki és ma bounce-olt"
eseteket számolja bele a napi arányba (l. 6. pont).

`store.py` minden írása egyszerű fájl-append, **nincs tranzakció, nincs
lock**. Ha bármi (a jelenlegi rendszer vagy a scraper) párhuzamosan ír,
sorok keveredhetnek. Jelenlegi ajánlás: `flock` cron alatt, ha egyszerre
több folyamat futhat.

---

## 3. Konfiguráció (`config.py`)

Minden `.env`-ből jön (`_load_dotenv`, saját minimál-parser, nincs
`python-dotenv` függőség). Sosem kerül valódi kulcs a kódba. Amit érdemes
tudni scraper-integráció szempontjából:

- `SMTP_ACCOUNTS` — több postafiók, vesszővel elválasztva, `user:jelszó`
  formátumban. A `mailer.py` ezek közt rotál.
- `DAILY_CAP_START` / `DAILY_CAP_CEILING` / `RAMP_STEP` / `RAMP_STEP_DAYS` —
  a napi keret és annak automatikus emelése (l. 5. pont). Ha a scraper
  hirtelen sok friss leadet termel, ez a keret NEM emelkedik automatikusan
  gyorsabban — a ramp logika szándékosan lassú, függetlenül attól, mennyi
  lead várakozik.
- `LEADS_CSV`, `SENT_CSV`, `DNC_CSV`, `BOUNCE_CSV`, `RAMP_JSON`, `LOG_FILE`
  — útvonalak, mind `data/` alatt. Ha a scraper külön néven vagy külön
  mappában akar dolgozni (pl. staging lista, ami még nincs jóváhagyva),
  külön konfig-kulcsot érdemes bevezetni, ne a meglévő `LEADS_CSV`-t
  irányítsd át.

---

## 4. A fő futtatási ciklus (`sender.py`)

```
1. guards.run()            -> válasz/leiratkozás/bounce beolvasás, DNC frissítés
2. limits.in_send_window() -> időablak (munkaidő, hétvége)
3. limits.remaining_today()-> napi keret - eddig ma kiküldött
4. build_plan(remaining)   -> kikeresi, kinek mit kell küldeni
5. mailer.send() soronként -> tényleges SMTP küldés (csak --live esetén)
6. store.record_send()     -> napló
```

**Dry-run az alapértelmezés.** `--live` nélkül semmi nem megy ki, csak
konzolra íródik a terv. Ezt a védelmet nem szabad megkerülni vagy
megfordítani — ha a scraper teszteléséhez gyakran kell éles-szerű
kimenet, azt `--dry` mellett, a print-kimenetből oldd meg, ne a
default-ot fordítsd meg.

**`build_plan()` logika** (`sender.py` 52-87. sor): minden leadhez
megnézi, van-e már `sent.csv`-ben rekordja (`_stage_of`), és ez alapján
dönti el, hogy friss cold levél, follow_up_1, follow_up_2, vagy semmi
(done / DNC-n van / unsendable formátumú) jár neki. **Follow-up mindig
előnyt élvez a friss cold felett** ugyanabban a napi keretben — ha a
scraper sok új leadet önt be, azok versenyeznek a keretért a folyamatban
lévő beszélgetésekkel, és veszítenek.

Guards hiba esetén (`guards.run()` kivételt dob) a küldés **azonnal
leáll, semmi nem megy ki** — ez szándékos: az üres/hibás válasz-lekérdezés
nem egyenlő azzal, hogy "senki nem válaszolt".

---

## 5. Volumen-szabályozás (`limits.py`)

- **Időablak**: `SEND_WINDOW_START`–`SEND_WINDOW_END` óra, hétvégén alapból
  nem küld (`SEND_ON_WEEKEND`).
- **Napi keret** postafiókonként, `ramp_state.json`-ban tárolva
  (`_load_state`/`_save_state`). Kezdő érték `DAILY_CAP_START`, felső
  határ `DAILY_CAP_CEILING`.
- **`evaluate_ramp()`**: naponta **egyszer** fut (a `last_eval` mező védi —
  ha többször hívod egy napon, csendben nem csinál semmit). Ha a
  bounce/reject arány a küszöb felett van, azonnal visszavesz
  (`RAMP_STEP`-pel csökkent); ha `RAMP_STEP_DAYS` egymást követő tiszta nap
  volt, emel. Ezt a `deliverability.py` hívja meg naponta egyszer, a
  küldési ablak zárása után.

A scraper által termelt lead-mennyiség **nem hat közvetlenül** a napi
keretre — a keret kizárólag a kézbesítési jelekből (bounce, reject) adódik.
Ha a cél az, hogy a scraper volumene befolyásolja a rampet (pl. gyorsabb
skálázás sok jó minőségű friss lead esetén), az `evaluate_ramp()`
módosítást igényel — jelenleg ez a függvény nem kap lead-mennyiségi inputot.

---

## 6. Védelmi réteg (`guards.py`) és kézbesítés-figyelés (`deliverability.py`)

`guards.run()` minden küldés előtt lefut (kivéve `--skip-guards`), IMAP-on
olvassa be a bejövő leveleket minden fiókból, és három dolgot csinál:
1. NDR (non-delivery report) felismerés feladó/tárgy minta alapján →
   hard/soft bounce szétválasztás reguláris kifejezésekkel. Csak hard
   bounce kerül azonnal DNC-be.
2. Válasz-felismerés: ha a feladó szerepel a `sent.csv`-ben (valaha kaptunk
   tőle levelet), az `replied`-ként DNC-be kerül — ez **nem tiltás**, csak
   azt jelzi, hogy a robot innentől nem küld neki automatikusan, ember
   vegye át.
3. Leiratkozás-felismerés kulcsszavak alapján a válasz szövegében →
   `unsubscribe_request` DNC.

`mailer.fetch_recent()` **kivételt dob** hiba esetén, sosem ad vissza üres
listát hibaként — ezt a `sender.py` úgy kezeli, hogy guards-hiba esetén
egyáltalán nem indul küldés. Ez a rendszer egyik legszigorúbb invariánsa.

`deliverability.py` naponta lefut a küldési ablak után, kiszámolja a napi
bounce-arányt **csak azokra, akiknek ma is küldtünk** (a `bounces.csv`
timestamp-je megbízhatatlan a "mikor ment ki az eredeti" kérdésre), és
meghívja `limits.evaluate_ramp()`-et.

---

## 7. Sablonok (`templates.py`)

A `cold()`, `follow_up_1()`, `follow_up_2()` függvények egy `lead` dict-et
(a `leads.csv` egy sora) kapnak, és `{subject, body, template}` dict-et
adnak vissza. Plain text only, nincs HTML, nincs tracking pixel (szándékos,
kézbesítést ront). Két kemény szabály van beledrótozva:
1. Fájdalom-első nyitás, nem cégbemutatkozás.
2. Ha egy sablon "utolsó levelet" ígér, azt be is kell tartani.

Ha a scraper új mezőket hoz be (pl. `pain_point`, forrás-specifikus
adatok), a `templates.py`-t bővíteni kell, hogy ezeket felhasználja — ez
megengedett módosítás, csak a fenti két szabályt ne sértse, és a
`_greeting()` logikát (nincs nyers placeholder) tartsa meg.

---

## 8. Cím-ellenőrzés (`verify.py`)

Két réteg: MX-rekord ellenőrzés (mindig működik, csak DNS kell) és
RCPT-probe (kimenő 25-ös port kell hozzá — sok felhő-szolgáltató blokkolja,
ezért van külön egress-teszt). **`unknown` sosem jelent "rossz címet"**,
csak "nem tudom" — csak `dead`-re szabad véglegesen kizárni egy címet.

`looks_unsendable()` olcsó, hálózat nélküli szűrés (formátum + role-cím
mint `info@`, `noreply@`). Ezt a `sender.build_plan()` minden futásnál
lefuttatja minden leadre — tehát a scraper **nem köteles** előszűrni, a
rendszer úgyis kiszűri unsendable címeket induláskor. Előszűrés a scraper
oldalán csak minőségjavítás, nem biztonsági követelmény.

---

## 9. Amit eddig sosem szabadott megkerülni (öt kemény szabály, `AGENTS.md`-ből)

1. Valódi kulcs/jelszó/postafiók-cím sosem kerül kódba, csak `.env`.
2. Küldés alapértelmezetten dry-run, csak `--live` küld ténylegesen.
3. Ha `guards.run()` kivételt dob, a küldés nem indulhat.
4. DNC-listás címre soha, semmilyen körülmények között nem megy levél.
5. Nincs követőpixel / nyitás-követés a levelekben.

Ezek eddig nem voltak vitatottak. Ha a scraper-integráció valamelyiket
érintené (pl. a scraper is tudna DNC-be írni, vagy a dry-run viselkedést
scraper-tesztekhez módosítani kéne), az külön átgondolást igényel — nem
automatikusan tiltott, de indoklást érdemel, mert ezek a szabályok valós
incidensekből (reputáció-vesztés, jogi panasz) születtek.

---

## 10. Nyitott kérdések a scraper-integrációhoz (itt kell dönteni)

Ezek azok a pontok, ahol a jelenlegi rendszer nem ad kész választ, mert
eddig nem volt scraper — itt várható, hogy módosítani kell:

- **Hogyan kerül be a lead**: közvetlen `leads.csv` append, külön staging
  fájl + jóváhagyási lépés, vagy `store` modul közvetlen hívása a scraper
  folyamatából? Ha staging kell (pl. a scraper minősége bizonytalan, és
  emberi review szükséges küldés előtt), az új fájl/mező bevezetést
  igényel — a `LEADS_HEADER` bővítése (pl. `status: pending/approved`)
  vagy külön `leads_staging.csv` mindkettő járható út.
- **Forrás-nyomon követés**: jelenleg semmilyen mező nem tárolja, honnan
  jött egy lead. Ha ez kell (pl. minőség-visszamérés forrásonként), a
  `LEADS_HEADER` bővítése és a `sent.csv`/riportolás összekötése is
  módosítást igényel.
- **Duplikátum-kezelés**: a rendszer jelenleg NEM dedupol a `leads.csv`-n
  belül explicit hibajelzéssel — a `sender.build_plan()` egy
  `dict[email] -> lead` mappát épít, tehát ismétlődő email esetén csak az
  utolsó sor számít, csendben. Ha a scraper gyakran termel duplikátumot,
  vagy dedupolj scraper-oldalon, vagy vezess be explicit dedup lépést a
  betöltésnél.
- **Frissítés vs. új sor**: ha a scraper egy már létező leadről újabb/jobb
  adatot talál (pl. pontosabb `contact_name`), a jelenlegi `store.py`-ban
  nincs upsert, csak append és teljes újraolvasás. Upsert-igény esetén ez
  új függvényt igényel `store.py`-ban.
- **Napi keret és lead-utánpótlás összejátszása**: ha a scraper lassabban
  termel leadet, mint a napi keret engedné, a `build_plan()` egyszerűen
  kevesebb levelet küld aznap (nincs hibajelzés, csak `store.log`). Ha ezt
  monitorozni kell, a `sender.py` log-üzenete már most tartalmazza
  (`"Nincs küldhető címzett"` vagy a terv mérete a kerethez képest).

Ezekre a kérdésekre a scraper konkrét architektúrája alapján kell választ
adni — a fenti fejezetek (2-9) adják meg hozzá a kontextust, hogy a
módosítás ne törje el a meglévő invariánsokat feleslegesen.
