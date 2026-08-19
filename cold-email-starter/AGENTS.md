# Utasítások kódoló agentnek (Codex / Claude Code)

Ez a fájl akkor lép életbe, ha egy AI agent dolgozik ezen a projekten.

## Mi ez a projekt

Cold email küldő rendszer. Python 3.10+, **külső függőség nélkül** (csak
stdlib). Ha új csomagot akarsz behozni, előbb kérdezd meg: a függőség-mentesség
szándékos tervezési döntés, mert így bárhol elindul.

## Kemény szabályok

1. **Soha ne írj valódi kulcsot, jelszót vagy postafiók-címet a kódba.**
   Minden titok a `.env`-ből jön, amit a `.gitignore` kizár. Ha egy fájlba
   kulcs kerül, az hiba, nem kényelmi megoldás.

2. **A küldés alapértelmezetten száraz futás.** A `sender.py` csak `--live`
   kapcsolóval küld. Ezt a védelmet ne vedd ki és ne fordítsd meg.

3. **A védelmi réteget ne kerüld meg.** Ha a `guards.run()` kivételt dob, a
   küldés NEM indulhat. Az üres eredmény nem egyenlő a "nincs válasz"
   állapottal: ha nem tudjuk, ki válaszolt, nem küldünk.

4. **A DNC-lista szent.** Aki rajta van, annak semmilyen körülmények között
   nem megy levél. Ne írj olyan kódot, ami "csak ez egyszer" átlépi.

5. **Ne tegyél követőpixelt vagy nyitás-követést a levelekbe.** Rontja a
   kézbesítést, és a rendszer szándékosan nem tartalmazza.

## Ha valamit módosítasz

- A `templates.py` a felhasználóé: a szöveg tartalmát ne írd át, csak akkor,
  ha kifejezetten ezt kérik. A benne lévő szabályok (fájdalom először, nincs
  hamis "utolsó levél" ígéret, nincs nyers `[Nev]` placeholder) valós
  incidensekből származnak.
- Ha a küldési logikát módosítod, futtasd le utána:
  ```bash
  python3 sender.py --dry --skip-guards
  ```
  és ellenőrizd, hogy a terv és a renderelés értelmes.
- A `data/` alatti CSV-k valódi felhasználói adatot tartalmazhatnak. Ne
  commitold, ne másold ki, ne küldd el sehova.

## Amit érdemes tudni

- A `store.py` minden írása CSV-append. Nincs tranzakció, ezért két
  párhuzamos futás összekeveredhet. Ha cronból futtatod, gondoskodj róla,
  hogy egyszerre csak egy példány fusson (pl. `flock`).
- A `limits.evaluate_ramp()` naponta EGYSZER értékel (a `last_eval` mező védi).
  Ha többször hívod, csendben nem csinál semmit. Ez szándékos.
- A `verify.probe_mailbox()` három értéket adhat: `alive`, `dead`, `unknown`.
  Az `unknown` SOHA nem jelenti azt, hogy a cím rossz. Csak `dead`-re szabad
  véglegesen kizárni egy címet.
