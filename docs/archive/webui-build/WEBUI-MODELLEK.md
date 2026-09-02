# Melyik fázishoz melyik Claude modell

> Ehhez tartozik: [WEBUI-TERV.md](WEBUI-TERV.md) (mit kell megépíteni) és
> [WEBUI-PROMPT.md](WEBUI-PROMPT.md) (mit másolj be).

---

## A vezérelv egy mondatban

**Opus csak ott, ahol a hiba néma vagy visszafordíthatatlan.** Minden más
fázis Sonnet, a szövegmunka Haiku.

---

## Miért fogy kevesebb keret egy kész tervvel

A modellválasztásnál nagyobb megtakarítás az, hogy **a tervezés már megtörtént.**

Terv nélkül a modell minden fázisban ugyanazt csinálná: végigolvassa a
kódbázist, kitalálja a képernyőket, kitalálja az API-t, kitalálja a
mezőneveket — és a következő fázisban **újra**, mert nem emlékszik rá. Ez a
munka nagyobb részét jelenti, és pont ez az, amiben az erős modellek drágák.

A [WEBUI-TERV.md](WEBUI-TERV.md) mellett a feladat más természetű: **végrehajtás,
nem tervezés.** Ehhez elég egy közepes modell — ezért szerepel a lenti
táblázatban ennyi Sonnet.

**Gyakorlati következmény:** ha egy fázis közben azt veszed észre, hogy a
modell tervezni kezd (hosszan mérlegel, alternatívákat sorol, kérdez a
mezőnevekről), az azt jelenti, hogy a terv ott hiányos. **Állítsd meg, és
inkább a tervet egészítsd ki** — az olcsóbb, mint végigvinni egy
improvizált fázist.

---

## A hozzárendelés

| Fázis | Modell | Miért ez |
|---|---|---|
| **F0** Alapozás | Sonnet 5 | Bejáratott scaffolding: `create-next-app`, `shadcn init`, egy FastAPI váz. Ezt a modell ezerszer látta. |
| **F1** API + `/api/meta` | 🔴 **Opus 5** | **Erre épül minden későbbi fázis.** A `report.py` refaktor során könnyű két igazságot csinálni ugyanarra a számra, és az csendben rossz riportot ad. A `/api/meta` kontraktus elrontása pedig azt jelenti, hogy a szabályok átszivárognak a frontendbe. |
| **F2** Váz, komponensek | Sonnet 5 | Komponensmunka kész specifikáció alapján. |
| **F3** Irányítópult | Sonnet 5 | Kész API-adatból megjelenítés. Az ellenőrzés is egyszerű: egyezzen a `report --daily`-vel. |
| **F4** Cégek | Sonnet 5 | Sok mező, de mechanikus. **Ez a leghosszabb fázis** — a terv miatt viszont nem nehéz. |
| **F5** Írási műveletek | Sonnet 5 | Kis felület. A kockázatos részt (visszafordíthatatlan `reject`) a terv már rögzíti, a modellnek nem kell eldöntenie. |
| **F6** Futtatás + SSE | 🔴 **Opus 5** | Párhuzamosság és folyamatkezelés. A hibák itt **némák**: két egyszerre futó lánc, elszivárgó folyamat, félbeszakadt stream. Ezek nem dobnak hibát, csak rossz eredményt adnak. |
| **F7** Küldés | 🔴 **Opus 5** | **Visszafordíthatatlan kiküldés.** A kétlépcsős kaput szerver-oldalon kell kikényszeríteni, és a token-érvényesítésen múlik, hogy nem megy-e ki elavult terv. Itt egy hiba levelekben jelenik meg. |
| **F8** Válaszok, riasztások | Sonnet 5 | Listák és részletnézetek. |
| **F9** Riportok, chartok | Sonnet 5 | Bklit komponensek + kész adat. |
| **F10** Ütemezés, beállítások | Sonnet 5 | Kis felület. A maszkolás szabályát a terv kimondja. |
| **F11** Lezárás | Sonnet 5, majd **Haiku 4.5** | A tesztek Sonnet; a dokumentáció-írás (`HOGYAN-HASZNALD.md`, `PARANCSOK.md`) Haiku. |

**Összesítve:** 3 fázis Opus, 8 fázis Sonnet, 1 részfeladat Haiku.

---

## Mennyivel drágább egy erősebb modell

Viszonyításnak, a repó saját ártáblájából ([leadgen/pricing.py](leadgen/pricing.py),
1 millió tokenre, input/output):

| Modell | Input | Output | Sonnethez képest |
|---|---|---|---|
| Haiku 4.5 | $1,00 | $5,00 | **0,33×** |
| Sonnet 5 | $3,00 | $15,00 | 1× |
| Opus 5 | $5,00 | $25,00 | **1,67×** |

⚠️ Ezek **API-árak**, nem az előfizetéses keret elszámolása. Arányként viszont
jó iránymutatók: az Opus nagyjából másfélszeres súlyú a Sonnethez képest, a
Haiku pedig a harmada.

**Ebből következik a gyakorlati tanács:** a 3 Opus-fázist ne told át Sonnetre
spórolásból — ott a hibázás ára nagyobb, mint a különbözet. A 8 Sonnet-fázist
viszont **ne told fel Opusra** „biztos, ami biztos" alapon; pont ez az, ami
feleslegesen viszi a keretet.

---

## Modellváltás Claude Code-ban

```
/model                 # menüből választasz
/model opus            # közvetlenül
/model sonnet
/model haiku
```

A váltás a **következő** üzenettől érvényes. Fázis közben is válthatsz — ha
például az F4 vége már csak apró javítás, `/model haiku` és fejezd be azzal.

**Fast mode** (`/fast`): Opus, gyorsabb kimenettel. Nem gyengébb modell —
ugyanaz az Opus. Hosszú, iteratív fázisoknál (F4) kellemesebb.

---

## Ha fogy a heti keret

Sorrendben ezeket tedd:

1. **Ne az Opus-fázisokat áldozd fel.** Inkább várj velük a keret
   megújulásáig. Egy elrontott F7 levelekben jelenik meg.
2. **Vidd Haikura a szövegmunkát.** Az F11 dokumentáció-írása, a magyar
   feliratok javítása, apró elnevezés-változtatások — mind mehet Haikuval.
3. **Bontsd ketté a nagy fázisokat.** Az F4 (cégek) természetesen esik szét:
   előbb a lista, külön üzenetben a részletnézet. Két rövidebb menet kevesebb
   kontextust hordoz, mint egy hosszú.
4. **Egy üzenet = egy fázis.** Ne kérj két fázist egyszerre. A hosszú
   beszélgetés minden további kérésnél újra és újra elküldi a korábbi
   kontextust.
5. **Új beszélgetés minden fázisnak.** A [WEBUI-PROMPT.md](WEBUI-PROMPT.md)
   pont ezért önmagában is teljes: nem hivatkozik korábbi beszélgetésre.

---

## Amit NE csinálj

- **Ne kérd, hogy „csináld meg az egész felületet".** A modell nem fog
  megállni ellenőrizni, és a végén egy nagy, átnézetlen halom lesz belőle —
  a hibák pedig egymásra épülnek.
- **Ne hagyd ki az ellenőrzést** a fázis végén. A terv minden fázishoz megad
  egyet; ezek olcsók, és a következő fázis rájuk épül.
- **Ne engedd, hogy a modell „menet közben javítson" a terven.** Ha ütközést
  talál, az érvényes visszajelzés — de a tervet **te** módosítsd, ne a fázis
  mellékhatásaként dőljön el.
