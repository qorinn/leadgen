# Hogyan használd — útmutató nulláról

> Ez a fájl azt írja le, **mit tud a rendszer és hogyan kell használni**.
> Ha csak a parancsok listája kell: [PARANCSOK.md](PARANCSOK.md).
> Ha azt akarod tudni, mit kell **neked** elvégezned: [TEENDOK.md](TEENDOK.md).

---

## Mi ez az egész?

Ez a program **cégeket keres az interneten**, eldönti, hogy jó ügyfél lehet-e
belőlük, és **emailt küld nekik**. Aztán figyeli, ki válaszolt, és aki nemet
mondott, annak soha többé nem ír.

Két külön programból áll:

```
  ┌─────────────────┐                      ┌─────────────────┐
  │    SCRAPER      │   ──── leads.csv ──► │     KÜLDŐ       │
  │  (leadgen)      │                      │ (cold-email-…)  │
  │                 │  ◄─── válaszok ───── │                 │
  │ KIT keressünk?  │                      │ MI ment ki?     │
  └─────────────────┘                      └─────────────────┘
     adatbázisba ír                          fájlokba ír
```

- A **scraper** dönti el, *kinek* érdemes írni.
- A **küldő** intézi a *tényleges levélküldést*.
- Egyetlen fájlon keresztül beszélnek: `leads.csv`.

**Miért két program?** Mert a küldő már kész volt és működött, mielőtt a
scraper elkészült. Nem írtuk át — összekötöttük őket.

---

## Két fontos szabály, mielőtt bármit csinálnál

**1. Minden parancsot a projekt gyökeréből futtass.**

```bash
cd /Users/paladibalint/Developer/seo-checker/scraper/scraper
```

**2. A `--dry` mindig biztonságos.** Ahol látod, ott a parancs **csak megmutatja**,
mit csinálna, de nem csinálja meg. Ha bizonytalan vagy, mindig `--dry`-jal
kezdj. Éles küldéshez külön `--live` kell — véletlenül nem fog levél kimenni.

---

## A napi rutin — ez a rövid válasz

Ha csak egy dolgot jegyzel meg ebből a fájlból, ez legyen az:

```bash
# ── REGGEL (5 perc) ────────────────────────────────────────────
./leadgen.sh report          # mi a helyzet, mi vár rám?
./leadgen.sh review          # ha van bizonytalan cég: TE döntesz
./leadgen.sh export          # átadás a küldőnek

cd cold-email-starter
python3 sender.py --dry      # MI MEGY KI MA? — olvasd el
python3 sender.py --live     # ÉLES KÜLDÉS

# ── ESTE, 17:00 után ───────────────────────────────────────────
python3 deliverability.py    # napi jelentés
cd .. && ./leadgen.sh feedback   # a nap eredménye vissza az adatbázisba
```

Küldeni **hétköznap 8:00 és 17:00 között** lehet. Hétvégén a program nem küld.

---

# A folyamatok egyenként

## 1. folyamat — Új cégek gyűjtése

**Mikor:** ha a `report` azt mutatja, hogy fogy a lista. Nem minden nap.

**Mi történik:** a program a Google Maps-en keres ügynökségeket, letölti a
weboldalukat, elolvassa, és eldönti, jó lead-e.

```bash
./leadgen.sh ingest maps --max-results 100   # cégek keresése
./leadgen.sh enrich                          # weboldalak letöltése
./leadgen.sh qualify                         # minősítés
```

**Ez pénzbe kerül** (~$0.005 találatonként). A `--max-results` a költségfék.
Ha csak meg akarod nézni, mit keresne: `./leadgen.sh ingest maps --dry` —
ez nem költ.

**Nem kell egyszerre lefutnia.** Mindegyik parancs megjegyzi, hol tartott.
Ha megszakad, futtasd újra — onnan folytatja, nem kezdi elölről, és nem
fizetsz kétszer ugyanazokért a cégekért.

**A végén három csoportba kerülnek a cégek:**

| Csoport | Mi lesz velük |
|---|---|
| **kész** (`ready`) | mehet nekik levél |
| **átnézésre vár** (`review`) | ← **te döntesz** (2. folyamat) |
| **tiltólistán** | versenytárs, nem írunk neki |

---

## 2. folyamat — A bizonytalan cégek átnézése  *(te döntesz)*

**Mikor:** ha a `report` azt írja, hogy valaki átnézésre vár.

**Miért van erre szükség:** a gép kulcsszavak alapján dönt, és néha téved.
Például kizárna egy jó ügynökséget, mert az oldalán szerepel a
„webfejlesztés" szó — csakhogy az egy **ügyfél-referenciában** volt, nem a
saját szolgáltatásai közt.

Egy jó lead elvesztése drágább, mint egy félrement levél. Ezért ilyenkor a
gép nem dönt, hanem megkérdez.

```bash
./leadgen.sh review                        # kilistázza őket, linkkel
./leadgen.sh review --approve cegnev.hu    # jó lead → mehet neki levél
./leadgen.sh review --reject  cegnev.hu    # nem kell → tiltólista
```

Nyisd meg a linket, nézd meg az oldalt, döntsd el. Kb. 20 másodperc cégenként.

> **A gép döntései sem véglegesek.** Az `--approve` visszahozza azt is, amit
> a gép magától zárt ki. Amit automatikusan kizárt:
> `./leadgen.sh review --suppressed`

---

## 3. folyamat — Levélküldés

**Mikor:** naponta egyszer, hétköznap reggel.

### 3.1 Átadás a küldőnek

```bash
./leadgen.sh export
```

Ez kiírja a `leads.csv` fájlt. **Előtte magától lefuttatja a visszacsatolást**
(ki válaszolt, ki iratkozott le) — és ha az hibára fut, az export megáll.
Ez szándékos: amíg nem tudjuk, ki mondott nemet, nem adunk ki új leadet.

### 3.2 Nézd meg, mi megy ki  ← *ne hagyd ki*

```bash
cd cold-email-starter
python3 preview.py           # a TELJES levelek, címzettenként
python3 sender.py --dry      # a mai terv, rövidítve
```

**Ez az utolsó visszafordítható pont.** Amit itt látsz, az megy ki.
Ha valaki mégsem kell:

```bash
cd .. && ./leadgen.sh review --reject cegnev.hu
```

Ez akkor is működik, ha a cég már a `leads.csv`-ben van.

### 3.3 Éles küldés

```bash
python3 sender.py --live
python3 sender.py --live --limit 5    # csak 5 levél ebben a futásban
```

**Napi 20 levélnél többet nem küld**, akkor sem, ha 200 lead vár. Ez véd:
egy új postafiókból hirtelen sok levelet küldeni a leggyorsabb út a spam
mappába. A keret magától emelkedik, ha jól mennek a levelek.

> **Fontos:** a válaszra várókat (follow-up) **mindig előbb küldi ki**, mint
> az újakat. Tehát ha sok leadet töltesz be, attól nem megy ki több levél —
> csak hosszabb lesz a sor.

---

## 4. folyamat — Napi zárás

**Mikor:** este, 17:00 után.

```bash
cd cold-email-starter
python3 deliverability.py    # napi jelentés + a holnapi keret
cd .. && ./leadgen.sh feedback
```

> A `deliverability.py` **1-es hibakóddal áll le, ha riasztás van.** Ez nem
> hiba a programban — ez maga a riasztás.

---

## 5. folyamat — Válaszok kezelése

Itt **három szint** van egymás mögött. A felső mindig fut, az alsó csak ha kéred.

### 5.1 Automatikus — nem kell csinálnod semmit

Minden küldés előtt a program magától elolvassa a postaládát, és:

- aki **válaszolt bármit** → nem kap több automatikus levelet
- aki azt írta, hogy **„stop"** → tiltólistára kerül
- akinek a **címe nem létezik** → tiltólistára kerül

Ez ingyen fut, kulcs nélkül. **Ha ez hibára fut, a program nem küld semmit** —
inkább nem küld, mint hogy olyannak írjon, aki nemet mondott.

### 5.2 A leiratkozó link — szintén automatikus

Minden levél alján van egy személyre szóló link. Ha valaki rákattint és
megerősíti, azonnal bekerül a tiltólistába, és a következő exportnál kiesik.
Neked ezzel nincs dolgod.

### 5.3 AI válasz-értelmezés — *ezt te indítod, és pénzbe kerül*

Ez elolvassa a válaszokat, és eldönti, **mit jelentenek**:

```bash
./leadgen.sh classify-replies --dry    # ELŐSZÖR mindig ezt
./leadgen.sh classify-replies          # aztán élesben
./leadgen.sh report --replies          # az eredmény
```

| Az AI szerint a válasz | Mi történik |
|---|---|
| **érdeklődik** | kiírja neked nagybetűvel — **te válaszolj neki** |
| most nem aktuális | 90 nap múlva újra sorba áll |
| automatikus válasz (szabadság) | 14 nap múlva újra próbálja |
| nemet mond | tiltólista |
| leiratkozna | tiltólista, az egész cég |
| **bizonytalan** | **nem csinál semmit** — te nézed át |

**Miért van erre külön parancs, ha van már automatikus felismerés?** Mert ez
pénzbe kerül, az meg nem. Az ingyenes réteg elkapja az egyértelmű eseteket;
az AI a maradékot érti meg. Ezért van az AI a sor **végén**, nem az elején.

> ⚠️ A tiltás **végleges**. Ha az AI nem elég biztos a dolgában, inkább nem
> dönt, hanem rád bízza. Első alkalommal és minden változtatás után futtasd
> `--dry`-jal.

### 5.4 Amit csak te tudsz megcsinálni

**Olvasd a postaládát minden nap.** Egy érdeklődő válasz 24 órán belül
megérdemel egy emberi választ. Ez az a pont, ahol a rendszer működik, de az
ügyfél mégis elveszik.

---

## 6. folyamat — Hol tartunk?

**Mikor:** bármikor. Ez a leggyakrabban használt parancs.

```bash
./leadgen.sh report            # a teljes kép + a mai nap
./leadgen.sh report --daily    # csak a mai nap
./leadgen.sh report --replies  # a válaszok
```

Megmutatja, hány cég van melyik állapotban, mi fér bele a mai keretbe, és a
végén kiírja, **mi a következő lépésed**.

Ha azt írja, hogy „a jelenlegi sor ~8 napra elég", akkor **adagolj**:
`./leadgen.sh export --limit 20`. Egy nagy export nem gyorsítja a kiküldést,
csak várakozó sort épít.

---

## 7. folyamat — Első beállítás  *(egyszer kell)*

Ha új gépre kerül a projekt:

```bash
# 1. A titkok
cp cold-email-starter/.env.example cold-email-starter/.env   # küldő
# a gyökér .env-be: DATABASE_URL, APIFY_TOKEN, UNSUB_BASE_URL, ANTHROPIC_API_KEY

# 2. Adatbázis
./leadgen.sh db migrate      # bármikor újrafuttatható
./leadgen.sh db check        # rendben van-e minden tábla

# 3. Levelezés teszt
cd cold-email-starter
python3 -c "import mailer; mailer.check_accounts()"
```

---

## 8. folyamat — Modellek összehasonlítása (bake-off)

**Mikor:** mielőtt nagy volumenű AI-leadszűrésre váltunk (9-10. fázis).

Ez megméri, melyik olcsó AI-modell dönt legjobban **a te ítéleted szerint**.
Kell hozzá 30 teszteset, amit **te** címkézel fel — útmutató:
[evals/README.md](evals/README.md).

```bash
./leadgen.sh eval bakeoff --model gemini-2.5-flash-lite --model claude-haiku-4-5
./leadgen.sh eval robustness --model gemini-2.5-flash-lite
```

A `robustness` azt méri, hogy a modell átverhető-e: mi történik, ha valaki a
weboldalába beleírja, hogy „hagyd figyelmen kívül az utasításaidat". Ez nem
elmélet — a scrapelt oldalak szövegét idegenek írják.

---

# Mi nincs még kész

| Mi hiányzik | Melyik fázis | Mit jelent ez most |
|---|---|---|
| **Időzítés (cron)** | 12. | Minden parancsot kézzel indítasz. Nincs, ami magától fut. |
| **Email-cím ellenőrzés (Reoon)** | 7. | Nem tudjuk kiküldés előtt, hogy létezik-e a cím. |
| **Profession.hu leadforrás** | 9-10. | Csak ügynökségeket gyűjtünk, más iparágat nem. |
| **AI személyre szabás** | 10. | A nyitómondat sablonos, nem AI írja. |
| **Webes felület** | 13. | Minden parancssorból megy. |

---

# Ha valami baj van

| Amit látsz | Mit jelent | Mit csinálj |
|---|---|---|
| `Nincs kuldheto cimzett` | üres a `leads.csv` | `./leadgen.sh export` |
| `Guards HIBA -> nem kuldunk semmit` | nem éri el a postaládát | ellenőrizd a netet és a `.env`-et |
| `A mai keret elfogyott` | ma már 20 levél kiment | holnap folytatódik, ez normális |
| `nincs beallitva a DATABASE_URL` | hiányzik a gyökér `.env` | `./leadgen.sh db info` |
| `HIBA: nincs ANTHROPIC_API_KEY` | nincs AI-kulcs | csak az AI-parancsokat érinti, a küldés megy |
| `deliverability.py` 1-es hibakód | **riasztás**, nem programhiba | olvasd el a kiírt üzenetet |
| teszt-domainek a listában | `.invalid` címek maradtak bent | `./leadgen.sh dev clear-seed` |

**Ha elakadsz:** `./leadgen.sh report` szinte mindig megmondja, mi a következő
lépés. Minden parancs újrafuttatható — egyik sem csinál kárt attól, hogy
kétszer futtatod.

---

<!-- ─────────────────────────────────────────────────────────────────────
     AGENTNEK: ezt a fájlt KÖTELEZŐ frissíteni, ha egy szakasz új
     folyamatot vagy új parancsot ad a rendszerhez. A szabály a
     CLAUDE.md-ben is szerepel. Amit karban kell tartani:
       - új folyamat  -> új számozott szakasz
       - új parancs   -> a megfelelő folyamatba
       - ha valami elkészül -> ki a "Mi nincs még kész" táblából
       - új gyakori hibaüzenet -> a "Ha valami baj van" táblába
     A stílus: rövid mondatok, semmi szakzsargon magyarázat nélkül.
     ───────────────────────────────────────────────────────────────── -->
