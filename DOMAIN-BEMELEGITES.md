# Új domain bemelegítése — lépésről lépésre

> **Mire jó ez:** hogy a nagyobb volumenű kiküldést ne a `paladi-web.hu`-ról
> csináld. Ha egy cold email kampány rosszul sül el, a domain hírneve sérül —
> és onnantól a **céges levelezésed** is rosszabbul kézbesül.
>
> **Állapot: 2026-08-22.** Ez előkészítés, nem sürgős. A mostani 10 leadhez
> nem kell. Akkor lesz rá szükség, amikor a volumen nő (9. fázis).

---

## Miért nem most csináljuk, és miért kell mégis előkészíteni

A projekt korábban azt döntötte, hogy **marad a `paladi-web.hu`** — jó okkal:
az évek óta élő domain a projekt legnagyobb kézbesítési vagyontárgya, és az
ügynökségi lista egyszeri, nem pótolható. Egy előélet nélküli domainről
kiküldve, ha spambe esik, **ugyanazoknak nem lehet újraküldeni.**

Ez a döntés **most is érvényes.** Ez az útmutató a *következő* körről szól.

**A lényeg, amit meg kell értened:** egy domain bemelegítése **hetekbe telik**,
és nem lehet sürgetni. Ezért kell **most** regisztrálni, hogy októberben vagy
novemberben már használható legyen. A regisztráció ~5000 Ft/év, és ha mégsem
kell, semmit nem vesztettél.

---

## 1. lépés — Milyen domaint válassz

### Külön domain, ne aldomain

Ne `mail.paladi-web.hu`-t használj. Az aldomain hírneve **visszahat** a fő
domainre — pont azt nem éred el vele, amit akarsz. Kelll egy **teljesen külön
domain**.

### Hasonlítson rád

A címzett a feladó címét látja. Ha az `paladi-fejlesztes.hu`, az hihető.
Ha `bestwebdev2026.xyz`, az gyanús.

**Jó jelöltek:**

```
paladiweb.hu          (a kötőjel nélküli változat)
paladi-fejlesztes.hu
paladibalint.hu
```

### Kerüld ezeket

| Amit ne | Miért |
|---|---|
| `.xyz`, `.top`, `.click`, `.info` végződés | ezekről aránytalanul sok spam megy, a szűrők eleve gyanakszanak |
| számokkal telepakolt név | `paladi2026web.hu` — spamszagú |
| korábban használt (dobott) domain | **örökölheti az előző tulajdonos rossz hírnevét** |

> ⚠️ **Ellenőrizd a domain múltját**, mielőtt megveszed. Ha korábban valakié
> volt és spameltek róla, a hírnevet is megveszed vele. Nézd meg az
> `archive.org`-on, és ellenőrizd egy blokklista-kereső oldalon (pl.
> `mxtoolbox.com/blacklists.aspx`).

---

## 2. lépés — Regisztráld MOST, használd KÉSŐBB

**Ez a leghosszabb lépés, ezért kezdd ezzel.**

Egy tegnap regisztrált domainről kiküldött cold email a legklasszikusabb
spam-minta. Az „öregítés" annyit jelent, hogy a domain **létezik egy ideje**,
mielőtt bármit küldenél róla.

**Legyen világos, mit ad és mit nem ad az öregítés:**

| Amit ad | Amit NEM ad |
|---|---|
| eltünteti a „tegnap regisztrálták" gyanújelet | **küldési hírnevet** — az csak valódi küldésből épül |

Vagyis a regisztráció önmagában **nem elég**. A regisztráció a belépő, a
bemelegítés (5. lépés) az igazi munka. De a regisztrációt nem lehet
visszamenőleg megcsinálni — ezért ezzel kezdj.

**Minimum 30 nap** a regisztráció és az első kiküldés között. 60-90 nap jobb.

---

## 3. lépés — Legyen rajta weboldal

**Egy domain, aminek nincs weboldala, de leveleket küld, gyanús.** A címzett
rá fog keresni, és a szűrők is nézik.

Nem kell sok. Elég:

- egy egyszerű oldal a nevedről, arról, hogy mit csinálsz, és elérhetőséggel;
- **vagy** átirányítás a `paladi-web.hu`-ra (`301 redirect`).

Az átirányítás a legolcsóbb megoldás, és teljesen elfogadható. Egy saját
oldal jobb, de ne ezen múljon.

> Mivel a `paladi-web.hu` Netlify-on van, az új domain is odatehető pár perc
> alatt — akár ugyanarra a site-ra mutató átirányításként.

---

## 4. lépés — Levelezés és DNS beállítás

### Válassz levelezési szolgáltatót

Egy domainnek **egy** levelezési szolgáltatója lehet. Mivel ez egy új domain,
itt szabadon választhatsz — nem kell Google Workspace-nek lennie.

| Szolgáltató | Mikor válaszd |
|---|---|
| **Google Workspace** | ugyanaz a felület, mint amit ismersz; drágább |
| **Zoho Mail** | jóval olcsóbb, saját domainhez is jó |
| **Migadu / Fastmail** | olcsó, technikailag rendben |

Bármelyik jó. **Ne használj olyan szolgáltatót, aminek nincs rendes DKIM
aláírása** — az kizáró ok.

### A négy DNS rekord — mind kötelező

Ez a rész nem opcionális. Enélkül a leveleid spambe esnek, akármeddig
melegíted a domaint.

| Rekord | Mit csinál | Honnan veszed |
|---|---|---|
| **MX** | ide érkezzen a levél | a szolgáltatód adja meg |
| **SPF** | ki küldhet a nevedben | a szolgáltatód adja meg |
| **DKIM** | digitális aláírás a levélen | a szolgáltatód admin felületén generálod |
| **DMARC** | mi legyen a hamisítványokkal | **te írod meg**, lásd lent |

A DMARC-ot ugyanúgy állítsd be, ahogy a `paladi-web.hu`-nál:

```
Név:  _dmarc.<ujdomain>.hu
Típus: TXT
Érték: v=DMARC1; p=none; rua=mailto:balint@paladi-web.hu; adkim=s; aspf=s
```

`p=none`-nal indulj — ez csak **jelent**, nem blokkol. Pár hét után, ha a
jelentések tiszták, mehet `p=quarantine`.

### Ellenőrizd, hogy tényleg kint van

```bash
dig +short TXT <ujdomain>.hu            # SPF
dig +short TXT google._domainkey.<ujdomain>.hu    # DKIM (a selector eltérhet)
dig +short TXT _dmarc.<ujdomain>.hu     # DMARC
dig +short MX  <ujdomain>.hu            # MX
```

Mind a négynek választ kell adnia. Ha valamelyik üres, **ne kezdj küldeni.**

---

## 5. lépés — A bemelegítés

Itt épül a küldési hírnév. **Ezt nem lehet sürgetni.**

### Amit a fogadó szerverek néznek

Nem csak azt, hogy hány levelet küldesz. Ezt is:

- **válaszolnak-e** a leveleidre (ez a legerősebb pozitív jel)
- **megnyitják-e**, kimozdítják-e a spamből
- hányan jelölik **spamnek** (a Google szerint **0,3% felett** baj van)
- mennyi **pattan vissza** (nem létező cím)
- **egyenletesen** nő-e a volumen, vagy hirtelen ugrik

### Az első két hét — valódi emberek

**Ne kampánnyal kezdj.** Az első leveleknek olyanoknak menjenek, akik
**biztosan válaszolnak**:

```
1-3. nap    napi 2-5 levél    ismerősöknek, korábbi ügyfeleknek
                              → KÉRD MEG ŐKET, hogy válaszoljanak
4-7. nap    napi 5-10 levél   ugyanez, tágabb körben
2. hét      napi 10-20 levél  vegyíts bele valódi, de biztonságos
                              megkereséseket
```

A „kérd meg őket, hogy válaszoljanak" nem trükk — a **válasz** a legerősebb
pozitív jel, amit egy postafiók kaphat. Öt válasz többet ér, mint ötven
elküldött levél válasz nélkül.

Írj nekik **valódi, személyes** levelet. Ne sablont.

### A 3. héttől — éles kampány, lassan

Innentől a rendszer beépített rámpája (`limits.py`) intézi: `DAILY_CAP_START=20`,
és **3 tiszta nap után** emel 20-szal, felfelé 200-ig. Ez a logika már
megvan, nem kell hozzányúlnod.

### Amit soha ne csinálj

| Ne | Miért |
|---|---|
| ne ugorj 5 levélről 100-ra | a hirtelen volumen-ugrás önmagában gyanús |
| ne küldj vásárolt listára | a legrosszabb, amit tehetsz — spamcsapdák vannak benne |
| ne hagyd ki a hétvégéket egyszer, aztán küldj sokat hétfőn | az egyenletesség számít |
| ne állítsd `p=reject`-re a DMARC-ot az első héten | ha valamit elrontottál, minden leveled eltűnik |

---

## 6. lépés ⚠️ — Ahol EZ a rendszer nem segít

**Ezt olvasd el, mielőtt bármit beállítasz.** Ez nem általános tanács, hanem
a te rendszeredre vonatkozó konkrét korlát.

A küldő két helyen kezeli a postafiókokat:

```python
# limits.py — a napi keret
daily_cap() = cap × a postafiókok SZÁMA

# mailer.py — melyik fiók küldjön
next_account() = körbejár, egyenletesen oszt el
```

**Mit jelent ez a gyakorlatban:** ha felveszel egy második postafiókot a
`SMTP_ACCOUNTS`-ba, akkor

1. a napi keret **azonnal 20-ról 40-re ugrik**, és
2. a rendszer **egyenletesen** osztja szét — vagyis a vadonatúj, hideg
   postafiók **az első napon 20 levelet küldene.**

Ez pontosan a leggyorsabb út a spam mappába.

### A megoldás: külön példány, ne második fiók

Ne a `SMTP_ACCOUNTS`-ba vedd fel. Ehelyett készíts egy **külön másolatot** a
küldőből, saját adatokkal:

```bash
cp -r cold-email-starter cold-email-warmup
cd cold-email-warmup
rm -f data/sent.csv data/ramp_state.json data/leads.csv   # tiszta lap
# a .env-ben: SMTP_ACCOUNTS = CSAK az új postafiók
#             DAILY_CAP_START=3   ← ezzel indulj, ne 20-szal
```

Így a két domain **egymástól függetlenül** melegszik és rámpázik. A régi megy
tovább a maga tempójában, az új lassan indul.

> **Ha mégis egy rendszerben akarod:** ahhoz postafiókonkénti keret kellene,
> ami most nincs. Felvettem az [OPCIONALIS.md](OPCIONALIS.md) listára.

### Ha egyszer mégis egy rendszerbe teszed őket

A `data/ramp_state.json`-ban a `cap` értéket **kézzel felezd**, különben a
napi volumen egy nap alatt duplázódik.

---

## 7. lépés — Mikor válts át élesre

Akkor, ha **mind a négy** igaz:

- [ ] a domain legalább **30 napja** regisztrálva van
- [ ] legalább **3 hete** küldesz róla, fokozatosan növekvő volumennel
- [ ] **kaptál valódi válaszokat**, és a `deliverability.py` nem riasztott
- [ ] egy próbalevél a **fő postaládába** érkezik (Gmail, céges cím, outlook.com)

Ha bármelyik nem teljesül, várj még egy hetet. **Nem sürgős** — a rossz
váltás visszafordíthatatlan, a késlekedés nem.

---

## Naptár — a te dátumaiddal

| Mikor | Mit |
|---|---|
| **most, augusztusban** | domain regisztráció + weboldal/átirányítás + DNS (1-4. lépés) |
| **szeptember eleje** | pihen. Ne küldj róla semmit. |
| **szeptember közepe** | bemelegítés indul: napi 2-5 levél ismerősöknek (5. lépés) |
| **szeptember vége** | napi 10-20, vegyes |
| **október eleje** | éles kampány az új domainről, ha a 7. lépés mind a négy pontja teljesül |

A `paladi-web.hu` közben **megy tovább változatlanul** — a mostani kampányt
nem kell átköltöztetni.

---

## Automatikus bemelegítő szolgáltatások — óvatosan

Léteznek szolgáltatások (Mailwarm, Warmbox, Lemwarm, Instantly), amik
postafiókok hálózatában küldözgetnek egymásnak leveleket, amiket a rendszer
automatikusan megnyit és megválaszol.

**Mérlegeld:**

| Mellette | Ellene |
|---|---|
| gyorsan termel „válasz" jeleket | a Google egyre jobban felismeri ezeket a hálózatokat |
| nem kell hozzá ismerős | havidíjas |
| automatikus | ha felismerik, **rontja** a hírnevet, nem javítja |

**A javaslatom:** a te volumenednél (napi 20) ne költs rá. Öt ismerős, aki
valóban válaszol egy valódi levélre, többet ér — és nulla kockázat.

---

## Ellenőrző lista

Mielőtt az első éles kampány elindul az új domainről:

- [ ] domain regisztrálva, legalább 30 napja
- [ ] domain múltja ellenőrizve (nem volt korábban spammelve)
- [ ] weboldal vagy átirányítás él
- [ ] MX rekord kint van, és megérkezik rá a levél
- [ ] SPF kint van
- [ ] DKIM kint van, és a kimenő levél alá van írva
- [ ] DMARC kint van (`p=none`-nal indulva)
- [ ] mind a négy `dig` parancs választ ad
- [ ] 3+ hét bemelegítés, valódi válaszokkal
- [ ] próbalevél a fő postaládába érkezik, három különböző szolgáltatónál
- [ ] **külön példányként** fut, nem második `SMTP_ACCOUNTS` bejegyzésként
