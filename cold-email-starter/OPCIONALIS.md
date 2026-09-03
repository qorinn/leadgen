
---

### C3. Új lead-források — az „app-first" pozicionálás mentén (2026-09-03)

**A vezérelv, amit a felhasználó kimondott:** *„ne a weboldal legyen az
elsődleges szolgáltatás, hanem az alkalmazások. Weboldalt már mindenki tud
készíteni és szerezni olcsón, de alkalmazásokat (webes vagy mobil) nagyon
kevesen készítenek."*

Ez visszamenőleg is fontos: a jelenlegi két kampány (`agency_partner`,
`ops_pain`) közül csak az `ops_pain` szól ténylegesen rendszerről. Minden új
forrásnál az a kérdés, hogy **alkalmazás-alakú problémát** talál-e.

**A második vezérelv:** konkrét, MÁR FENNÁLLÓ problémával keressük meg őket.
Az `ops_pain` azért működik, mert egy álláshirdetés kimondott fájdalom.

#### Amit érdemes megépíteni, sorrendben

**1. Az `ops_pain` kiterjesztése több álláshirdetési oldalra.**
A legjobb arány: a kód (`score`, grounding, export, feedback) MÁR KÉSZ, csak
egyetlen forrás van bekötve (profession.hu). Új forrás = új modul a
`leadgen/sources/` alá, a `sources` tábla raw-first mentése változatlan.
Jelöltek: cvonline.hu, allasportal.hu, jobline.hu, Indeed HU.
⚠️ A LinkedIn robots.txt-je kifejezetten tiltja az automatizált hozzáférést
(lásd `sources/apify.py` fejléce) — az nem jöhet szóba.

**2. Elavult / rossz értékelésű mobilalkalmazás.**
Google Play és App Store scraper (van rá kész Apify actor). Célzás: magyar
cégek, akiknek VAN appjuk, de 2+ éve nem frissült, vagy tele van rossz
értékeléssel. Ez a legtisztábban app-alakú jel az összes ötlet közül —
a megkeresésben egy szót sem kell weboldalról ejteni.

**3. Partnerkeresés élesítése (az `agency_partner` finomítása).**
A mostani szűrés ügynökség-általános. Élesíthető: olyan ügynökségek, akiknek
a portfóliójában CSAK weboldalak vannak, alkalmazás nincs — nekik pont az
hiányzik, amit az alvállalkozó ad. Az `enrich` már letölti a portfólió- és
szolgáltatás-oldalakat, tehát az adat nagyrészt megvan.

#### Amit MEGVIZSGÁLTUNK ÉS ELVETETTÜNK — az indoklással

Ezek elsőre kézenfekvőnek tűnnek; a felhasználó tapasztalata alapján viszont
nem működnének. Ne kerüljenek vissza indoklás nélkül.

| Ötlet | Miért nem |
|---|---|
| **„Nincs weboldala"** (Maps, `withoutWebsite`) | Nincs mivel felvenni a kapcsolatot: email nincs, az SMS régi készüléken hibásan jelenik meg (mért tapasztalat). Ráadásul a versenytársak PONT ezt csinálják hideghívással — a leggyakoribb válasz, hogy „naponta kapok ilyen ajánlatot". |
| **Új iparágak** (fogorvos, ügyvéd, edzőterem…) | Ugyanaz a probléma, mint fent. Ezekben az irányokban inkább PARTNERT érdemes keresni, nem ügyfelet. |
| **Facebook Ads Library** | Aki hirdet, annak jellemzően már van ügynöksége, aki a weboldalt és a hirdetést is viszi — nagyon alacsony konverziós esély. |
| **Elavult weboldal az `agency_partner` listán** | Marketingügynökségeknél értelmetlen jel: az ő oldaluk a kirakatuk. Más célcsoporton lehet értelme, ott viszont az előző két sor problémája jön elő. |

#### Nyitott kérdés: Google 2. oldal

A felhasználó ötlete: a Google találati lista MÁSODIK oldalán álló cégek
begyűjtése (Google Search actor), és megkeresés SEO + weboldal-optimalizálás
szöggel. A lead-jel jó és konkrét — a gond a MEGKERESÉS szöge: az SEO és a
weboldal pont az, amit nem akarunk elsődlegesként árulni. Ajtónyitónak
működhet, de a levélnek gyorsan rendszerre kell fordulnia. Előbb az 1-3.
pontot érdemes kihasználni.

#### Mérőszám, mielőtt bármelyikbe belekezdesz

**Nem a leadhiány a szűk keresztmetszet.** 2026-09-03-i állapot: 33 cég vár
emberi döntésre, 10 kész `ops_pain` lead áll a jóváhagyási kapuban, a napi
küldési keret pedig 20-30. Egy új forrás csak akkor hoz több ügyfelet, ha
ezek már elfogytak — vagy ha JOBB leadeket ad ugyanabba a keretbe.
