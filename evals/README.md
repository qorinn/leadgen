# Bake-off tesztkészlet (opcionális modellkalibráció)

> 2026-08-25 óta ez **nem lead-kizárási és nem implementációs kapu**. Az AI
> több `opportunity_angles` irányt ad, a cég pedig gyenge jel esetén is
> megmarad. A régi `FIT`/`NO FIT` címke csak azt méri, felismeri-e a modell a
> webapp irányt; nem azt, hogy meg kell-e keresni a céget.

A `bakeoff-30.jsonl` **emberi munka**, és szándékosan az. A protokoll:
[SCRAPER-PLAN.md 2981–3258](../SCRAPER-PLAN.md) — „Függelék: bake-off protokoll".

## Miért nem generálja ezt AI

A 10 határeset kézi címkéje itt csak kalibrációs referencia. Ha egy modell
írná a címkéket, az eval azt mérné, hogy két modell egyetért-e egymással. Ezt
nyugodtan hagyd ki, amíg nem akarsz modelleket összehasonlítani.

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
./leadgen.sh eval bakeoff --model gpt-5.6-luna
./leadgen.sh eval bakeoff --model gpt-5.6-luna --model gpt-5-nano   # egymás mellett
./leadgen.sh eval robustness --model gpt-5.6-luna
```

**Jelöltek, amiket érdemes egymás mellé tenni** (a provider a modellnévből
derül ki, tehát bármelyik mehet ugyanabba a futásba):

| Modell | Miért jelölt |
|---|---|
| `gpt-5.6-luna` | jelenlegi alapértelmezés — a legolcsóbb OpenAI tier |
| `gpt-5-nano` | az előző generáció ugyanebben a szerepben |
| `gpt-5.6-terra` | drágább, de erősebb — megéri-e a különbség? |
| `gemini-2.5-flash-lite` | ha visszatérnél a Geminire |
| `claude-haiku-4-5` | a QUALITY tier modellje, összehasonlításnak |

**Ezt a fájlt verziókövesd.** Ez a rendszer első és sokáig egyetlen evalja:
fél év múlva egy új modellnél ugyanez a 30 eset 2 perc alatt megmondja,
megéri-e váltani.
