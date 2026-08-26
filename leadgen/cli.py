#!/usr/bin/env python3
"""leadgen parancssor.

    .venv/bin/python -m leadgen.cli db migrate
    .venv/bin/python -m leadgen.cli db check

Ez a modul SZANDEKOSAN vekony: csak argumentumot elemez es kiir. Minden
uzleti logika a tobbi modul fuggvenyeiben van, hogy a 13. szakasz webes
felulete ugyanazokat hivhassa -- a CLI ne legyen zsakutca.

Parancscsoportok:
    db      -- migracio, allapot, kapcsolodasi adatok
    export  -- DB -> cold-email-starter/data/leads.csv
    report  -- hol tart a tolcser, es mi fer bele a mai keretbe
    dev     -- fejlesztoi teszt-adat (sosem eles)
"""
from __future__ import annotations

import argparse
import sys

from . import (classify, config, db, deadev, dev, engines, evals, export,
               feedback, labels, llm, llmcheck, pipeline, report, score)
from .sources import maps, profession


def _cmd_db_migrate(_args: argparse.Namespace) -> int:
    print(f"Migraciok innen: {config.MIGRATIONS_DIR}")
    applied = db.migrate()
    print(f"\nKesz. Ujonnan alkalmazva: {len(applied)}")
    return 0


def _cmd_db_check(_args: argparse.Namespace) -> int:
    info = db.server_info()
    version = str(info.get("version", "?")).split(",")[0]
    print(f"Szerver : {version}")
    print(f"Adatbazis: {info.get('db')}")
    print()

    counts = db.check()
    missing = [t for t, n in counts.items() if n is None]
    width = max(len(t) for t in counts)
    for table, n in counts.items():
        state = "HIANYZIK" if n is None else f"{n} sor"
        print(f"  {table:<{width}}  {state}")

    if missing:
        print(f"\nHIBA: {len(missing)} tabla hianyzik. Futtasd: db migrate")
        return 1
    print(f"\nMind a {len(counts)} tabla megvan.")
    return 0


def _cmd_db_info(_args: argparse.Namespace) -> int:
    """Kapcsolodasi adatok jelszo NELKUL -- hibakeresesre."""
    from urllib.parse import urlsplit

    u = urlsplit(config.require_database_url())
    print(f"host      = {u.hostname}")
    print(f"port      = {u.port}")
    print(f"felhasznalo = {u.username}")
    print(f"adatbazis = {(u.path or '').lstrip('/')}")
    print(f"jelszo    = {'meg van adva' if u.password else 'HIANYZIK'}")
    if u.port == 6543:
        print("\nFIGYELEM: ez a transaction pooler (6543). A migraciok elhasalnak rajta.")
        print("Kerd a session poolert (5432).")
    print(f"\nkuldo konyvtar = {config.SENDER_DIR}  "
          f"({'letezik' if config.SENDER_DIR.exists() else 'HIANYZIK'})")
    print(f"email validacio = {config.EMAIL_VALIDATION}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    export.run(dry=args.dry, limit=args.limit, skip_feedback=args.skip_feedback)
    return 0


def _cmd_feedback(_args: argparse.Namespace) -> int:
    """Onalloan is futtathato -- pl. ha latsz egy valaszt a postafiokban,
    es azonnal at akarod vezetni a DB-be."""
    feedback.run(verbose=True)
    return 0


def _cmd_dev_seed(_args: argparse.Namespace) -> int:
    created = dev.seed()
    print(f"Teszt-cegek: {created} uj, a tobbi mar letezett.")
    print("Torles: leadgen dev clear-seed")
    return 0


def _cmd_dev_clear_seed(_args: argparse.Namespace) -> int:
    print(f"Torolve: {dev.clear_seed()} teszt-ceg.")
    return 0


def _cmd_ingest_maps(args: argparse.Namespace) -> int:
    engine = engines.get(args.engine)
    print(f"Engine: {engine.label}")
    stats = maps.ingest(engine, max_results=args.max_results, dry=args.dry,
                        refresh_days=args.refresh_days, force=args.force,
                        location=args.location)
    if not args.dry:
        print(f"\n  lefuttatott lekerdezes={stats['lekerdezes']}  "
              f"korabban mar lefutott={stats['kihagyva']} (kihagyva)")
        print(f"  talalat={stats['talalat']} uj ceg={stats['uj_ceg']} "
              f"mar ismert={stats['mar_ismert']} kulcs nelkul={stats['kulcs_nelkul']}")
        if stats["hatralevo"]:
            print(f"\n  Meg {stats['hatralevo']} lekerdezes var -- a keret ({args.max_results}) "
                  f"elfogyott.\n  Futtasd ujra ugyanezt a parancsot: onnan folytatja.")
    return 0


def _cmd_enrich(args: argparse.Namespace) -> int:
    pipeline.run_enrich(limit=args.limit)
    return 0


def _cmd_ingest_ops_pain(args: argparse.Namespace) -> int:
    # A `get()` kikapcsolt engine-re hibat dob -- itt viszont a FORRAS fut,
    # ami a minositestol fuggetlen. A hirdeteseket be lehet gyujteni azelott,
    # hogy a 10. szakasz classifiere elkeszulne.
    engine = engines.ALL_ENGINES["ops_pain"]
    print(f"Engine: {engine.label}")
    if not engine.enabled:
        print("  (az engine MINOSITESE meg ki van kapcsolva -- a hirdeteseket")
        print("   begyujtjuk, a minosites a 10. szakaszban jon)")
    profession.ingest(engine, max_results=args.max_results, dry=args.dry,
                      location=args.location or "",
                      resolve_maps=args.resolve_maps,
                      refresh_days=args.refresh_days, force=args.force)
    return 0


def _cmd_llm_check(args: argparse.Namespace) -> int:
    if args.summary:
        llmcheck.osszesites()
        return 0
    models = args.model or [config.LLM_BULK_MODEL, config.LLM_QUALITY_MODEL]
    return llmcheck.run(models, ismetles=args.repeat,
                        keret_usd=args.budget, dry=args.dry)


def _cmd_score(args: argparse.Namespace) -> int:
    hiany = llm.kulcs_hianyzik(config.LLM_BULK_MODEL)
    if hiany:
        print(f"HIBA: {hiany}")
        print("  (vagy allitsd at a LLM_BULK_MODEL-t olyan modellre, amihez van kulcsod)")
        return 1
    score.run(limit=args.limit, dry=args.dry)
    return 0


def _cmd_resolve_domains(args: argparse.Namespace) -> int:
    profession.resolve_pending(limit=args.limit, dry=args.dry)
    return 0


def _cmd_enrich_deadev(args: argparse.Namespace) -> int:
    deadev.run(limit=args.limit, mind=args.all, dry=args.dry)
    return 0


def _cmd_qualify(args: argparse.Namespace) -> int:
    engine = engines.get(args.engine)
    print(f"Engine: {engine.label}")
    pipeline.run_qualify(engine, limit=args.limit)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    if args.grounding:
        return report.grounding()
    if args.signal == "dead_dev":
        return report.dead_dev()
    if args.replies:
        return report.replies()
    return report.run(daily_view=args.daily)


def _cmd_classify_replies(args: argparse.Namespace) -> int:
    hiany = llm.kulcs_hianyzik(config.LLM_QUALITY_MODEL)
    if hiany:
        print(f"HIBA: {hiany}")
        return 1
    classify.run(limit=args.limit, dry=args.dry)
    return 0


def _cmd_eval_bakeoff(args: argparse.Namespace) -> int:
    # Az alapertelmezes a configbol jon, nem a parserbol: igy a .env-ben
    # beallitott modell szamit alapnak, es nem kell ket helyen irni.
    args.model = args.model or [config.LLM_BULK_MODEL]
    esetek = evals.betolt()
    csoportok: dict[str, int] = {}
    for e in esetek:
        csoportok[e.get("csoport", "?")] = csoportok.get(e.get("csoport", "?"), 0) + 1
    print(f"Tesztkeszlet: {len(esetek)} eset  {csoportok}")
    if csoportok.get("hatareset", 0) < 5:
        print("\nFIGYELEM: 5-nel kevesebb hatareset van a keszletben. A terv szerint")
        print("a dontest EZEK adjak -- a konnyu eseteken minden modell jo lesz.\n")

    eredmenyek = []
    for model in args.model:
        print(f"\n{'=' * 60}\n{model}\n{'=' * 60}")
        eredmenyek.append(evals.futtat(model, esetek))
    evals.tablazat(eredmenyek)

    for r in eredmenyek:
        if r.tevedesek:
            print(f"\n--- {r.model}: ahol maskepp dontott, mint te ---")
            for t in r.tevedesek:
                print(f"  {t}")
    return 0


def _cmd_eval_sentences(args: argparse.Namespace) -> int:
    models = args.model or [config.LLM_QUALITY_MODEL]
    return evals.mondatok(models, limit=args.limit)


def _cmd_eval_robustness(args: argparse.Namespace) -> int:
    args.model = args.model or [config.LLM_BULK_MODEL]
    for model in args.model:
        print(f"\n{'=' * 60}\n{model} -- robusztussagi teszt (terv C)\n{'=' * 60}")
        evals.robusztussag(model)
    return 0


def _cmd_engines(_args: argparse.Namespace) -> int:
    print(f"{'kulcs':22} {'allapot':10} {'kampany':18} nev")
    print("-" * 80)
    for key, e in sorted(engines.ALL_ENGINES.items()):
        allapot = "aktiv" if e.enabled else "kikapcsolva"
        print(f"{key:22} {allapot:10} {e.campaign:18} {e.label}")
    print("\nUj iparag felvetele: leadgen/engines.py -- az iparag adat, nem kod.")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    """Emberi dontes. Az AUTOMATIKUS dontesek is felulbirlhatok innen."""
    if args.approve:
        # A gep automatikus VERSENYTARS-dontese felulbiralhato. Mas
        # suppression-ok (leiratkozas, bounce) ezen a parancson at sem
        # oldhatok fel veletlenul.
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select c.id,
                       exists (
                         select 1 from contacts ct
                          where ct.company_id = c.id
                            and ct.local_check is distinct from 'fail'
                            and coalesce(ct.verify_result, '') <> 'invalid'
                            and coalesce(ct.bounce_state, '') <> 'hard_bounce'
                       ) as van_kapcsolat
                  from companies c
                 where c.normalized_domain = %s
                   and (
                     c.status in ('review', 'hold', 'rejected')
                     or (c.status = 'suppressed' and exists (
                       select 1 from suppression sp
                        where sp.normalized_domain = c.normalized_domain
                          and sp.reason = 'competitor'
                     ))
                   )
                """,
                (args.approve,))
            hit = cur.fetchone()
            n = 1 if hit else 0
            status = ""
            if hit:
                cur.execute("delete from suppression where normalized_domain = %s "
                            "and reason = 'competitor'", (args.approve,))
                status = "ready" if hit["van_kapcsolat"] else "scored"
                cur.execute(
                    "update companies set status = %s, status_note = 'kezi jovahagyas' "
                    "where id = %s", (status, hit["id"]))
                for label in ("manual_review", "enterprise_hold", "legacy_rejected"):
                    labels.clear_label(cur, hit["id"], label)
        print(f"Jovahagyva: {n} ceg -> {status}" if n else
              "Nincs jovahagyhato review/hold/competitor ceg ezen a domainen.")
        return 0

    if args.suppressed:
        rows = db.query("""
            select c.normalized_domain, c.company_name, c.status_note,
                   s.raw_signal->>'title' as title
              from companies c
              left join sources s on s.company_id = c.id and s.source_type = 'website_crawl'
             where c.status = 'suppressed' and c.status_note like 'versenytars%'
             order by c.normalized_domain
        """)
        if not rows:
            print("Nincs automatikusan kizart ceg.")
            return 0
        print(f"{len(rows)} ceget a rendszer AUTOMATIKUSAN zart ki versenytarskent.\n")
        print("Ha valamelyiket tevesnek tartod, visszahozhatod:")
        print("  ./leadgen.sh review --approve <domain>\n")
        for r in rows:
            print(f"  https://{r['normalized_domain']}")
            print(f"    {r['company_name']}")
            print(f"    {r['status_note']}")
            print(f"    cim: {(r['title'] or '')[:88]}\n")
        return 0
    if args.reject:
        # MIERT NEM CSAK `review` ALLAPOTBOL: az 5. szakasz emberi feladata az,
        # hogy a kikuldes elott VEGIGOLVASD a dry-run kimenetet -- "ez az utolso
        # visszafordithato pont". Csakhogy amit ott latsz, az mar `queued`:
        # exportalva van a leads.csv-be. Ha innen nem lehetne kihuzni egy ceget,
        # a felulvizsgalatnak nem lenne eszkoze. A `sent` is benne van: onnan a
        # kihuzas a MEG HATRALEVO follow-upokat allitja le.
        reason = args.reason or "manual_block"
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("select id from companies where normalized_domain = %s "
                        "and status in ('review','queued','sent','ready','enriched','new')",
                        (args.reject,))
            hit = cur.fetchone()
            n = 1 if hit else 0
            if hit:
                cur.execute("update companies set status = 'suppressed', status_note = %s "
                            "where id = %s",
                            (f"kezi elutasitas: {reason}", hit["id"]))
                cur.execute("insert into suppression (normalized_domain, reason, note) "
                            "values (%s, %s, 'kezi elutasitas') "
                            "on conflict (normalized_domain) where normalized_domain is not null "
                            "and email is null do nothing", (args.reject, reason))
                # A folyamatban levo megkereses lezarasa. Enelkul a domain lock
                # reszleges indexe szerint a szekvencia orokre "aktiv" maradna.
                cur.execute("update outreach set status = 'stopped' "
                            "where company_id = %s and status in ('queued','sent')",
                            (hit["id"],))
        if n:
            print(f"Elutasitva: {args.reject} -> suppressed ({reason})")
            print("A leads.csv-bol a kovetkezo exportnal tunik el:")
            print("  ./leadgen.sh export")
        else:
            print("Nincs ilyen ceg (vagy mar tiltolistan van).")
        return 0

    rows = db.query("""
        select c.normalized_domain, c.company_name, c.status_note, c.signal_summary,
               (select ct.email from contacts ct where ct.company_id = c.id limit 1) as email
          from companies c where c.status = 'review'
         order by c.signal_score desc nulls last, c.company_name
    """)
    if not rows:
        print("Nincs atnezendo ceg.")
        return 0
    print(f"{len(rows)} ceg var emberi dontesre.\n")
    print("A gyenge kizaro jel gyakran ugyfel-referenciabol vagy blogcikkbol jon,")
    print("nem a ceg sajat szolgaltatas-listajabol. Nyisd meg az oldalt es dontsd el.\n")
    for r in rows:
        print(f"  https://{r['normalized_domain']}")
        print(f"    {r['company_name']}   {r['email'] or '(nincs email)'}")
        print(f"    {r['status_note']}")
        print(f"    jovahagyas : leadgen review --approve {r['normalized_domain']}")
        print(f"    elutasitas : leadgen review --reject  {r['normalized_domain']}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leadgen", description="Lead-scraper")
    sub = parser.add_subparsers(dest="group", required=True)

    db_parser = sub.add_parser("db", help="adatbazis-muveletek")
    db_sub = db_parser.add_subparsers(dest="action", required=True)
    db_sub.add_parser("migrate", help="a meg nem futtatott migraciok").set_defaults(
        func=_cmd_db_migrate)
    db_sub.add_parser("check", help="tablak es sorszamok").set_defaults(
        func=_cmd_db_check)
    db_sub.add_parser("info", help="kapcsolodasi adatok (jelszo nelkul)").set_defaults(
        func=_cmd_db_info)

    exp = sub.add_parser("export", help="leadek kiirasa a kuldonek")
    exp.add_argument("--dry", action="store_true",
                     help="csak megmutatja, mit irna ki -- nem ir es nem allit sorba")
    exp.add_argument("--limit", type=int, default=0,
                     help="ennyi UJ leadnel tobbet ne allitson sorba (adagolas)")
    exp.add_argument("--skip-feedback", action="store_true",
                     help="csak fejlesztes kozben: kihagyja a kotelezo feedback-importot")
    exp.set_defaults(func=_cmd_export)

    fb = sub.add_parser("feedback", help="a kuldo CSV-inek beolvasasa a DB-be")
    fb.set_defaults(func=_cmd_feedback)

    rp = sub.add_parser("report", help="hol tart a tolcser, es mi tortenik ma")
    rp.add_argument("--daily", action="store_true",
                    help="csak a mai kep: napi keret vs. sorbanallas")
    rp.add_argument("--replies", action="store_true",
                    help="a valaszok besorolas szerinti bontasa")
    rp.add_argument("--signal", metavar="NEV", choices=("dead_dev",),
                    help="egy signal reszletes bontasa (pl. dead_dev)")
    rp.add_argument("--grounding", action="store_true",
                    help="az AI-allitasok es a hozzajuk tartozo idezetek")
    rp.set_defaults(func=_cmd_report)

    cr = sub.add_parser("classify-replies", help="AI valasz-osztalyozas (6. szakasz)")
    cr.add_argument("--dry", action="store_true",
                    help="csak megmutatja a besorolast -- SEMMIT nem ir")
    cr.add_argument("--limit", type=int, default=50)
    cr.set_defaults(func=_cmd_classify_replies)

    ev = sub.add_parser("eval", help="modell-ertekeles (bake-off)")
    ev_sub = ev.add_subparsers(dest="action", required=True)
    bo = ev_sub.add_parser("bakeoff", help="a 30 eset vegigfuttatasa")
    bo.add_argument("--model", action="append", default=None,
                    help="tobbszor is megadhato -- egymas mellett meri oket")
    bo.set_defaults(func=_cmd_eval_bakeoff)
    ms = ev_sub.add_parser("sentences",
                           help="B) teszt: personalization mondatok VAKON")
    ms.add_argument("--model", action="append", default=None,
                    help="tobbszor is megadhato (alap: a QUALITY modell)")
    ms.add_argument("--limit", type=int, default=8,
                    help="ennyi leadre generaljon mondatot")
    ms.set_defaults(func=_cmd_eval_sentences)

    rb = ev_sub.add_parser("robustness", help="tamado bemenetek (terv C)")
    rb.add_argument("--model", action="append", default=None)
    rb.set_defaults(func=_cmd_eval_robustness)

    sub.add_parser("engines", help="elerheto lead engine-ek").set_defaults(func=_cmd_engines)

    rv = sub.add_parser("review", help="emberi dontesre varo cegek")
    rv.add_argument("--approve", metavar="DOMAIN", help="jo lead -> ready")
    rv.add_argument("--reject", metavar="DOMAIN",
                    help="ne keressuk meg -> suppressed (mar exportalt leadre is)")
    rv.add_argument("--reason", metavar="OK", default=None,
                    choices=("manual_block", "competitor", "existing_client",
                             "negative_reply", "unsubscribe"),
                    help="a tiltas oka (alapertelmezes: manual_block)")
    rv.add_argument("--suppressed", action="store_true",
                    help="az AUTOMATIKUSAN kizart cegek (felulbirlhatod oket)")
    rv.set_defaults(func=_cmd_review)

    ing = sub.add_parser("ingest", help="cegek betoltese egy forrasbol")
    ing_sub = ing.add_subparsers(dest="source", required=True)
    m = ing_sub.add_parser("maps", help="Google Maps (Apify)")
    m.add_argument("--engine", default="agency_partner")
    m.add_argument("--max-results", type=int, default=50,
                   help="felso korlat a TELJES futasra (~$0.005 / talalat)")
    m.add_argument("--dry", action="store_true", help="csak a terv, nem koltunk")
    m.add_argument("--refresh-days", type=int, default=30,
                   help="ennyi napnal regebbi lekerdezes ujra futhat (0 = soha)")
    m.add_argument("--location", metavar="VAROS",
                   help="csak erre a telepulesre fusson (pl. Budapest)")
    m.add_argument("--force", action="store_true",
                   help="minden lekerdezes ujra fut, meg a mar lefuttatottak is")
    m.set_defaults(func=_cmd_ingest_maps)

    op = ing_sub.add_parser("ops-pain", help="Profession.hu allashirdetesek")
    op.add_argument("--max-results", type=int, default=50,
                    help="felso korlat a TELJES futasra (koltsegfek)")
    op.add_argument("--location", metavar="VAROS", default="",
                    help="pl. Budapest (uresen: orszagos)")
    op.add_argument("--dry", action="store_true",
                    help="csak a terv -- NEM kolt")
    op.add_argument("--resolve-maps", action="store_true",
                    help="FIZETOS: Google Maps a domain feloldasahoz (~$0.005/ceg)")
    op.add_argument("--refresh-days", type=int, default=1,
                    help="ennyi napon belul ne fusson ujra ugyanaz a kereses "
                         "(alap: 1 = naponta egyszer; 0 = mindig fusson)")
    op.add_argument("--force", action="store_true",
                    help="minden kereses fusson, meg a ma mar lefuttatottak is")
    op.set_defaults(func=_cmd_ingest_ops_pain)

    lc = sub.add_parser("llm-check",
                        help="eles API-teszt: mukodik-e, es MENNYIBE kerul")
    lc.add_argument("--model", action="append", default=None,
                    help="tobbszor is megadhato (alap: a ket beallitott modell)")
    lc.add_argument("--repeat", type=int, default=1,
                    help="ennyi hivas modellenkent")
    lc.add_argument("--budget", type=float, default=0.50,
                    help="koltsegfek USD-ben: e felett el sem indul")
    lc.add_argument("--dry", action="store_true",
                    help="csak a becsult koltseg -- NEM hiv API-t")
    lc.add_argument("--summary", action="store_true",
                    help="az eddigi merések osszesitese modellenkent")
    lc.set_defaults(func=_cmd_llm_check)

    sc = sub.add_parser("score", help="AI-minosites + evidence grounding (10. szakasz)")
    sc.add_argument("--limit", type=int, default=20)
    sc.add_argument("--dry", action="store_true",
                    help="csak megmutatja a minositest -- SEMMIT nem ir")
    sc.set_defaults(func=_cmd_score)

    rd = sub.add_parser("resolve-domains",
                        help="a domain nelkul beragadt cegek feloldasa (FIZETOS)")
    rd.add_argument("--limit", type=int, default=20)
    rd.add_argument("--dry", action="store_true", help="csak a terv -- nem kolt")
    rd.set_defaults(func=_cmd_resolve_domains)

    en = sub.add_parser("enrich", help="weboldalak feldolgozasa (`new` -> `enriched`)")
    en.add_argument("--limit", type=int, default=25)
    en.set_defaults(func=_cmd_enrich)
    en_sub = en.add_subparsers(dest="action")
    dd = en_sub.add_parser("dead-dev",
                           help="8.2: ki keszitette a weboldalt, es el-e meg")
    dd.add_argument("--all", action="store_true",
                    help="a mar megvizsgaltakat is ujra nezi")
    dd.add_argument("--limit", type=int, default=200)
    dd.add_argument("--dry", action="store_true",
                    help="csak megmutatja -- semmit nem ir")
    dd.set_defaults(func=_cmd_enrich_deadev)

    ql = sub.add_parser("qualify", help="minosites (`enriched` -> `ready`/`scored`/`review`)")
    ql.add_argument("--engine", default="agency_partner")
    ql.add_argument("--limit", type=int, default=200)
    ql.set_defaults(func=_cmd_qualify)

    dev_parser = sub.add_parser("dev", help="fejlesztoi eszkozok")
    dev_sub = dev_parser.add_subparsers(dest="action", required=True)
    dev_sub.add_parser("seed", help="teszt-cegek beszurasa (.invalid domainek)").set_defaults(
        func=_cmd_dev_seed)
    dev_sub.add_parser("clear-seed", help="teszt-cegek torlese").set_defaults(
        func=_cmd_dev_clear_seed)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
