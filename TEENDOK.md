# Teendők — amit nekem kell csinálnom

> Élő lista. Ha kész vagy egy sorral, húzd ki (`- [x]`).
> Az agent munkája nem szerepel itt — csak az, amit **ember** tud elvégezni.

**Állapot: 2026-08-22 (szombat).** A rendszer épül, az első éles levél még nem ment ki.

---

## 🔴 1. Ami MOST blokkol — enélkül nem indul el a rendszer

### 1.1 Nézd át a 10 bizonytalan céget

```bash
./leadgen.sh review
```

10 cég vár emberi döntésre. A gép azért nem döntött, mert a kizáró kulcsszó
(pl. „webfejlesztés") gyakran **ügyfél-referenciából** jön, nem a cég saját
szolgáltatásaiból. Nyisd meg az oldalt, és döntsd el.

```bash
./leadgen.sh review --approve <domain>   # jó lead
./leadgen.sh review --reject  <domain>   # versenytárs / nem kell
```

### 1.2 Ellenőrizd 5 véletlen `ready` céget kézzel

Nyisd meg 5 cég weboldalát a `leads.csv`-ből. **Tényleg marketingügynökség?
Tényleg nincs saját fejlesztésük? Tényleg jó az email cím?**
Ha ötből egy is hibás, szólj — a kulcsszólistát kell javítani, nem továbbmenni.

### 1.3 Döntsd el: `press@mito.group` menjen-e ki

A Mito az egyik legnagyobb magyar digitális ügynökség, **saját fejlesztői
csapattal** — valószínűleg versenytárs, nem partner. A cím ráadásul
sajtókapcsolati. Javaslatom: húzd ki.

```bash
./leadgen.sh review --reject mito.group --reason competitor
```

### 1.4 Olvasd el mind a 10 levelet

```bash
cd cold-email-starter && python3 preview.py
```

**Ez az utolsó visszafordítható pont.** 10 perc. Amit ott látsz, az megy ki.

### 1.5 KÜLDD KI A 10 LEVELET  ← *ez a mérföldkő*

```bash
cd cold-email-starter
python3 sender.py --dry      # utolsó ellenőrzés
python3 sender.py --live     # ÉLES
```

Küldési ablak: **hétköznap 8:00–17:00**. Hétvégén nem küld.

---

## 🟠 2. Amit sosem teszteltünk élesben — a küldés UTÁN, sorban

Ezek mind **valódi elküldött levelet igényelnek**, ezért nem lehetett őket
korábban kipróbálni. A rendszer visszacsatolási iránya (ki válaszolt, ki
pattant vissza) így még **egyszer sem futott éles adaton**.

### 2.1 Guards éles teszt — a válasz-figyelés

A `guards.py` olvassa a postaládát, és eldönti, ki válaszolt. Ez a védelem
állítja le a follow-upokat. **Soha nem futott valódi válaszon.**

```bash
cd cold-email-starter && python3 guards.py
```

Amit látnod kell: `scanned=<szám> replies=<szám>`. Ha `replies=0`, miközben
tudod, hogy valaki válaszolt — szólj, az hiba.

> ⚠️ **Fontos korlát:** a guards **csak azoktól** veszi figyelembe a választ,
> akiknek a `sender.py` ténylegesen küldött (`sent.csv`). A `preview.py
> --send-to` teszt-levélre adott válaszodat **figyelmen kívül hagyja**.
> Ezért nem tudtad eddig kipróbálni.

### 2.2 A „stop" válasz kipróbálása

**Csak akkor működik, ha valódi címzettként kaptad a levelet.** Ha rendes
tesztet akarsz, szólj: felveszem a saját címedet valódi leadként, a
`--live --limit 1` csak neked küld, és utána végigkövetjük a láncot.

Hol látszik, ha működött:

| Hol | Mit keress |
|---|---|
| `cold-email-starter/data/do-not-contact.csv` | új sor, `unsubscribe_request` okkal |
| `cold-email-starter/data/replies.csv` | a válasz szövege elmentve |
| `./leadgen.sh report` után | a TILTOLISTA szekcióban |

### 2.3 A leiratkozó gomb kipróbálása VALÓDI levélből

Én `curl`-lel teszteltem végig (megerősítő oldal → gomb → adatbázis → a lead
eltűnt az exportból), de **te még nem kattintottál rá egy valódi levélből.**

> ⚠️ A `preview.py --send-to` teszt-levelében a link **szándékosan nem
> működik** — különben a saját tesztelésed egy valódi céget iratna le.
> Az „Érvénytelen link" oldalra visz, és ez a helyes viselkedés.
>
> Valódi teszthez ugyanaz kell, mint a 2.2-höz: egy éles levél magadnak.

### 2.4 Napi postaláda-olvasás  ← *a leggyakoribb bukási pont*

**A küldés után minden nap.** Egy ügynökségi válasz 24 órán belül megérdemel
egy emberi választ. Ez az a pont, ahol a rendszer működik, de az ügyfél
mégis elveszik.

### 2.5 Napi zárás a küldési ablak után

```bash
cd cold-email-starter && python3 deliverability.py   # exit 1 = riasztás, nem hiba
cd .. && ./leadgen.sh feedback
```

---

## 🟡 3. AI réteg — a kód kész, ez hiányzik

### 3.1 Anthropic (Claude) API kulcs

`console.anthropic.com` → API keys → a **gyökér** `.env`-be:

```
ANTHROPIC_API_KEY=...
```

Ez kell a válasz-értelmezéshez. Amíg nincs, a válaszokat kézzel nézed át —
10 levélnél ez teljesen rendben van.

### 3.2 Az első 20 automatikus besorolás átnézése

```bash
./leadgen.sh classify-replies --dry     # ELŐSZÖR mindig szárazon
./leadgen.sh classify-replies
./leadgen.sh report --replies
```

Ha egyet is rosszul sorolt `unsubscribe`-ként, **azonnal szólj** — az
visszafordíthatatlan.

### 3.3 A 30 teszteset (bake-off)  — *nem sürgős, de a 9-10. fázis kapuja*

Formátum és útmutató: [evals/README.md](evals/README.md). ~40 perc.
Ez dönti el, melyik olcsó modellre építsük a nagy volumenű leadgyűjtést.
**A 10 határeset a te üzleti döntésed** — ezt AI nem tudja helyetted.

### 3.4 A `dead_dev` kampány szövegének átírása *(8. fázis)*

Elkészült a „halott fejlesztő" kampány **vázlata** a
`cold-email-starter/templates.py`-ban (`deadev_cold`, `deadev_follow_up_1`,
`deadev_follow_up_2`). A szöveg a terv javaslatából indul — **olvasd el és
írd át a saját hangodra**, mielőtt élesbe menne.

Miért más, mint az ügynökségi: ott partnert keresel (tegező, kollegiális),
itt egy KKV-t szólítasz meg, akinek problémája van (magázó). A vázlat már
magázó, de a megfogalmazás a tiéd.

**Ez a kampány addig nem indul el**, amíg nincs benne lead — lásd lent.

### 3.5 A DEAD találatok kézi átnézése *(amikor lesz találat)*

```bash
./leadgen.sh report --signal dead_dev
```

**A terv kemény szabálya:** *„Ha a footer-kredit nem egyértelmű, a lead
inkább essen ki, mint hogy rossz nevet írj egy emailbe."*

A levél szó szerint tartalmazza a fejlesztő nevét. A riport kiírja a footer
eredeti szövegét — abból döntsd el, jó-e a találat. Nézz át **10 DEAD
találatot**, mielőtt az első levél kimegy ebből a kampányból.

> **Most nincs mit átnézni:** a jelenlegi 60 céged ügynökség, ők maguk
> készítik a weboldalukat. Ez a jel a hétköznapi KKV-knál működik, akik a
> 9. fázissal érkeznek.

---

## 🟢 4. Külső szolgáltatások — a következő fázisokhoz

### 4.1 Apify token *(9. fázis — Profession.hu leadgyűjtés)*

Van már fiókod a Google Maps-hez. Ugyanaz a token kell, `APIFY_TOKEN` néven
a gyökér `.env`-ben. **Ellenőrizd, hogy még érvényes-e.**

### 4.2 Apify actor előteszt *(kötelező, a terv 0.3 pontja)*

Mielőtt bármit építenék rá: futtasd le a Profession.hu actort **egyetlen kis
lekérdezéssel**, és nézd meg **saját szemmel** a nyers kimenetet.
**A kritikus mező: van-e benne a hirdetés teljes szövege.** Ha nincs, az egész
9-10. fázis másik forrást igényel — és ezt jobb most tudni, mint utána.

### 4.3 Reoon kredit *(7. fázis — KÉSZ, csak a kulcs hiányzik)*

**A kód kész és tesztelt.** Az ingyenes szűrő **már most is fut** minden
exportnál — ez már ki is szűrt hibás címeket. A fizetős fokozat opcionális.

**Ha bekapcsolod:** `reoon.com` → fiók + kredit (~$11,90 / 10 000 cím,
kb. **0,04 Ft / cím**). Aztán a gyökér `.env`-be:

```
EMAIL_VALIDATION=full
REOON_API_KEY=...
```

**Az első futás után KÖTELEZŐ ellenőrizned a cache-t** — ez pénz:

```bash
./leadgen.sh export --dry     # 1. futás: N lekérdezés
./leadgen.sh export --dry     # 2. futás: 0 lekérdezés, N cache-találat
```

Ha a második futásnál **nem 0** a lekérdezés, azonnal állítsd vissza
`local_only`-ra és szólj — akkor a cache nem működik, és minden exportnál
újra fizetnél ugyanazokért a címekért.

**Amit figyelj még:** ha bekapcsolás után sok lead esik ki „nem tudott
dönteni" indokkal, akkor a küszöb túl szigorú a jelenlegi listádra.
A `.env`-ben állítható: `TIER_A_SCORE=70` → pl. `55`. Az export mindig
kiírja, ki miért maradt ki, tehát ez látható lesz, nem néma.

---

## 🔵 5. Később — ne most

- [ ] **DMARC szigorítás.** Most `p=none` (csak jelent). 2-3 hét múlva, ha a
      jelentések tiszták: `p=quarantine`.
- [ ] **Teszt-maradék takarítása.** 1-1 `.invalid` sor van a `sent.csv`,
      `bounces.csv` és `do-not-contact.csv` fájlokban a fejlesztésből.
      Ártalmatlanok. Ha zavarnak, kézzel törölhetők.
- [ ] **Analytics a leiratkozó oldalon.** A Google Analytics jelenleg látja a
      leiratkozó URL-t, amiben benne van a személyes token.
      Részletek: [OPCIONALIS.md](OPCIONALIS.md).
- [ ] **Tartalék domain regisztrálása és öregítése.**
      **Teljes útmutató: [DOMAIN-BEMELEGITES.md](DOMAIN-BEMELEGITES.md).**
      A regisztráció az egyetlen lépés, amit **nem lehet visszamenőleg**
      megcsinálni, és ~5000 Ft/év — ezért érdemes most elintézni, akkor is,
      ha a bemelegítés csak szeptemberben indul.
      Sorrend: domain kiválasztás → regisztráció → weboldal/átirányítás →
      DNS (MX, SPF, DKIM, DMARC) → **30 nap pihenés** → bemelegítés.
