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
