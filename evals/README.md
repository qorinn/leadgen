# Bake-off tesztkészlet

A `bakeoff-30.jsonl` **emberi munka**, és szándékosan az. A protokoll:
[SCRAPER-PLAN.md 2981–3258](../SCRAPER-PLAN.md) — „Függelék: bake-off protokoll".

## Miért nem generálja ezt AI

A 10 határeset kézi címkéje a **te üzleti döntésed**. Ha egy modell írná a
címkéket, az eval azt mérné, hogy két modell egyetért-e egymással — nem azt,
hogy jó leadeket válogatnak-e neked. A könnyű eseteken minden modell jó lesz;
**a választ a 10 határeset adja meg.**

## Formátum

Soronként egy JSON objektum (JSONL). A `//`-vel kezdődő sorok kimaradnak.

| Mező | Kötelező | Mit tartalmaz |
|---|---|---|
| `id` | ✅ | rövid azonosító, pl. `fit-01`, `hat-03` |
| `csoport` | ✅ | `fit` \| `nofit` \| `hatareset` — 10-10-10 |
| `cimke` | ✅ | a **te** ítéleted: `FIT` \| `NO FIT` |
| `szoveg` | ✅ | a hirdetés teljes szövege |
| `miert` | ajánlott | egy mondat, miért ez a címke |
| `ceg` | | cégnév |
| `pozicio` | | a meghirdetett pozíció |
| `forras` | | alapértelmezés: `Profession.hu álláshirdetés` |

A `miert` mező később aranyat ér: ha egy modell máshogy dönt, abból látod,
hogy ő értette félre, vagy a te kritériumod nem volt egyértelmű.

## Egy sor példaként

```json
{"id":"fit-01","csoport":"fit","cimke":"FIT","ceg":"Példa Kft.","pozicio":"Szervizkoordinátor","miert":"Excel + munkalap + terepi szerelők ütemezése, mind a három jel megvan","szoveg":"Szervizkoordinátort keresünk, aki a beérkező hibabejelentéseket rögzíti, a szerelők napi beosztását Excelben vezeti, és a munkalapokat kezeli..."}
```

## Hogyan gyűjtsd (30-40 perc, terv A/4)

```text
1. profession.hu kereső
2. keress rá: szervizkoordinátor, diszpécser, munkairányító,
   projektkoordinátor, logisztikai koordinátor       → 10 db FIT
3. NO FIT csoporthoz: hegesztő, sofőr, eladó, takarító → 10 db
4. a HATÁRESET csoportot te válogatod — ezek azok,
   ahol neked is gondolkodnod kell egy pillanatig      → 10 db
```

Határeset-ötletek a tervből: irodai asszisztens egy 3 fős cégnél (túl kicsi);
projektmenedzser, de a szöveg általános; adminisztrátor, de csak számlázás
(kész szoftver van rá); koordinátor egy szoftvercégnél (versenytárs);
művezető gyárban, fix telephelyen (nincs terepi elem).

## Futtatás

```bash
./leadgen.sh eval bakeoff --model gemini-2.5-flash-lite
./leadgen.sh eval bakeoff --model claude-haiku-4-5
./leadgen.sh eval bakeoff --model gemini-2.5-flash-lite --model claude-haiku-4-5   # egymás mellett
./leadgen.sh eval robustness --model gemini-2.5-flash-lite
```

**Ezt a fájlt verziókövesd.** Ez a rendszer első és sokáig egyetlen evalja:
fél év múlva egy új modellnél ugyanez a 30 eset 2 perc alatt megmondja,
megéri-e váltani.
