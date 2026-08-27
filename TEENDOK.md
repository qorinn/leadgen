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

### 3.1 Két API kulcs + EGY SOR ÁTÍRÁSA a `.env`-ben

**A Gemini helyett OpenAI-t használunk** (2026-08-22, a te döntésed alapján).
A Gemini-integráció **nincs törölve** — egy sorral bármikor visszakapcsolható.

A **gyökér** `.env`-be:

```
OPENAI_API_KEY=sk-...          # platform.openai.com → API keys
ANTHROPIC_API_KEY=sk-ant-...   # console.anthropic.com → API keys
```

**⚠️ És írd át ezt a meglévő sort** — a `.env`-edben jelenleg a Gemini modell
szerepel, ami felülírja az új alapértelmezést:

```
LLM_BULK_MODEL=gpt-5.6-luna    # ← ezt cseréld (most: gemini-2.5-flash-lite)
```

| Kulcs | Mire kell | Mennyi hívás |
|---|---|---|
| `OPENAI_API_KEY` | hirdetések minősítése | sok, olcsó modell |
| `ANTHROPIC_API_KEY` | válasz-értelmezés + magyar mondatok | kevés, jó modell |

**Ha a modellnév nem stimmel**, a program beszédes hibával megáll (nem
csendben), és kiírja, melyik kulcs hiányzik. Ha a `gpt-5.6-luna` nem érhető el
a fiókodban, szólj — a `.env`-ben bármelyik OpenAI modellre átírható
(`gpt-5.6-terra`, `gpt-5-nano`, ...), a kód nem változik.

**Visszatérés a Geminire** bármikor, egy sorral:
`LLM_BULK_MODEL=gemini-2.5-flash-lite` + `GEMINI_API_KEY=...`

### 3.2 Anthropic kulcs — részletek

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

### 3.3 A 30 teszteset (bake-off) — *opcionális, nem blokkol semmit*

Ezt nem kell elvégezned az alkalmazás következő szakaszai előtt. A rendszer már
nem használ bináris „jó lead / rossz lead" AI-kaput: több lehetséges irányt
ment el, és csak a biztos kizárásokat tiltja. A bake-off akkor hasznos, ha később
két modell közül szeretnéd kiválasztani azt, amelyik jobb idézeteket és
relevánsabb sorrendet ad. Formátum: [evals/README.md](evals/README.md).

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

### 3.6 🔒 A két új kampány élesítése *(10. fázis)*

**Két kampány sablonja készen áll, de VÁZLAT** — és a rendszer **nem is
engedi kiküldeni őket**, amíg te jóvá nem hagytad. Ez nem formalitás: az
export élesben blokkolta őket, amikor teszteltem.

| Kampány | Kinek szól | Hangnem |
|---|---|---|
| `dead_dev` | akinek eltűnt a webfejlesztője | magázó |
| `ops_pain` | aki adminisztrátort keres (Excel + munkalap) | magázó |

**Élesítés három lépésben, kampányonként:**

```bash
# 1. írd át a szöveget a saját hangodra
#    cold-email-starter/templates.py  ->  ops_pain_cold, ops_pain_follow_up_1, ...

# 2. nézd meg, hogy fest
cd cold-email-starter && python3 preview.py

# 3. vedd fel a nevét
#    leadgen/contract.py  ->  APPROVED_CAMPAIGNS
```

**Amíg ezt nem teszed meg, ezekből nem megy ki levél.** A 10 ügynökségi
leaded ettől függetlenül megy tovább.

### 3.7 ⚠️ DÖNTSD EL: melyik modell írja a mondatokat  ← *ez most aktuális*

**Lefuttattam az első éles AI-tesztet.** Az eredmény: **a mondatok jelenlegi
formájukban nem küldhetők ki**, és ez nem a te hibád — a terv szerint ilyenkor
a prompton kell javítani, amit meg is tettem. De a **modellválasztás a tiéd.**

Amit ugyanazon a bemeneten mértem (3-3 mondat):

| | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| ár 1000 mondatra | **~$0,60** | ~$3,00 |
| nyelvhelyesség | *„fektetek hangsúlyt"*, *„Az H-Control"* | rendben |
| tartalmi hiba | *„sok cégnél ez elég hanyag szokott lenni"* (sértő!) | *„a honlapon szereplő leírásból"* (rossz forrás) |

A **forrás-hibát javítottam** (a prompt most megkapja, honnan az idézet).
Utána a Sonnet ezt adta:

> *„A Profession.hu-n megjelent álláshirdetésükben a szerviz részleg napi
> működésének koordinálását nevezték meg a pozíció egyik feladataként."*

**Készítettem hozzá vak összehasonlítót**, mert ezt látni kell, nem elhinni:

```bash
./leadgen.sh eval sentences --limit 9 \
  --model gpt-5.6-luna --model claude-haiku-4-5 --model claude-sonnet-5
```

Ez ugyanarra a 9 valódi leadre generál mondatot mindhárom modellel, **véletlen
sorrendben összekeverve**, és a megfejtés a fájl végén van elrejtve. Így nem
befolyásol, hogy melyiket melyik írta.

**A már elkészült lista:** [evals/mondatok-2026-08-24.md](evals/mondatok-2026-08-24.md)
Olvasd végig, jelöld be mondatonként, melyiket küldenéd ki — **és csak utána**
nézd meg a megfejtést. A terv szerint érdemes másnap nekiülni.

**A skálázott költség (mérve, nem becsülve):**

| modell | 1 mondat | 333 lead/nap | havonta |
|---|---|---|---|
| `gpt-5.6-luna` | $0,00016 | $0,05 | **$1,64** |
| `claude-haiku-4-5` | $0,00073 | $0,24 | **$7,28** |
| `claude-sonnet-5` | $0,00298 | $0,99 | **$29,72** |

> ⚠️ **A mondat leadenként készül egyszer**, és mind a 3 levélben ugyanaz.
> Napi 1000 **levél** tehát ~333 új **lead** — nem 1000 mondat. Az 5x szorzó
> így havi ~$22 különbséget jelent, nem havi százakat.

**A döntésed (2026-08-25): `gpt-5.6-luna`** — legolcsóbb és a legtermészetesebb.

```
LLM_QUALITY_MODEL=gpt-5.6-luna
```

> ⚠️ **Egy dolgot mérlegelj, mielőtt átírod.** A `LLM_QUALITY_MODEL` nem csak
> a mondatokat írja — a **válasz-értelmezés** is ezt használja
> (`classify-replies`), és ott az `unsubscribe` / `negative` címke
> **véglegesen** kizár egy céget.
>
> A mondatokat vakon összehasonlítottad, a válasz-értelmezést nem. Ha
> óvatos akarsz lenni, a kettő szétválasztható: a mondatok mehetnek Lunával,
> a válasz-értelmezés maradhat Claude-on. Szólj, és beállítom külön
> kapcsolóval — most közös.

---

### ⚠️ FRISSÍTVE a vak teszted után (2026-08-24)

**A visszajelzésed alapján két dolgot átírtam**, és mindkettő megváltoztatja
a képet:

**1. A prompt most a MUNKÁRÓL ír, nem a hirdetésről.** Igazad volt: a régi
prompt parafrazeálásra ösztönzött, és egy szóval sem mondta meg a modellnek,
hogy te mit csinálsz — így nem tudta, melyik szálat emelje ki.

**2. Egy mondat helyett 2-3 mondat** (max. 60 szó). A terv az egy mondatot a
Tier B szintre szánta; a Tier A-ra maga is „konkrét tény + konkrét probléma"-t
ír elő, ami egy mondatba nem fér bele.

**3. A költségkép is megváltozott.** Az új, hosszabb prompt átlépte az
Anthropic cache-küszöbét — de **csak a Sonnetnél** (a Haiku minimum
cache-mérete magasabb). Mérve, 333 lead/nap mellett:

| modell | cache | havonta |
|---|---|---|
| `claude-haiku-4-5` | nem kap | ~$13,2 |
| `claude-sonnet-5` | **meleg** | ~$15,5 *(1 mondat)* / ~$28 *(2-3 mondat)* |

**A 3x-os listaár a gyakorlatban ~17%-ra olvadt.** A költség-ellenérv a
Sonnettel szemben lényegében megszűnt.

**Új vak lista kell** — a régi már az előző prompttal készült:

```bash
./leadgen.sh eval sentences --limit 9 \
  --model gpt-5.6-luna --model claude-haiku-4-5 --model claude-sonnet-5
```

> A Haiku *„hanyag szokott lenni"* mondata jól mutatja, miért kell ez az emberi
> kör: nyelvtanilag jó, de **sértő** — és semmi nem jelezte volna automatikusan.

### 3.8 Olvass el 20 AI-generált mondatot *(a `score` nagyobb futása után)*

```bash
./leadgen.sh report --grounding
```

Ez kiírja a levélbe kerülő mondatot **és az idézetet, amiből készült**.
A terv kritériumai: természetes a szórend? nincs tükörfordítás-szag?
nem hízeleg? tényleg abból indul ki, ami az idézetben van?

> **Amelyik mondatot nem küldenéd ki a saját neveddel, az bukott.** Olyankor
> nem a modell a hibás, hanem a prompt (`leadgen/prompts.py`) — szólj, és
> javítom.

Ha a bukási arány **20% felett** van, a modell hallucinál — akkor ne
élesítsd a kampányt, hanem futtassuk le a bake-offot másik modellel.

---

### 3.9 🔒 A `webshop_growth` kampány élesítése *(11. fázis)*

**Ugyanaz a folyamat, mint a 3.6-nál, egy harmadik kampányra.** A 8.3
(„kinőtte a webshopját") sablonja készen áll, de **vázlat** — nem megy ki
belőle levél, amíg át nem írod.

| Kampány | Kinek szól | Hangnem |
|---|---|---|
| `webshop_growth` | dobozos webshop-platformon futó, nagyobb forgalmú cégnek | magázó |

**⚠️ Ennél a szövegnél két dologra vigyázz** — mindkettő benne van a
sablonban kommentként is:

1. **Ne mondd, hogy rossz a platformjuk.** Sokan tudatosan és elégedetten
   használják, és gyakran igazuk is van. A támadás azonnal védekezést vált ki.
   A levél egy konkrét korlátra kérdez rá, és a megoldás **kiegészítés, nem
   csere** — az sokkal kisebb elköteleződés, tehát könnyebben mond igent.
2. **Az árbevétel SOHA nem kerülhet a levélbe.** A szám nálunk csak
   rangsorol. Leírva azt üzenné, hogy a címzett pénzügyi adatait bogarásszuk.

```bash
# 1. írd át:  cold-email-starter/templates.py -> webshop_cold, webshop_follow_up_1, ...
# 2. nézd meg: cd cold-email-starter && python3 preview.py
# 3. vedd fel: leadgen/contract.py -> APPROVED_CAMPAIGNS
```

## 🟢 4. Külső szolgáltatások — a következő fázisokhoz

### 4.1 ✅ Apify token — *megvan, működik*

Ellenőrizve 2026-08-22: a token érvényes, a havi keret $10, ebből eddig
**$0,57** fogyott.

### 4.2 ✅ Actor előteszt — *elvégezve, ÁTMENT*

A terv 0.3 pontja kötelezővé tette. Lefuttattam helyetted, mert a kérdés
ténykérdés volt, nem ízlés:

```
actor    : solidcode/profession-hu-scraper
kérdés   : megvan-e a hirdetés TELJES szövege?
válasz   : ✅ IGEN — 1978 karakter, de csak `includeDetails=True` mellett
hiányzik : ❌ a cég weboldala. Sehol nem szerepel.
költség  : $0,005
```

**Ha ránéznél te is:** a nyers válasz itt van: `/tmp/profession_proba.json`.

### 4.3 A domain-feloldás fizetős — döntsd el, mennyit szánsz rá

Mivel a Profession.hu nem adja meg a weboldalt, a cégeket a Google Maps-ből
kell feloldani: **~$0,005/cég**, mért találati arány **4-ből 3**.

Egy 200 hirdetéses backfill nagyságrendileg **$1-2**. A `--limit` a fék:

```bash
./leadgen.sh resolve-domains --dry          # megmutatja, kiket kérdezne le
./leadgen.sh resolve-domains --limit 20     # élesben
```

Jelenleg **8 cég** vár feloldásra. Nem sürgős — nem vesznek el.

### 4.4 Reoon kredit *(7. fázis — KÉSZ, csak a kulcs hiányzik)*

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

### 4.5 📄 Árbevétel-adat: mi ingyenes és mi nem *(11. fázis — OPCIONÁLIS)*

> **Ez az egész rész opcionális.** Ha soha nem futtatod le, a rendszer
> változatlanul működik. Az árbevétel csak **sorrendet** ad — nem zár ki senkit.

**Nem kell minden céget lekérned.** Naponta 20 levél megy ki, tehát a sor
tetején lévő **20-30 cégről** elég adat. A rendszer eleve a legjobb pontszámúakat
teszi a lista elejére. A beszámolók évente frissülnek, tehát ez nem ismétlődő munka.

**Három út van, és csak az első ingyenes:**

| Út | Ár | Mikor éri meg |
|---|---|---|
| **Kézi lekérés a portálon** | **0 Ft** | most ez a helyes választás |
| **Csoportos igénylés** (e-beszámoló) | egyedi árajánlat, **fizetős** | 50+ cégnél |
| **Opten / Bisnode API** | nem publikus, ajánlatkérés | havi több száz cégnél |

> ⚠️ **A csoportos igénylés FIZETŐS.** A hivatalos űrlap első fele számlázási
> adatokat kér (számlakérő neve, számlázási cím, adószám, számlafogadó e-mail),
> tehát költségtérítéses szolgáltatás. Az árat nem tünteti fel — ajánlatot adnak.
> Viszonyításnak: az Opten webshopjában **egy** pénzügyi beszámoló **759 Ft**
> (2026-08-27-i listaár) — 30 cég így kb. 23 000 Ft, kézzel ugyanez 30 perc.

#### A) A kézi út — kezdd ezzel

```bash
./leadgen.sh enrich financials --limit 20     # listát ír data/financials_worklist.csv-be
# kitöltöd (cégenként ~1 perc), majd:
./leadgen.sh enrich financials --import data/financials_worklist.csv
./leadgen.sh report --economic
```

Részletes leírás: [HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) 14. folyamat.

**Ha ez megvan, ebből döntsd el, kell-e egyáltalán fizetős forrás.** Lehet, hogy
20 cég után kiderül, hogy neked ez az adat nem sokat mond — akkor megspóroltál
egy előfizetést.

#### B) A csoportos igénylés — csak ha a volumen indokolja

1. Nyisd meg: <https://e-beszamolo.im.gov.hu/beszamolo_allomany_ertekesitese>
2. Töltsd le a **„Csoportos beszámoló kérő lap"** űrlapot (`.docx`).
3. Add meg a szűrési szempontokat, és jelöld be, mely adatokra tartasz igényt.
   **Nekünk ez az öt kell** (mind szerepel az igényelhető mezők listájában):
   - Értékesítés nettó árbevétele
   - Átlagosan foglalkoztatottak száma a tárgyévi üzleti évben
   - Mérlegfőösszeg
   - Adózott eredmény
   - **Cég adószáma** ← ez külön fontos, lásd lent
4. Küldd el: **e-beszamolo@mkifk.hu** (kérdés: +36 (1) 795 5111, 3. menü → 3. almenü)
5. A kapott fájl egy paranccsal betölthető:

```bash
./leadgen.sh enrich financials --import <a kapott fajl>.csv
```

> **Miért kérd az adószámot is:** jelenleg **0 cégnek van adószáma** a
> rendszerben, a párosítás pedig `company_id → adószám → domain` sorrendben
> megy. Cégnév alapján szándékosan soha nem párosítunk — egy téves névegyezés
> rossz céghez írna árbevételt, és onnan az már egy levélbe kerülő téves állítás.
> Ha a kapott fájlban csak cégnév van, szólj, és írok hozzá egy párosító lépést.

### 4.6 📊 Kalibráld az árbevételi küszöböt *(a 4.5 vagy az első kézi kör UTÁN)*

Ez **üzleti döntés, nem technikai** — a terv is így írja. Az alapértelmezés:

| Küszöb | Alapérték | Mit jelent |
|---|---|---|
| `REVENUE_MEDIUM_HUF` | 100 000 000 | efölött MEDIUM |
| `REVENUE_HIGH_HUF` | 500 000 000 | efölött HIGH (+15 pont) |
| `HEADCOUNT_MEDIUM` / `HEADCOUNT_HIGH` | 5 / 25 | a létszám önmagában is emel |
| `WEBSHOP_REVENUE_MIN_HUF` | 300 000 000 | efölött érdekes a 8.3 („kinőtte") |

Nézd meg az első 20-30 találatot (`./leadgen.sh report --economic`), és tedd
fel a kérdést: **ettől a mérettől várható, hogy fizet egy egyedi
fejlesztésért?** Ha nem, emeld; ha túl kevés cég marad, csökkentsd. A gyökér
`.env`-ben állítható, kódot nem kell módosítani.

---

## 🟣 4.6 Automatikus napi futás — *a kód kész, ez a te két lépésed*

A 12. fázis elkészült: a gyűjtés, feldolgozás és átadás mehet magától
minden reggel 7:30-kor. A küldés szándékosan a kezedben marad.

### 4.6.1 Kapcsold be az ütemezést

```bash
./leadgen.sh schedule install
./leadgen.sh schedule status     # ellenőrzés
```

Ez **nem indít el semmit azonnal** — az első automatikus futás másnap reggel
lesz. Bármikor kikapcsolható: `./leadgen.sh schedule uninstall`.

**Amit tudnod kell róla:**

- A lánc **naponta ~$0,22-t költ** az Apify-gyűjtésre (50 találat).
  Ha ezt sokallod, a `leadgen/schedule.py` `lepesek()` függvényében a
  `--max-results 50` szám csökkenthető.
- Ha a géped 7:30-kor alszik, a futás **nem marad el** — felébredés
  után bepótolja. (Ezért launchd, és nem cron.)
- A napló: `cold-email-starter/data/leadgen_daily.log`.

### 4.6.2 Add meg a riasztási email-címed

A gyökér `.env`-be:

```
ALERT_EMAIL=sajat@cimed.hu
```

Enélkül a riasztások **nem vesznek el** — bekerülnek a
`cold-email-starter/data/alerts.log` fájlba, és megjelennek a
`./leadgen.sh report --daily` tetején. Csak az email-értesítés marad el.

Három dologról fogsz szólást kapni:

| Riasztás | Miért fontos |
|---|---|
| kézbesítési gond | a domain reputációja romlik — ezt időben kell látni |
| 3 napja nincs kiküldhető lead | valahol elakadt a tölcsér |
| **24 órája megválaszolatlan érdeklődő** | **ez a legdrágább lead a rendszerben** |

### 4.6.3 Egy hét múlva: döntsd el, mehet-e a küldés is automatikusan

Most a `sender.py --live` kézi. Ez a javasolt indulás: amíg nem látod
stabilnak a válaszarányt és a bounce-okat, olvasd el, mi megy ki.

Ha egy-két hét után a számok rendben vannak, a küldés is betehető a láncba.
**Ez tudatos döntés legyen, ne csúszás** — onnantól a gép a te nevedben ír
embereknek, anélkül hogy előtte elolvasnád.

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
