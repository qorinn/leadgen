# Leadgen scraper és cold-email workflow

Helyben futó, Python-alapú lead-intelligence rendszer magyar B2B megkeresésekhez. Forrásokból cégeket gyűjt, ellenőrzi és rangsorolja őket, majd az arra alkalmas leadeket egy külön cold-email küldő rendszer számára exportálja.

## Mit tud

- Cégeket gyűjt több forrásból, és egységes adatmodellben tárolja őket.
- Weboldal- és kapcsolatadatokat dúsít, valamint email-címeket ellenőriz.
- AI-val értékeli a releváns üzleti jeleket, bizonyítékot rendel hozzájuk, és személyre szabott nyitómondatot készít.
- Pontozza, szűri és emberi átnézésre adja a leadeket; a leiratkozott, visszapattanó vagy elutasított címeket kizárja.
- A jóváhagyott leadeket CSV-be exportálja a `cold-email-starter` számára.
- Visszaolvassa a küldési, válasz-, bounce- és leiratkozási visszajelzéseket, így a következő export nem küld újra tiltott vagy már kezelt címre.
- Tartalmaz napi futtatási, küldési sebességkorlát-, monitoring- és riasztási funkciókat.
- Opcionális helyi webes felületet ad a leadek, futások, riportok, küldési előnézetek és beállítások kezeléséhez.

## Fő részek

- `leadgen/` – a scraper, enrichment, pontozás, export és üzemeltetési logika.
- `cold-email-starter/` – külön küldő komponens és levélsablonok.
- `webui/` – helyi FastAPI + Next.js kezelőfelület.
- `tests/` – automatizált üzleti és integrációs tesztek.

## Használat

A telepítéshez, konfigurációhoz és a teljes napi folyamathoz lásd a [HOGYAN-HASZNALD.md](HOGYAN-HASZNALD.md) útmutatót. A parancsok teljes listája a [PARANCSOK.md](PARANCSOK.md)-ben található.

Az éles kulcsok, postafiókadatok, leadlisták, cache-ek és futásidejű naplók nem részei a repónak. A szükséges változókat a [.env.example](.env.example) alapján kell beállítani.

## Fontos

A rendszer nem automatikus tömeges kiküldésre készült: az export és a küldés előtt jóváhagyási, suppression- és kézbesítési védelmek működnek. A tényleges kampányindításért, az adatforrások jogszerű használatáért és a vonatkozó adatvédelmi szabályok betartásáért mindig az üzemeltető felel.
