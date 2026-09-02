# Prompt a `paladi-web.hu` repóhoz — leiratkozó oldal

> Ezt a szöveget másold be Claude Code-nak **a weboldal repójában**.
> A scraper-oldal (adatbázis, token, levélsablon) már kész és tesztelt.

---

## A feladat

Készíts egy leiratkozó oldalt a Netlify-on futó `paladi-web.hu` site-hoz.
Egy cold email kampány levelei ilyen linket tartalmaznak:

```
https://paladi-web.hu/leiratkozas/287f9366-bd19-4249-a62d-9cfb2ac9a8a7
```

A `287f9366-...` egy UUID token, ami egy Supabase adatbázisban egy konkrét
email címhez tartozik. A kattintás után a címzettnek le kell tudnia iratkozni.

## Kötelező architektúra — ez a rész nem opcionális

### 1. A `GET` NEM ÍRHAT AZ ADATBÁZISBA

Ez a legfontosabb szabály az egész feladatban. A Gmail, az Outlook ATP és a
céges levélszkennerek **automatikusan letöltik** a levelekben lévő linkeket,
még mielőtt a címzett látná őket. Ha a `GET` önmagában leiratkoztatna, a
címzettek egy részét egy robot iratná le — némán, és soha nem derülne ki.

Ezért:

| Kérés | Mit csinál |
|---|---|
| `GET /leiratkozas/<token>` | HTML oldalt ad vissza egy megerősítő gombbal. **Semmit nem ír.** |
| `POST /leiratkozas/<token>` | Végrehajtja a leiratkozást, és visszaigazoló HTML-t ad. |

A megerősítő gomb egy sima HTML `<form method="POST">` legyen, ne JavaScript.
Így akkor is működik, ha a JS le van tiltva, és nincs mit hibázni.

### 2. A Supabase kulcs NEM kerülhet a böngészőbe

A Netlify Function szerveroldalon hívja a Supabase-t. A böngésző csak HTML-t
kap. Ne generálj kliensoldali `supabase-js` hívást.

### 3. Nulla npm függőség

A Netlify Node 18+ futtatókörnyezetében van globális `fetch`. A Supabase-t
sima REST hívással éred el — ne telepíts `@supabase/supabase-js`-t.

---

## Az adatbázis-kontraktus

Az adatbázisban **két PostgreSQL függvény** van, és a weboldal **csak ezt a
kettőt hívhatja** (minden más táblához nincs joga — RLS védi).

### `unsub_lookup(p_token uuid)` — olvasás, a `GET`-hez

```
POST https://khubsykpmmcixynsnlka.supabase.co/rest/v1/rpc/unsub_lookup
Headers:
  apikey: <SUPABASE_ANON_KEY>
  Authorization: Bearer <SUPABASE_ANON_KEY>
  Content-Type: application/json
Body:
  {"p_token": "287f9366-bd19-4249-a62d-9cfb2ac9a8a7"}
```

Válasz — **tömb, egy elemmel** (vedd a `[0]`-t):

```json
[{"found": true, "masked_email": "i***@gofba.hu", "company_name": "goFBA Kft.", "already": false}]
```

| Mező | Jelentés |
|---|---|
| `found` | `false` = ismeretlen token → „ez a link már nem érvényes" oldal |
| `masked_email` | maszkolt cím, hogy a címzett felismerje — **teljes cím soha nem jön vissza** |
| `company_name` | a cég neve |
| `already` | `true` = már korábban leiratkozott → ne mutass gombot, csak nyugtázd |

### `unsub_confirm(p_token uuid)` — írás, a `POST`-hoz

Ugyanaz a hívási mód, `unsub_confirm` néven. Válasz:

```json
[{"found": true, "masked_email": "i***@gofba.hu"}]
```

**Idempotens**: kétszer meghívva ugyanazt adja, nem hiba. Ha a felhasználó
frissíti az oldalt vagy kétszer kattint, nem kell külön kezelned.

---

## Környezeti változók (Netlify → Site settings → Environment variables)

```
SUPABASE_URL=https://khubsykpmmcixynsnlka.supabase.co
SUPABASE_ANON_KEY=<a Supabase dashboard "anon public" kulcsa>
```

Ha bármelyik hiányzik, a függvény adjon **500-at és naplózzon** — ne csendben
essen vissza „sikeres" oldalra, mert akkor a felhasználó azt hinné,
leiratkozott, holott nem.

---

## Útvonal-kezelés

`netlify.toml`:

```toml
[[redirects]]
  from = "/leiratkozas/*"
  to = "/.netlify/functions/leiratkozas/:splat"
  status = 200
```

A függvényben a tokent az `event.path` **utolsó, nem üres útvonal-szegmenséből**
olvasd ki. Fallback: `event.queryStringParameters?.t`. Így a
`/leiratkozas?t=<token>` alak is működik, ha valamiért arra lenne szükség.

---

## Token-validálás

**Mielőtt bármit hívnál**, ellenőrizd, hogy a token szabályos UUID-e:

```
/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
```

Ha nem az → azonnal a „link nem érvényes" oldal, **RPC hívás nélkül**.
Ez nem elméleti eset: a teszt-levelek szándékosan a
`https://paladi-web.hu/leiratkozas/TESZT-EZ-A-LINK-NEM-MUKODIK` címet
tartalmazzák, és ettől a függvény nem eshet 500-ba.

---

## Az oldal megjelenése

- **Magyar nyelvű**, tegező hangnem (a levelek is tegeznek).
- Illeszkedjen a `paladi-web.hu` meglévő arculatához (színek, betűtípus) —
  nézd meg a site meglévő stílusát és használd azt.
- Mobilbarát, egyetlen oszlop, nagy kattintható gomb.
- Ne kérj semmilyen adatot. Ne legyen bejelentkezés, ne legyen űrlapmező.
- Ne legyen külső betűtípus/CDN — egy statikus, önálló HTML.

### Négy állapot, mind a négyet kezeld

| Állapot | Szöveg (javaslat) |
|---|---|
| **Megerősítés** (`found: true`, `already: false`) | „Leiratkozás — `i***@gofba.hu`. Ha rákattintasz, többet nem küldök levelet erre a címre." + gomb: **Leiratkozom** |
| **Kész** (POST után) | „Kész. Nem küldök több levelet a(z) `i***@gofba.hu` címre. Elnézést a zavarásért!" |
| **Már leiratkozott** (`already: true`) | „Erről a címről már leiratkoztál — nem küldök több levelet." (gomb nélkül) |
| **Érvénytelen token** (`found: false` vagy rossz formátum) | „Ez a leiratkozó link nem érvényes. Ha nem szeretnél több levelet, írj a balint@paladi-web.hu címre." |

Hiba esetén (RPC nem elérhető, hálózati hiba) **ne** mutass sikeres oldalt:
írd ki, hogy most nem sikerült, és add meg a `balint@paladi-web.hu` címet
alternatívaként.

---

## Amit a végén ellenőrizz

1. `GET` egy érvényes tokenre → megerősítő oldal, és az **adatbázisban semmi
   nem változott** (ezt kérdezd meg tőlem, én ellenőrzöm a másik repóból).
2. `POST` ugyanarra → visszaigazolás.
3. `GET` **újra** ugyanarra → „már leiratkoztál" állapot.
4. `GET /leiratkozas/TESZT-EZ-A-LINK-NEM-MUKODIK` → „nem érvényes" oldal,
   **nem** 500-as hiba.
5. `GET /leiratkozas/` (token nélkül) → „nem érvényes" oldal.
6. Nézd meg a kész oldal forrását: **a Supabase kulcs nem szerepelhet benne.**

---

## Hibakeresés

Ha a Supabase azt válaszolja, hogy *„Could not find the function
public.unsub_lookup(p_token) in the schema cache"*, akkor a PostgREST
séma-cache-t kell frissíteni. A Supabase SQL Editorban:

```sql
notify pgrst, 'reload schema';
```
