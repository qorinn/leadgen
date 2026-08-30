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

**Mit tesztelj később:** miután F4 elkészül (a Cégek lista szűrőkkel), nézd
meg, hogy a `/cegek?status=review` link **tényleg szűr-e** a Cégek oldalon
— most még csak egy üres vázlat oldalra visz, mert F4 nincs kész. Ha F4 más
néven implementálja a szűrő paramétert (nem `status`), ezt a linket is
frissíteni kell.

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
