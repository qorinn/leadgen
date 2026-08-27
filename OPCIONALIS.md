# Opcionális módosítások

> Élő lista. Semmi nem sürgős — a rendszer mindegyik nélkül működik.
> Ha eszedbe jut valami, szólj, és felveszem ide. Ha kérsz egyet, megcsinálom.
>
> A becslés **agent-munkaidő**, nem a te időd.

---

## A) Már megbeszéltük

### A1. ~~Gemini → GPT csere~~ — ✅ **KÉSZ (2026-08-22)**

**Elkészült, a becsült ~30 perc tartott.** Az OpenAI a BULK tier
alapértelmezése; a **Gemini-integráció érintetlenül megmaradt** a
`llm.py`-ban, egy `.env` sorral visszakapcsolható.

Amit a csere igényelt (pontosan annyi, amennyit becsültem):
egy új függvény (`_call_openai`), a névfelismerés bővítése, egy kulcs a
configban. **A hívó oldalak — `score.py`, `classify.py`, `evals.py` — egyetlen
karakterrel sem változtak.**

Egy dolgot menet közben javítani kellett: a hibaüzenetek bedrótozva kérték a
`GEMINI_API_KEY`-t. Modellváltás után ez rossz kulcsot kért volna. Most a
**providerből** vezetjük le (`llm.kulcs_hianyzik`), tesztsorral védve.

<details><summary>Az eredeti leírás</summary>

**Miről szól:** jelenleg két AI-szolgáltató van bedrótozva — a Claude (válasz-
értelmezés) és a Gemini (nagy volumenű leadszűrés, még nincs éles feladata).
A Gemini helyére bármikor jöhet GPT.

**Mennyire bonyolult:** kevéssé. A kód a **modell nevéből** ismeri fel, melyik
szolgáltatóé, ezért csak ennyi kell:

- egy új függvény a GPT híváshoz (~40 sor, ugyanolyan alakú, mint a meglévő
  Gemini-hívás)
- három egysoros kiegészítés: névfelismerés, API kulcs, elérhetőség-ellenőrzés

A többi kód **nem változik** — a válasz-értelmező, a bake-off, a riport
ugyanúgy fut tovább.

**Javaslatom:** ne cseréld le vakon, hanem **tegyük be a GPT-t versenyzőnek.**
Az eredeti terv eleve jelöltként sorolja fel (`gpt-5-nano`, `gpt-5-mini`), és
a beépített összehasonlító (`eval bakeoff`) pont arra való, hogy ne
találgassunk: ugyanaz a 30 teszteset, három modell, a mérés dönt.
A terv ártáblázata szerint a `gpt-5-nano` a legolcsóbb jelölt.

> Ehhez OpenAI API kulcs kell, és a 30 teszteset ([TEENDOK.md](TEENDOK.md) 3.3).

</details>

---

### A2. A leiratkozó oldal kivétele az Analyticsből  `~10 perc (a weboldal repójában)`

**A gond:** a leiratkozó URL tartalmazza a személyes tokent
(`/leiratkozas/<token>`), és a Google Analytics ezt `page_path`-ként elküldi a
Google-nek. Ez egy **személyhez köthető azonosító** — méghozzá pont azon az
egy oldalon, ahová azok érkeznek, akik kifejezetten békét kértek.

A cookie-banner miatt valószínűleg nem jogsértő (a mérés csak hozzájárulás
után indul), de fölösleges kockázat. Mellékesen a bannert is el kell tüntetnie
a látogatónak, mielőtt leiratkozhat — rossz élmény pont ott.

**Megoldás:** a `/leiratkozas/*` útvonal kizárása a mérésből, vagy a token
levágása a küldött útvonalból. Ez a **weboldal repójában** van, nem itt.

---

### A3. Az érvénytelen leiratkozó link 404 helyett 200  `~5 perc (a weboldal repójában)`

Jelenleg az érvénytelen token **404-et** ad. Szemantikailag rendben, de
levélbe ágyazott linknél a 200 biztonságosabb: egyes céges link-ellenőrzők a
404-et „törött link"-ként jelölik, ami rontja a levél megítélését.
A megjelenített oldal maga jó.

---

### A4. `UNSUB_BASE_URL` a `www.` verzióra  `~1 perc`

A `paladi-web.hu` 301-gyel átirányít a `www.paladi-web.hu`-ra. Működik (az
űrlap relatív, a POST jó helyre megy), de egy fölösleges ugrás van a
levélben lévő linkben. A `.env`-ben:

```
UNSUB_BASE_URL=https://www.paladi-web.hu/leiratkozas
```

Utána egy `./leadgen.sh export` kell, hogy a `leads.csv` frissüljön.

---

### A5. Inbox placement mérés  `~2 óra + előfizetés`

Seed-listás mérés: elküldöd ugyanazt a levelet több szolgáltatónál lévő
teszt-fiókoknak, és megnézik, melyik fülbe esett (GlockApps, MailReach,
Inbox Monster).

**Most nem éri meg:** a szerkezeti javítások után a próbaleveled a fő
postaládába érkezett. Akkor térj vissza rá, ha a válaszarány indokolatlanul
leesik, vagy új sablon/kampány indul.

Ingyenes változat: ugyanaz a levél egy privát Gmailre, egy céges
Workspace-címre és egy outlook.com-ra.

---

### A6. Hard bounce után újrapróbálás másik címmel  `~1 óra`

**Jelenleg:** ha egy cím visszapattan, a céget **nem** próbáljuk újra másik
címmel. Ez tudatos döntés (2026-08-20): a bounce az egyetlen hiba, ami
visszamenőleg is kárt okoz, és a második cím ugyanabból az elavult forrásból
származna.

**Mikor térjünk vissza rá:** ha már van ügyfél, és a lead-utánpótlás válik
szűk keresztmetszetté. Akkor `rejected` helyett `ready` + cooldown jöhet, de
csak olyan második címre, amit a Reoon `valid`-nak mért.

---

### A7. Fizetős céginformációs adatforrás  `~3 óra + előfizetés`

**A helyzet:** a 11. fázisban kiderült, hogy az e-beszámoló portál automatikus
lekérdezése jogilag nem járható (captcha + „hitelezővédelmi cél" a
Felhasználási Feltételekben). Marad a kézi lista és a hivatalos, e-mailben
igényelt csoportos lekérdezés (TEENDOK.md 4.5).

**Amit lehetne:** van fizetős magyar céginformációs API (Opten, Bisnode/Dun &
Bradstreet, Céginfo). Ezek szerződéssel, gépi lekérdezéssel adják ugyanezt az
adatot — árbevétel, létszám, adószám, jogi cégnév.

**Mit adna:** ez oldaná meg azt is, hogy **jelenleg 0 cégnek van adószáma** a
DB-ben, és hogy a Maps-leadek 78%-ánál csak márkanevet ismerünk, nem jogi
cégnevet — ami a beszámoló-kereséshez kellene.

**A kód készen áll rá:** a `financials.ment()` egy `forras` paramétert kap
(`manual` / `csv_import` / `api:<nev>`). Egy adapter beírása után minden
más — az `economic_value`, a bónusz, a 8.3 metszet — változatlanul működik.

**Mit tudunk az árról (2026-08-27):** az API-előfizetéseknek **nincs publikus
listaára** — Opten és Bisnode is ajánlatkérésre dolgozik. Viszonyítási pont a
darabáras webshop: egy pénzügyi beszámoló **759 Ft**, egy hatályos cégadatlap
1 320 Ft. Előfizetésben ez darabonként olcsóbb, de csak ajánlatból derül ki.

**Mikor éri meg:** ha havonta több száz céget kell minősíteni. 20-30 leadnél
a kézi út olcsóbb — és az e-beszámoló csoportos igénylése (szintén fizetős,
TEENDOK.md 4.5) is olcsóbb lehet nála.

### A8. Webshop-célzott Maps engine  `~30 perc (adat, nem kód)`

**A helyzet:** a 8.3 („kinőtte a webshopját") kód kész és mért, de **a
jelenlegi adathalmazon 0 találat** — a listánk marketingügynökségekből és
álláshirdető cégekből áll, azok nem webshopok.

**Amit lehetne:** egy új `EngineDef` blokk a `leadgen/engines.py`-ban
webshop-jellegű keresésekkel („webáruház", „online bolt", + iparágak). Az
iparág adat, nem kód — a scrapelés, enrichment, export változatlan marad.

**Mit adna:** a 8.3-nak valódi bemenetet. Enélkül a 8.3 csak akkor talál
valamit, ha véletlenül webshopos cég kerül be másik forrásból.

## B) Amit én javaslok

### B1. ~~A „stop" mintafelismerő elhagyása~~ — **ELVETVE (2026-08-22)**

**Felhasználói döntés: marad.** Az indok, amiért felmerült: az AI
válasz-értelmező látszólag átvette a szerepét. Az indok, amiért mégis marad:
az AI **pénzbe kerül és kézzel indul**, a mintafelismerő pedig **ingyen fut,
minden küldés előtt, magától**.

A kettő nem verseng: a mintafelismerő az egyértelmű eseteket kapja el
azonnal és ingyen, az AI pedig **mögötte** áll a sorban, és a maradékot érti
meg. Ez a sorrend spórol pénzt.

*Ez a döntés a mai szűkítés után érvényes: a listából kikerültek a bizonytalan
minták (`nem érdekel`, `köszönöm, nem`), és csak az egyértelműek maradtak.*

### B2. Postafiókonkénti napi keret  `~1,5 óra`

**A jelenlegi korlát** (mérve 2026-08-22): a küldő két helyen kezeli a
fiókokat, és mindkettő egyenlően bánik velük:

```python
limits.daily_cap()  = cap × a fiókok SZÁMA      # a keret duplázódik
mailer.next_account() = körbejár, egyenletesen   # a levél 50-50%-ban oszlik
```

Vagyis egy második postafiók felvétele **azonnal 20-ról 40-re emeli** a napi
keretet, és a vadonatúj, hideg fiók **az első napon 20 levelet küldene**.

**Miért fáj ez:** így nem lehet egy új domaint lassan bemelegíteni a rendszeren
belül. A [DOMAIN-BEMELEGITES.md](DOMAIN-BEMELEGITES.md) ezért külön példányt
javasol (`cp -r cold-email-starter cold-email-warmup`) — az működik, csak
kicsit kényelmetlen.

**Amit ez a módosítás adna:** fiókonkénti `cap` és fiókonkénti rámpa, hogy a
régi domain teljes sebességgel mehessen, miközben az új napi 3-mal indul.

**Mikor éri meg:** amikor tényleg két domainen küldesz párhuzamosan. Addig a
külön példány olcsóbb megoldás.

### B3. Webes felület  `~1 nap`

A terv 13. fázisa, opcionálisként. Napi 20-40 lead kézzel is átnézhető a
`review` paranccsal. Akkor éri meg, ha a napi átnézés 15 percnél többet visz.

---

## C) A te ötleteid

*(ide kerülnek, amiket menet közben mondasz)*
