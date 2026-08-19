# Cold email küldő rendszer (starter kit)

Önálló, futtatható cold email motor. Csak Python 3.10+ kell hozzá, **semmilyen
külső csomag nem szükséges** (minden a standard könyvtárból megy).

Nem egy "küldj ki mindenkinek" script. A logika nagy része arról szól, hogy
**kinek NE küldjünk**, mert a cold email sikere szinte teljesen ezen múlik.

---

## Gyors indulás

```bash
cp .env.example .env          # ide jönnek a saját adataid
cp data/leads.example.csv data/leads.csv

python3 -c "import mailer; mailer.check_accounts()"   # bejelentkezés-teszt
python3 sender.py --dry                                # SEMMIT nem küld, csak mutat
python3 sender.py --live                               # éles küldés
```

A `--dry` az alapértelmezés. Éles küldés csak explicit `--live` kapcsolóval
indul: a véletlen kiküldés visszafordíthatatlan.

Napi rutin (cron vagy kézzel):

```bash
python3 sender.py --live          # a küldési ablakban, akár óránként
python3 deliverability.py         # naponta egyszer, az ablak zárása után
```

---

## Mi történik egy futásnál

```
1. guards.py        válasz / leiratkozás / bounce beolvasás  -> DNC
2. limits.py        időablak + mai keret ellenőrzése
3. sender.py        follow-upok először, majd friss cold
4. mailer.py        SMTP küldés, postafiók-rotációval
5. store.py         minden küldés naplóba
```

`deliverability.py` naponta kiszámolja a mutatókat, és a `limits.py` rampje
ez alapján emeli vagy csökkenti a holnapi keretet.

---

## Fájlok

| Fájl | Mit csinál |
|---|---|
| `config.py` | minden beállítás, környezeti változóból |
| `store.py` | CSV-tárolás: leadek, küldések, DNC, bounce-ok |
| `templates.py` | **ezt kell átírnod** a saját ajánlatodra |
| `mailer.py` | SMTP küldés + IMAP olvasás |
| `guards.py` | válasz-, leiratkozás- és bounce-figyelés |
| `verify.py` | MX- és cím-ellenőrzés küldés előtt |
| `limits.py` | időablak, napi keret, automatikus ramp |
| `sender.py` | a fő futtató |
| `deliverability.py` | napi őrjárat és riasztás |

Az adatok a `data/` mappában, sima CSV-ben. Bármikor megnyithatod Excelben.

---

## A négy szabály, ami számít

**1. Lassan indulj.** Új domainről napi 20 levél. A rendszer magától emeli
20-asával, ha három egymást követő nap tiszta. Ha a bounce átlépi a 4%-ot,
azonnal visszavesz. A hirtelen volumen-ugrás a leggyorsabb út a spam-mappába.

**2. A lista fontosabb, mint a szöveg.** Egy rossz listán a legjobb szöveg is
bukik. Küldés előtt ellenőrizd a címeket (`verify.py`), és a visszapattanó
címeket AZONNAL zárd ki. Egy nem létező címre való újra-küldés duplán bünteti
a hírneved.

**3. Fájdalom először, ne szolgáltatás-lista.** Az első mondat a címzett
problémájáról szóljon, ne rólad. A "Bemutatkozom, mi egy X-szel foglalkozó cég
vagyunk" nyitó a leggyorsabb út a törlésig.

**4. Ne ígérj olyat, amit nem tartasz be.** Ha a levél azt írja "utoljára
írok", akkor tényleg az legyen az utolsó. Nálunk két külön sablon is
véglegességet ígért, miközben a szekvencia folytatódott, és ebből jogos
ügyfélpanasz lett.

---

## Amiket mi már elrontottunk (tanulj a mi kárunkon)

**Az üres válasz nem ugyanaz, mint a "nincs válasz".** Ha az IMAP-kapcsolat
hibára fut és üres listával tér vissza, a rendszer azt hiszi, senki nem
válaszolt, és kiküldi a follow-upot azoknak is, akik már válaszoltak. Ezért a
`mailer.fetch_recent` hiba esetén **kivételt dob**, és a `sender.py` ilyenkor
meg sem kezdi a küldést.

**A bounce időbélyege csal.** A bounce-napló azt rögzíti, mikor DOLGOZTUK FEL
a visszapattanást, nem azt, mikor ment ki az eredeti levél. Amikor egyszer
bepótoltunk egy többnapos hátralékot, a mérő 248 százalékos bounce-arányt
számolt és hamis riasztást küldött. A `deliverability.py` ezért csak azt
számolja bele a mai arányba, akinek MA is küldtünk.

**Nem minden bounce a te hibád.** A "nem létezik ez a cím" a lista öregedése,
a "policy rejected" viszont a hírneved. Ha mindkettőre riasztasz, a riasztás
zajjá válik és ki fogod kapcsolni. Ezért a riasztás csak a reputáció-releváns
részre néz, a teljes szám a naplóban marad.

**A felhőszolgáltatód valószínűleg blokkolja a 25-ös portot.** A cím-ellenőrző
RCPT-probe ehhez kimenő 25-ös portot igényel, amit a Hetzner, az AWS és a GCP
alapértelmezésben tilt. Ilyenkor a probe MINDEN címre "unknown"-t ad. A
`verify.py` ezért külön teszteli a portot, és az "unknown" mindig "nem tudom",
soha nem "rossz cím".

**A régi lista gyorsan romlik.** A 30+ napos címek jelentős része már halott.
Ha kifogysz a friss leadekből és a régieket kezded újra küldeni, a bounce-arány
megugrik. Inkább küldj kevesebbet friss listára, mint sokat egy régire.

---

## Jogi rész (EU / GDPR)

Ezt nézd meg, mielőtt elindulsz. Nem jogi tanács, csak a gyakorlati keret:

- A hideg **B2B** megkeresés jogalapja jellemzően a jogos érdek
  (GDPR 6. cikk (1) f). Ennek **feltétele**, hogy könnyű legyen tiltakozni.
- Ezért van minden sablonban egy leiratkozási mondat és minden levélben egy
  `List-Unsubscribe` fejléc. **Ne vedd ki őket.**
- Aki jelzi, hogy nem kér többet, azonnal és véglegesen a DNC-listára kerül.
  A `guards.py` ezt automatikusan intézi, de nézd át időnként kézzel is.
- Magánszemélyeknek (B2C) való hideg megkeresés más elbírálás alá esik.
  Ez a rendszer B2B-re készült.
- Ellenőrizd a saját országod szabályait is. Magyarországon a Grt. és a GDPR
  együtt irányadó.

---

## Beállítás előtt: a domain

A küldés technikai része kevés, ha a domain nincs rendben. Küldés előtt
állítsd be:

- **SPF** rekord a küldő szolgáltatódra
- **DKIM** aláírás
- **DMARC** rekord (kezdd `p=none`-nal, később szigorítsd)

Ellenőrzés: mxtoolbox.com vagy `dig TXT sajatdomain.hu`.

Erősen ajánlott **külön domaint** használni a hideg megkeresésre (pl.
`sajatceg-info.hu`), hogy a fő domained hírnevét ne kockáztasd. Ha a
küldődomain hírneve romlik, a fő domainről küldött számláid és
ügyfélleveleid is spambe kerülhetnek.

---

## Amit NEM tartalmaz

- **Lead-gyűjtés / scraping.** A `data/leads.csv`-t neked kell feltöltened.
  Ez szándékos: a lead-forrás jogi és minőségi kérdés, azt neked kell eldöntened.
- **Nyitás- és kattintás-követés.** Szándékosan nincs benne: a követőpixel
  ront a kézbesítésen, és a válaszarány úgyis többet mond.
- **Adatbázis.** CSV-ben minden, hogy átlátható és hordozható maradjon.

---

## Mikor állj le

Ha bármelyik igaz, állítsd le a kampányt és nézd át a listát:

- bounce-arány tartósan 4% felett
- SMTP-elutasítás 3% felett (a szolgáltatód fékez)
- spam-panasz érkezik
- 1000 kiküldött levél után 1% alatti válaszarány (rossz lista vagy rossz üzenet)

Irányszámok: **1% alatti válaszarány** = rossz lista vagy rossz üzenet.
**1-3%** = működőképes. **3% felett** = skálázható.

---

## Licenc

MIT, lásd a `LICENSE` fájlt. Szabadon használhatod, módosíthatod, ügyfélnél is
bevetheted.
