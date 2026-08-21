# Integrációs terv — scraper ↔ cold-email-starter

> Készült: 2026-08-19. Határidő: **2026. október 12., legalább 1 ügyfél.**
> Ez a dokumentum a `SCRAPER-PLAN.md` és a `cold-email-starter/` közti kontraktust
> rögzíti, és szakaszokra bontja a megépítést. A `SCRAPER-PLAN.md` marad a
> **követelményrendszer**; ez a fájl a **végrehajtási terv**. Ha a kettő ütközik,
> az ütközés itt, a „Ellentmondások" fejezetben van kimondva.

---

## 📍 Állapot — 2026-08-21 (péntek)

| Szakasz | Állapot |
|---|---|
| **0. Emberi előfeltételek** | ✅ **KÉSZ** |
| **1. Alapozás** | ✅ **KÉSZ** |
| **2. Export (DB → leads.csv)** | ✅ **KÉSZ** (a levélszöveg átírva 08-20-án) |
| **3. Feedback (CSV → DB)** | ✅ **KÉSZ** |
| **4. 8.1 engine (ügynökségi lista)** | 🟡 **agent-rész kész — 10 valódi lead exportálva, 10 átnézésre vár** |
| **5. Első éles kiküldés** | 🟡 **agent-rész kész — a `--live` futás RÁD vár** |
| 6-13. | ⬜ nem kezdődött el |

**A teljes lánc szárazon végigfutott valódi adattal.** Ami hátravan az 5. szakaszból,
az egyetlen emberi lépés: elolvasni a 10 levelet, és elindítani a `--live` futást.

```
export ......................... 10 sor, 0 új sorba állítva (mind folyamatban lévő)
guards.py (önállóan) ........... IMAP OK, 0 üzenet, 0 hiba
sender.py --dry (guards-szal) .. 10 levél a tervben, mai keret 20, 0 placeholder
preview.py --limit 1 ........... teljes levél átnézve, aláírás + leiratkozás rendben
pytest ......................... 103 teszt zöld
```

### ⏩ Módosított cél (2026-08-20, felhasználói döntés)

*„Jövő héten minden egyes scraper kész kell legyen és működjön az automatizált
(személyre szabott) email küldés."*

Ez felgyorsítja az eredeti szakasz-sorrendet. Ami emiatt változik:

- a 4. szakasz **kézi seed-gyűjtés helyett Apify-alapú** lett (lásd ott);
- a 6. (AI réteg) és a 10. (classifier + personalization) **előrébb kerül**, mert
  ezek adják a „személyre szabott" részt — e nélkül a küldés automatizált ugyan,
  de sablonos;
- a 12. (cron) is bekerül a hétbe, mert e nélkül nem „működik automatikusan".

**Reális becslés:** ~20 óra agent-munka, 7 nap alatt kb. napi 3 óra. Megvalósítható,
de két külső függés blokkolhatja, és ezek nem agent-munkával oldódnak meg:
API-kulcsok (Apify, Gemini, Anthropic) és a 0.3 szerinti Actor-előtesztek.

> **Ami ettől nem változik:** a napi küldési keret. A `DAILY_CAP_START=20` a
> kézbesítési jelekből emelkedik, nem a leadek számától. Tehát „minden scraper kész"
> és „napi 20 levél" egyszerre igaz lesz — a rendszer teljessége és a kiküldött
> volumen két külön dolog. Ez nem ellenérv a gyorsítás ellen, csak azt jelenti,
> hogy a lead-utánpótlás rövid távon nem szűk keresztmetszet.

**Ellenőrzött tények (nem feltételezés):**

```
SMTP  balint@paladi-web.hu ........ OK   (Google Workspace, app-jelszó)
IMAP  imap.gmail.com:993 .......... OK   (INBOX kiválasztva, 0 üzenet, 9 mappa)
DNS   SPF / DKIM / DMARC .......... OK   (p=quarantine, adkim=s, aspf=s)
Sablonok ....................... 0 placeholder a három levélben

Python 3.12.14 (Homebrew) + .venv    psycopg 3.2.13, httpx, selectolax, pytest
DB    PostgreSQL 17.6 @ Supabase .. 7 tábla létrehozva, mind 0 sor
pytest ......................... 49 teszt zöld
sender.py --dry --skip-guards .. változatlanul fut
```

**Élesben ellenőrzött kényszerek** (teszt-sorokkal, mind visszagörgetve):
azonos `normalized_domain` → ütközik · két platform-only cég megfér egymás mellett ·
kulcs nélküli cég nem hozható létre · **domain lock: egy cégre egyszerre egy aktív
outreach** · lezárás után új sequence indítható · ismeretlen suppression `reason`
elutasítva · ugyanaz a `(source_type, source_url)` páros nem kerül be kétszer ·
`updated_at` trigger frissít.

**A 2. szakaszban élesben ellenőrizve** (teszt-cégekkel, `.invalid` domainekkel):

```
export --dry / export ................. 3 lead, helyes kampány és personalization
kontakt-választás ..................... personal nyert a generic felett
DOMAIN LOCK ........................... 2. cím felvétele után is 1 sor a fájlban
idempotencia .......................... 3 egymás utáni export, azonos md5
domain-szintű suppression ............. a lead eltűnt a fájlból
folyamatban lévő lead (sent) .......... BENN MARADT (különben nincs follow-up)
a küldő do-not-contact.csv-je ......... kihagyva, "kihagyva (DNC): 1"
sender.py --dry --skip-guards ......... helyes levelek, personalization landol
pytest ................................ 56 teszt zöld
```

**A következő lépés:** a **te** átnézésed (lásd a 2. szakasz „Az ÉN feladataim" pontját),
utána a 3. szakasz — feedback-import, `replies.csv`, és az export kötelező blokkolása.

**Amit még nem kértünk el a felhasználótól** (nem blokkoló, a saját szakaszánál kell):
Gemini + Anthropic API kulcs (6. szakasz), Reoon kredit (7. szakasz), Apify token
(9. szakasz), ügynökség-lista `seeds/agencies.txt` (4. szakasz).

---

## Döntésnapló

Az itt rögzített döntések a szakaszok végrehajtása közben születtek. Ha egy későbbi
session mást akarna csinálni, előbb ezt olvassa el — mindegyik mögött indoklás van.

### 2026-08-19 — Küldő domain és postafiók

| | |
|---|---|
| **Döntés** | Marad a **paladi-web.hu**. Nincs külön „cold email" domain. Egy **új, dedikált** Google Workspace postafiók: `balint@paladi-web.hu`. |
| **Elvetve** | Külön outreach-domain (pl. `paladiweb.hu`) új szolgáltatóval; a meglévő `hello@` használata; olcsóbb szolgáltató (Zoho/Migadu). |
| **Indok** | A 8.1 ügynökségi lista **egyszeri és nem pótolható** (Magyarországon reálisan 60-300 cég). Ha egy előélet nélküli domainről megy ki és spam mappába esik, ugyanazoknak nem lehet újraküldeni. A paladi-web.hu évek óta él, hibátlan SPF/DKIM/DMARC-cal — ez a projekt legnagyobb kézbesítési vagyontárgya. **Az első kampány nem volumen-korlátos** (60-150 lead napi 20-szal 3-7 nap), tehát a ramp itt még nem szűk keresztmetszet — az csak a 9-10. szakasztól lesz az. |
| **Miért nem olcsóbb szolgáltató** | A paladi-web.hu MX-e a Google-re mutat. Egy domainnek egy levelezési szolgáltatója lehet, tehát „olcsóbb postafiók ugyanezen a domainen" nem létező opció — az az összes levelezés migrációját jelentené. Az „olcsóbb szolgáltató" és az „új domain" ugyanaz a kérdés. |
| **Miért nem a `hello@`** | A `guards.py` minden futásnál a teljes 14 napos INBOX-ot végigolvassa (9. ellentmondás) — forgalmas fő postafiókon lassú; a válaszok elkeverednének; és a `hello@` cégcímnek olvasódik, miközben a levél lényege, hogy egy ember ír személyesen. |
| **Mikor kell újragondolni** | A 9. szakasznál (Profession engine, nagyobb volumen). Addigra érdemes egy tartalék domaint regisztrálni és **használat nélkül öregíteni**. |

> ⚠️ **Ha valaha második postafiók kerül be:** a `limits.daily_cap()` a per-fiók keretet
> a fiókok számával szorozza, tehát egy `cap=100`-nál hozzáadott fiók a napi volument
> egy nap alatt 100-ról 200-ra ugratja. Ilyenkor a `data/ramp_state.json`-ban a `cap`
> értéket kézzel kell felezni.

### 2026-08-21 — Kizárás: mi globális és mi kampány-specifikus

| | |
|---|---|
| **A kérdés** | A felhasználó vetette fel: *„lehet, hogy vannak olyan scraperek, ahol az egyik scraperben rossz lead, de a másikban jó lead, ugyanaz a cég."* |
| **Ellenőrizve** | Igaz volt. A `rejected` státusz **véglegesen** kizárta a céget minden jövőbeli engine elől, mert az `ingest` ON CONFLICT ága nem állította vissza a státuszt, a `qualify` pedig `campaign` szerint szűr — vagyis az első engine, ami megtalálta a céget, „lefoglalta" örökre. |
| **Döntés** | Kétféle kizárás van, és **csak az egyik globális**: |

```
GLOBÁLIS, végleges — a CÉG tulajdonsága, nem a kampányé
  suppression tábla:  unsubscribe · negative_reply · manual_block
                      competitor · existing_client · hard_bounce
  → domain- vagy email-szinten, minden engine előtt zárva

KAMPÁNY-SPECIFIKUS — csak ehhez az ajánlathoz nem illik
  companies.status = 'rejected'
  → ha egy MÁSIK engine találja meg, visszaáll 'new'-ra és újraértékelődik
```

**Indoklás:** a „nincs marketing kulcsszó" azt jelenti, hogy *ehhez a kampányhoz*
nem illik — nem azt, hogy a cég sosem lehet lead. Egy könyvelőcég, amit az
ügynökségi engine elutasít, kiváló lead lehet az álláshirdetés-engine-nek.
A leiratkozás és a versenytárs-státusz viszont a cég tulajdonsága, azt semmilyen
engine nem írhatja felül.

**Ellenőrizve** (szimulált forgatókönyvvel): ugyanaz az engine újra megtalálja →
marad `rejected`; másik engine megtalálja → `new`, új kampánnyal; `suppressed`
cég másik engine-nél → marad `suppressed`.

### 2026-08-20 — Hard bounce: nincs újrapróbálás ⏳ VISSZATÉRÉSRE JELÖLVE

| | |
|---|---|
| **Döntés** | Hard bounce után a cég `rejected` státuszba kerül, és **nem próbálkozunk másik címmel ugyanannál a cégnél**. A cím `manual_block` suppressionbe kerül, a kapcsolat `invalid` lesz, az outreach `stopped`. |
| **Elvetve** | A megengedőbb változat (`ready` + 30 napos cooldown), ami egy másik címmel újrapróbálkozott volna. |
| **Indok** | A felhasználó döntése: *„Ne rontsuk a domain reputációt."* A bounce az egyetlen hiba a rendszerben, ami **visszamenőleg** is kárt okoz — rontja a küldő domain hírnevét, és onnantól a jó leadeknek sem érkezik meg a levél. Egyetlen cég megmentése nem éri meg ezt, főleg úgy, hogy a második cím ugyanabból a nyilvánvalóan elavult forrásból származik. |
| **Ára** | Egy elavult `info@` cím miatt elveszíthetünk egy egyébként jó céget. Ez magyar KKV-knál nem ritka. |
| **⏳ MIKOR TÉRJÜNK VISSZA RÁ** | **Ha már van ügyfél, ÉS a lead-utánpótlás válik szűk keresztmetszetté** (a `report` azt mutatja, hogy a napi keret nem telik be lead hiányában). A felhasználó szó szerint: *„Később ha lesz ügyfelem módosíthatjuk."* |
| **Hogyan** | `leadgen/feedback.py`, a `_import_dnc()` `hard_bounce` ága. A visszatéréskor ne egyszerűen `ready` legyen: csak olyan **második címre** szabad újrapróbálni, amit a Reoon `valid`-nak mért (tehát `EMAIL_VALIDATION=full` kell hozzá, 7. szakasz), és akkor is cooldownnal. |

### 2026-08-20 — Levélszöveg: felszínesen robotosnak hangzott, átírva

| | |
|---|---|
| **Probléma** | A felhasználó a dry-run kimenetet olvasva jelezte: „elég hidegek, nagyon robotosak, nem hiszem, hogy sokan válaszolnának rá". |
| **Diagnózis** | Három konkrét minta: (1) minden bekezdés önálló kijelentő mondat, kötőszó/gondolatjel nélkül — felsorolásnak hangzik, nem gondolatmenetnek; (2) a `follow_up_1`-ben „nem az a kérdés, hogy X, hanem hogy Y" szimmetrikus ellentétpár — tipikus copywriter/AI-minta, élő beszédben ritkán épül fel spontán így; (3) a `follow_up_2` tipp-felsorolásnak hangzott („Ha X, akkor Y. Ha Z, akkor W."), nem odavetett gondolatnak. |
| **Javítás** | Mindhárom levél átírva: gondolatjeles, kötőszavas mondatfűzés (`—`, „és", „szóval"), változó mondathossz, feltételes/lágyabb megfogalmazás a kérdéseknél. A tartalmi mag (ki vagyok, mit láttam náluk, mi a kérdés) nem változott — csak a mondatok közti kötés. |
| **Ellenőrzés** | Teljes lánc újrafuttatva a módosítás után: `pytest` 56/56 zöld (a `test_contract.py` a `"template": "..."` azonosítókra köt, azok nem változtak), `export --dry` + `sender.py --dry --skip-guards` változatlanul helyes kimenetet ad. |
| **Nyitott** | A tónus szubjektív — ha a felhasználó a következő olvasásnál még mindig nem érzi elégnek, ismételt finomítás várható. Ez nem egyszeri lezárt döntés, hanem a `templates.py` a felhasználóé, bármikor felülírható. |

### 2026-08-19 — Levélszöveg: ékezet és leiratkozási szó

| | |
|---|---|
| **Döntés** | A `templates.py`-ban a **címzettnek menő szöveg ékezetes**; a kommentek és docstringek ASCII-ban maradnak. A leiratkozás hívószava **„stop"**, nem „nem". |
| **Indok (ékezet)** | Tudatos eltérés a kód-konvenciótól. Ellenőrizve: az `EmailMessage` a tárgyat RFC 2047-tel kódolja, a törzset UTF-8/8bit-tel küldi, a `smtplib.send_message` hibátlanul átviszi (mindkettő letesztelve helyi SMTP szerverrel). Ékezet nélkül a levél igénytelen és gépies benyomást keltene — pont azt rontaná el, amiért a személyre szabás létezik. |
| **Indok („stop")** | Az 5. ellentmondás megelőzése a forrásnál: ha a saját levelünk kéri, hogy írják vissza, hogy „nem", akkor a `guards.UNSUB_PATTERNS` pontatlansága a mi hibánk. A „stop" ugyanolyan könnyű kilépés (GDPR 6(1)(f) feltétele), de magyar szövegben egyértelmű. |

---

# 1. rész — Felmérés

## 1.1 A `cold-email-starter` — tények

| Kérdés | Válasz (kódból ellenőrizve) |
|---|---|
| **Nyelv / futtatás** | Python 3.10+ (README), **stdlib-only**, csomagkezelő nincs. Lapos modulok, `import store` stílus, a scripteket a `cold-email-starter/` könyvtárból kell indítani. |
| **Adattárolás** | Nincs adatbázis. Négy CSV a `data/` alatt + egy JSON: `leads.csv`, `sent.csv`, `do-not-contact.csv`, `bounces.csv`, `ramp_state.json`. Kezelő: `store.py`. |
| **Írás módja** | `store._append` = sima fájl-append. **Nincs tranzakció, nincs lock, nincs upsert, nincs dedup.** Minden olvasás teljes újraolvasás `csv.DictReader`-rel. |
| **Címzettek forrása** | `data/leads.csv`. Fejléc (`store.py:19`): `email,company,contact_name,website,industry,city,notes`. Az **`email` az egyetlen kulcs** az egész rendszerben. |
| **Email validáció** | Igen, `verify.py`. Két réteg: `looks_unsendable()` (formátum + role-prefix lista, hálózat nélkül, **ez fut minden futásnál minden leadre** — `sender.py:70`), és `has_mx()` / `probe_mailbox()` (MX + RCPT-probe, `dnspython` vagy rendszer-`dig`). A `probe_mailbox`-ot a `sender.py` **nem hívja** — csak kézzel használható. |
| **Bounce / leiratkozás / válasz** | `guards.py`, IMAP-on, minden küldés előtt. NDR-felismerés feladó+tárgy mintából, hard/soft bounce szétválasztás regexszel, válaszoló felismerés (feladó szerepel-e a `sent.csv`-ben), leiratkozás kulcsszóval. Mind a három a `do-not-contact.csv`-be ír. |
| **Suppression** | `do-not-contact.csv`, **csak email-szinten**, három ok: `replied`, `unsubscribe_request`, `hard_bounce`. Idempotens írás (`store.add_to_dnc`). |
| **Ütemezés / sequence** | Igen. `limits.in_send_window()` (munkaidő + hétvége), `limits.daily_cap()` (rampelt keret **× postafiókok száma**), `sender._stage_of()` a `sent.csv` `template` oszlopából vezeti le a szekvencia-fokot (`cold` → `follow_up_1` → `follow_up_2` → `done`). Follow-up mindig előbb, mint friss cold. |
| **Külső szolgáltatás** | Csak SMTP + IMAP. Kulcsok: `SMTP_ACCOUNTS` (`cim:jelszo,cim:jelszo`), `SMTP_HOST/PORT/USE_SSL`, `IMAP_HOST/PORT`, `FROM_NAME`, `REPLY_TO`. Mind `.env`-ből (`config._load_dotenv`, `setdefault`-tal). Nincs API, nincs webhook, nincs tracking. |

**Smoke-teszt lefuttatva** (a scratchpadben, a repó érintése nélkül):
`sender.py --dry --skip-guards` a példa-leadekkel hibátlanul lefut, kiírja a tervet és
a renderelt leveleket. A rendszer működik.

## 1.2 A gép — tények

| | |
|---|---|
| Python | **csak `python3` = 3.9.6** (macOS rendszer-Python). Nincs 3.10/3.11/3.12. |
| Csomagkezelő | nincs `uv`, nincs `poetry`, nincs `pipx`. **Van** Homebrew 6.0.18. |
| Egyéb | Node v24.12.0, npm. **Nincs** Docker, nincs `psql`, nincs `supabase` CLI. |
| OS | macOS 26.5.2 (Darwin 25.5.0) |

A `cold-email-starter` a 3.9.6-on **is elfut** (ellenőrizve), mert minden modul
`from __future__ import annotations`-t használ, tehát a `str | None` annotációk
sosem értékelődnek ki. Ez szerencse, nem tervezés — a scraper viszont 3.11+-t fog
igényelni, tehát **két interpreter lesz a gépen**. Ez az 1. szakasz egyik feladata.

---

## 1.3 ⚠️ Ellentmondások — a terv feltételezi vs. a küldő valójában

Mindegyik kódból ellenőrizve, fájl:sor hivatkozással. **A 7., 8. és 9. pont nem
szerepelt a `CLAUDE.md` eddigi listáján** — ezeket most találtam.

| # | A terv feltételezi | A küldő valójában | Hol dől el |
|---|---|---|---|
| **1** | **Domain lock**: egy domain = egy aktív sequence (*Az aranyszabály*) | `sender.build_plan` `dict[email] -> lead`-et épít (`sender.py:58-62`), a domain fogalmát nem ismeri | A domain lockot **az exportáló oldalon** kell kikényszeríteni. → 2. szakasz |
| **2** | AI personalization mondat megy a levélbe (Tier A/B) | `templates.py` csak `contact_name` / `company` / `industry` mezőt renderel | `LEADS_HEADER` bővítés + `templates.py` módosítás. → 2. szakasz |
| **3** | Offer arbitration, engine-enként külön CTA | **egyetlen** sablonkészlet: `cold` / `follow_up_1` / `follow_up_2` | `campaign` mező + sablonválasztás a `sender.build_plan`-ben. → 2. szakasz |
| **4** | `suppression` domain- **vagy** email-szintű, 5 ok (`unsubscribe`, `negative_reply`, `manual_block`, `competitor`, `existing_client`) | `do-not-contact.csv` **csak email-szintű**, 3 ok (`replied`, `unsubscribe_request`, `hard_bounce`) | A DB suppression a szigorúbb; a küldő DNC-je ennek részhalmaza. A domain-szintű tiltás a **leads.csv-ből való kihagyással** érvényesül, nem DNC-írással (lásd 2. szakasz indoklás). |
| **5** | AI válasz-osztályozás tölti a suppressiont | `guards.UNSUB_PATTERNS` tartalmazza a nyers `r"\bnem\b"` mintát, és a válasz **első 600 karakterén** illeszt (`guards.py:40,127`) | Magyar szövegben tömeges hamis `unsubscribe_request`. Szűkíteni kell. → 3. szakasz |
| **6** | Validáció kiszűri: `noreply@`, `webmaster@`, `admin@`, `privacy@`, `gdpr@` | `verify.ROLE_PREFIXES` (`verify.py:113`) — **nincs benne** `admin`, `privacy`, `gdpr` | A scraper helyi szűrője legyen a szigorúbb. `info@` **mindkettőben átmegy** — szándékosan, magyar KKV-nál gyakran ez az egyetlen cím. |
| **7** 🆕 | AI-feladat #5: a beérkező válaszok osztályozása tölti a `suppression` táblát | **A válaszok szövege sehol nem marad meg.** `guards.run()` IMAP-ról beolvassa, mintát illeszt rá, majd **eldobja** — csak egy DNC-sor születik, ok-kóddal. A `bounces.csv` is csak a tárgy első 200 karakterét őrzi. | **Az AI válasz-osztályozásnak nincs bemenete.** `guards.py`-ban egy új, append-only `replies.csv` kell. → 3. szakasz |
| **8** 🆕 | n8n a karmester, Apify futtat, Supabase az állapot — „nincs saját szerver" | A küldő **helyi CSV-kre** és **helyi IMAP/SMTP-kapcsolatra** épül, a fejlesztő gépén. Egy felhőben futó n8n ezekhez a fájlokhoz nem fér hozzá. | Vagy a küldő költözik, vagy az n8n kiesik. **Javaslat: kiesik** — lásd az A) döntést. |
| **9** 🆕 | (a terv nem foglalkozik vele) | `guards.run()` minden futásnál **a teljes 14 napos INBOX-ot** végigolvassa, minden levélre teljes `RFC822` fetch-csel, minden fiókra. Nincs UID-watermark, nincs feldolgozott-jelölés (`mailer.fetch_recent`, `guards.py:104`). Csak az `INBOX`-ot nézi. | Óránkénti `--live` cronnál ez percekbe kerülhet egy forgalmas postafiókon, és minden választ újra és újra feldolgoz. A mappába szűrt válaszokat nem látja. → kockázat, 12. szakasz |

**Két apróság, ami nem ellentmondás, de tervezéskor számít:**

- `limits.daily_cap()` = per-fiók keret × `SMTP_ACCOUNTS` fiókok száma (`limits.py:52`).
  Két postafiókkal az 1. napi keret **40**, nem 20. A „7 hét a plafonig" számítás
  egy postafiókra igaz.
- `templates.py` jelenleg **placeholder szöveget tartalmaz** (`<IDE IRD A KONKRET
  FAJDALMAT...>`) — ez a dry-run kimenetben látszik. Amíg ez nincs átírva,
  **egyetlen éles levél sem mehet ki.** Ez emberi feladat, és ma kell elkezdeni.

## 1.4 Amit nem tudtam eldönteni a kódból — nyitott kérdések

Ezekre a válasz emberi döntés vagy külső információ, nem kódolvasás:

1. **Hány postafiók és milyen domainen?** Ettől függ a napi keret és a felfutás.
   Ha a küldő domain új, a ramp 20-ról indul; ha bejáratott, magasabbról lehet.
2. **Van-e már Supabase / Apify / Reoon fiók**, vagy nulláról kell? Ez az
   0. szakasz emberi részének hossza.
3. **Az ügynökségi (8.1) kampány levele kollegiális hangvételű** — a jelenlegi
   `templates.py` szerkezete (fájdalom-először cold email) erre csak részben passzol.
   A szöveget a felhasználónak kell megírnia; az invariáns szerint az agent
   csak kifejezett kérésre nyúl hozzá.
4. **Az `EMAIL_VALIDATION` induló értéke** — `local_only` vagy `full`. Ez pénzkérdés,
   lásd a B) döntést; javaslat `local_only`, de a Reoon-fiók megléte dönt.

---

# 2. rész — Az integrációs döntések

## A) Egy adatbázis vagy kettő? → **Kettő, de nem két igazságforrás**

**Döntés:** két tároló marad, viszont **koncernenként egy** birtokosa van.

```
Supabase (Postgres)        │  cold-email-starter/data/*.csv
───────────────────────────┼──────────────────────────────────
IGAZSÁGFORRÁS ERRE:        │  IGAZSÁGFORRÁS ERRE:
  cég, kapcsolat, forrás   │    mi ment ki, mikor, melyik fiókból
  signal, score, status    │    ki válaszolt / pattant vissza
  suppression (teljes)     │    napi keret, ramp állapot
  hogy KI a jelölt         │    hogy MI a következő üzenet
```

A két tároló között **két irányú, de aszinkron** kapcsolat van, mindkettőt a
scraper vezérli (lásd C és E).

**Mérlegelt alternatívák:**

- *Migráljuk a küldőt Supabase-re.* Elvi szempontból ez a helyes: egy adatbázis,
  egy igazság. Gyakorlatban a `store.py` mind a 9 modul alatt van, a `guards.py`,
  `limits.py`, `deliverability.py` mind CSV-t olvas — ez 1-2 nap átírás **és** a
  meglévő, bizonyítottan működő védelmi réteg átírása, éles küldés előtt.
  A határidő mellett ez rossz üzlet. **Elvetve.**
- *Tükrözzük a CSV-ket a DB-be kétirányúan.* Konfliktuskezelést igényel
  (ki nyer, ha mindkettő írt), és a CSV-ken nincs lock. **Elvetve.**
- *Marad minden CSV-ben, nincs Supabase.* A dedupe, a signal-összeadás, a
  score-olás és a domain lock join nélkül nem megy, és a későbbi webes felület
  is DB-t igényel. **Elvetve.**

**A technikai adósság, amit ezzel vállalunk** (és mikor kell visszatérni rá):

| Adósság | Következmény | Mikor kell javítani |
|---|---|---|
| Két suppression lista, ami elcsúszhat | Ha a feedback-import kimarad, a DB nem tud a küldő DNC-jéről | Már most kezelve: az export **abortál**, ha az import nem futott le (lásd C) |
| A `leads.csv` **származtatott** artefakt | Kézzel szerkesztve némán szétcsúszik | Dokumentálva a fájl első sorában + `CLAUDE.md`-ben; a webes felület után (13. szakasz) tiltható |
| Nincs tranzakció a határon | Ha az export félbeszakad, félkész `leads.csv` marad | Atomikus írás: temp fájl + `os.replace` (2. szakasz) |
| A napi keret és a DB `status` külön él | Egy exportált, de ki nem küldött lead „queued"-ben marad | Ez helyes viselkedés, nem hiba — de a monitoring (12. szakasz) mutassa meg |

---

## B) Hol legyen az email validáció? → **Megosztva, de mindkét lépés a scraperben**

**Döntés:** a `SCRAPER-PLAN.md` kétlépcsős modellje (Validation fejezet, 2088-2155),
azzal a pontosítással, hogy **a fizetős lépés is a scraperben fut, de az export
pillanatában**, nem az enrichmentkor.

```
enrichment idején (olcsó, azonnal):
    1. INGYENES HELYI SZŰRŐ a scraperben
       formátum · MX · role-prefix (bővített lista) · eldobható domain
       · platform-szemét · kép/JS-ből kiszedett hulladék
       → eredmény: contacts.local_check = pass | fail + ok
                                                                  ↓
export előtt közvetlenül (fizetős, csak a túlélőkre, csak egyszer):
    2. REOON  →  contacts.verify_result + contacts.verified_at
       cache: ha verified_at < 90 nap, NEM hívjuk újra
                                                                  ↓
küldés pillanatában (ingyen, minden futásnál):
    3. verify.looks_unsendable()  — a küldő meglévő hálója, marad
```

**Miért nem a küldőben fut a Reoon:** a `sender.build_plan()` **minden futásnál
újraértékel minden leadet** a `leads.csv`-ben — ha a validáció ott lenne, ugyanarra
a címre naponta újra elfogyna a kredit. Ráadásul a küldő stdlib-only, a Reoon-hívás
HTTP-klienst és API-kulcsot vinne be oda. A scraperben viszont a `contacts` sorhoz
kötve egyszer fut le, és az eredmény eltárolva marad.

**Miért nem csak a scraperben, enrichment idején:** a terv helyesen mondja, hogy
*„egy három hete végzett validáció elavult"*. Ezért a Reoon-hívás nem az
enrichment része, hanem az **export kapujában** történik — a lead ekkor van
órákra a kiküldéstől. A 90 napos cache csak akkor üt be, ha a lead kiesett és
később visszatér.

**A catch-all szabály** a tervből változatlanul (2126-2135): `valid` → mehet,
`catch-all` → csak Tier A/B, `unknown` → csak Tier A, `invalid` → eldobás.
Az `EMAIL_VALIDATION = off | local_only | full` kapcsoló a scraper `.env`-jébe kerül,
**induló érték: `local_only`.**

**A 6. ellentmondás miatt:** a scraper helyi role-listája a küldőé **bővítve**
`admin`, `privacy`, `gdpr`, `office` (nem: `info`) — a küldő `ROLE_PREFIXES`-ét
**nem írjuk át**, mert az egy második, független háló, és a szigorúbb lista
felfelé kompatibilis.

---

## C) Hogyan jut vissza az eredmény? → **Fájl-alapú, watermarkos import, minden export előtt kötelezően**

Ez a terv legfontosabb kérdése, és a válasz szándékosan a legegyszerűbb működő
mechanizmus.

**Döntés:** a scraperben van egy `feedback` parancs, ami **közvetlenül olvassa** a
küldő három CSV-jét, és upsertel a DB-be. Ugyanaz a gép, ugyanaz a repó — nem kell
API, nem kell webhook, nem kell futó szolgáltatás.

```
cold-email-starter/data/sent.csv           →  outreach (status, stage, sent_at)
cold-email-starter/data/do-not-contact.csv →  suppression (email/domain szint)
cold-email-starter/data/bounces.csv        →  contacts.bounce_state + suppression
cold-email-starter/data/replies.csv  🆕    →  reply_events (osztályozásra vár)
```

**Gyakoriság — három ok, három ütem:**

| Mikor | Miért |
|---|---|
| **Minden `export` parancs első lépéseként, kötelezően** | Ez az, ami megakadályozza, hogy holnap újra kiadjuk ugyanazt a leadet |
| **Naponta egyszer, cronból**, a küldési ablak zárása után (12. szakasz) | Hogy a `status` és a riportok akkor is frissek legyenek, ha aznap nem exportálunk |
| **Kézzel, válaszgyanú esetén** | Ha a felhasználó lát egy választ a postafiókban, egy `feedback` futás azonnal átvezeti |

**A kemény szabály — ez a küldő „guards hiba = nem küldünk" invariánsának a párja:**

```
ha a feedback-import HIBÁRA FUT
   vagy a sent.csv/DNC fájl nem található
   vagy a legutolsó sikeres import régebbi, mint az utolsó sent.csv módosítás
        ↓
   az EXPORT MEGÁLL, exit 1, semmit nem ír a leads.csv-be
```

Indoklás: ha nem tudjuk, ki válaszolt vagy iratkozott le, akkor nem tudjuk, kit
szabad kiadni. A „nem tudom" itt sem lehet egyenlő azzal, hogy „senki".

**Idempotencia:** a `feedback_watermark` tábla tárolja fájlonként a legutolsó
feldolgozott `ts`-t és sorszámot. Az import mindig csak az az utáni sorokat nézi,
és minden írás upsert — tehát tetszőlegesen sokszor újrafuttatható.

**Miért nem API/n8n/webhook:** a küldő nem szolgáltatás, hanem CLI-script. Egy
webhook-réteg köré egy futó folyamatot igényelne, amit üzemeltetni kell — pont azt
a terhet, amit a terv is kerülni akar. A CSV-k append-only, időbélyegzett naplók:
pontosan az az adatstruktúra, amit inkrementálisan olvasni a legegyszerűbb.

---

## D) Ki birtokolja a lead állapotát? → **Két állapotgép, éles határral**

**Ezek nem ugyanannak a dolognak két nézete.** Az egyik a *cégé*, a másik az
*üzeneté*, és sosem szabad összeolvasztani őket.

```
SCRAPER ÁLLAPOTGÉP  (companies.status)      │ KÜLDŐ ÁLLAPOTGÉP (sent.csv-ből)
a LEAD életciklusa — a scraper írja         │ az ÜZENET foka — a küldő írja
────────────────────────────────────────────┼──────────────────────────────────
new       → most került be                  │ (nincs sor)   → cold jár neki
enriching → épp fut rajta a crawl           │ cold          → FU1 jár, 5 nap múlva
enriched  → weboldal-adatok megvannak       │ follow_up_1   → FU2 jár, 10 nap múlva
scored    → classifier lefutott             │ follow_up_2   → done
ready     → mehet outreachbe                │
queued    → kiírva a leads.csv-be           │
sent      → a sent.csv-ben megjelent  ←─────┤ (a feedback-import állítja)
done      → a szekvencia végigment   ←──────┤ (a feedback-import állítja)
replied   → válaszolt, ember veszi át ←─────┤ (a feedback-import állítja)
rejected  → nem fit                         │
suppressed→ tiltva                          │
error     → hiba, újrapróbálható            │
```

**Írási jogok — ez a szabály, amit soha nem törünk:**

| Ki | Mit írhat | Mit NEM írhat |
|---|---|---|
| **Scraper** | minden Supabase tábla; a `leads.csv` **teljes tartalma** | `sent.csv`, `do-not-contact.csv`, `bounces.csv`, `ramp_state.json` — soha |
| **Küldő** | `sent.csv`, `do-not-contact.csv`, `bounces.csv`, `replies.csv`, `ramp_state.json` | Supabase — soha; `leads.csv` — soha (ma sem írja) |

**A `queued` → `sent` átmenetet a feedback-import végzi, nem az exportáló.**
Ez fontos: ha az exportáló írná, akkor egy lead, ami kikerült a `leads.csv`-be, de
a napi keret elfogyása miatt sosem ment ki, hazudna a riportban.

**„opened" állapot nincs és nem is lesz** — a küldő 5. invariánsa tiltja a
nyitáskövetést. A `SCRAPER-PLAN.md` `outreach` táblájából ezt a mezőt el kell hagyni,
és a későbbi webes felület sem ígérhet megnyitási arányt.

---

## E) A konkrét átadási formátum → **A scraper teljes egészében újraírja a `leads.csv`-t**

**Döntés:** fájl-átadás, **push** irányban (a scraper indítja), teljes újraírás,
atomikusan.

```
leadgen export
      ↓
  1. feedback-import (kötelező, hiba → abort)
  2. lekérdezés: minden aktív lead a DB-ből
  3. domain lock + suppression + cooldown érvényesítés
  4. Reoon (ha EMAIL_VALIDATION=full)
  5. leads.csv.tmp megírása  →  os.replace()  →  leads.csv
  6. companies.status = 'queued', outreach sor létrehozása
```

**Miért teljes újraírás és nem append?** Három okból, és mindhárom fontos:

1. **A `store.py`-ban nincs upsert és nincs dedup.** `build_plan` ismétlődő email
   esetén csendben az utolsó sort veszi. Append mellett minden export duplikálna.
2. **A domain-szintű suppression így ingyen érvényesül.** Ha egy céget menet közben
   letiltunk, elég kihagyni az újraírásból: a `build_plan` csak a `leads.csv`-ben
   szereplő címeket veszi figyelembe, tehát a follow-up automatikusan elmarad.
   **Így nem kell a `do-not-contact.csv`-be írnunk** — az marad `guards.py`
   kizárólagos tulajdona, ahogy eddig.
3. **Újraindíthatóság.** Az export tiszta függvény a DB állapotából: bármikor
   újrafuttatható, ugyanazt az eredményt adja.

> ⚠️ **A csapda, amit ez rejt:** ha az export csak az ÚJ jelölteket írná ki, akkor
> minden folyamatban lévő lead kiesne a fájlból, és **elmaradnának a follow-upjaik**,
> mert a `build_plan` a lead sorából indul ki. Ezért az export mindig a
> **unió**: új jelöltek **+** minden `queued`/`sent` státuszú lead, ami még nem
> `done` és nincs suppressionben.

**A mezőlista, ami átmegy a határon** (`store.LEADS_HEADER` bővítése — biztonságos,
mert minden olvasás `DictReader` név szerint):

| Mező | Ki tölti | Mire kell |
|---|---|---|
| `email` | scraper | **a kulcs**, `.strip().lower()` |
| `company` | scraper | megszólítás, tárgy |
| `contact_name` | scraper | megszólítás (üres → semleges) |
| `website` | scraper | emberi átnézés |
| `industry` | scraper | sablon-szöveg |
| `city` | scraper | emberi átnézés |
| `notes` | scraper | **signal-összefoglaló**, emberi átnézésre |
| 🆕 `campaign` | scraper | **melyik sablonkészlet** (`agency_partner`, `dead_dev`, `ops_pain`, `ad_landing`) — a 3. ellentmondás megoldása |
| 🆕 `personalization` | scraper | az evidence-groundolt nyitómondat; **üres → sablon-fallback** — a 2. ellentmondás megoldása |
| 🆕 `source_url` | scraper | jogi minimum (0.4): honnan van az adat |
| 🆕 `scraped_at` | scraper | signal-frissesség |
| 🆕 `company_id` | scraper | a DB UUID — hibakereséshez és a jövőbeli join-hoz |

A visszairányban a `sent.csv` **nem** kap `company_id`-t (a küldő nem tud róla) —
a feedback-import `email` alapján joinol, ami elegendő, mert a `contacts.email`
gyakorlatilag egyedi.

---

## F) Hol fusson a válasz-osztályozás? → **A scraperben, de a küldőnek először meg kell őriznie a válaszokat**

**A 7. ellentmondás miatt ez a kérdés ma nem is megválaszolható: a válasz szövege
sehol nem marad meg.** `guards.run()` beolvassa IMAP-ról, regexet illeszt rá, majd
eldobja.

**Döntés — két lépés:**

1. **`guards.py` kap egy új, append-only `replies.csv`-t** (`ts, email, subject,
   body, classified`). Ez tudatosan **nem** módosítja a guards döntési logikáját:
   minden válaszoló ugyanúgy DNC-be kerül `replied` okkal, ahogy eddig. Csak
   megőrizzük azt, amit eddig eldobtunk. Kicsi, izolált változás.
2. **Az osztályozás a scraperben fut** (BULK tier LLM), a `feedback` parancs
   részeként, a `replies.csv`-ből. Kimenet: `interested` / `not_now` / `negative` /
   `unsubscribe` / `auto_reply` / `bounce_like`, és ez tölti a `suppression` táblát
   a terv szerinti okokkal.

**Miért a scraperben:** ott van az API-kulcs, ott van a `suppression` tábla, ott van
LLM-kliens, és a küldő stdlib-only maradhat. A küldő oldalán csak egy fájlírás
történik.

**És a 5. ellentmondás javítása, ami ehhez tartozik:** a `guards.UNSUB_PATTERNS`-ből
a nyers `r"\bnem\b"` mintát ki kell venni. Ez **nem gyengíti a védelmet**: minden
válaszoló a `replied` szabály miatt amúgy is DNC-be kerül, tehát a szűkítés nem
enged ki senkit — csak megszünteti a tömeges hamis `unsubscribe_request` okot,
ami miatt ma egy érdeklődő válasz is véglegesként kerülne suppressionbe.

**Az `auto_reply` külön eset:** a mai `guards.py` egy „házon kívül vagyok"
automatikus választ is `replied`-ként DNC-be tesz, tehát a lead örökre elveszik.
Az osztályozás ezt felismeri, és a scraper visszaadja a leadet a sorba
(`cooldown_until = +14 nap`) — a küldő DNC-jéből viszont **nem töröljük**, hanem
a lead új outreach-ciklusban, ugyanarról a címről indul újra. Ha ez gyakori,
a 12. szakaszban `guards.py`-ban is kezelhető (`Auto-Submitted` fejléc szűrés).

---

## Két további döntés, ami nem szerepelt a kérdések közt, de blokkoló

### G) n8n → **most nem építjük be**

A terv n8n-t tesz karmesternek. A 8. ellentmondás miatt ez most nem működik: a küldő
helyi CSV-ken és helyi IMAP-on él, egy konténerizált/felhős n8n nem éri el őket.

**Helyette:** a scraper egyetlen Python CLI (`leadgen <parancs>`), amit `cron`/`launchd`
indít. Indoklás a határidő szempontjából: a Claude Code Python-fájlokat ír és
verziózik; egy n8n workflow JSON-ját nehezen és rosszul. A rendszer minden lépése
így egy commitolható, tesztelhető, újrafuttatható parancs lesz.

**Mikor térjünk vissza rá:** ha a küldő valaha VPS-re költözik, vagy ha több,
párhuzamos, ütemezett forrás összehangolása kezd fájni. Addig a `cron` + a
Supabase `status` oszlop ugyanazt a szerepet tölti be, kevesebb mozgó alkatrésszel.

### H) Scrapling → **most `httpx` + `selectolax`**

A terv Scraplinget ír a website-crawlra. Az első engine-hez (8.1) statikus HTML-t
kell letölteni és parse-olni — ehhez a Scrapling adaptív-selector és böngésző-fetcher
rétege nem ad hozzá semmit, viszont nehezebb függőség és 3.10+-t igényel.

**Helyette:** `httpx` + `selectolax` a közös enrichment engine-ben, egy `fetch()`
absztrakció mögött. **Mikor térjünk vissza rá:** amikor egy konkrét forrás JS-renderelést
igényel (ekkor a `fetch()` mögé kerül be Playwright vagy Scrapling, egy fájl változik).

---

# 3. rész — A szakaszok

**Olvasási segédlet minden szakaszhoz:**
`[külön session]` = ezt egyedül csináld egy sessionben, ne fűzd össze mással.
`[összefűzhető]` = ha maradt keret, a következő szakasz elkezdhető ugyanabban.

---

## ✅ 0. szakasz — Emberi előfeltételek `[KÉSZ: 2026-08-19]`

**Cél:** meglegyen minden, ami nélkül a 5. szakaszban nem lehet éles levelet küldeni.
**Becsült agent-munkaidő:** 0,5 óra.
**Kész-definíció:** `python3 -c "import mailer; mailer.check_accounts()"` minden fiókra
`OK`-t ír; a `sender.py --dry --skip-guards` kimenetében **nincs egyetlen `<IDE IRD ...>`
placeholder sem**; a Supabase projekt létezik és a connection string a kezedben van.

### Az ÉN feladataim (ember)

- ✅ ~~**Döntés: hány postafiók, melyik domainen.**~~ → **paladi-web.hu**, egy új,
  dedikált postafiók: `balint@paladi-web.hu`. Az indoklás a Döntésnaplóban.
  (Tartaléknak regisztrálva a `paladiweb.hu`, Netlify DNS-en 301-gyel a fő oldalra;
  levelezésre a 9. szakasztól használható, addig öregszik.)
- ✅ ~~**SPF, DKIM, DMARC beállítása.**~~ → Már készen volt, ellenőrizve `dig`-gel:
  SPF `include:_spf.google.com ~all`, DKIM `google._domainkey` 2048 bit,
  DMARC `p=quarantine; adkim=s; aspf=s`. Nyitott apróság (nem blokkoló):
  hiányzik a `rua=`, tehát nem érkeznek DMARC-jelentések.
- ✅ ~~**Supabase projekt + connection string.**~~ → `aws-1-eu-west-1`, session pooler
  (5432), TCP kapcsolat ellenőrizve. A `DATABASE_URL` a gyökér `.env`-ben.
- ✅ ~~**Az ügynökségi (8.1) kampány három levele.**~~ → Megírva a `templates.py`-ba
  (`agency_cold`, `agency_follow_up_1`, `agency_follow_up_2`). Ékezetes szöveg,
  tegezés, „stop" leiratkozási szó — mind a Döntésnaplóban indokolva.
  ⚠️ **Nyitott:** a 3. levél tapasztalata az agenttől származik, a felhasználónak
  ki kell cserélnie egy valódi sajátra, mielőtt élesben kimegy (5. szakasz).
- ✅ ~~**Reoon döntés.**~~ → Most nem veszünk kreditet. `EMAIL_VALIDATION=local_only`,
  a Reoon a 7. szakaszban kapcsolható be.
- ⬜ **Gemini + Anthropic API kulcs** — a 6. szakaszban kell, nem most.

### Az agent feladatai

1. ✅ ~~`.env` létrehozása~~ — **két** `.env` készült: `cold-email-starter/.env`
   (SMTP/IMAP) és a gyökér `.env` (Supabase). A titkokat a felhasználó írta be;
   az agent nem olvasta őket.
2. ✅ ~~`.gitignore` a repó gyökerében~~ — **ez eddig nem létezett.** Előrehozva az
   1. szakaszból, mert enélkül a gyökérbe írt `.env` a git-be került volna.
3. ✅ ~~`mailer.check_accounts()` futtatása~~ — `SMTP balint@paladi-web.hu: OK`.
   Plusz külön IMAP-teszt: bejelentkezés OK, INBOX kiválasztva (0 üzenet).
4. ✅ ~~A 8.1 sablonok megírása~~ — a felhasználó kifejezett kérésére.
5. ✅ ~~Ellenőrzés, hogy az ékezetes magyar szöveg átmegy-e a küldőn~~ — helyi SMTP
   szerverrel letesztelve: tárgy RFC 2047, törzs UTF-8/8bit, mindkettő hibátlan.

### Ellenőrzés a szakasz végén

```bash
cd cold-email-starter
python3 -c "import mailer; mailer.check_accounts()"    # minden fiók OK
python3 sender.py --dry --skip-guards | grep -c "IDE IRD"   # eredmény: 0
```

---

## ✅ 1. szakasz — Alapozás `[KÉSZ: 2026-08-19]`

**Cél:** működő Python-környezet, projektstruktúra, DB-séma és a determinisztikus
segédfüggvények — **nulla üzleti logika**.
**Becsült agent-munkaidő:** 2,5 óra.
**Kész-definíció:** `leadgen db migrate` lefut egy üres Supabase projekten,
`leadgen db check` kiírja a hat tábla sorszámát, `pytest` zölden fut.

### Az ÉN feladataim (ember)

- **A szakasz előtt** — a Supabase connection string átadása (0. szakaszból).
- **A szakasz alatt** — semmi. Ez tiszta agent-munka.
- **A szakasz után** — nézd meg a Supabase Table Editorban, hogy a hat tábla ott van-e,
  és hogy a `suppression` táblának van-e sora (üresnek kell lennie).

### Az agent feladatai

1. **Python 3.12 telepítése**: `brew install python@3.12`. A `python3` **marad 3.9.6**,
   mert a küldő azon fut és nem akarjuk elmozdítani. A scraper saját venv-et kap
   3.12-vel: `/opt/homebrew/bin/python3.12 -m venv .venv`.
2. **Projektstruktúra** a repó gyökerében:
   ```
   leadgen/
     __init__.py
     cli.py            # argparse, alparancsok — vékony réteg
     config.py         # .env olvasás, ugyanaz a minta, mint a küldőnél
     db.py             # EGYETLEN hely, ahol psycopg-t hívunk
     normalize.py      # domain, cégnév, telefon, email normalizálás
     blocklist.py      # platform-domain blocklist
     migrations/
       001_init.sql
   tests/
     test_normalize.py
   pyproject.toml      # függőségek: psycopg[binary], httpx, selectolax, pytest
   .env.example        # a scraper saját .env-je, NEM a küldőé
   .gitignore          # ÚJ, a repó gyökerében
   ```
3. **`.gitignore` a repó gyökerében** (ma nincs!): `.env`, `.venv/`, `__pycache__/`,
   `data/`, `cache/`, `*.sqlite`, `.DS_Store`. Ez az invariáns #4 miatt kötelező.
4. **`001_init.sql`** — a `SCRAPER-PLAN.md` sémája (2156-2311), a döntéseinkkel:
   - `companies` (UUID pk, `normalized_domain` UNIQUE **nullable**, `platform_url`,
     `tax_number`, `name_key`, `status`, `cooldown_until`, `signal_score`,
     `best_offer`, `created_at`, `updated_at`)
   - `sources` (`company_id`, `source_type`, `source_url`, `raw_signal` JSONB,
     `detected_at`) + UNIQUE (`source_type`, `source_url`) — ez a 0.2 fejezet
     inkrementális működésének a kulcsa
   - `contacts` (`company_id`, `email` UNIQUE, `name`, `email_type`, `local_check`,
     `verify_result`, `verified_at`, `source_url` **NOT NULL** — a 0.4 jogi minimum)
   - `suppression` (`normalized_domain`, `email` nullable, `reason`, `note`,
     `created_at`)
   - `outreach` (`company_id`, `contact_id`, `campaign`, `offer`, `status`,
     `stage`, `queued_at`, `sent_at`, `replied_at`, `sender_account`)
     + **részleges UNIQUE index** `(company_id) WHERE status IN ('queued','sent')`
     — ez a **domain lock** DB-szintű kikényszerítése
   - `feedback_watermark` (`file`, `last_ts`, `last_row`, `updated_at`)
   - `reply_events` (`email`, `received_at`, `subject`, `body`, `classification`,
     `classified_at`)
5. **`normalize.py`** — tiszta függvények, semmi I/O:
   `normalize_domain()`, `normalize_company_name()` (kisbetű, ékezettelenítés,
   `kft/bt/zrt/nyrt/kkt/ev` + a kiírt hosszú változatok levágása),
   `normalize_phone()` (+36 alak), `normalize_email()` (`.strip().lower()` — a
   küldővel **azonos** szabály, a dedup erre épül).
6. **`blocklist.py`** — a terv 2470-2500 szerinti platform-lista. Ha egy domain
   a listán van: **nem lehet company key**, `platform_url`-be megy, és a dedupe
   fallbackre vált (adószám → `name_key` + település → telefon).
7. **`tests/test_normalize.py`** — a terv példáival: `https://www.example.hu`,
   `shop.example.hu`, `example.hu/contact` → mind `example.hu`; a
   `"Paládi Klíma Kft." / "PALÁDI KLÍMA KFT" / "...Korlátolt Felelősségű Társaság"`
   → mind `paladi klima`; `facebook.com/valami` → **nem** company key.
8. **`CLAUDE.md` bővítése** egy „A scraper" szakasszal: hol a venv, mi a CLI,
   melyik interpreter melyik rendszerhez tartozik, és hogy a `leads.csv`
   **származtatott fájl, kézzel ne szerkeszd**.

> **Miért van itt pytest, ha a küldőben nincs test suite?** Mert a domain- és
> cégnév-normalizálás hibái **némák**: két cég összeolvad, vagy egy cég kétszer
> kap levelet, és ez sehol nem dob hibát. Ez a 15 perc teszt a legjobb ár/érték
> arányú védelem az egész tervben. A többi modulra nem írunk tesztet.

### Ellenőrzés a szakasz végén — ✅ lefuttatva

```bash
.venv/bin/python -m leadgen.cli db migrate   # + 001_init.sql, majd idempotens
.venv/bin/python -m leadgen.cli db check     # 7 tábla, mind 0 sor
.venv/bin/pytest                             # 49 teszt zöld
cd cold-email-starter && python3 sender.py --dry --skip-guards   # VÁLTOZATLAN
```

Az utolsó sor a lényeg: **az 1. szakasz nem nyúlt a küldőhöz.**

### Amit a szakasz közben tanultunk

- **A teszt azonnal megtérült.** A `normalize_company_name` a többszavas társasági
  formákat (`nonprofit kft`) sosem vágta volna le, mert a szó szintű szűrő egy
  két szóból álló bejegyzést nem tud illeszteni. Élesben ez azt jelentette volna, hogy
  a „Teszt Nonprofit Kft." és a „Teszt Kft." **két külön cégként** kerül be — két levél
  ugyanannak. Némán. Ezt a `tests/test_normalize.py` találta meg, nem egy code review.
- **`.venv/bin/pytest` és `python -m pytest` nem ugyanaz.** Az utóbbi a cwd-t is a
  `sys.path`-ra teszi, az előbbi nem — a `from leadgen import ...` csak az egyikkel
  működött. Javítva a `pyproject.toml` `pythonpath = ["."]` sorával, hogy mindkettő jó legyen.
- **Eltérés a tervtől:** a függőségek `requirements.txt`-ben vannak, nem a
  `pyproject.toml` `[project]` táblájában. Így nincs build backend és nincs
  `pip install -e .` lépés, tehát nem tud elavulni egy telepített másolat a forráshoz
  képest. A `pyproject.toml` csak a pytest konfigját tartalmazza.
- **A `.gitignore` a 0. szakaszban készült el**, előrehozva — enélkül a gyökérbe írt
  `.env` a git-be került volna.

---

## 🟡 2. szakasz — A határ, 1. irány: export DB → `leads.csv` `[agent-rész kész: 2026-08-20]`

**Cél:** a DB-ből ki lehessen írni egy olyan `leads.csv`-t, amiből a küldő helyes
leveleket tervez — domain lockkal, suppressionnel, kampány-választással.
**Becsült agent-munkaidő:** 2,5 óra.
**Kész-definíció:** kézzel beszúrt 3 teszt-cégből az `export` helyes `leads.csv`-t ír;
a `sender.py --dry --skip-guards` mindhármat a **helyes kampány sablonjával** rendereli;
ha egy céget suppressionbe teszek, a következő export után eltűnik a fájlból.

> **Ez a szakasz szándékosan az összes scrapelés ELŐTT van.** A legkockázatosabb rész
> az integráció, nem a scrapelés — és kézzel beszúrt sorokkal teljes egészében
> tesztelhető. Ha ez működik, bármelyik engine rácsatlakoztatható.

### Az ÉN feladataim (ember)

- **A szakasz alatt** — nézd át és fogadd el a `templates.py` szerkezeti módosítását
  (kampány-választás + `personalization` mező). A **szövegekhez** az agent nem nyúl.
- **A szakasz után** — olvasd el a dry-run kimenetét soronként. Ez az utolsó pont,
  ahol olcsó észrevenni, ha valami nem stimmel a levélben.

### Az agent feladatai — ✅ mind kész

> A megvalósult modulok: `leadgen/contract.py` (a határ definíciója),
> `leadgen/export.py` (az exportáló), `leadgen/dev.py` (teszt-adat),
> `leadgen/migrations/002_export.sql`, `tests/test_contract.py`.

1. **`store.LEADS_HEADER` bővítése** (`store.py:19`) az E) pont mezőivel. Biztonságos:
   minden olvasás `DictReader`, tehát név szerinti.
2. **`templates.py`**: `CAMPAIGNS` dict, ami `campaign` → `(cold, follow_up_1,
   follow_up_2)` hármast ad; a meglévő három függvény lesz a `default` kampány.
   A `_greeting()` és a két bedrótozott szabály **változatlan**.
   A `personalization` mező a nyitómondat helyére kerül; **ha üres, sablon-fallback**.
3. **`sender.build_plan` minimális módosítása** (`sender.py:76-85`): a sablon-hármas
   a lead `campaign` mezőjéből jöjjön, ismeretlen/üres érték esetén `default`.
   Kb. 10 sor. Minden más marad.
4. **`leadgen/export.py`**:
   - lekérdezés: minden `ready` státuszú lead **+** minden `queued`/`sent`, ami még
     nem `done` (ez a „unió", lásd E) pont csapdája)
   - **suppression join a legelső lépésként** (domain VAGY email), a terv 0.4 szerint
   - **domain lock**: `normalized_domain`-enként pontosan egy contact; ha több van,
     a legjobb `email_type` nyer (`personal` > `generic` > `role`)
   - **cooldown**: `cooldown_until > now()` → kihagyás
   - **offer arbitration**: a legmagasabb `*_fit` dönti el a `campaign`-t; a cég
     **egyetlen** kampányba kerül (terv 2342-2370)
   - **atomikus írás**: `leads.csv.tmp` → `os.replace()`
   - `--dry` kapcsoló: kiírja, mi menne a fájlba, de nem ír
   - a `leads.csv` első sora után egy megjegyzés-sor **nem** fér el (CSV),
     ezért a figyelmeztetés (`származtatott fájl`) a `CLAUDE.md`-be és a
     `data/README.txt`-be kerül
5. **`leadgen/cli.py`**: `export` alparancs.
6. Seed-script: `leadgen dev seed` — 3 fiktív teszt-cég beszúrása, hogy a szakasz
   újraindítható és tesztelhető legyen valódi scrapelés nélkül.

### Amit a szakasz közben tanultunk

- **Részleges UNIQUE indexnél az `ON CONFLICT`-nak meg kell ismételnie az index
  feltételét**, különben a Postgres nem találja meg:
  `on conflict (normalized_domain) where normalized_domain is not null do nothing`.
  Minden jövőbeli `companies`-upsertre igaz.
- **A sorrend nem kozmetika.** A `sender.build_plan` a `fresh` listát a fájl
  sorrendjében veszi, és a napi keret levágja a végét — tehát **a sorrend dönti el,
  ki kap ma levelet**. Az első verzióban a két lekérdezés máshogy rendezett, és az
  azonos `queued_at` miatt a sorrend futásonként változott. Most a rendezés egységesen
  `signal_score desc, email`, és három egymás utáni export bitre azonos fájlt ad.
- **A `personalization` két helyen él**: `companies` (munkaverzió, a scoring írja) és
  `outreach` (befagyasztva a sorba állításkor). Enélkül egy újrapontozott cég
  follow-upja már más bizonyítékra hivatkozna, mint a kiküldött cold email.
- **Átmeneti megoldás a 3. szakaszig:** az exportáló közvetlenül beolvassa a küldő
  `do-not-contact.csv`-jét. A teljes, watermarkos feedback-import ezt váltja fel —
  de a DNC-listára nem várhatunk egy szakaszt.
- **A teszt-adat `.invalid` domaineket használ** (RFC 2606), tehát egy véletlen
  `--live` futás sem tudna valakinek ténylegesen levelet küldeni. Az exportáló ezen
  felül hangosan figyelmeztet, ha ilyen cím van a listában.

### Ellenőrzés a szakasz végén — ✅ lefuttatva

```bash
.venv/bin/python -m leadgen.cli dev seed
.venv/bin/python -m leadgen.cli export --dry     # 3 sor, helyes kampány
.venv/bin/python -m leadgen.cli export
cd cold-email-starter && python3 sender.py --dry --skip-guards
# → 3 levél, mindegyik az agency_partner sablonnal, personalization mondattal

# domain lock teszt: szúrj be egy MÁSODIK contactot ugyanahhoz a domainhez
.venv/bin/python -m leadgen.cli export
wc -l data/leads.csv    # a sorszám NEM nőtt

# suppression teszt
# (kézzel: INSERT INTO suppression ... reason='manual_block')
.venv/bin/python -m leadgen.cli export
grep <az_a_cim> cold-email-starter/data/leads.csv    # nincs találat
```

---

## ✅ 3. szakasz — A határ, 2. irány: feedback-import `[KÉSZ: 2026-08-20]`

<!-- 4. szakasz allapota lentebb -->

**Cél:** a küldő eredménye (küldés, bounce, leiratkozás, válasz) visszakerüljön a DB-be,
és az export enélkül ne is induljon el.
**Becsült agent-munkaidő:** 2,5 óra.
**Kész-definíció:** egy szimulált küldés után a `feedback` import helyesen állítja a
`status`-t; egy kézzel a DNC-be írt cím a következő exportból kiesik; ha a `sent.csv`
nem olvasható, az `export` **exit 1**-gyel megáll és nem ír fájlt.

### Az ÉN feladataim (ember)

- **A szakasz alatt** — döntsd el, elfogadod-e a `guards.py` két módosítását:
  (a) `replies.csv` írása, (b) a `\bnem\b` minta kivétele az `UNSUB_PATTERNS`-ből.
  Mindkettő indoklása fent, az F) pontban. A (b) nem gyengíti a védelmet.
- **A szakasz után** — nézd meg a `data/replies.csv`-t, ha már van benne sor.

### Az agent feladatai

1. **`guards.py` — `replies.csv`**: minden felismert válasz (NDR-en kívül) egy sorral
   naplózódik (`ts, email, subject, body, classified`), a `body` első ~2000 karaktere.
   `store.py`-ban új header + `record_reply()`. **A guards döntési logikája nem változik.**
2. **`guards.UNSUB_PATTERNS`** — a nyers `r"\bnem\b"` minta törlése. A konkrétabb
   minták (`nem erdekel`, `koszonom, nem`, `ne kuldj...`) maradnak.
3. **`leadgen/feedback.py`**:
   - watermark-alapú inkrementális olvasás mind a négy CSV-ből
   - `sent.csv` → `outreach.status`/`stage`/`sent_at`, `companies.status`
     (`sent`; `follow_up_2` esetén `done`)
   - `do-not-contact.csv` → `suppression` (ok-térkép: `replied` → nem suppression,
     hanem `companies.status='replied'` + ember-sor; `unsubscribe_request` →
     `unsubscribe`; `hard_bounce` → `manual_block` + `contacts.verify_result='invalid'`)
   - `bounces.csv` → `contacts.bounce_state`
   - `replies.csv` → `reply_events` (osztályozatlanul; a 6. szakasz osztályozza)
   - **cooldown**: aki `done` lett válasz nélkül → `cooldown_until = +90 nap`
     (terv 2372-2405)
4. **Az export blokkolása**: az `export` első lépése a `feedback` futtatása; hiba,
   hiányzó fájl, vagy elavult watermark esetén **exit 1, semmilyen írás**.
5. **`leadgen/cli.py`**: `feedback` alparancs (önállóan is futtatható).

### Amit a szakasz közben tanultunk

- **A leiratkozás-felismerés KÉTIRÁNYBAN hibás volt**, nem csak a tervezett
  hamis-pozitív irányban. Mérve:

  | Válasz | Régi kód | Új kód |
  |---|---|---|
  | „Most nem aktuális, de jövőre kérdezz rá!" | ❌ leiratkozásnak vette | ✅ nem |
  | „Kérlek távolíts el a listáról" | ❌ **egy mintára sem illeszkedett** | ✅ igen |
  | „Kérem töröljenek a listáról" | ❌ nem illeszkedett | ✅ igen |

  Az ok: a minták ASCII-ban vannak (`tavolits`, `nem erdekel`, `torol.*listar`),
  a magyar válaszok viszont ékezetesek. Ha csak a `\bnem\b`-et töröltük volna
  a terv szerint, az ékezetes leiratkozások helyzete **romlott** volna. Ezért a
  `guards._fold()` ékezet-hajtogatást végez az illesztés előtt — a bounce-minták
  (`nincs ilyen felhasznalo`) is ettől lettek működőképesek.
  Regressziós teszt: `tests/test_guards_patterns.py`.

- **A `guards.py` minden futásnál újraolvassa a teljes 14 napos postafiókot**
  (9. ellentmondás), tehát ugyanaz a válasz többször is elénk kerül. A dedup
  ezért a **Message-ID**-n áll, amit a `mailer.fetch_recent` mostantól kinyer.
  Az IMAP `uid` erre nem jó: postafiókonként külön számozódik.

- **Leiratkozásnál az `outreach` sort is le kell zárni**, nem elég a cég státuszát
  `suppressed`-re állítani. A domain lock részleges indexe (`where status in
  ('queued','sent')`) különben örökre „aktívnak" látná a szekvenciát, és a cég
  soha nem kaphatna új outreach sort. Ezt az életciklus-teszt találta meg.

- **A `dev clear-seed` nem adott tiszta lapot**: a `suppression` és a
  `reply_events` szándékosan nem kapcsolódik céghez (egy tiltás akkor is érvényes
  marad, ha a cég kikerül a DB-ből), ezért egy korábbi teszt leiratkozása némán
  blokkolta az újra beszúrt teszt-cégeket. Most a `.invalid` címekhez tartozó
  tiltásokat is takarítja.

- **Nyitott döntés — hard bounce esetén mi legyen a céggel?** A jelenlegi
  viselkedés: a *cím* suppressionbe kerül és `invalid` lesz, az outreach lezárul,
  a **cég viszont visszakerül `ready`-be 30 napos cooldownnal**, hogy egy másik
  címmel később újra próbálkozhasson. Az alternatíva a `rejected` lenne
  (konzervatívabb, de elveszít egy jó céget egyetlen elavult `info@` cím miatt).
  Felülvizsgálandó az első valódi bounce-ok után.

### Ellenőrzés a szakasz végén — ✅ lefuttatva

Végigjátszva egy teljes életciklus szimulált küldéssel:

```
3 cold kiküldés ............... ceg=sent, outreach=sent, sent_at kitöltve
érdeklődő válasz .............. ceg=replied  (NEM suppression — ember vegye át)
leiratkozás ................... ceg=suppressed, outreach=stopped, suppression=unsubscribe
hard bounce ................... cím suppressed+invalid, ceg=ready + 30 nap cooldown
teljes létra válasz nélkül .... ceg=done, outreach=done, cooldown=90 nap
lezárt lead ................... kiesik a leads.csv-ből
idempotencia .................. 2. futás: 0 új sor
ABORT: hiányzó sent.csv ....... exit=1, a leads.csv ÉRINTETLEN
pytest ........................ 74 teszt zöld
```

```bash
# szimulált küldés: kézzel írj egy sort a sent.csv-be az egyik teszt-leadre
.venv/bin/python -m leadgen.cli feedback
# → a DB-ben companies.status = 'sent', outreach.sent_at kitöltve

# DNC teszt
python3 -c "import store; store.add_to_dnc('teszt@example.hu','unsubscribe_request')"
.venv/bin/python -m leadgen.cli feedback
.venv/bin/python -m leadgen.cli export
grep teszt@example.hu cold-email-starter/data/leads.csv   # nincs találat

# abort teszt
mv cold-email-starter/data/sent.csv /tmp/ && \
  .venv/bin/python -m leadgen.cli export; echo "exit=$?"   # exit=1, leads.csv érintetlen
mv /tmp/sent.csv cold-email-starter/data/

# idempotencia: kétszer egymás után
.venv/bin/python -m leadgen.cli feedback && .venv/bin/python -m leadgen.cli feedback
# → a második futás 0 új sort dolgoz fel
```

**Ezzel a határ mindkét iránya kész és tesztelt — scrapelés nélkül.**

---

## 🟡 4. szakasz — A 8.1 engine: ügynökségi partner lista `[agent-rész kész: 2026-08-21]`

**Cél:** valódi leadek kerüljenek a DB-be — az egyetlen engine, ami napokon belül
kiküldhető listát ad.
**Becsült agent-munkaidő:** 3 óra.
**Kész-definíció:** legalább **60 kvalifikált ügynökség** van a DB-ben `ready`
státuszban, mindegyiknél email cím **és** `source_url`; a kizárt (fejlesztést is
hirdető) cégek `suppression`-ben vannak `competitor` okkal.

> **Miért ez az EGY engine end-to-end, és nem az 1. (Operational Pain)?**
> Négy oka van, és mind a határidőről szól:
> 1. **Nem igényel AI-t.** A kvalifikáció kulcsszóegyezés (a terv maga mondja ki,
>    a „Ami NEM igényel AI-t" fejezetben). Tehát **nem blokkolja a bake-off**.
> 2. **Nem igényel Apify-t.** Nincs fizetős Actor, nincs 0.3 szerinti előteszt-kockázat.
> 3. **Véges és kicsi a célcsoport** (100-300 cég) — nem kell volumen-motor.
> 4. **A legmagasabb válaszarány**, és 1 lead = N projekt.
>
> Cserébe minden határ-elemet kihajt: dedupe, suppression, enrichment,
> email-extraction, validáció, export, küldés, feedback. Az 1. engine a 9-10. szakaszban jön.

> **⚠️ 2026-08-20: a szakasz átírva kézi listáról automatizált forrásra.**
> Az eredeti terv kézi seed-gyűjtést javasolt, mert a `SCRAPER-PLAN.md` 8.1 fejezete
> szerint „ez nem scraping-probléma, ez egy lista". A felhasználó jogosan kifogásolta:
> a projekt célja az automatizálás. **Amit méréssel megállapítottunk:**
>
> | Forrás | Állapot | Következmény |
> |---|---|---|
> | `cylex.hu` | **Cloudflare challenge**, még a `robots.txt` is | közvetlenül nem scrapelhető; a megkerülése detekció-kijátszás lenne, nem építjük |
> | `linkedin.com` | `robots.txt`: *„The use of robots or other automated means to access LinkedIn without the express permission of LinkedIn is strictly prohibited"* | kizárva |
> | **Apify Google Maps actor** | ✅ működő út | kategória + település szerint keres ügynökségeket, a blokkolást az Apify infrastruktúrája kezeli |
> | Szakmai szervezetek taglistái | ✅ jellemzően statikus HTML | a generic directory motor kezeli, forrásonként egy config |
>
> Vagyis az automatizálás **az Apify-on keresztül vezet** — pontosan úgy, ahogy a
> `SCRAPER-PLAN.md` „Apifyt hogyan használnám?" fejezete előírja: kész, olcsó Actor
> ott, ahol a platform bonyolult. Emberi feladat így **egy token beszerzése**, nem
> egy lista összegyűjtése.

### Az ÉN feladataim (ember)

- **A szakasz előtt** — **Apify fiók + API token** a gyökér `.env`-be (`APIFY_TOKEN`).
  Free tier is elég a teszteléshez. Kb. 10 perc. **Ez az egyetlen blokkoló.**
- **A szakasz előtt (terv 0.3, kötelező)** — futtasd le a Google Maps actort
  **egyetlen kis lekérdezéssel** (pl. „marketing ügynökség Budapest", limit 10), és
  nézd meg **saját szemmel** a nyers outputot. **A kritikus mező: a `website`.**
  Ha az actor nem adja vissza a cég weboldalát, csak a Maps-profilt, akkor az egész
  enrichment elesik, és másik actort kell keresni.
- **Opcionális gyorsító, nem kötelező** — ha eszedbe jut 5-10 ügynökség, akit
  ismersz, dobd be egy `seeds/agencies.txt` fájlba (soronként egy domain). Az
  engine ezt is beolvassa, kiegészítésként. Ez már nem feltétele a szakasznak.
- **A szakasz után, kötelezően** — nézd át a `ready` listát **saját szemmel**.
  Ez 60 sor, 15 perc. Húzd ki, akit ismersz, akivel dolgoztál, vagy aki mégis
  versenytárs. Ezek `manual_block` / `existing_client` okkal mennek suppressionbe.

### Az agent feladatai

0. **`leadgen/sources/apify.py`** — Actor futtatás + dataset letöltés (ezt a
   9. szakasz újrahasznosítja a Profession engine-hez).
   **`leadgen/sources/directory.py`** — generic, config-vezérelt directory scraper
   statikus HTML-hez (szakmai szervezetek taglistái). Input: start URL-ek,
   lapozás-minta, cég-selector, mező-selectorok. Új katalógus = új config, nem új kód.
   **Fallback:** `seeds/*.txt` beolvasása, ha a felhasználó kézzel is ad domaineket.

1. **`leadgen/enrich.py` — a közös enrichment engine** (a terv „A közös enrichment
   engine" fejezete). Ezt **egyszer írjuk meg**, minden későbbi engine ezt használja:
   - `fetch(url)` absztrakció `httpx`-szel (timeout, retry, UA, `robots.txt` tisztelet)
   - oldal-felderítés: `/`, `/kapcsolat`, `/contact`, `/rolunk`, `/about`,
     `/szolgaltatasok`, `/services`, `/impresszum`, `/csapat`, `/karrier`
   - kivonat: `title`, `meta_description`, `emails[]`, `phones[]`, `socials[]`,
     `service_text`, `about_text`, `has_form`, `has_booking`, `has_shop`,
     `footer_html`, `pages_found[]`
   - **tech fingerprint (7.5)**: CMS generator meta, SSL lejárat, viewport meta,
     footer copyright év, webshop platform. Ingyen, regexszel — a terv szerint
     ez nem AI-feladat.
   - **nem tárolja az egész oldalt**, csak a strukturált kivonatot (`sources.raw_signal`
     JSONB-ben) + a nyers HTML-t egy `cache/` mappában (gitignore-olva), hogy az
     evidence grounding később ellenőrizhető legyen
   - **batch-elt működés**: `SELECT ... WHERE status='new' LIMIT 50` → feldolgoz →
     `status='enriched'`. Rövid, determinisztikus futás, ahogy a terv 2645-2711 előírja.
2. **`leadgen/engines/agency.py`**:
   - a seed-fájl beolvasása, domain normalizálás + blocklist, `companies` upsert
   - enrichment futtatása
   - **kvalifikáció kulcsszóval** (terv 8.1): kell marketing-kulcsszó
     (`ppc`, `google ads`, `meta ads`, `közösségi média`, `seo`, `tartalom`,
     `branding`, `stratégia`, `kreatív`) ÉS **nem lehet** fejlesztés-kulcsszó
     (`egyedi fejlesztés`, `webfejlesztés`, `applikációfejlesztés`,
     `szoftverfejlesztés`, `fejlesztő csapat`, `react`, `laravel`, `node`,
     `ios`, `android`)
   - **a kizártak → `suppression`, `reason='competitor'`** — ez ingyen ad
     versenytárs-térképet, ahogy a terv írja
   - email-kinyerés a terv sorrendjében (source → homepage/footer → `/kapcsolat`
     → `/impresszum` → `/rolunk` → ÁSZF/privacy), `email_type` besorolás
     (`personal` / `generic` / `role`) regexszel
   - **helyi validáció** (B) pont 1. lépése): formátum, MX, bővített role-lista,
     eldobható domainek
   - `personalization` mondat **AI nélkül**: sablonos, de tényszerű — a kvalifikációnál
     talált konkrét szolgáltatás-szavakból (pl. „Láttam, hogy nálatok a PPC és a
     tartalom az erősség, fejlesztést viszont nem hirdettek szolgáltatásként.")
     A valódi AI personalizáció a 10. szakaszban jön.
   - `status='ready'`, `campaign='agency_partner'`
3. **`leadgen/cli.py`**: `ingest agency --seeds seeds/agencies.txt`, `enrich`,
   `qualify agency` alparancsok — **külön lépések**, hogy bármelyik újrafuttatható legyen.

### Amit a szakasz közben tanultunk

- **Az `urllib.robotparser` hamis tiltást ad WAF mögötti oldalakra.** A beépített
  `RobotFileParser.read()` a Python alapértelmezett User-Agentjével tölt le, amit a
  Cloudflare-féle védelmek 403-mal utasítanak el — a parser pedig a 403-at „minden
  tiltva"-ként értelmezi. Mérve: a `marketing21.hu` és a `2100labs.com` robots.txt-je
  kifejezetten **engedélyez** mindent (`Disallow:` üresen), a parser mégis tiltást
  jelzett. Így az enrichment gyakorlatilag **minden magyar oldalon némán elbukott
  volna** — nem hibával, hanem „robots.txt tiltja" üzenettel. Javítva: saját UA-val
  töltjük le, és csak a ténylegesen beolvasott szabályokat vesszük figyelembe.

- **Idegen domainű email címek szivárognak be a crawlból.** A `marketingtanacsado.hu`-n
  megjelent egy `admin@megacp.com` (a tárhelyszolgáltatóé) és egy másik domainhez
  tartozó cím is. Ha ilyet írnánk a `leads.csv`-be, nem a célzott céget keresnénk meg.
  Javítva: a cég **saját domainjéhez** tartozó címek élveznek elsőbbséget, és a
  role-prefix lista bővült (`admin`, `privacy`, `gdpr`, `support`) — az `info@`
  szándékosan **nem** szerepel benne.

- **A `https://domain` újraépítése hibás volt** — a Maps által visszaadott VALÓDI
  URL-t eldobtuk. A `chiro.hu`-nál a `https://chiro.hu` 500-at ad, a
  `http://www.chiro.hu` viszont 301-et. Javítva: az eredeti URL az első jelölt,
  utána jönnek a `https://`, `https://www.`, `http://` variánsok.
  *(Megjegyzés: az érintett 10 cégnél ez végül nem segített — azok az oldalak
  böngészővel is 500/403-at adnak, tehát valóban hibásak. A javítás mégis
  helyes: a jövőbeli forrásoknál ez a leggyakoribb elérési hiba.)*

- **Valós adatminőség, első futás:** 60 cégből 10 weboldala **nem érhető el**
  (HTTP 500, 403 vagy nem feloldható DNS). Böngésző User-Agenttel is ugyanaz —
  nem a scraper hibája. Ezzel tervezni kell: nagyjából minden hatodik magyar
  KKV-weboldal elérhetetlen egy automatizált látogatás számára.

- **🔑 A kulcsszó-kizárás túl szigorú volt — kettéosztva.** Az első éles futáson
  9 cégből 8 lett „versenytárs". Kézzel megnézve a találatokat kiderült, hogy a
  `plus-kreativ.hu` azért esett ki, mert egy **ügyfél-referenciában** szerepelt a
  „webfejlesztési feladatokat" kifejezés — nem a saját szolgáltatásai közt.

  A két hiba ára **nem szimmetrikus**: egy jó ügynökség elvesztése drágább, mint egy
  félrement levél, mert a célcsoport véges (100-300 cég). Ezért a kizárás két szintű:

  | Szint | Példa | Mi történik |
  |---|---|---|
  | **erős** | `egyedi fejlesztés`, `fejlesztő csapat`, `React`, `Laravel` | azonnal `suppressed`, `reason='competitor'` |
  | **gyenge** | `webfejlesztés`, `weboldal készítés`, `webdesign` | `review` — **ember dönt**, nem dobjuk el |

  Új parancs: `leadgen review` listázza őket a döntéshez.

### Ellenőrzés a szakasz végén — ✅ lefuttatva

```bash
.venv/bin/python -m leadgen.cli ingest agency --seeds seeds/agencies.txt
.venv/bin/python -m leadgen.cli enrich            # batch-enként, többször futtatható
.venv/bin/python -m leadgen.cli qualify agency
.venv/bin/python -m leadgen.cli report            # ready / rejected / competitor / no-email bontás
```

Kézzel nézd meg: 5 véletlen `ready` cég weboldalát nyisd meg. **Tényleg
marketingügynökség? Tényleg nincs saját fejlesztésük? Tényleg jó az email cím?**
Ha ötből egy is hibás, a kulcsszólistát kell javítani, nem továbbmenni.

---

## 🟡 5. szakasz — Az első éles kiküldés `[agent-rész kész: 2026-08-21]`

**Cél:** menjen ki az első valódi levél. **Ez a terv legfontosabb mérföldköve.**
**Becsült agent-munkaidő:** 1 óra.
**Kész-definíció:** a `sent.csv`-ben van legalább 10 valódi sor, a `feedback` import
ezt visszavezette a DB-be, és a `deliverability.py` lefutott riasztás nélkül.

### Az ÉN feladataim (ember)

- **A szakasz előtt** — olvasd el a **teljes** dry-run kimenetet. Minden levelet.
  Ez 10 perc, és ez az utolsó visszafordítható pont.
- **A szakasz előtt** — küldj magadnak egy próbalevelet. **Ne a `leads.csv`-be
  írd be a saját címed** (az `export` felülírja a fájlt, és a `sent.csv`-be is
  bekerülnél): erre való a `preview.py --send-to`, ami valódi levelet küld, de
  **nem ír a `sent.csv`-be**, tehát a valódi lead sorban marad.

  ```bash
  cd cold-email-starter
  python3 preview.py --send-to sajat@cimem.hu --limit 1
  ```

  Nézd meg egy Gmailben és egy céges postafiókban is:
  **spam mappa? formázás? aláírás? leiratkozási mondat?**
- **A szakasz alatt** — indítsd te a `--live` futást. Az agent ne küldjön élesben.
- **A szakasz után, naponta** — **olvasd a postafiókot.** Egy ügynökségi válasz
  24 órán belül megérdemel egy emberi választ. Ez a leggyakoribb pont, ahol a
  rendszer működik, de az ügyfél mégis elveszik.

### Az agent feladatai — ✅ mind kész (a 4. pont a `--live` futásra vár)

1. ✅ `export` futtatása, a kimenet ellenőrzése.
2. ✅ `guards.py` **önálló** futtatása először (`python3 guards.py`) — így derül ki
   IMAP-probléma **anélkül**, hogy közben küldenénk.
3. ✅ `sender.py --dry` (guards-szal, `--skip-guards` nélkül) — teljes lánc szárazon.
4. ⏳ A felhasználó `--live --limit 10` futása után: `feedback` import, `report`,
   `deliverability.py`.
5. ✅ A napi rutin leírása a `CLAUDE.md`-be (a cron csak a 12. szakaszban jön).

Menet közben **három hiba javítva**, mindhárom a kiküldés előtti utolsó
ellenőrzésen bukott ki (lásd lent).

### Amit a szakasz közben tanultunk

- **🔑 Egy `mailto:` link URL-kódolása hard bounce-t okozott volna.** A 4. szakasz
  exportjában szerepelt egy `%20peter@mpmarketing.hu` cím. A forrás egy
  `mailto:%20peter@mpmarketing.hu` link volt: az oldal készítője szóközzel kezdte
  a címet, a böngésző `%20`-ként kódolta, a kinyerő regexp (`[A-Za-z0-9._%+-]+@`)
  pedig a `%`-ot engedélyezett karakternek látta.

  **Miért ez a legdrágább hibatípus a rendszerben:** a hard bounce az egyetlen
  hiba, ami **visszamenőleg** is kárt okoz — rontja a küldő domain reputációját,
  és onnantól a *jó* leadeknek sem érkezik meg a levél. Egy rossz cím tehát nem
  egy elveszett leadbe kerül, hanem az összes többibe.

  Két helyen javítva: az `enrich._clean_emails` most **URL-dekódol** kinyerés
  előtt, a `normalize._EMAIL_RE` pedig szigorúbb lett (nem enged `%`-ot, szóközt,
  vezető/záró pontot, dupla pontot, ékezetet). Regressziós teszt mindkettőre.
  *(Mellékhatás: kiderült, hogy a helyes `peter@mpmarketing.hu` cím is benne volt
  a DB-ben — csak a hibás verzió volt régebbi, és a `created_at` szerinti
  rendezés miatt az nyert.)*

- **A `press@` / `karrier@` / `allas@` címek „személyes"-nek minősültek.** A
  `classify_email` csak azt nézte, hogy a prefix szerepel-e a role/generic
  listákon — ami nem szerepelt, az `personal` lett. Így a `press@mito.group`
  a legjobb minőségű címként nyert. Ezek nem döntéshozói címek: sajtókapcsolat,
  illetve álláspályázat. Oda küldött ajánlat a legjobb esetben elvész, a
  legrosszabban spamnek jelölik. A `ROLE_PREFIXES` bővítve, a meglévő 46
  kapcsolat újraosztályozva (3 változott).

- **Nem volt eszköz arra, hogy egy már exportált leadet kihúzz.** A szakasz
  emberi feladata az, hogy a kiküldés előtt végigolvasd a dry-run kimenetet —
  „ez az utolsó visszafordítható pont". Csakhogy amit ott látsz, az már
  `queued` állapotú, a `review --reject` pedig csak `review` állapotból működött.
  A felülvizsgálatnak tehát nem volt eszköze. Javítva: a `--reject` most
  `queued` és `sent` állapotból is kihúz, lezárja az outreach sort (különben a
  domain lock miatt a cég soha többé nem kaphatna új sequence-t), és `--reason`
  kapcsolót is kapott.

- **Az új `report` parancs.** Az ellenőrző listák eddig is hivatkoztak rá, de
  nem létezett. Két nézete van: a tölcsér (`report`) és a mai kép
  (`report --daily`). Utóbbi azt a számot mutatja, amit az „A 5. szakaszban"
  kockázat kért: **hány napra elég a sorban álló lead a jelenlegi napi keret
  mellett.** A küldő oldali számokat (napi keret, ma kiküldve, maradék) nem
  számolja újra, hanem **megkérdezi a küldőt a saját interpreterén** — így nem
  keletkezik második igazság a napi keretre.

### Ellenőrzés a szakasz végén

```bash
cd cold-email-starter
python3 guards.py                      # önállóan, IMAP-teszt          ✅ 0 hiba
python3 sender.py --dry                # teljes lánc szárazon          ✅ 10 levél
python3 sender.py --live --limit 10    # EZT TE INDÍTOD                ⏳
python3 deliverability.py              # exit 1 = riasztás, nem hiba   ⏳
cd .. && .venv/bin/python -m leadgen.cli feedback && .venv/bin/python -m leadgen.cli report
```

---

## 6. szakasz — AI réteg: bake-off + válasz-osztályozás `[külön session]`

**Cél:** legyen kiválasztott modell, működő LLM-kliens, és a beérkező válaszok
automatikusan töltsék a `suppression` táblát.
**Becsült agent-munkaidő:** 2,5 óra. **+ 2 óra emberi bake-off.**
**Kész-definíció:** a bake-off táblázat ki van töltve és commitolva; a
`leadgen classify-replies` a `replies.csv` sorait besorolja, és a `negative` /
`unsubscribe` esetek suppressionbe kerülnek.

> **Időzítés:** ezt akkor kell megcsinálni, amikor az 5. szakasz után **megjönnek
> az első válaszok** — tipikusan 2-4 nappal az első kiküldés után. Addig a válaszokat
> kézzel is át tudod nézni (10-20 db).

### Az ÉN feladataim (ember)

- **A szakasz előtt, ~2 óra** — a `SCRAPER-PLAN.md` „Függelék: bake-off protokoll"
  (2981-3258) végrehajtása: 30 magyar teszteset (10 FIT, 10 NO FIT, **10 határeset**),
  kézi címkékkel, három modellen, playgroundban. **A 10 határeset dönt.**
  A tesztkészletet mentsd a repóba (`evals/bakeoff-30.jsonl`) — ez lesz a rendszer
  első és sokáig egyetlen evalja.
- **A szakasz előtt** — Gemini + Anthropic API kulcs a scraper `.env`-jébe.
- **A szakasz után** — nézd át az első 20 automatikus válasz-besorolást. Ha egyet is
  rosszul sorolt be `unsubscribe`-ként, azt azonnal javítsd — az visszafordíthatatlan.

### Az agent feladatai

1. **`leadgen/llm.py`** — egy vékony kliens, `bulk()` és `quality()` függvénnyel,
   a modellnév konfigból. **Prompt-sorrend a caching miatt:** stabil rendszer-prompt
   és few-shot előre, a változó lead-adat hátra (terv „Prompt caching" fejezete).
   Temperature 0. JSON-parse hibára retry egyszer, aztán `status='error'`.
2. **A bake-off futtatókód** (`leadgen/cli.py: eval bakeoff`) — a 30 esetet
   végigfuttatja a jelölt modelleken, és kiírja a négy mérőszámot
   (találat / határeset-találat / érvénytelen JSON / hamis idézet). A felhasználó
   playgroundos mérését ez **kiegészíti**, nem helyettesíti.
3. **`leadgen/classify.py`** — válasz-osztályozás a `reply_events` táblából:
   `interested` / `not_now` / `negative` / `unsubscribe` / `auto_reply` / `other`.
   Kimenet-kezelés:
   - `unsubscribe` → `suppression`, `reason='unsubscribe'`, **domain szinten**
   - `negative` → `suppression`, `reason='negative_reply'`
   - `not_now` → `cooldown_until = +90 nap`, nincs suppression
   - `auto_reply` → `cooldown_until = +14 nap`, a lead visszatér a sorba
   - `interested` → `companies.status='replied'`, **külön riport-sor**, hogy
     az ember lássa (ez a legfontosabb kimenet!)
4. **Robusztussági teszt** a terv C) protokollja szerint (üres bemenet, nagyon hosszú
   szöveg, angol nyelvű input, HTML-szemét, **prompt injection**). Ez utóbbi nem
   elméleti: a scrapelt weboldalak szövegét idegenek írják.

### Ellenőrzés a szakasz végén

```bash
.venv/bin/python -m leadgen.cli eval bakeoff --model gemini-2.5-flash-lite
.venv/bin/python -m leadgen.cli classify-replies --dry   # először SZÁRAZON
.venv/bin/python -m leadgen.cli classify-replies
.venv/bin/python -m leadgen.cli report --replies         # besorolás-bontás
```

---

## 7. szakasz — Reoon validáció élesítése `[összefűzhető a 6-tal]`

**Cél:** `EMAIL_VALIDATION=full` — a fizetős verifikáció bekapcsolása az export kapujában.
**Becsült agent-munkaidő:** 1,5 óra.
**Kész-definíció:** az export Reoon-t hív a nem-cache-elt címekre, az eredmény a
`contacts` táblában marad, és ugyanarra a címre 90 napon belül **nem fut le kétszer**.

### Az ÉN feladataim (ember)

- **A szakasz előtt** — Reoon fiók + kredit vásárlás (~$11.90 / 10 000), API kulcs
  a `.env`-be.
- **A szakasz után** — nézd meg a kredit-fogyást az első futás után. Ha többet fogyott,
  mint ahány új címed volt, a cache nem működik → azonnal állítsd vissza `local_only`-ra.

### Az agent feladatai

1. `leadgen/validate.py` — Reoon API kliens, batch-elt hívás, hibatűrés
   (API-hiba → `unknown`, **nem** `invalid`; a küldő `verify.py` doksijának
   ugyanaz a logikája: „nem tudom" ≠ „rossz").
2. Cache: `contacts.verified_at` + `verify_result`; 90 napnál frissebb eredmény
   esetén nincs hívás. **Kötelező unit-teszt erre**, mert ez pénz.
3. Catch-all szabály (terv 2126-2135) bekötése a tier-be.
4. `EMAIL_VALIDATION` kapcsoló: `off` / `local_only` / `full`.
5. Kredit-számláló a `report` kimenetben.

### Ellenőrzés a szakasz végén

```bash
EMAIL_VALIDATION=full .venv/bin/python -m leadgen.cli export --dry
# a log mutatja: N cím validálva, M cache-találat
EMAIL_VALIDATION=full .venv/bin/python -m leadgen.cli export --dry   # újra
# a log mutatja: 0 cím validálva, N+M cache-találat   ← EZ a lényeg
```

---

## 8. szakasz — 8.2 „halott fejlesztő" enrichment `[külön session]`

**Cél:** a legerősebb objektív signal bekötése — és mivel **enrichment, nem source**,
minden meglévő és jövőbeli leadre visszamenőleg lefut.
**Becsült agent-munkaidő:** 2 óra.
**Kész-definíció:** minden `enriched` cégre lefutott a footer-kredit felismerés, és
a `DEAD` fejlesztőjű cégek `signal_score`-ja +35-tel emelkedett; az `ALIVE` fejlesztők
`suppression`-ben vannak `competitor` okkal.

### Az ÉN feladataim (ember)

- **A szakasz után** — nézz meg **10 `DEAD` találatot kézzel**. Tényleg az a fejlesztő
  van a footerben? Tényleg halott a domainje? A terv kemény szabálya:
  *„Ha a footer-kredit nem egyértelmű, a lead inkább essen ki, mint hogy rossz nevet
  írj egy emailbe."*

### Az agent feladatai

1. Footer-kredit regex a **már letárolt** HTML-ből (`cache/`): `készítette|fejlesztette|
   webdesign|weboldal készítés|web design|powered by|design by|developed by` + az azt
   követő kimenő link.
2. **Platform/CMS-kreditek kiszűrése** (`wordpress.org`, `wix.com`, `shoprenter.hu`,
   `unas.hu`, `shopify.com`, ...) — ezek nem fejlesztők.
3. Életjel-ellenőrzés: `DEAD` (DNS nem oldódik / parkolt / 404) / `DORMANT`
   (él, de régi copyright + elavult CMS + nincs friss tartalom) / `ALIVE`.
4. `ALIVE` → `suppression`, `reason='competitor'`. Ingyen versenytárs-térkép.
5. **Időfüggő `signal_score`** implementálása (terv 2560-2620): a
   `sources.detected_at`-ből számolt lecsengési szorzó, a lapos görbével a
   nem-avuló signalokra (`8.2`, `7.5`, `7.1`) és a meredekkel az avulókra
   (álláshirdetés, hirdetés, értékelés).
6. Új kampány: `campaign='dead_dev'` + a hozzá tartozó sablonok — **a szöveget a
   felhasználó írja**, az agent csak a szerkezetet készíti elő.

### Ellenőrzés a szakasz végén

```bash
.venv/bin/python -m leadgen.cli enrich dead-dev --all
.venv/bin/python -m leadgen.cli report --signal dead_dev   # DEAD/DORMANT/ALIVE bontás
```

---

## 9. szakasz — Operational Pain engine, A rész: source + ingest `[külön session]`

**Cél:** a Profession.hu álláshirdetés-forrás bekötése, inkrementálisan.
**Becsült agent-munkaidő:** 2,5 óra.
**Kész-definíció:** a napi futás csak az **új** (`source_type` + `source_url` páros,
ami még nincs a `sources` táblában) hirdetéseket dolgozza fel, és a cégekhez feloldja
a domaint.

### Az ÉN feladataim (ember)

- **A szakasz előtt, KÖTELEZŐ (terv 0.3)** — 30 perces Actor-előteszt: futtasd le az
  Apify Profession Actort **5-20 találatra**, és nézd meg **saját szemmel** a nyers
  outputot. **A kritikus mező: a `description` teljes szövege**, nem csak a cím.
  Ha ez hiányzik, az egész engine vaktában megy — akkor másik Actort kell keresni,
  vagy saját scrapert írni. **Ne kezdd el a szakaszt az előteszt előtt.**
- **A szakasz előtt** — Apify fiók (Starter $29, vagy Free tier a teszteléshez),
  API token a `.env`-be.

### Az agent feladatai

1. `leadgen/sources/apify.py` — Actor futtatás + dataset letöltés, API-n keresztül.
2. `leadgen/engines/ops_pain.py` — a terv keresőszavai (`szervizkoordinátor`,
   `diszpécser`, `munkairányító`, `logisztikai koordinátor`, ...) és description-kulcsszavai.
3. **Inkrementalitás**: `sources` UNIQUE (`source_type`, `source_url`) — a már látott
   hirdetés némán kiesik. Az első futás nagy backfill, utána napi néhány tucat.
4. **Cégnév → domain feloldás**: a hirdetés cégnevéből. Sorrend: a hirdetésben
   szereplő URL → keresés → `name_key` alapú DB-egyezés. Ha nincs domain, a lead
   `status='error'` és nem vész el.
5. Az enrichment (4. szakasz) újrahasznosítása — **nem írunk új crawlert**.

### Ellenőrzés a szakasz végén

```bash
.venv/bin/python -m leadgen.cli ingest ops-pain --limit 20   # kicsiben először
.venv/bin/python -m leadgen.cli ingest ops-pain --limit 20   # ÚJRA: 0 új sor
.venv/bin/python -m leadgen.cli enrich
.venv/bin/python -m leadgen.cli report
```

---

## 10. szakasz — Operational Pain engine, B rész: classifier + evidence grounding `[külön session]`

**Cél:** a lead classifier és az evidence grounding — a rendszer hitelességi
védőrétege.
**Becsült agent-munkaidő:** 3 óra.
**Kész-definíció:** a classifier `webapp_fit >= 70` esetén enged tovább, **és minden
`evidence[].quote` szó szerint megtalálható a scrapelt szövegben**; ami nem, azt a
rendszer eldobja, és ha nem marad evidence, a lead `rejected`.

### Az ÉN feladataim (ember)

- **A szakasz után** — olvass el **20 generált personalization mondatot**.
  A terv B/3 kritériumai szerint: természetes a szórend? nincs tükörfordítás-szag?
  nem hízeleg? **Amelyiket nem küldenéd ki a saját neveddel, az bukott** — akkor
  nem a modell a hibás, hanem a prompt.

### Az agent feladatai

1. `leadgen/score.py` — a classifier a 6. szakaszban kiválasztott BULK modellel,
   a bake-off system prompttal (szó szerint az, amit a bake-offon mértünk).
2. **Evidence grounding ellenőrző** — **nem AI hívás, sima string keresés**
   (terv „Evidence grounding" fejezete): szóköz- és kisbetű-normalizálás, részleges
   egyezés az idézet első 40 karakterére. Kemény szabály:
   `NINCS BIZONYÍTÉK → NINCS ÁLLÍTÁS → NINCS EMAIL`.
3. **Personalization mondat** a QUALITY tierrel, csak a `webapp_fit >= 70` leadekre.
   Ha a `personalization_quote` nem ellenőrizhető → **a lead sablon-emailre esik
   vissza**, personalizáció nélkül; nem esik ki teljesen.
4. **Offer arbitration** bekötése: `website_fit` / `webapp_fit` / `mobile_fit` →
   `best_offer` → `campaign`. Egy cég **egyetlen** kampányba kerül.
5. Új kampány sablonok (`ops_pain`) — szerkezet az agenttől, szöveg a felhasználótól.

### Ellenőrzés a szakasz végén

```bash
.venv/bin/python -m leadgen.cli score --limit 20 --dry
.venv/bin/python -m leadgen.cli report --grounding   # hány quote bukott az ellenőrzésen
.venv/bin/python -m leadgen.cli export --dry
cd cold-email-starter && python3 sender.py --dry --skip-guards
```

Ha a grounding-bukás aránya **20% felett** van, a modell hallucinál → vissza a
6. szakasz bake-offjához, más modellel.

---

## 11. szakasz — e-beszámoló (7.1) + webshop kinövés (8.3) `[összefűzhető]`

**Cél:** objektív méret- és árbevétel-szűrő, és a metszete a tech fingerprinttel.
**Becsült agent-munkaidő:** 2,5 óra.
**Kész-definíció:** a `ready` leadeknél kitöltött `revenue` / `headcount`;
`economic_value` már **tény, nem AI-tipp**; és megvan a
`dobozos platform + magas árbevétel` lista.

### Az ÉN feladataim (ember)

- **A szakasz előtt (terv 0.3)** — nézd meg **3-5 cégre kézzel**, mennyire
  automatizálható az e-beszámoló lekérés, és van-e rate limit. Ha nehézkes:
  akkor is megéri — legyen manuális fallback a legjobb 20-30 leadre.
- **A szakasz után** — kalibráld az árbevételi küszöböt az első találatok alapján.
  Ez üzleti döntés, nem technikai.

### Az agent feladatai

1. `leadgen/enrich_financials.py` — **célzott, per-cég lekérés**, csak a már
   megszűrt (`scored`, `webapp_fit >= 70`) leadekre. Nem bulk.
2. `economic_value` = LOW / MEDIUM / HIGH az árbevétel + létszám alapján.
   Csak MEDIUM+ megy outreachbe.
3. **8.3**: szűrés a `platform IN (Shoprenter, Unas, Wix, Shopify Basic, WooCommerce)`
   ÉS `árbevétel > küszöb` metszetére. Ez nem engine, hanem egy `WHERE` — pár óra.
   Új kampány: `webshop_growth`.
4. `signal_score` bővítése a `+15 magas árbevétel` és `+25 dobozos webshop + magas
   árbevétel` tételekkel.

### Ellenőrzés a szakasz végén

```bash
.venv/bin/python -m leadgen.cli enrich financials --limit 20
.venv/bin/python -m leadgen.cli report --economic     # LOW/MEDIUM/HIGH bontás
.venv/bin/python -m leadgen.cli report --campaign webshop_growth
```

---

## 12. szakasz — Ütemezés, napi rutin, monitoring `[külön session]`

**Cél:** a rendszer emberi beavatkozás nélkül fusson naponta, és lássam, ha baj van.
**Becsült agent-munkaidő:** 2 óra.
**Kész-definíció:** a napi lánc cronból lefut, a `--live` küldés `flock`-kal védve
van, és egy napi összefoglaló megmutatja a keretet, a bounce-arányt és a válaszokat.

### Az ÉN feladataim (ember)

- **A szakasz alatt** — döntsd el, hogy a `--live` küldés **cronból menjen-e**,
  vagy maradjon kézi. Javaslat a kezdeti hetekben: **maradjon kézi**, amíg a
  válaszarányt és a bounce-okat nem látod stabilnak. A scraper-oldal viszont
  mehet cronból.
- **A szakasz után, naponta 5 perc** — olvasd a napi összefoglalót.

### Az agent feladatai

1. `launchd`/`cron` bejegyzések:
   ```
   07:30  leadgen ingest (minden aktív engine, inkrementálisan)
   08:00  leadgen enrich   (batch 50)
   08:30  leadgen score    (batch 50)
   09:00  leadgen export
   09:15  [kézi vagy cron] sender.py --live
   18:00  leadgen feedback && leadgen classify-replies
   18:15  deliverability.py
   ```
2. **`flock` minden íráson** — a `store._append` nem tranzakcionális, és most már
   két folyamat írhat a `data/` alá. Ez kötelező, nem opcionális.
3. `leadgen report --daily` — egy képernyőnyi összefoglaló: mai keret vs. kiküldve,
   bounce-arány, új válaszok besorolás szerint, `ready` leadek száma
   (**„elfogy-e a lead a keret előtt?"**), grounding-bukás arány.
4. **Riasztás egy fájlba/emailbe**, ha: `deliverability.py` exit 1, vagy 3 napja
   nincs `ready` lead, vagy `interested` válasz érkezett és 24 órája nincs
   megválaszolva.
5. **A `guards.py` teljesítménye** (9. ellentmondás): ha a 14 napos INBOX-olvasás
   lassúvá válik, itt jön a UID-watermark vagy a `days` csökkentése 7-re.

6. **🆕 Az SMTP-elutasítások naplózása — a ramp vak foltja.**

   **A hiba:** a `deliverability.py` **fixen nullát** ad át az elutasításokra:
   ```python
   limits.evaluate_ramp(sent=..., bounces=..., rejects=0)   # ← hardcode
   ```
   Emiatt a `REJECT_RATE_ALERT=0.03` küszöb **soha nem sül el**, és a ramp
   kizárólag a visszapattanásokból tanul. Nem látja, ha a Google elkezdi
   **elutasítani** a küldéseket (rate limit, policy reject) — pedig pont ez az
   a jel, ami időben szólna, mielőtt komoly baj lesz.

   **Miért nem hiba, hanem befejezetlen funkció:** a `sender.py` már számolja a
   sikertelen küldéseket (`failed += 1`, a `mailer.send()` hibaágán), de sehova
   nem menti — így a `deliverability.py`-nak nincs mit beolvasnia.

   **Amit meg kell csinálni** (~fél óra):
   - `store.py`: új `rejects.csv` (`ts, email, account, error`) + `record_reject()`
   - `sender.py`: a `mailer.send()` hibaágán hívja meg (a `store.log` mellett)
   - `deliverability.py`: a mai `rejects.csv` sorok számát adja át a
     `evaluate_ramp(rejects=...)` paraméternek a hardcode-olt 0 helyett
   - a `leadgen feedback` importálja is (a `contacts.bounce_state`-hez hasonlóan),
     hogy a scraper is lássa

   **Miért itt van és nem korábban:** napi 20 levélnél egy elutasítás azonnal
   látszik a logban. Akkor válik fontossá, amikor a cron veszi át a futtatást,
   és már nem olvassa ember a kimenetet.

### Ellenőrzés a szakasz végén

Egy teljes nap végigfutása beavatkozás nélkül, majd:
```bash
.venv/bin/python -m leadgen.cli report --daily
tail -50 cold-email-starter/data/sender.log
```

---

## 13. szakasz — Webes felület `[opcionális, utolsó]`

**Cél:** böngészőből átnézni és jóváhagyni a leadeket, olvasni a válaszokat.
**Becsült agent-munkaidő:** 6+ óra — **a határidő után.**
**Kész-definíció:** —

**Ez most NEM épül meg.** Amit viszont **már most úgy csinálunk**, hogy később ne
kelljen újraírni:

| Döntés az 1-12. szakaszban | Miért fizetődik ki a 13.-nál |
|---|---|
| **Supabase Postgres**, nem SQLite | a webes felület közvetlenül rácsatlakozik (PostgREST / Supabase JS), nulla backend-munka |
| Minden üzleti logika a `leadgen/` **függvényeiben**, a `cli.py` csak vékony réteg | ugyanazokat a függvényeket egy HTTP-réteg is hívhatja; a CLI nem lesz zsákutca |
| UUID pk + `created_at`/`updated_at` minden táblán | listázás, lapozás, „mi változott" nézet triviális |
| **Soha nem törlünk sort**, csak státuszt írunk | audit-nézet és „miért esett ki ez a lead?" utólag is megválaszolható |
| `sources.raw_signal` JSONB-ben marad | a felületen megmutatható a nyers bizonyíték a lead mellett |
| A `status` értékkészlet **kódban egy helyen** (enum) | a felület nem drótoz be sztringeket |
| **Nincs `opened` mező, sehol** | a felület nem ígérhet megnyitási arányt, mert a küldő invariánsa tiltja a trackinget |

Ha később mégis kell egy gyors nézet: a Supabase beépített **Table Editor** és a
mentett SQL query-k a `ready` lista átnézéséhez már most elegendők — **a 13. szakasz
kihagyható**, amíg a napi 20-40 lead kézzel is átnézhető.

---

## Szakasz-térkép: mi mehet együtt, mi nem

| Szakasz | Agent-óra | Session | Blokkolja |
|---|---:|---|---|
| 0. Emberi előfeltételek | 0,5 | párhuzamos, ma | mindent (SMTP), az 5-öt (sablonszöveg) |
| 1. Alapozás | 2,5 | **külön** | 2, 3, 4 |
| 2. Export (DB → CSV) | 2,5 | **külön** | 5 |
| 3. Feedback (CSV → DB) | 2,5 | **külön** | 5, 6 |
| 4. 8.1 engine | 3 | **külön** | 5 |
| 5. Első éles kiküldés | 1 | **külön, rövid** | — |
| 6. AI réteg + válasz-osztályozás | 2,5 | **külön** (+2 óra ember) | 10 |
| 7. Reoon | 1,5 | *összefűzhető a 6-tal* | — |
| 8. 8.2 halott fejlesztő | 2 | **külön** | — |
| 9. Ops Pain: source | 2,5 | **külön** | 10 |
| 10. Ops Pain: classifier | 3 | **külön** | — |
| 11. e-beszámoló + 8.3 | 2,5 | *összefűzhető* | — |
| 12. Ütemezés + monitoring | 2 | **külön** | — |
| 13. Webes felület | 6+ | a határidő után | — |

**Miért van szinte minden „külön session"-ben:** nem az óraszám miatt (2-3 óra bőven
belefér az 5 órás limitbe), hanem mert **mindegyik szakasz végén ellenőrzés van, amit
el kell olvasni.** Két szakasz összefűzve azzal a kockázattal jár, hogy a második
elrontja az elsőt, és a session végén már nem látod, melyik lépésnél romlott el.

**Sorrendfüggetlen újraindíthatóság** — minden szakasz betartja:
- minden CLI-parancs **idempotens**: kétszer futtatva ugyanaz az eredmény
- minden batch-elt lépés a DB `status` oszlopából olvassa, hol tart — soha nem
  a session memóriájából
- minden szakasz végén a kód **commitolható**, és a `sender.py --dry --skip-guards`
  változatlanul lefut
- ha egy session megszakad: `leadgen report` megmutatja, mi hol tart, és a
  következő session onnan folytatja

**Az első hét terve (ma 2026-08-19, szerda):**

```
szerda    0. szakasz (ember: domain, SMTP, Supabase, sablonszöveg)  +  1. szakasz
csütörtök 2. szakasz  +  3. szakasz               ← a határ mindkét iránya kész
péntek    4. szakasz (ember: 45 perc lista-gyűjtés reggel)
péntek    5. szakasz  →  🎯 AZ ELSŐ LEVELEK KIMENNEK
```

Ez teljesíti a terv legfontosabb megkötését: **működő end-to-end pipeline az első
héten.** Utána a 6-12. szakasz mehet heti 2-3 sessionben, a válaszok kezelése mellett.

---

# 4. rész — Kockázatok

## A 3 dolog, ami a legvalószínűbben megcsúsztatja a határidőt

### 1. A küldési keret, nem a leadhiány — és az emberi szöveg, ami elé áll

Ez a legalábecsültebb kockázat, mert nem technikai. A matek:
`DAILY_CAP_START=20`, `RAMP_STEP=20` / 3 tiszta nap, `ceiling=200`, **egy postafiókkal
~7 hét a plafonig** — és a határidőig pontosan ennyi van. Ha a `templates.py`
szövege 3 napot csúszik, az nem 3 nap, hanem **3 nap × a teljes ramp-görbe**.

Ráadásul: a `templates.py` ma is placeholdert tartalmaz, a ramp csak *tiszta* napokra
emel, és **egy rossz nap visszavesz egy lépcsőt**. Egy 4% feletti bounce-arány
napokat töröl a görbéből.

**Ellenintézkedés:** a 0. szakasz emberi feladatai **ma** kezdődnek, párhuzamosan az
1. szakasz agent-munkájával. A második postafiók megduplázza a napi keretet
(`limits.daily_cap()` = per-fiók × fiókszám) — ha van rá mód, **állíts be kettőt**.

### 2. A 0.3 szerinti forrás-előteszt kimarad, és a 9. szakasz falnak megy

A terv maga figyelmeztet rá: az Apify Actor leírása és a valósága nem ugyanaz,
főleg magyar tartalomnál. A Profession engine **teljes egészében a `description`
mezőn áll** — ha az Actor csak a hirdetés címét adja vissza, a classifier vaktában
osztályoz, és a hiba csak a kiküldött, értetlenséget kiváltó levelekben derül ki.

**Ellenintézkedés:** a 9. szakasz emberi feladata **blokkoló**: 30 perc kézi
Actor-teszt 5-20 találatra, **saját szemmel**, mielőtt egy sor kód íródna.
Ez a terv 0.3 fejezete, és nem opcionális.

### 3. Az emberi szűk keresztmetszet: a válaszok megválaszolása

A rendszer minden része automatizálható, **kivéve azt az egyet, ami az ügyfelet hozza**.
Egy ügynökségi válasz 24 órán belül emberi választ érdemel. Ha a válaszok
felgyűlnek, a rendszer tökéletesen működik, és mégsem lesz ügyfél.

Ehhez jön, hogy több szakasz **emberi bemenetre vár** (bake-off 2 óra, seed-lista
45 perc, Reoon fiók, Apify token, sablonszövegek). Egy elakadt emberi feladat egy
teljes agent-sessiont blokkol.

**Ellenintézkedés:** minden szakasznál külön ki van írva, hogy az emberi feladat
**előtte / közben / utána** van-e. Az „előtte" feladatokat a session indítása előtt
kell elvégezni. A 12. szakasz riasztást ad, ha egy `interested` válasz 24 órája
megválaszolatlan.

---

## Hol derülhet ki, hogy a `cold-email-starter` nem illik — és mi a B terv

### A 2. szakaszban: a `templates.py` kampányonkénti szétbontása

**A kockázat:** négy kampány (`agency_partner`, `dead_dev`, `ops_pain`,
`webshop_growth`) × három fok = 12 sablonfüggvény egy fájlban, mindegyik a saját
hangnemével. A `templates.py` ráadásul az invariáns szerint **a felhasználóé** —
az agent nem írhatja át a szövegeket.

**B terv:** a `personalization` mező helyett a scraper a **teljes levéltörzset**
adja át egy `body` oszlopban, és a `templates.py` egy pass-through függvénnyé
egyszerűsödik (`{subject: lead["subject"], body: lead["body"]}`). Így a szövegezés
teljesen a scraper oldalára kerül, ahol verziózható, kampányonként külön fájlban.
**Ára:** a `templates.py`-ba drótozott két szabály (fájdalom-először, nincs hamis
„utoljára írok") és a `_greeting()` üres-név védelme átkerül a scraperbe — ezeket
**meg kell ismételni**, nem elhagyni, mert valós incidensekből származnak.

### A 3. szakaszban: ha a feedback nem joinolható vissza megbízhatóan

**A kockázat:** a `guards.py` a bounce-ból az eredeti címzettet a **levéltörzsből
bányássza ki**, `store.already_contacted()`-del egyeztetve. Ha egy szolgáltató NDR-je
más formátumú, a bounce a `bounces.csv`-be sem kerül be — a DB soha nem tudja meg,
hogy a cím rossz. Hasonlóan: a válaszfelismerés csak az `INBOX`-ot nézi, tehát egy
szabály által mappába szűrt válasz **láthatatlan**.

**B terv:** a scraper nyit **saját, read-only IMAP-kapcsolatot** (`mailer.fetch_recent`
mintájára, de az összes mappára és UID-watermarkkal), és a `reply_events` táblát
onnan tölti. A küldő `guards.py`-ja változatlanul marad a **védelmi** szerepében —
két független olvasó, ami ebben az esetben előny, nem duplikáció.
**Ára:** a postafiók jelszava bekerül a scraper `.env`-jébe is.

### A 5. szakaszban: ha a napi keret és a lead-utánpótlás nem találkozik

**A kockázat:** a follow-up mindig veri a friss cold-ot ugyanabban a keretben
(`build_plan`: `followups + fresh`, aztán `[:limit]`). Ha a 8.1 lista 60 leadje
elindul, a 2. héten a napi 20-as keretet **teljesen elfogyaszthatják a follow-upok**,
és új cold levél napokig nem megy ki.

**B terv:** ez a küldő **szándékos** viselkedése (a folyamatban lévő beszélgetés
többet ér), tehát nem javítani kell, hanem **tervezni vele**: az export ne öntsön be
egyszerre 200 leadet, hanem a `leadgen report --daily` mutassa a „queued vs. napi
keret" arányt, és a lista adagolva menjen. Ha mégis kell felülbírálás, az a
`build_plan` sorrendjének egysoros módosítása — de csak tudatos döntésként.

---

## Amit tudatosan feláldozunk — és mikor kell visszatérni rá

| Mit | Miért most | Mikor térjünk vissza |
|---|---|---|
| **n8n** (a terv karmestere) | a küldő helyi CSV-ken él, felhős n8n nem éri el; a workflow-JSON nem verziózható jól Claude Code-dal | ha a küldő valaha VPS-re költözik, vagy ha 4+ ütemezett forrás összehangolása fáj |
| **Scrapling** | az első engine statikus HTML-t olvas; `httpx` + `selectolax` elég, és 3.9-cel is menne | amikor egy forrás JS-renderelést igényel — egy `fetch()` függvény mögé kerül be |
| **Egyetlen igazságforrás** (DB-migráció a küldőben) | 1-2 nap átírás a bizonyítottan működő védelmi rétegen, éles küldés előtt | a 13. szakasznál, vagy ha a két suppression lista bizonyíthatóan elcsúszik |
| **Batch API + prompt caching optimalizálás** | napi néhány tucat lead mellett a megtakarítás centekben mérhető | ha a napi classifikált lead > 500, vagy az első backfill több ezres |
| **2. (Bad Existing App) és 5. (Long-tail SMB) engine** | a terv maga függeszti fel őket; a volumen nem a szűk keresztmetszet | nemzetközi terjeszkedésnél (2.), illetve ha a minőségi engine-ek kifogynak (5.) |
| **Webes felület** | most nulla ügyfelet hoz; napi 20-40 lead kézzel is átnézhető | a határidő után, vagy ha a napi átnézés 15 percnél többet visz |
| **Teljes test suite** | a küldőben szándékosan nincs; a scraperben csak a néma hibák helyére írunk tesztet (normalizálás, Reoon-cache) | ha egy második ember is dolgozni kezd a kódon |
| **A `guards.py` IMAP-teljesítménye** (14 napos teljes újraolvasás) | napi 20 levélnél észrevehetetlen | ha a `--live` futás percekbe kezd telni, vagy óránkénti cronra váltunk (12. szakasz) |
| **Deliverability finomhangolás** | külön projekt; az SPF/DKIM/DMARC alap viszont a 0. szakaszban KÖTELEZŐ | az első bounce-riasztás után |

**Amit NEM áldozunk fel**, mert olcsó most és utólag napokba kerül — pontosan úgy,
ahogy a `SCRAPER-PLAN.md` írja:

```
✅ suppression tábla (domain + email szinten)      → 1. szakasz
✅ platform-domain blocklist                        → 1. szakasz
✅ status oszlop + batch-elt, újraindítható futás   → 1. szakasz
✅ forrás-rögzítés minden adatnál (contacts.source_url NOT NULL)  → 1. szakasz
✅ domain lock (részleges UNIQUE index + exporter)  → 1-2. szakasz
✅ evidence grounding (string-ellenőrzés, nulla költség)  → 10. szakasz
✅ a küldő öt invariánsa, mind                      → végig
```
