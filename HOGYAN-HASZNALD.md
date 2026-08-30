# Hogyan használd — útmutató nulláról

> Ez a fájl azt írja le, **mit tud a rendszer és hogyan kell használni**.
> Ha csak a parancsok listája kell: [PARANCSOK.md](PARANCSOK.md).
> Ha azt akarod tudni, mit kell **neked** elvégezned: [TEENDOK.md](TEENDOK.md).
> Ha új küldő domaint készítesz elő: [DOMAIN-BEMELEGITES.md](DOMAIN-BEMELEGITES.md).

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

> **Ez a rutin rövidebb lesz, ha bekapcsolod az automatikus futást.**
> A gyűjtést, a feldolgozást és az átadást a gép is elvégezheti minden
> reggel — akkor neked csak az átnézés és a küldés marad.
> Lásd a [16. folyamatot](#16-folyamat--az-automatikus-napi-futás-12-fázis).
> A küldés akkor is a te kezedben marad.

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

## 6. folyamat — Email-címek ellenőrzése

**Mikor:** magától fut minden exportnál. Nincs külön parancsa.

**Miért fontos:** ha egy levél visszapattan (nem létező cím), az **visszamenőleg**
rontja a domained hírnevét — és onnantól a **jó** címekre sem érkezik meg a
leveled. Ez az egyetlen olyan hiba a rendszerben, ami a *múltbeli* munkádat is
tönkreteszi. Ezért ellenőrizzük a címeket kiküldés előtt.

**Három fokozat van**, a gyökér `.env`-ben állítod:

| Beállítás | Mit csinál | Kerül pénzbe? |
|---|---|---|
| `off` | semmit — csak fejlesztéshez | nem |
| **`local_only`** ← *jelenleg ez fut* | ingyenes ellenőrzés: formátum, létezik-e a domain postafiókja, eldobható cím-e | **nem** |
| `full` | a fenti **plusz** Reoon: tényleg létezik-e a konkrét cím | igen, kb. **0,04 Ft / cím** |

```
EMAIL_VALIDATION=local_only     # a gyökér .env-ben
```

**Az ingyenes fokozat már most is dolgozik.** Az exportnál látni fogod:

```
helyi szuro KIZART: hello@pelda.invalid -- teszt-domain (nem letezo TLD)
kihagyva (email-validacio): 1
```

### Ha bekapcsolod a fizetőset

Kell hozzá Reoon-fiók és kredit (~$11,90 / 10 000 cím), az API kulcs a
gyökér `.env`-be:

```
EMAIL_VALIDATION=full
REOON_API_KEY=...
```

**Ugyanarra a címre 90 napig nem kérdez rá kétszer** — ez a cache, ez védi a
pénztárcádat. Ellenőrizni így tudod:

```bash
./leadgen.sh export --dry     # első futás: N lekérdezés
./leadgen.sh export --dry     # második: 0 lekérdezés, N cache-találat  ← ez a lényeg
```

Ha a második futásnál **nem** 0 a lekérdezés, valami baj van a cache-sel —
azonnal állítsd vissza `local_only`-ra és szólj.

> **Ha az ellenőrző szolgáltatás nem elérhető, senki nem esik ki.** Az ilyen
> címek „nem tudom" jelölést kapnak, nem „rossz"-at. Egy félperces kimaradás
> nem törölheti a listádat.

### Amit a fizetős fokozat kizárhat

| A cím állapota | Mi történik |
|---|---|
| létezik | mehet a levél |
| **nem létezik** / spamcsapda / eldobható | kizárva |
| a domain mindent elfogad (nem lehet eldönteni) | csak az erősebb leadeknek megy |
| nem sikerült eldönteni | csak a legerősebb leadeknek megy |

Az „erősebb lead" a pontszámot jelenti, amit a rendszer a cégnek adott.
A határok a `.env`-ből állíthatók (`TIER_A_SCORE`, `TIER_B_SCORE`), ha úgy
látod, túl sok jó lead esik ki.

**Az export mindig kiírja, ki miért maradt ki** — néma kizárás nincs.

---

## 7. folyamat — „Ki készítette a weboldalukat?"

**Mikor:** akkor futtasd, ha új cégeket gyűjtöttél. Nem naponta.

**Az ötlet:** rengeteg magyar cég weboldalának alján ott van, hogy ki
készítette. Megnézzük azt a fejlesztőt — és ha **az már nem működik**, akkor
annak a cégnek **jelenleg nincs, aki karbantartsa az oldalát**.

Ez a rendszer legerősebb objektív jele: nincs benne találgatás, és pont egy
valódi, aktuális problémára tapint rá.

```bash
./leadgen.sh enrich dead-dev --dry     # először nézd meg
./leadgen.sh enrich dead-dev           # élesben
./leadgen.sh report --signal dead_dev  # az eredmény
```

Három kimenet lehet:

| Eredmény | Mit jelent | Mi történik |
|---|---|---|
| 🔥 **DEAD** | a fejlesztő eltűnt | **top lead** — +35 pont |
| ⭐ **DORMANT** | a fejlesztő él, de évek óta inaktív | jó lead — +20 pont |
| ❌ **ALIVE** | aktív fejlesztő cég | nem lead — **a fejlesztő** tiltólistára kerül versenytársként |

> **Az ALIVE ág ingyen ad versenytárs-térképet.** A megkeresett cég marad
> lead; a *fejlesztője* kerül tiltólistára.

### ⚠️ A DEAD találatokat NÉZD ÁT KÉZZEL

Ebben a kampányban a levél **szó szerint tartalmazza a másik cég nevét**:

> „...feltűnt, hogy a weboldalukat annak idején az **XY** készítette.
> Úgy tűnik, ők már nem működnek."

Ha a felismerés téved, az nem apró pontatlanság, hanem kínos. A
`report --signal dead_dev` ezért kiírja a footer **szó szerinti szövegét** is
— abból el tudod dönteni, jó-e a találat.

> **Most miért nem talál semmit?** Mert a jelenlegi 60 céged **ügynökség** —
> ők maguk készítik a saját weboldalukat, nincs footer-kreditük. Ez a jel a
> hétköznapi kis- és középvállalatoknál működik (szerelő, fogorvos, gyártó),
> akik a 9. folyamattal érkeznek majd.

---

## 8. folyamat — Álláshirdetés-alapú leadek *(új forrás)*

**Mikor:** naponta vagy hetente, ha új leadeket akarsz ebből a forrásból.

**Az ötlet:** ha egy cég olyan pozíciót hirdet, aminek a munkaköre nagyrészt
**adminisztráció és koordináció** (szervizkoordinátor, diszpécser,
munkairányító), akkor ott jó eséllyel Excelben és papíron megy a munka — és
egy belső webalkalmazás valódi problémát oldana meg.

```bash
./leadgen.sh ingest ops-pain --dry                    # mit keresne — NEM költ
./leadgen.sh ingest ops-pain --max-results 50         # élesben
./leadgen.sh resolve-domains --limit 20               # ← FIZETŐS, lásd lent
./leadgen.sh enrich                                   # a szokásos folytatás
```

### A költség

| Mi | Mennyi |
|---|---|
| hirdetések letöltése | ~$0,005 / futás + pár cent |
| **domain-feloldás** | ~$0,005 / cég |

**Nagyjából 1 cent egy lead.** A `--max-results` a költségfék.

### ⚠️ Miért kell külön a domain-feloldás

A Profession.hu **nem adja meg a cég weboldalát** — csak a nevét. Mérve:
12 hirdetésből **0 alkalommal** szerepelt a weboldal a szövegben.

A program három lépcsőben próbálja kitalálni, olcsótól a drágáig:

1. a hirdetés szövegében szereplő weboldal — **ingyen**
2. már ismerjük ezt a céget? — **ingyen**
3. Google Maps keresés a cégnévre — **fizetős**

Az első kettő ennél a forrásnál ritkán talál, ezért van külön parancs a
harmadikra. **Mérve: 4-ből 3 céget megtalált** a Maps.

> **Akihez nem találunk domaint, az nem vész el.** „Hiba" állapotban vár,
> és bármikor újra megpróbálható. Semmi nem törlődik.

### Naponta nyugodtan futtathatod

A program **kétszer is véd az ismétlődés ellen**:

- ugyanaz a **hirdetés** nem kerül be kétszer → nincs duplikált cég;
- ugyanaz a **keresés** nem fut le újra aznap → **nem fizeted ki kétszer**.

Ha ma már lefuttattad és újra elindítod, ezt írja ki, és **nem költ**:

```
Minden kereses lefutott mar 1 napon belul -- nem koltunk.
```

**Ez nem időzítő, hanem egy pipa a nyilvántartásban.** Semmi nem fut magától
— amikor *te* elindítod a parancsot, a program megnézi, lefutott-e már ma ez
a keresés, és ha igen, kihagyja.

Ha holnap elindítod, le fog futni (az álláshirdetések naponta frissülnek).
Ha mégis ma akarod újra: `--force`.

### Ez a forrás még nem küld levelet

A hirdetéseket **be lehet gyűjteni**, de a minősítés (kinek jó lead és kinek
nem) még nincs kész — az a következő fázis. Amíg nincs kész, ezek a cégek
**nem kerülhetnek a levélküldésbe**: két külön zár tartja őket
(nem „kész" az állapotuk, és a motor ki van kapcsolva).

---

## 9. folyamat — Az AI eldönti, ki a jó lead

**Mikor:** miután begyűjtötted a hirdetéseket (8. folyamat).

Az AI elolvassa a hirdetés szövegét, és eldönti, van-e ott valódi probléma,
amit egy belső rendszer megoldana. **De nem hisszük el neki csak úgy.**

```bash
./leadgen.sh score --dry          # ELŐSZÖR mindig ez
./leadgen.sh score                # élesben
./leadgen.sh report --grounding   # mit állított, és miből
```

### A bizonyíték-szabály — ez a legfontosabb

Az AI-nak **minden állításához szó szerinti idézetet** kell adnia a hirdetésből.
A program utána **megkeresi az idézetet a szövegben**:

```
NINCS BIZONYÍTÉK  →  NINCS ÁLLÍTÁS  →  NINCS EMAIL
```

Ami nem található meg szó szerint, azt a program **eldobja**. Ha egyetlen
alátámasztott állítás sem marad, a lead kiesik.

**Miért ilyen szigorú:** ha az AI kitalál egy tényt, és az bekerül a levélbe,
a hatás nem semleges, hanem **káros**. Egy általános levél unalmas. Egy
magabiztosan **téves** személyre szabott levél hiteltelenné tesz:

> AI: *„Láttam, hogy három telephelyen dolgoznak…"*
> Valóság: egy telephely van, az AI kitalálta.

Ez az ellenőrzés **ingyen van** — nem AI-hívás, csak szövegkeresés.

> Ha a `report --grounding` azt írja, hogy a bukási arány **20% felett** van,
> a modell hallucinál. Olyankor ne menj tovább — másik modell kell.

### Egy cég csak egy ajánlatot kap

Ha egy cégnél többféle ajánlat is indokolt lenne, a program a **legerősebbet**
választja, és a többit nem küldi ki külön levélben. Nem fordulhat elő, hogy
valaki ma „belső rendszert építek" levelet kap, holnap meg „weboldalt készítek".

### 🔒 Vázlat sablonnal nem megy ki levél

Az új kampányok szövege **vázlat**, amíg át nem írod. A program ezért nem
engedi őket kiküldeni — az exportnál ezt fogod látni:

```
kihagyva (JOVA NEM HAGYOTT KAMPANY): 3
  Ezeknek a sablonja meg VAZLAT.
```

Élesítés három lépésben:

1. írd át a szöveget: `cold-email-starter/templates.py`
2. nézd meg: `cd cold-email-starter && python3 preview.py`
3. vedd fel a kampány nevét: `leadgen/contract.py` → `APPROVED_CAMPAIGNS`

---

## 10. folyamat — Hol tartunk?

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

## 11. folyamat — Első beállítás  *(egyszer kell)*

Ha új gépre kerül a projekt:

```bash
# 1. A titkok
cp cold-email-starter/.env.example cold-email-starter/.env   # küldő
# a gyökér .env-be: DATABASE_URL, APIFY_TOKEN, UNSUB_BASE_URL,
#                   OPENAI_API_KEY, ANTHROPIC_API_KEY

# 2. Adatbázis
./leadgen.sh db migrate      # bármikor újrafuttatható
./leadgen.sh db check        # rendben van-e minden tábla

# 3. Levelezés teszt
cd cold-email-starter
python3 -c "import mailer; mailer.check_accounts()"
```

---

## 12. folyamat — AI-szolgáltató váltása

**Mikor:** ha egy másik szolgáltatónál van kereted, vagy olcsóbbat találsz.

A rendszer **három szolgáltatót ismer**, és a **modell nevéből** találja ki,
melyikről van szó. Váltani egyetlen sor átírása a gyökér `.env`-ben:

| Ha a modell neve így kezdődik | Akkor ide megy |
|---|---|
| `gpt-`, `o1`, `o3`, `o4` | OpenAI |
| `claude-` | Anthropic |
| `gemini` | Google |

```bash
# a gyökér .env-ben:
LLM_BULK_MODEL=gpt-5.6-luna      # sok, olcsó hívás (hirdetés-minősítés)
LLM_QUALITY_MODEL=claude-haiku-4-5   # kevés, jó hívás (magyar mondatok)
```

Ehhez a megfelelő kulcs is kell (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
vagy `GEMINI_API_KEY`). **Ha hiányzik, a program megmondja, melyik** — nem
kell találgatnod.

> **A program kódja nem változik váltáskor.** Ezt élesben kipróbáltuk:
> a Geminiről OpenAI-ra váltás után a minősítő, a válasz-értelmező és az
> összehasonlító egyetlen karakterrel sem változott.

---

## 13. folyamat — Modellek összehasonlítása (bake-off)

**Mikor:** opcionálisan, ha modellt váltanál vagy romlik a személyre szabás.

Ez már nem küldési vagy implementációs kapu. A rendszer nem az AI-val dob ki
cégeket: több lehetséges szolgáltatási irányt ment, bizonyíték nélkül pedig
`scored` állapotban tartja a céget. A bake-off azt méri, melyik olcsó modell
ad jobb rangsort és pontosabb idézeteket. A 30 eset útmutatója:
[evals/README.md](evals/README.md).

```bash
./leadgen.sh eval bakeoff --model gemini-2.5-flash-lite --model claude-haiku-4-5
./leadgen.sh eval robustness --model gemini-2.5-flash-lite
```

A `robustness` azt méri, hogy a modell átverhető-e: mi történik, ha valaki a
weboldalába beleírja, hogy „hagyd figyelmen kívül az utasításaidat". Ez nem
elmélet — a scrapelt oldalak szövegét idegenek írják.

---

## 14. folyamat — „Mekkora ez a cég?"  *(árbevétel és létszám)*

**Mikor:** ha egy körben sok új cég jött be, és el kell dönteni, kivel
foglalkozz először.

**Az ötlet:** a magyar cégek éves beszámolói nyilvánosak. Ebből kiderül két
szám: **mennyi az árbevétel** és **hányan dolgoznak ott**. Ez a különbség a
„nagy cég rossz weboldallal" (a legjobb lead, ami létezik) és a „kis cég rossz
weboldallal" (majdnem értéktelen) között.

### ⚠️ Ezt a részt kézzel kell csinálni — és ennek oka van

Megnéztük a hivatalos portált (e-beszamolo.im.gov.hu). **Nem szabad géppel
lekérdezni**, két okból:

- a keresője elé captcha van kötve;
- a Felhasználási Feltételek szerint a szolgáltatás **hitelezővédelmi célra**
  való, és a korlátozás technikai megkerülése **feljelentéssel** járhat.

Ezért a rendszer nem kérdezi le magától. Helyette **listát ír neked**, te
kitöltöd, és visszatöltöd. Egy cég kb. 1 perc.

```bash
./leadgen.sh enrich financials --limit 20
```

Ez kiír egy fájlt ide: `data/financials_worklist.csv`. Nyisd meg (Excel vagy
Numbers is jó), és minden sorhoz töltsd ki:

| Oszlop | Mit írj bele |
|---|---|
| `revenue_huf` | értékesítés nettó árbevétele — **FORINTBAN** |
| `headcount` | átlagos statisztikai állományi létszám |
| `financial_year` | melyik év beszámolója (pl. 2024) |

> ### 🔴 A leggyakoribb hiba: az ezer forint
>
> A beszámoló űrlapja **ezer forintban** mutatja a számokat („adatok E Ft-ban").
> Ha ott 350 000 áll, az **350 millió forint** — ide `350000000`-t írj, nem
> `350000`-et. A rendszer szól, ha valami gyanúsan kicsi, de nem tudja
> kijavítani helyetted.

Ha egy cégnek nincs közzétett beszámolója, **hagyd üresen a sort** — a
következő listában újra elő fog jönni.

Aztán töltsd vissza:

```bash
./leadgen.sh enrich financials --import data/financials_worklist.csv
./leadgen.sh report --economic
```

Egyetlen céget gyorsabban is fel lehet venni:

```bash
./leadgen.sh enrich financials --set pelda.hu --revenue 420000000 --headcount 12 --year 2024
```

### Mi lesz az eredmény

| Érték | Mit jelent |
|---|---|
| 🔥 **HIGH** | 500 M Ft felett vagy 25 fő felett — **+15 pont** |
| ⭐ **MEDIUM** | 100 M Ft felett vagy 5 fő felett |
| **LOW** | ez alatt |

> **A LOW nem kizárás.** A cég bent marad, csak hátrébb kerül a sorban. Aki
> nem került be a listába, azzal sem történik semmi rossz — egyszerűen nincs
> róla adatunk.

A három küszöb üzleti döntés, nem technikai. A gyökér `.env`-ben állítható:
`REVENUE_MEDIUM_HUF`, `REVENUE_HIGH_HUF`, `WEBSHOP_REVENUE_MIN_HUF`.

### Nem kell minden céget lekérned

**Ez az egész folyamat opcionális.** Ha soha nem futtatod le, a rendszer
ugyanúgy működik — az árbevétel csak sorrendet ad.

És ha lefuttatod, akkor sem kell mind a 100 cég. Naponta 20 levél megy ki,
tehát **a sor tetején lévő 20-30 cégről elég adat** — a lista eleve a legjobb
pontszámúakkal kezdődik. A beszámolók évente frissülnek, tehát ez nem
ismétlődő munka: egyszer 20-30 perc, és hetekig nem kell hozzányúlni.

### Van gyorsabb út is — de az fizetős

A portálnak van hivatalos, **csoportos** lekérdezése: kitöltesz egy „Csoportos
beszámoló kérő lap" nevű űrlapot, és elküldöd az `e-beszamolo@mkifk.hu` címre.
Az így kapott fájl egy paranccsal betölthető.

> ⚠️ **Ez költségtérítéses.** Az űrlap első fele számlázási adatokat kér. Az árat
> nem tünteti fel — ajánlatot adnak rá. Viszonyításnak: egy cég pénzügyi
> beszámolója az Opten webshopjában 759 Ft, tehát 30 cég kb. 23 000 Ft — ugyanez
> kézzel 30 perc.

**A javaslatom:** csináld meg előbb kézzel 20 céggel, és abból döntsd el, kell-e
egyáltalán fizetős forrás. Részletek: [TEENDOK.md](TEENDOK.md) 4.5.

---

## 15. folyamat — „Kinőtte a webshopját"  *(8.3)*

**Mikor:** a 14. folyamat után, vagy ha új cégeket dolgoztál fel.

**Az ötlet:** a dobozos webshop-rendszerek (Shoprenter, Unas, Shopify, Wix,
WooCommerce) induláskor kiválóak, de növekedéskor konkrét korlátokba ütköznek.
Ha egy cég **sok pénzt forgat** ilyen platformon, jó eséllyel már ütközik.

Nincs hozzá új gyűjtés: a weboldalt már letöltöttük, az árbevétel a 14.
folyamatból van.

```bash
./leadgen.sh webshop-growth --dry     # először nézd meg
./leadgen.sh webshop-growth           # élesben
./leadgen.sh report --campaign webshop_growth
```

### ⚠️ Amit a rendszer szándékosan NEM csinál

- **Nem hiszi el a kulcsszót.** Ha egy ügynökség weboldalán ott van, hogy
  „Shoprenter webshop készítés", az az **ő szolgáltatásuk**, nem az ő
  rendszerük. Csak akkor számít találatnak, ha a weboldal **tényleg a
  platformról tölti be a fájljait**, és van rajta kosár.
- **Nem írja felül a meglévő kampányt.** Ha a cég már egy másik kampányban
  van, a webshop-irány csak megjegyzésként mentődik el.
- **Nem írja bele az árbevételt a levélbe.** Soha. A levél csak annyit mond,
  hogy melyik platformot látta.

### A hangnem — ez itt a legfontosabb

A sablon **nem mondja, hogy rossz a platformjuk.** Sokan tudatosan és
elégedetten használják, és gyakran igazuk is van. A levél egy konkrét
korlátra kérdez rá, és a megoldás **kiegészítés, nem csere**.

> ### 🔒 Ez a kampány még nem küld levelet
>
> A `webshop_growth` sablon szövege **vázlat** — az én szövegem, nem a tiéd.
> Amíg át nem írod és fel nem veszed a jóváhagyott kampányok közé, ezek a
> leadek **nem kerülnek ki** a `leads.csv`-be. Lépések:
> [TEENDOK.md](TEENDOK.md) 3.9.

---

## 16. folyamat — Az automatikus napi futás  *(12. fázis)*

**Mikor:** egyszer beállítod, utána magától megy.

Eddig minden parancsot te indítottál el. Ettől a fázistól a gép **minden
reggel 7:30-kor** végigcsinálja a gyűjtést, a feldolgozást és az átadást —
neked csak a levelek kiküldése marad.

### Mit csinál magától

Reggel 7:30-kor sorban lefut:

| Lépés | Mit csinál |
|---|---|
| 1. gyűjtés | új cégek a Google Mapsről *(ez pénzbe kerül, napi 50 találat a keret)* |
| 2. feldolgozás | letölti és elolvassa a weboldalukat |
| 3. fejlesztő-keresés | ki készítette az oldalt, él-e még |
| 4. AI-értékelés | ki a jó lead, és mi legyen a levél első mondata |
| 5. webshop-vizsgálat | dobozos platformon van-e a boltjuk |
| 6. visszajelzés | ki válaszolt, ki iratkozott le, mi pattant vissza |
| 7. válasz-besorolás | az AI elolvassa az új válaszokat |
| 8. átadás | megírja a `leads.csv`-t a küldőnek |
| 9. ellenőrzés | van-e baj, amiről szólni kell |

### Amit szándékosan NEM csinál magától

**A levélküldést.** A `sender.py --live` marad a te kezedben.

Ez nem hiányosság, hanem döntés: a kiküldés visszafordíthatatlan, és a levél
**a te nevedben** megy ki. A gép előkészít, te elolvasod, és te küldöd el.

Ugyanígy kézi marad az esti `deliverability.py` is — az a küldés után futtatandó.

### A beállítás

```bash
./leadgen.sh schedule install     # ettől kezdve minden reggel 7:30-kor fut
./leadgen.sh schedule status      # fut-e, és mikor futott utoljára
./leadgen.sh schedule uninstall   # ha mégsem kell
```

Az `install` **nem indít el semmit azonnal** — az első futás másnap reggel lesz.

Ha a géped 7:30-kor alszik, a futás **nem marad el**: felébredés után bepótolja.

### A napi rutinod ezután

```bash
# ── REGGEL ─────────────────────────────────────────────────────
./leadgen.sh report --daily   # a gép már dolgozott — mi a helyzet?
./leadgen.sh review           # ha van bizonytalan cég: TE döntesz

cd cold-email-starter
python3 sender.py --dry       # MI MEGY KI MA? — olvasd el
python3 sender.py --live      # ÉLES KÜLDÉS

# ── ESTE, 17:00 után ───────────────────────────────────────────
python3 deliverability.py     # napi jelentés
cd .. && ./leadgen.sh feedback
```

A `report` és az `export` kikerült a reggeli rutinból: azokat a gép már
elvégezte. A `report --daily` viszont maradt — **ez mutatja meg, mi történt.**

### Ha kézzel akarod lefuttatni a láncot

```bash
./leadgen.sh daily --dry          # mit csinálna? (semmit nem futtat)
./leadgen.sh daily                # az egész lánc, most
./leadgen.sh daily --skip-ingest  # ugyanaz, de a FIZETŐS gyűjtés nélkül
```

### Riasztások — ha baj van, szólni fog

A gép magától fut, tehát ha valami elromlik, senki nem olvassa a kimenetet.
Ezért három dologra figyel, és ezekről **emailt küld a saját címedre**:

| Riasztás | Mit jelent |
|---|---|
| **kézbesítési gond** | túl sok levél pattan vissza, vagy a Google elutasítja a küldést |
| **elfogytak a leadek** | 3 napja nincs kiküldhető cég — valahol elakadt a folyamat |
| **megválaszolatlan érdeklődő** | valaki érdeklődött, és 24 órája nem válaszoltál neki |

Az utolsó a legfontosabb: **ez a legdrágább lead a rendszerben.**

Ugyanezek megjelennek a `./leadgen.sh report --daily` tetején is, és bekerülnek
a `cold-email-starter/data/alerts.log` fájlba.

**Ugyanarról a bajról naponta csak egyszer kapsz emailt.** Ha minden reggel
ugyanaz az üzenet jönne, egy hét múlva szűrőt tennél rá — és akkor a valódi
riasztást sem vennéd észre.

Ha nem érkezik email, a riasztás akkor is megvan a fájlban és a riportban.
Beállítás: `ALERT_EMAIL=sajat@cimed.hu` a gyökér `.env`-ben.

---

# Mi nincs még kész

| Mi hiányzik | Melyik fázis | Mit jelent ez most |
|---|---|---|
| **Webes felület** | 13. | Minden parancssorból megy. Az építés elkezdődött ([WEBUI-TERV.md](WEBUI-TERV.md)): `./leadgen.sh ui` egy rendszerállapot-oldalt mutat, az olvasó API (cégek, riportok, riasztások, válaszok, költségek) már kész a háttérben, de képernyő még nincs hozzá. |

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
| `helyi szuro KIZART: ...` | egy cím nem ment át az ellenőrzésen | ez helyes működés, nem hiba |
| a napi lánc nem futott le | alvó gép vagy hibás beállítás | `./leadgen.sh schedule status` |
| `A(z) ... lepes hibara futott` | egy lépés elakadt, a többi ment tovább | nézd meg a naplót: `cold-email-starter/data/leadgen_daily.log` |
| `a riasztasi email NEM ment ki` | az értesítés nem ért célba | a riasztás ettől megvan: `data/alerts.log` és `report --daily` |
| `arbevetel gyanusan kicsi` | valószínűleg ezer forintot írtál | szorozd meg 1000-rel a `revenue_huf` mezőt |
| `NINCS ILYEN CEG` az importnál | a sor nem párosítható | töltsd ki a `company_id` vagy a `normalized_domain` oszlopot |
| `nincs letoltott oldal` a 8.3-nál | a cég weboldala még nincs feldolgozva | `./leadgen.sh enrich` |
| `EMAIL_VALIDATION=full, de nincs REOON_API_KEY` | hiányzik a kulcs | csak az ingyenes szűrő fut, a küldés megy |

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
