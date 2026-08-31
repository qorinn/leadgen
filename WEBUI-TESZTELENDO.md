# Webes felület — amit később konkrétan érdemes leellenőrizni

Ez a lista azokat a pontokat gyűjti, ahol a [WEBUI-TERV.md](WEBUI-TERV.md) és a
tényleges kód (vagy a védelmi tesztek) között ütközés volt egy fázis
megvalósítása közben. Mindegyiknél döntés született, hogy tudjunk haladni —
de ezek olyan döntések, amiket érdemes utólag, saját szemmel is megnézni.

Fázisonként, időrendben.

---

## F2 — Váz, navigáció, közös komponensek

### 1. A cég-státusz jelvény (`StatusBadge`) színe nem a Pythonból jön

**Mi történt:** a terv szerint a `StatusBadge` a `/api/meta`-ból kapná a
státusz **címkéjét ÉS a színét** is. A valóságban a `/api/meta` csak címkét
ad, színt nem — az sehol nincs megírva a Python oldalon.

**Mit döntöttünk:** a szín a frontendben, a státusz **sorrendje** alapján
generálódik (egy fix, ciklikus színsor), nem a státusz nevéből. Így egy adott
státusz mindig ugyanolyan színt kap, de ezt a színt senki nem "jelentette be"
Python oldalról — csak a sorrendből következik.

**Mit tesztelj később:** nyisd meg a Cégek listát (F4 után), és nézd meg,
hogy a színek jól elkülönítik-e egymástól a státuszokat, és hogy logikus-e
a sorrendjük (pl. a korai státuszok és a "kész" állapot vizuálisan
elkülönül-e). Ha nem tetszik, dönthettek úgy is, hogy a szín mégis
Python-oldalon (a `report.py`-ban) legyen definiálva, és a `/api/meta`
bővüljön vele.

---

### 2. A chart-könyvtár (Bklit) szavai összeütköznek a védelmi teszttel

**Mi történt:** van egy teszt (`tests/test_webui_contract.py`), ami
megakadályozza, hogy valaki véletlenül bemásoljon egy üzleti listát (pl.
státuszneveket) a TypeScript kódba. Ez a teszt elkezdett hibázni, amikor
telepítettük a chart-könyvtárat (Bklit) — mert a könyvtár **saját, a
cégadatoktól teljesen független** belső kódjában is előfordul a "ready" és a
"hold" szó (ezek animációs állapotnevek, nem cég-státuszok).

**Mit döntöttünk:** a teszt mostantól nem vizsgálja a `components/ui/` és a
`components/charts/` mappát — ezeket nem mi írjuk, hanem a `shadcn add`
parancs telepíti, és egy frissítés úgyis felülírná őket.

**Mit tesztelj később:** ha valaha kézzel írsz kódot ebbe a két mappába
(nem kellene, de ha mégis), a védelmi teszt **nem fogja észrevenni**, ha
ott bekerül egy valódi státusznév. Érdemes időnként átfutni, hogy tényleg
csak generált/telepített fájlok vannak-e ott.

---

## F3 — Irányítópult

### 3. A védelmi teszt tévesen jelzett hibát a `daily.review` típusú kódrészleteknél

**Mi történt:** az irányítópult kódja olyan mezőket olvas ki, mint
`daily.replied` vagy `daily.review` — ezek egy már **típusosan ellenőrzött**
API-válasz mezői (ha a Python oldalon eltűnne egy ilyen mező, a fordítás
azonnal hibát adna, nem csendben félremenne). A védelmi teszt viszont nem
tudta megkülönböztetni ezt egy "bemásolt listától", és hibázott.

**Mit döntöttünk:** a tesztet pontosítottuk, hogy a `pont.mező` formájú
hivatkozásokat (pl. `daily.review`) ne jelezze hibának, csak a szabad
szövegben (idézőjelben) álló szavakat.

**Mit tesztelj később:** ha egy jövőbeli fázisban valaki egy `.review`
formájú, de **mégis hibás** (bedrótozott, nem API-ból jövő) kódrészletet ír,
ezt a teszt mostantól **nem fogja elkapni** — mert kivételt kapott a
`.mező` forma. Érdemes kódolvasáskor külön figyelni erre.

---

### 4. A "Rád vár" gomb egy nyers státusz-nevet tartalmaz a linkjében

**Mi történt:** az irányítópulton az "emberi döntésre vár" sorra kattintva a
felület a `/cegek?status=review` címre visz — ez a `"review"` szó szó
szerint bele van írva a linkbe, mert ez egy konkrét, ismert szűrő-érték.

**Mit döntöttünk:** ez engedélyezett mintaként lett elfogadva (a védelmi
teszt kivételt kapott rá), mert ez egy **fix, egyetlen** hivatkozás egy
már ismert mezőnévre — nem egy teljes lista bemásolása. Ez a minta várhatóan
újra elő fog kerülni F4-ben és F5-ben (pl. "Cégek szűrése kész státuszra"
gomb).

**Mit tesztelj később:** az F4 fázis elkészült, és a `/cegek?status=review`
link **valóban szűr** a Cégek oldalon (a `?status=` query-paramétert a lista
oldal induláskor beolvassa és a Státusz szűrőbe teszi). Nyisd meg az
Irányítópultot, kattints az "emberi döntésre vár" sorra, és nézd meg, hogy
a Cégek lista tényleg csak a `review` státuszú cégeket mutatja-e.

---

### 5. (apró hiba, magától javítva) Két egymásba ágyazott `<main>` címke

**Mi történt:** a felület váza (F2-ben épült sidebar) már ad egy `<main>`
HTML címkét, és az irányítópult (F3) is berakott egy másikat — ez érvénytelen,
kettős `<main>` volt az oldalon.

**Mit döntöttünk:** ez nem terv-ütközés volt, hanem egyszerű hiba, amit
észrevétel után rögtön javítottunk (a belső `<main>`-t egy sima `<div>`-re
cserélve).

**Mit tesztelj később:** nincs teendő, csak informálva legyél — ha valaha
akadálymentesítési (accessibility) eszközzel nézed az oldalt, ez már nem
fog problémát jelezni.

---

## F4 — Cégek: lista és részletnézet

### 6. Az `email` oszlop hiányzott a Cégek listából

**Mi történt:** a terv szerint a Cégek lista oszlopai közt szerepel az
"email", de a már megépített (F1) `/api/companies` lekérdezés nem
kapcsolódott a `contacts` táblához — egy cégnek több kontaktusa/emailje is
lehet, tehát nem volt egyértelmű, melyiket mutassa a lista.

**Mit döntöttünk:** bővítettük a lekérdezést — cégenként a "legjobb"
(legszemélyesebb típusú, legújabb) kontaktus emailjét mutatja, ugyanazzal a
sorrenddel, amit a `report.py` már használ (`personal` > `generic` > `role`
> `unknown`). Ez módosítja a korábban lezártnak tekintett F1 API-t (új
`email` mező a `CompanyListItem`-en), de visszafelé kompatibilis módon.

**Mit tesztelj később:** nyisd meg a Cégek listát, és néhány sornál
hasonlítsd össze az ott mutatott emailt a részletnézet "Kapcsolatok"
szekciójával — legyen ugyanaz, ha egy cégnek csak egy kontaktusa van, és a
személyes/generic/role sorrend szerint helyes, ha több van.

---

### 7. A gazdasági érték (LOW/MEDIUM/HIGH) szűrő nincs a `/api/meta`-ban

**Mi történt:** a Cégek lista "Gazdasági érték" szűrőjéhez kellett a három
lehetséges érték (LOW/MEDIUM/HIGH), de ez sehol nincs listaként a Python
oldalon — sem a `/api/meta`-ban, sem egy névvel ellátott konstansban
(`financials.py` és `report.py` is csak nyers szövegként használja).

**Mit döntöttünk:** ez egy zárt, adatbázis-szinten kikényszerített halmaz
(CHECK constraint a `companies` táblán), nem egy növekvő üzleti lista, mint
a státuszok vagy kampányok — ezért a három érték a frontendbe került, fix
listaként.

**Mit tesztelj később:** ha valaha egy negyedik gazdasági-érték kategória
kerül be (új migráció + DB constraint módosítás), ezt a frontend listát
kézzel kell frissíteni — a `/api/meta` erről nem fog tájékoztatni.

---

### 8. A pénzügyi mezők eltűntek, mert a Postgres `numeric` oszlopok szövegként jönnek

**Mi történt:** a cég-részletnézet Pénzügy szekciója (és pár másik, pl.
`financial_bonus`) néha üresen jelent meg, pedig volt adat mögötte. Az ok: a
Postgres `numeric` (tizedestört) oszlopok — `revenue`, `balance_total`,
`profit`, `financial_bonus`, és az AI-szögek `score`/`confidence` mezői — a
"nyers" (`select *`, típus nélküli) API-válaszban **szövegként** jönnek
(pl. `"0"`, nem a szám `0`), mert a szerver így őrzi meg a pontosságukat.
A frontend viszont csak a valódi szám típust ismerte fel, a szöveges "0"-t
üresnek nézte.

**Mit döntöttünk:** a frontend szám-felismerő segédfüggvénye (`asNum`)
mostantól a szöveges számokat is felismeri, nem csak a valódi szám típust.

**Mit tesztelj később:** nyisd meg egy olyan cég részletnézetét, aminek van
árbevétele vagy `financial_bonus` értéke (pl. a `financials.py`-jal frissített
cégek), és nézd meg, hogy a Pénzügy szekció tényleg megjeleníti-e a
számokat, nem csak akkor, ha nullák.

---

### 9. Az üres listás szekciók (Kapcsolatok, Outreach, stb.) teljesen eltűntek "nincs adat" üzenet helyett

**Mi történt:** ha egy cégnek nincs kapcsolattartója, a "Kapcsolatok"
szekció **egésze** (a címével együtt) eltűnt az oldalról — pedig a terv
"minden mező, ami nem null, jelenjen meg" elve mellett az is hasznos
infó, hogy MEGNÉZTÜK és tényleg nincs kapcsolattartó, nem csak hogy a
szekció hiányzik (ami összetéveszthető egy hibával).

**Mit döntöttünk:** a Kapcsolatok, Címkék, Outreach és Nyers-források
szekciók mostantól mindig megjelennek, és üres listánál egy kifejezett
"Nincs kapcsolattartó." / "Nincs címke." / "Még nem indult outreach." /
"Nincs rögzített forrás." szöveget mutatnak. A Suppression szekció
KIVÉTEL — az a terv szerint is csak akkor jelenik meg, ha van suppression
bejegyzés ("ha van: ok, megjegyzés, dátum").

**Mit tesztelj később:** nyiss meg egy nagyon friss (frissen scrapelt,
még nem dolgozott fel) céget, és nézd meg, hogy tényleg minden szekció
látszik-e, akár "nincs adat" üzenettel is — egyik se tűnjön el nyomtalanul.

---

### 10. A "csak localhost" védelmi teszt tévesen jelzett hibát a cég-domain linkjénél

**Mi történt:** a részletnézet fejlécében a cég domainjére mutató, kattintható
link (`https://${domain}`) elbuktatta a "csak localhost, nincs kitett port"
védelmi tesztet — a teszt bármilyen `https://` kezdetű szöveget megnéz, és
ez szó szerint `https://`-vel kezdődik a forráskódban.

**Mit döntöttünk:** ez a szabály valójában a SAJÁT szerverünk címére
vonatkozik (ne hívjunk ki nem-localhost API-t) — nem arra, hogy a felület
kifelé, a scrapelt cégek saját weboldalára linkeljen (ez a terv szerint
kifejezetten elvárt: "domain (kattintható)"). A tesztet pontosítottuk: egy
olyan cím, ami futáskor, adatbázisból származó értékből épül fel (a forrás
`${domain}` jelölést tartalmaz), nem lehet bedrótozott szerver-cím, ezért
ezeket kihagyja.

**Mit tesztelj később:** nyiss meg egy céget, aminek van domainje, és
kattints a domain linkre a fejlécben — a cég saját weboldala nyíljon meg új
fülön, ne valamilyen belső cím.

---

### 11. A szűrő legördülők a nyers értéket mutatták címke helyett

**Mi történt:** a Cégek lista szűrőiben (Státusz, Kampány, stb.) minden
legördülő a "__minden__" technikai kulcsot mutatta az "Összes" felirat
helyett, mert a használt UI-könyvtár (Base UI Select) alapból a nyers
értéket írja ki, nem a hozzá tartozó címkét.

**Mit döntöttünk:** ez egyszerű hiba volt, amit észrevétel után rögtön
javítottunk (kézzel visszakeresi a legördülő a kiválasztott érték
címkéjét).

**Mit tesztelj később:** nincs teendő, csak nézd meg, hogy minden legördülő
tényleg a jól olvasható címkét mutatja-e (pl. "kész (exportálható)"), nem a
nyers kulcsot.

---

## F5 — Emberi döntések (az első írási műveletek)

### 12. (apró hiba, magától javítva) A megerősítő ablak érvénytelen HTML-t adott, ha a következmény összetett volt

**Mi történt:** az elutasítás-megerősítő ablak (Cégek részletnézet) egy
szöveget ÉS egy legördülőt is mutat (az elutasítás okát) — de a
`MegerositoDialog` a következményt mindig egy `<p>` (bekezdés) HTML-elembe
tette, és egy `<div>`-et vagy másik `<p>`-t egy `<p>`-be tenni érvénytelen
HTML, amit a böngésző hydration-hibával jelzett.

**Mit döntöttünk:** ez nem terv-ütközés volt, hanem egyszerű hiba, amit
észrevétel után rögtön javítottunk (a `MegerositoDialog` mostantól `<div>`-et
használ `<p>` helyett, hogy bármilyen tartalom biztonságosan beleférjen).

**Mit tesztelj később:** nyisd meg a Cégek részletnézeten az "Elutasítás"
gombot, és nézd meg, hogy a szöveg és az ok-legördülő rendesen megjelenik-e,
konzolhiba nélkül.

---

### 13. A CSV-letöltés endpoint és a "review"/"suppressed" szavak megint elakasztották a védelmi teszteket

**Mi történt:** két különböző dolog bukott el egyszerre.

Egyrészt a `/api/financials/worklist` egy CSV-fájlt ad vissza (nem JSON-t),
ezért nem lehet neki Pydantic `response_model`-je — a védelmi teszt viszont
minden `GET`-től megkövetelte azt.

Másrészt az "üzleti szó" védelmi teszt most a `ReviewActions` komponens
nevében, a `review-actions.tsx` fájl import-útvonalában, egy `/api/review/...`
route-stringben és a fülváltó "suppressed" fül-azonosítójában is elakadt —
holott egyik sem cégadat, csak kód-szintű elnevezés, ami véletlenül
egyezik egy státusznévvel (ugyanaz a probléma, mint a Bklit "ready"/"hold"
szava F2-ben).

**Mit döntöttünk:**
- A `response_model`-teszt kivételt kapott azokra a `GET`-ekre, amik nem
  `dict`-et adnak vissza (pl. `PlainTextResponse` egy fájlletöltésnél).
- Az "üzleti szó" teszt mostantól **csak az idézőjeles/sablon
  string-literálok tartalmát** vizsgálja, nem a teljes fájlszöveget — egy
  komment vagy egy azonosító neve (`ReviewActions`) soha nem lehet "másolt
  lista", csak egy ténylegesen használt string-érték. Az import-útvonalakat
  és a saját API-route-stringeket (`./...`, `@/...`, `/api/...`) is
  kivettük, mert azok kód-hivatkozások, nem adatok.
- Emellett a "suppressed" fül-azonosítót átneveztük ("auto-versenytars"-ra),
  és az elutasítás-ok mezőnek megszűnt az előre kiválasztott
  "manual_block" alapértéke (most kötelező explicit választás) — ez NEM
  csak a teszt megkerülése, hanem valódi UX-javítás is: a felhasználó
  tudatosan válasszon okot, ne csússzon át egy alapértelmezésen.

**Mit tesztelj később:** ha egy jövőbeli fázisban valaki egy VALÓDI
státusz-listát másol be TypeScriptbe, de azt egy importútvonalba vagy
kommentbe rejti, ezt a teszt **nem fogja elkapni** — ez a pontosítás
kifejezetten a kód-hivatkozásokat (útvonalak, azonosítók) zárja ki, magát a
"csak string-literálban keresünk" elvet nem gyengíti tovább.

---

### 14. A terv saját ellenőrző parancsa nem "megy vissza" úgy, ahogy a kommentje mondja

**Mi történt:** a WEBUI-TERV.md F5 ellenőrzése szó szerint ezt írja elő:

```
# egy teszt-domainen, majd vissza:
review --reject <domain> --reason manual_block
review --approve <domain>
```

Éles domainen (`contentplus.hu`) kipróbálva: az `--approve` **nem** hozza
vissza a céget — azt írja ki, hogy "Nincs jóváhagyható review/hold/competitor
cég ezen a domainen." Ez nem hiba, hanem **szándékos védelem**: a
`review.approve()` csak a `review`/`hold`/`rejected` állapotot vagy az
automatikusan felismert **versenytárs**-kizárást (`reason='competitor'`)
oldja fel — egy kézi `manual_block` elutasítást direkt NEM enged
egyetlen paranccsal visszavonni (`leadgen/review.py` docstringje: "Mas
suppression-ok... ezen a fuggvenyen at sem oldhatok fel veletlenul").

**Mit döntöttünk:** nem a kódot javítottam — ez a viselkedés helyes és
szándékos. Kétszer futtattam le a teljes ellenőrzést, hogy tényleges,
visszaigazolt kört kapjak:
- CLI: `review --reject contentplus.hu --reason manual_block` → utána kézzel
  kellett visszaállítani (mert a fenti okból az `--approve` nem tette).
- API: `POST /api/review/{id}/reject {"reason":"competitor"}` majd
  `POST /api/review/{id}/approve` → ez **valóban** visszaállt (mert a
  `competitor` ok feloldható), és egy második `approve` helyesen 409-et
  adott ("a cég nincs jóváhagyható állapotban"). A cég státusza és
  `status_note`-ja mindkét esetben (CLI és API) bájtra ugyanazt az
  eredményt adta ugyanarra a bemenetre — ez volt a terv tényleges
  kérdése ("a felületről végzett művelet ugyanazt az adatbázis-állapotot
  eredményezze, mint a CLI").
- A céget a teszt végén kézzel visszaállítottam az eredeti állapotára
  (`status='review'`, az eredeti `status_note`) — csak az `updated_at`
  időbélyeg tér el az eredetitől, tartalmi adat nem sérült.

**Mit tesztelj később:** ha a WEBUI-TERV.md-t valaha frissítik, érdemes ezt
a kommentet pontosítani (`--reason competitor` legyen a példában, vagy a
komment mondja ki, hogy `manual_block` esetén kézi visszaállítás kell) —
most félrevezető, mert azt sugallja, bármelyik `--reject` visszafordítható
egyetlen `--approve` paranccsal.

---

## F6 — Futtatások és élő napló

### 6. A `daily --skip-ingest` a tervben ingyenes, a valóságban AI-t költ

**Mi történt:** a WEBUI-TERV.md F6 katalógus-táblája így sorolja fel:

```
| daily (teljes lánc)   | 💰 igen (ingest) | ~$0,22 |
| daily --skip-ingest   | nem              | —      |
```

A `leadgen/schedule.py` `lepesek()` viszont a `score` és a
`classify-replies` lépést is tartalmazza — mindkettő AI-hívás. Az ingest
elhagyása tehát az **Apify**-költséget veszi le, az AI-t nem.

**Mit döntöttünk:** a `daily --skip-ingest` a katalógusban **fizetősként**
szerepel (💰 AI jelvény, megerősítő párbeszéd), nem ingyenesként. Egy
„nem kerül pénzbe" felirat, ami után jön egy AI-számla, rosszabb, mint egy
fölösleges megerősítés.

**Mit tesztelj később:** ha zavaró, hogy a napi lánc kétszer is
megerősítést kér, a helyes megoldás nem a jelölés levétele, hanem egy
`--skip-ai` kapcsoló a láncban — akkor a jelölés is igaz lesz.

---

### 7. A `~$0,22`-es becslés nem szerepel a felületen

**Mi történt:** a terv `~$0,22`-t ír a `daily` sorába. Ez a szám sehol
nincs a kódban: a lánc ingest-lépése `--max-results 50`, ami
50 × $0,005 = **$0,25** Apify-költség, plusz egy előre nem becsülhető
AI-rész.

**Mit döntöttünk:** a felület nem a terv számát írja ki, hanem kiszámolja
azt, amit tud (`schedule.lepesek()` kerete × `pricing.APIFY_TALALAT_USD`),
és külön kimondja, hogy az AI-rész tokenenként számlázódik, tehát előre nem
becsülhető. Ez a terv saját szabálya: *„ne találj ki számot; ha ismeretlen,
írd ki, hogy ismeretlen."* Ha a lánc kerete valaha változik, a felület
becslése magától követi — tesztsor őrzi (`tests/test_webui_jobs.py`).

**Mit tesztelj később:** ha valaha kalibrálod a napi keretet, nézd meg, hogy
a Futtatás oldal `daily` kártyáján tényleg az új szám jelenik-e meg.

---

### 8. Az Apify egységára eddig négy helyen volt kézzel leírva

**Mi történt:** a `$0,005 / találat` szám a `sources/maps.py`-ban, a
`sources/profession.py`-ban és két CLI súgószövegben szerepelt külön-külön.
A felület költség-párbeszédének is kellett — ez lett volna az ötödik.

**Mit döntöttünk:** a szám átkerült a `leadgen/pricing.py`-ba
(`APIFY_TALALAT_USD`, forrással és dátummal, ahogy a modellárak), és a
`maps.py` / `profession.py` onnan olvassa. A két CLI súgószöveg (`--help`)
szövegében maradt a `~$0.005` — az egy mondat, nem számítás.

**Mit tesztelj később:** ha az Apify árat emel, egy helyen kell átírni, de a
két `--help` szöveget is érdemes utánavezetni.

---

### 9. Két ESLint-hiba marad a Futtatás oldalon — a repó meglévő mintája miatt

**Mi történt:** a `npm run lint` a `useEffect(betolt, [betolt])` mintára
hibát ad (`react-hooks/set-state-in-effect`). Ugyanez a hiba megvan a
korábbi fázisok fájljaiban is (`app/page.tsx`, `cegek/suppressed-lista.tsx`,
`cegek/page.tsx`, `adat-tabla.tsx`) — összesen 39 hiba a projektben, ebből
a legtöbb a telepített chart-könyvtárban.

**Mit döntöttünk:** az új fájlok a **meglévő** mintát követik, nem vezettünk
be külön adatbetöltési stílust egyetlen oldal kedvéért. A
`npx tsc --noEmit` és a `npm run build` tisztán lefut.

**Mit tesztelj később:** ha egyszer eldöntitek, hogy a betöltés
`useSyncExternalStore`-ra vagy egy adatlekérő könyvtárra (SWR / TanStack
Query) áll át, azt egyszerre kell megtenni minden oldalon — nem fázisonként.

---

## F7 — Küldés (kétlépcsős)

### 10. Az időablak nincs benne a terv válasz-alakjában

**Mi történt:** a WEBUI-TERV.md F7 pontosan megadja a `/api/send/preview`
válaszát: `token`, `lejar`, `levelek[]`, `mai_keret`, `terv_meret`. Az
időablak (`limits.in_send_window()`) nincs köztük. Márpedig az ablakon kívül
— hétköznap 8–17 órán kívül, vagy hétvégén — a `sender.py --live` lefuttatja
a védelmi kört, majd `exit 0`-val kilép **anélkül, hogy bármit kiküldene**.

**Mit döntöttünk (felhasználói döntés, 2026-08-30):** a válasz két mezővel
bővült, `ablak_nyitva` és `ablak_ok`. Mindkettő a `limits.in_send_window()`
két visszatérési értéke, újraszámolás nélkül. A felület így már az
előnézetnél kiírja, hogy most nem menne ki semmi.

**Mit tesztelj később:** ha a WEBUI-TERV.md F7 JSON-példáját frissítitek,
vegyétek fel ezt a két mezőt is, hogy a terv és a kód ne csússzon szét.

---

### 11. A token hash-e a levél TÖRZSÉT is fedi, nem csak a tárgyát

**Mi történt:** a terv így fogalmaz: *„A token a terv tartalmi hash-e
(címzettek + fokok + tárgyak)."* A `templates.py` viszont a felhasználóé, és
az előnézet után is bármikor átírható. Ha a törzs nem része a hash-nek, egy
tárgy-változás nélküli sablonszerkesztés után **más szöveg menne ki, mint
amit az ember jóváhagyott** — és a token érvényes maradna.

**Mit döntöttünk:** a hash a törzset is tartalmazza. Ez szigorítás, nem
lazítás: a token pontosan azt fedi le, amit az ember a képernyőn látott.
Kifelé a token továbbra is egy átlátszatlan string, tehát az API alakja nem
változott. Tesztsor őrzi (`tests/test_webui_send.py`).

**Mit tesztelj később:** a hash **sorrend-érzékeny** is. Ez szándékos (a terv
rangsorolt és a napi keretnél elvágott lista, tehát más sorrend = más terv),
de ha valaha hamis elutasítást tapasztalsz változatlan listán, itt kezdd a
keresést.

---

### 12. Az előnézet a védelmi kör (guards) LEFUTÁSA ELŐTTI tervet mutatja

**Mi történt:** a `sender.py --dry` alapból lefuttatja a guardsot. Az viszont
IMAP-ot nyit és **ír** (tiltólista, bounce-napló) — egy előnézetnek nem
szabad írnia, és nem is várakoztathatja a felhasználót egy postafiók
beolvasására.

**Mit döntöttünk:** az előnézet guards nélkül készül, és a felület ezt ki is
írja: küldéskor a guards lefut, és a listát csak **szűkítheti** (aki közben
válaszolt, leiratkozott vagy visszapattant, kimarad). Ezért az ellenőrzés is
a `sender.py --dry --skip-guards` kimenetéhez hasonlított.

**Mit tesztelj később:** ha egyszer több levél megy ki naponta, érdemes lehet
egy „védelmi kör futtatása most" gombot adni az előnézet mellé — de az már
írna, tehát külön megerősítést érdemelne.

---

### 13. ⚠️ Az ellenőrzés 3. lépése a tervben leírt formában NEM működik

**Mi történt:** a WEBUI-TERV.md F7 ellenőrzése ezt írja elő:

```
# 3. kérj előnézetet, majd futtass egy exportot, majd küldj -> ELUTASÍTVA
```

Ezt szó szerint követve **a küldés nem lett elutasítva, hanem elindult egy
éles futás.** Nem a kapu hibázott: az `export` szándékosan újraírja a
`leads.csv`-t a **folyamatban lévő** leadekkel együtt (CLAUDE.md), és mivel
nem volt új `ready` lead, a fájl bájtra ugyanaz maradt. A terv tehát tényleg
nem változott, a hash egyezett, és a szerver helyesen engedte tovább.

**Nem ment ki levél**, mert vasárnap volt: a küldő lefuttatta a védelmi kört
(0 válasz, 0 leiratkozás, 0 bounce — nem írt sehova), majd `Nem kuldunk:
hetvege` üzenettel kilépett. A `sent.csv`, a `do-not-contact.csv` és a
`bounces.csv` változatlan. **Ez szerencse volt, nem a teszt érdeme.**

**Mit döntöttünk:** a 3. lépést egy **homokozó küldő-könyvtárban**
futtattuk le: szintetikus `.invalid` leadek, és **nincs `.env`**, tehát a
`sender.py` már a védelmi kör előtt `exit 1`-gyel megáll — ott egy éles
küldés strukturálisan lehetetlen, nem naptárfüggő. Ott a valódi terv-változás
(egy lead kikerül) helyesen 409-et adott, a friss token pedig helyesen
kinyitotta a kaput.

**Mit tesztelj később / mit javítsunk a terven:** a 3. lépés szövege
félrevezető. Helyette olyan műveletet kell írni, ami **tényleg** megváltoztatja
a tervet — például `review --reject <domain>` egy sorban álló leadre, vagy egy
export, ami után tényleg más a `leads.csv`. Amíg ez nincs javítva, ezt a
lépést **soha ne futtasd az éles küldő ellen** hétköznap 8 és 17 óra között.

---

## F8 — Válaszok és riasztások

### 14. Az F1-ben megépített `/api/replies` hiányos volt a saját fázisához képest

**Mi történt:** a `GET /api/replies`-t és a `ReplyItem` sémát még az F1
fázis építette meg, "minden GET egyben" elven. Az F8 terve viszont a
`reply_events` tábla **négy** olyan mezőjét is előírja ("Részletek: a teljes
szöveg és az AI indoklása", illetve a lista-oszlopok közt "modell"), amiket
az F1-es `select` nem hozott ki: a `body` (teljes szöveg) és a `model`
oszlop egyáltalán nem szerepelt sem a lekérdezésben, sem a Pydantic
modellben, és a cég-azonosító (`company_id`) sem — csak a név és a domain.

**Mit döntöttünk:** kibővítettük az F1-ben megépített router-t és sémát
(`webui/api/routers/replies.py`, `webui/api/schemas.py`) a hiányzó mezőkkel,
ahelyett hogy egy párhuzamos, kézzel írt lekérdezést tettünk volna az F8
oldalba. Ez nem terv-módosítás, hanem egy korábbi fázis hiányosságának
pótlása — a `reply_events.body` és `.model` oszlop már az 1. és a 6.
szakasz óta létezik a DB-ben, csak a webui F1 nem exportálta.

**Mit tesztelj később:** ha egy jövőbeli fázis (pl. F9 — Riportok) egy
korábban megépített `/api/...` végpontot bővít, első lépésként nézd meg,
hogy az F1 "minden GET egyben" refaktorja tényleg kihozta-e az adott
fázishoz kellő MINDEN mezőt — a WEBUI-TERV.md fázis-leírásai néha
részletesebbek, mint amit az F1 idején elő lehetett látni.

### 15. A "kiemelt" válasz-osztályok (interested/other) nem írhatók be a frontendbe

**Mi történt:** a terv szerint a felület külön kiemeli az `interested`
(24 órás óra) és az `other` (bizonytalan) besorolású válaszokat. A
`tests/test_webui_contract.py::test_a_frontend_nem_drotoz_be_uzleti_listat`
viszont minden `report._REPLY_ORDER`-beli kulcsot (köztük az
`interested`-et) tilt a TypeScript string-literáljaiban — ezt a tesztet még
az F2 fázis írta, előre védve a jövőbeli fázisokat, F8-at is beleértve.

**Mit döntöttünk:** a `/api/meta` `valasz_osztalyok` tömbjét két új, Python
oldalon számolt boolean mezővel bővítettük (`surgos`, `attekintendo` —
lásd `leadgen/report.py` `_REPLY_SURGOS` / `_REPLY_ATTEKINTENDO`). A
frontend ezt a két flaget olvassa ki soronként, sosem magát a
besorolás-kulcsot hasonlítja `"interested"`-hez vagy `"other"`-hoz — így a
kiemelés szabálya (melyik besorolás sürgős) Pythonban marad, a teszt zöld,
és ha a szabály valaha változik (pl. a `negative` is sürgőssé válik),
elég a `report.py`-t módosítani.

**Mit tesztelj később:** ha egy jövőbeli fázis (riportok, chartok) egy
besorolás- vagy státusz-kulcs szerint akarna csoportosítani vagy színezni a
frontendben, ne a kulcsot írd be — bővítsd a megfelelő `/api/meta` listát
egy szerep-flaggel, ahogy itt történt.

---

## F9 — Riportok és chartok

### 16. A Bklit `BarYAxis` NEM függőleges oszlopdiagramra való

**Mi történt:** a terv szerint a Tölcsér és a Gazdasági érték nézet
"oszlop" (bar) charttal jelenik meg. A `webui/app/components/charts/`
alatt (F2-ben telepítve) van egy `BarXAxis` (kategória-címkék alul) és egy
`BarYAxis` komponens is — utóbbit érték-tengelynek néztem, és mindkettőt
felraktam a `<BarChart>` alá. Élesben a `BarYAxis` a képernyő **bal
szélén, a szidebar fölött** jelenítette meg ugyanazokat a kategória-
címkéket, amiket a `BarXAxis` már alul kiírt — mert a `BarYAxis`
forráskódja (`bar-y-axis.tsx`) a `barScale`/`barXAccessor`-t (a
KATEGÓRIA-tengelyt) használja Y-koordinátaként. Ez egy **vízszintes**
oszlopdiagramhoz készült komponens (kategóriák a bal oldalon, érték balról
jobbra), nem függőlegeshez — a névből ez nem derül ki.

**Mit döntöttünk:** a `BarYAxis`-t eltávolítottam mindkét chartból. A
`Grid` (szaggatott vízszintes vonalak) ad vizuális érzetet a nagyságrendről
gomb és tengely-cimke nélkül is; a pontos számokat egy lista adja a chart
alatt (ugyanaz a szám, mint a CLI `report` szöveges kimenete) — hosszú
magyar státusz-címkéknél (pl. "feldolgozva (minositesre var)") ezt a
`BarXAxis` sem bírta el olvashatóan, azt is eltávolítottam a Tölcsér
nézetből (a Gazdasági érték nézet 4 rövid címkéjénél — HIGH/MEDIUM/LOW/
nincs adat — a `BarXAxis` megmaradt, mert ott elfér).

**Mit tesztelj később:** ha egy jövőbeli fázis vízszintes oszlopdiagramot
épít (pl. hosszú kategórianevekhez jobban illene), a `BarYAxis` OTT a
helyén való — csak `barScale`-nek Y-irányú `scaleBand`-nak kell lennie.

### 17. Egy CSV-fájlnév véletlenül egybeesett egy DB-státusz-kulccsal

**Mi történt:** a "Nyers naplók" fülnek a küldő öt CSV-jét kell felsorolnia
(`sent.csv`, `do-not-contact.csv`, ...). Első nekifutásra a fájlneveket
kézzel írtam be egy TypeScript tömbbe (`{ nev: "sent", cimke: "sent.csv" }`
stb.) — a `test_a_frontend_nem_drotoz_be_uzleti_listat` erre lebukott: a
`"sent"` fájlnév **szó szerint egyezik** a `companies.status = 'sent'`
értékkel, amit a teszt tilt a frontendben (WEBUI-TERV.md Invariánsok #1).
A két "sent" semmilyen kapcsolatban nincs egymással — az egyik egy
fájlnév, a másik egy lead-életciklus állapot —, de a teszt szó szerint,
kontextus nélkül keres.

**Mit döntöttünk:** a `/api/meta` kapott egy új `kuldo_csv_nevek` mezőt
(`leadgen/report.py` `SENDER_CSV_NEVEK`-ből), és a frontend ezt olvassa ki
a kézzel írt lista helyett. Ez amúgy is a helyesebb megoldás (a fájlnevek
listája Pythonban van definiálva, egy helyen), nem csak a teszt megkerülése.

**Mit tesztelj később:** ha egy jövőbeli fázis egy olyan sztringlistát
venne fel a frontendbe, ami VÉLETLENÜL egybeesik egy üzleti kulccsal (akkor
is, ha a jelentése teljesen más), a `/api/meta`-ból olvasás nemcsak a
tesztet elégíti ki, hanem el is kerüli a jövőbeli félreértést, ha a két
lista valaha tényleg összefonódna.

---

## F10 — Ütemezés és beállítások

### 18. A terv nem adott "Ellenőrzés" blokkot F10-hez

**Mi történt:** F9-hez hasonlóan F10-nek sincs explicit `### Ellenőrzés`
szakasza a WEBUI-TERV.md-ben.

**Mit döntöttünk:** a többi fázis mintáját követve a `./leadgen.sh schedule
status` CLI-kimenetét vetettem össze a `GET /api/schedule/status` válaszával
(mezőről mezőre egyezik), és a `leadgen/config.settings_adat()` /
`leadgen/db.migrations_adat()` / `feedback_watermark_adat()` függvényeket
éles adaton futtattam le a `/api/settings` és `/api/diagnostics` mögött —
ezeknek nincs CLI-ikertestvérük (a "Beállítások" és a "Diagnosztika" fül
tisztán webui-only nézet, korábban egyik parancs sem irta ki ezt az adatot
egyben), tehát csak a helyesség ellenőrizhető, az egyezés nem.

**Mit tesztelj később:** ha az F11 "API-szerződés tesztek" pontja ezekre a
végpontokra is tesztet ír, vegye figyelembe, hogy a `/api/settings` és a
`/api/diagnostics` szándékosan NEM `report.py`-stílusú `*_adat()`/print
ikerpár — a maszkolást és az osszefuzest a `leadgen.config.settings_adat()`
illetve a `leadgen.db.migrations_adat()`/`feedback_watermark_adat()` vegzi,
onnan kell a vart erteket venni, nem egy CLI kimenetbol.

### 19. A telepítés/eltávolítás gombot NEM futtattam végig élesben

**Mi történt:** a `leadgen/schedule.py` `telepit()`/`eltavolit()`
függvényeit szétválasztottam a bevett `*_adat()` mintára
(`telepit_adat()`/`eltavolit_adat()` dict-et ad vissza, a CLI-print
függvény ezt hívja és íratlan marad a kimenete) — ezt a `webui F10`
"Gombok: telepítés / eltávolítás" követelménye kényszerítette ki, mert a
router-nek strukturált JSON kell, nem szöveg. A böngészős ellenőrzésnél
megnyitottam az "Eltávolítás" gomb megerősítő dialógusát (a szöveg és a
gombok helyesek), de **nem nyomtam meg a végleges gombot** — Escape-pel
zártam be —, mert ez a gép **valódi**, élesben telepített launchd-
bejegyzését törölte volna. Utána ellenőriztem `GET /api/schedule/status`-
szal, hogy a rendszer változatlanul `installed: true, loaded: true`.

**Mit döntöttünk:** a `POST /api/schedule/install` és `.../uninstall`
végpontot csak kód-olvasással és a GET-tel való összevetéssel ellenőriztem,
a tényleges POST-ot nem futtattam le sem telepített, sem el nem távolított
állapotból indulva.

**Mit tesztelj később:** az F11 "Teljes végigjátszás" pontjánál valaki
tudatosan nyomja meg mindkét gombot (eltávolítás → `launchctl list` a
labelre → telepítés → `launchctl list` újra), lehetőleg úgy, hogy közben
tudja, hogy ez a gép tényleges reggeli automatizmusát kapcsolja ki/be.

---

## F11 — Lezárás

### 20. A `/api/meta`-ra épülő nézetek végtelen betöltő-vázat mutattak API-hiba esetén

**Mi történt:** a "hibaállapotok végigvitele" auditnál kiderült, hogy a
`useMeta()` hook hibaágát (`hiba` mező) **egyik komponens sem olvasta ki** —
a `riportok/kampany.tsx`, a `riportok/nyers-naplok.tsx` és a
`beallitasok/diagnosztika.tsx` mind `if (!meta) return <Betoltes />`
mintával blokkolt, ami `/api/meta` hiba eseten **örökre** betöltő-váz marad:
nincs hibaüzenet, nincs Újra gomb. Élesben ellenőrizve (API leállítva,
frontend futva): a Kampány fül tényleg végtelen skeletont mutatott.

Egy MÁSIK, súlyosabb hiba is kiderült eközben: a `useMeta()` modul-szintű
`inFlight` cache-e egy ELUTASÍTOTT Promise-t is örökre megtartott —
tehát az ELSŐ `/api/meta` hiba után **egyetlen későbbi próbálkozás sem
indított volna új HTTP-hívást**, még akkor sem, ha a szerver közben
visszajött. Ez a hiba addig rejtve maradt, mert eddig semelyik komponens
nem próbált újra.

**Mit döntöttünk:** a `useMeta()` most `.catch()`-ben nullázza az
`inFlight`-ot (új próbálkozás = új HTTP-hívás), és egy `ujra()` függvényt is
visszaad, ami MINDEN `useMeta()`-t használó komponensre hat (modul-szintű
cache). A három érintett komponens most `metaHiba ? <HibaAllapot ujra=.../>
: !meta ? <Betoltes /> : ...` mintára vált. Külön javítás:
`futtatas/elozmenyek.tsx` `if (!adat) return null;` (néma, üres képernyő
betöltés közben) és nyers `<p className="text-destructive">` (Újra gomb
nélkül) helyett most `Betoltes`/`HibaAllapot`-ot használ, mint minden más
lista-nézet.

**Mit tesztelj később:** ha egy jövőbeli komponens `useMeta()`-t hard
blokkoló feltételként használja (`if (!meta) return <Betoltes />`), mindig
olvassa ki és kezelje a `hiba`/`ujra` mezőt is — ez most már a hook
szerződésének a része, nem csak a `meta`/`betoltve` pár.

### 21. Az F11 API-szerződés tesztjei a meglévő `test_webui_contract.py`-ba kerültek

**Mi történt:** a WEBUI-TERV.md F11 szakasza `tests/test_webui.py` fájlt
nevez meg a négy ellenőrzéshez, de a webui-kontraktus tesztek már F1 óta a
`tests/test_webui_contract.py`-ban élnek, és pont ugyanezt a célt szolgálják
(a docstringje szó szerint erről szól).

**Mit döntöttünk:** nem hoztam létre egy második, átfedő célú fájlt — a
három hiányzó ellenőrzést (a `/api/meta` kampányai az AKTUÁLIS
`APPROVED_CAMPAIGNS`-t tükrözik; egyetlen GET-válasz sem tartalmaz titkot;
a `/api/send/live` érvénytelen tokennel 409-et ad) a meglévő fájlba tettem.
A negyedik pontot (nincs `--live` a katalógusban) NEM ismételtem meg — az
már F6/F7 óta megvan `test_webui_jobs.py`-ban és `test_webui_send.py`-ban.
A titok-ellenőrző tesztet szándékosan **valódi leakkel** is lefuttattam
(ideiglenesen kikapcsoltam a maszkolást, futtattam, visszaállítottam) —
tényleg elbukott, tehát nem csak vakon zöld.

**Mit tesztelj később:** ha valaha tényleg szükség lenne egy külön
`tests/test_webui.py`-ra (pl. mert a kontraktus fájl túl naggyá nő), a
szétválasztás egy tudatos refaktor legyen, ne egy fázis mellékterméke.

### 22. A "Teljes végigjátszás" alatt két valódi `sender.py --live` kísérletet találtam a jobs-előzményben

**Mi történt:** a Futtatás oldal élő tesztelésekor az Előzmények táblában két
"Éles küldés" bejegyzés szerepelt **2026-08-30 18:06:09** és **18:09:05**
időbélyeggel (az egyik `Kesz`, a másik `Hibara futott exit 1`) — jóval az
aznapi agent-munkamenet aktivitása előtt (~21:30 körül). Ez NEM az én
munkamenetemből indult: a `POST /api/send/live` a `Küldés` oldal
kétlépcsős, emberi megerősítést igénylő útján keresztül hívható csak, és a
job-történet minden induló forrást megjelenít, nem csak az agenttől
jövőket.

**Ellenőrizve:** a `cold-email-starter/data/sent.csv` **változatlan**
maradt (még mindig csak az egyetlen, 2026-08-20-i `.invalid` teszt-sor van
benne) — tehát egyik kísérlet sem küldött ki valódi levelet. Ez azért
történhetett biztonságosan, mert 18:06/18:09 **a küldési ablakon (8:00-17:00)
kívül** volt: a `sender.py --live` ilyenkor ártalmatlanul kilép, mielőtt
bármit kiküldene (CLAUDE.md: „AZ ABLAK dry-run alatt nincs kikényszerítve,
de éles alatt igen").

**Mit döntöttünk:** nem nyúltam hozzá (nem törölhető és nem is kellene
törölni egy valódi job-history bejegyzést), és nem próbáltam kideríteni,
ki indította — feltehetően a felhasználó saját tesztje párhuzamosan. A
"Teljes végigjátszás" ellenőrzésnél emiatt még óvatosabban jártam el: az
Éles küldés gombot magát sehol nem nyomtam meg, csak az előnézetig mentem.

**Mit tesztelj később:** ha ez a mintázat rendszeresen előfordul (valaki
a küldési ablakon kívül próbálkozik éles küldéssel), érdemes lehet a
Küldés oldalon egy előre jelzést adni, mielőtt az ember egyáltalán
eljutna a megerősítő dialógusig — jelenleg az `Elonezet` komponens csak
FIGYELMEZTET az ablakra, de nem tiltja le a gombot (ez tudatos döntés
volt F7-ben: a szerver úgyis elutasítja/ártalmatlanul kilép, a felület
csak kényelem).
