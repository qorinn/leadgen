# Bemásolható prompt a fázisokhoz

> Ehhez tartozik: [WEBUI-TERV.md](WEBUI-TERV.md) (a terv) és
> [WEBUI-MODELLEK.md](WEBUI-MODELLEK.md) (melyik modellel).

## Használat

1. **Nyiss új beszélgetést** Claude Code-ban, a repó gyökerében.
2. Állítsd be a modellt a [WEBUI-MODELLEK.md](WEBUI-MODELLEK.md) szerint
   (pl. `/model sonnet`).
3. Másold be az alábbi promptot, és **írd át benne a fázis számát**
   (két helyen: a címben és az ellenőrzésnél).
4. A végén nézd át, amit írt, és futtasd le magad is az ellenőrzést.

---

## A prompt — ezt másold be

```
Valósítsd meg a WEBUI-TERV.md  ### F4 ###  fázisát.

MIELŐTT BÁRMIT ÍRNÁL:
1. Olvasd el a WEBUI-TERV.md-ből a fenti fázis szakaszát, valamint a
   dokumentum elején az "Invariánsok" és a "Könyvtárszerkezet" részt.
2. Olvasd el a CLAUDE.md-t — a repó konvenciói kötelezőek.
3. Nézd meg a kódban, ami már létezik, és HASZNÁLD ÚJRA. Ne írj új
   lekérdezést olyanra, amire már van függvény a leadgen/ alatt.

CSAK EZT AZ EGY FÁZIST CSINÁLD MEG. Ne kezdj bele a következőbe, még akkor
sem, ha kis munkának tűnik.

A LEGFONTOSABB SZABÁLYOK (a teljes lista a WEBUI-TERV.md-ben):
- Az üzleti logika Pythonban marad. Az APPROVED_CAMPAIGNS, a domain lock, a
  suppression-okok, a status-átmenetek SOHA nem másolódnak TypeScriptbe — a
  frontend a /api/meta-ból tudja meg, mi engedélyezett.
- A sender.py --live csak kétlépcsősen indulhat, és ezt a SZERVER
  kényszeríti ki, nem a gomb.
- Titok soha nem mehet ki API-n (jelszó, API-kulcs, DATABASE_URL) — csak
  maszkolva.
- Csak localhost. Nincs 0.0.0.0, nincs kitett port.
- A küldő (cold-email-starter/) moduljait csak subprocess-en át hívd: másik
  interpreteren futnak (rendszer python3 3.9.6). Minta: report._sender_state().
- A felület magyar, ékezetesen. A kód, az API-mezők és a fájlnevek angolok.
  A .py fájlokban a magyar komment ÉKEZET NÉLKÜL (a repó konvenciója).
- A frontend nem ír SQL-t. Minden írás POST, és meglévő leadgen függvényt hív.

HA A TERV ÉS A VALÓSÁG ÜTKÖZIK:
Állj meg és kérdezz. NE tervezd újra magadtól, és ne találj ki mezőnevet,
API-alakot vagy képernyőt, ami nincs a tervben. Ha valami hiányzik a tervből,
azt mondd meg — a tervet javítjuk, nem improvizálunk.

HA VALAMIT NEM TUDSZ ELLENŐRIZNI, MONDD MEG.
Ne írd azt, hogy "kész", ha nem futtattad le. A hibás teszt eredményét is
mutasd meg, ne magyarázd el helyette.

AZ ADATBÁZIS ÉLES:
A DATABASE_URL az éles Supabase-re mutat, nincs külön teszt-DB. Ellenőrző
scriptben SOHA ne commitolj, és ne írj át valódi cégadatot. Ha írnod kell a
teszthez, előbb kérdezz.

A FÁZIS VÉGÉN:
1. Futtasd le a WEBUI-TERV.md-ben az  ### F4 ###  fázisnál megadott
   ellenőrzést, és mutasd meg a tényleges kimenetét.
2. Futtasd le: .venv/bin/pytest    (a meglévő teszteknek zöldnek kell maradniuk)
3. Ha a fázis új parancsot vagy folyamatot adott a rendszerhez, frissítsd a
   dokumentációt a CLAUDE.md "Dokumentáció-karbantartás" szakasza szerint.
4. Írd le röviden: mi készült el, mit nem tudtál megcsinálni, és miért.
```

---

## Rövid változat — ha egy fázis félbeszakadt

```
Folytasd a WEBUI-TERV.md  ### F4 ###  fázisát ott, ahol abbamaradt.

Előbb nézd meg, mi van már készen (git status, és a fázisnál felsorolt
fájlok), és csak a hiányzó részt csináld meg. Ne írd újra, ami már kész.

A szabályok változatlanok: a WEBUI-TERV.md "Invariánsok" szakasza és a
CLAUDE.md érvényes. Csak ezt az egy fázist fejezd be.

A végén futtasd le a fázis ellenőrzését és a .venv/bin/pytest-et, és mutasd
meg a kimenetet.
```

---

## Ellenőrző kérdések, ha valami gyanús

Ha a végén nem vagy biztos benne, hogy jó lett, ezeket kérdezheted:

```
Mutasd meg, hol tartod be a "az üzleti logika Pythonban marad" szabályt.
Van bárhol a frontendben bedrótozott státusz-, kampány- vagy ok-lista?
```

```
Futtasd le újra a fázis ellenőrzését, és mutasd a NYERS kimenetet,
kommentár nélkül.
```

```
Mit NEM csináltál meg abból, amit a WEBUI-TERV.md ennél a fázisnál kér?
```

---

## Amire figyelj a válaszában

| Gyanús jel | Mit jelent |
|---|---|
| hosszan mérlegel, alternatívákat sorol | a terv ott hiányos — inkább egészítsd ki, mint hogy improvizáljon |
| „valószínűleg működik", „ennek jónak kell lennie" | nem futtatta le; kérd el a kimenetet |
| státusz- vagy kampánylista a TypeScript kódban | megsérti az 1. invariánst — a /api/meta-ból kell jönnie |
| a következő fázisba is belekezdett | állítsd meg; a fázisokat külön kell átnézni |
| `0.0.0.0` vagy külső port a kódban | megsérti az 5. invariánst |
