#!/usr/bin/env python3
"""Inietta catalogo e indice tariffe nel template e scrive dist/.

Non tocca la rete: prende quello che c'e' in data/ e produce il sito. Puo'
girare in locale (`python scripts/build.py`) o dentro GitHub Actions subito
dopo fetch_prices.py.
"""
import json, pathlib, shutil, sys

ROOT   = pathlib.Path(__file__).resolve().parent.parent
DATA   = ROOT / 'data'
PUBLIC = ROOT / 'public'
DIST   = ROOT / 'dist'

# ── l'indirizzo pubblico del sito: cambialo quando avrai il tuo dominio ────
SITE = 'https://efficiency-life.com'

# ── monetizzazione: tre interruttori, tutti spenti finche' non li accendi ──
#
# TP_MARKER  il tuo ID partner Travelpayouts (app.travelpayouts.com, in alto a
#            destra sotto il nome account). Vuoto = nessun link affiliato: il
#            sito resta uno strumento di ricerca e manda l'utente diretto.
# TP_LINK    il formato di redirect, letto da un link vero generato dal
#            pannello. I segnaposto {marker} {trs} {p} {campaign} {url}
#            vengono riempiti dal sito.
# TP_P_*     il codice del singolo programma. Se manca, quel pulsante manda
#            l'utente diretto invece che dal redirect: il marker viaggia
#            comunque come parametro sulla pagina di destinazione.
# ADS_CLIENT il codice editore AdSense (ca-pub-...). Vuoto = nessuno script di
#            terze parti entra nella pagina e il banner cookie non compare.
# ADS_SLOT   l'identificatore dell'unita' pubblicitaria responsive.
TP_MARKER    = '772942'          # ID partner
TP_TRS       = '569809'          # progetto "Efficiencylife-flight"
TP_CAMPAIGN  = '100'
TP_LINK      = 'https://tp.media/r?campaign_id={campaign}&marker={marker}&p={p}&trs={trs}&u={url}'
# 3.09.2026 — il redirect tp.media/r risponde "Forbidden" per questo account,
# anche con un indirizzo generato dal pannello: i deep link non sono ancora
# abilitati. Finche' restano vuoti, i pulsanti vanno diretti su Aviasales con
# ?marker=772942 attaccato, che e' l'altra via di attribuzione. Rimetti '4114'
# quando l'assistenza sblocca i deep link.
TP_P_FLIGHT  = ''                # Aviasales (era 4114)
TP_P_HOTEL   = ''                # codice programma alloggi, quando ce ne sara' uno
# Hotellook ha chiuso il 20 ottobre 2025 e con lui l'unico motore alberghi del
# circuito. Finche' questa riga e' vuota il pulsante alloggio non compare: un
# pulsante che manda traffico senza incassare e' peggio di nessun pulsante.
# Quando ti iscrivi a un programma della categoria "Hotels & Accommodation",
# incolla qui il suo formato di ricerca con i segnaposto {city} {in} {out}
# {cur} {marker}.
TP_HOTEL_URL = ''

# Attivita' ed esperienze — Klook. La sua ricerca accetta il nome della citta'
# in chiaro, quindi un solo formato copre tutte le destinazioni.
TP_P_ACT     = ''                # Klook (era 4110): programma non ancora
TP_C_ACT     = '137'             # approvato, e il redirect e' comunque bloccato
TP_ACT_URL   = 'https://www.klook.com/search/result/?query={city}&search_scope=main_search'
# Travelpayouts Drive — lo script con cui il circuito verifica il sito. Vive
# dietro il banner di consenso insieme alla pubblicita': si carica solo dopo un
# si' esplicito. Svuota questa riga per toglierlo del tutto.
TP_DRIVE_URL = 'https://emrldtp.com/NTY5ODA5.js?t=569809'

ADS_CLIENT = ''
ADS_SLOT   = ''


DESC = ("Efficiency Life Flight ordina migliaia di tariffe aeree reali per chilometri "
        "per euro invece che per prezzo: scegli l'aeroporto di partenza, la destinazione "
        "la trova il motore.")
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' fill='%2303070E'/%3E"
           "%3Cpath d='M16 6 L26 25 L16 20 L6 25 Z' fill='%232E8DFF'/%3E%3C/svg%3E")


def main() -> int:
    tpl = (ROOT / 'src' / 'app.html').read_text()
    cat = (DATA / 'catalog.json').read_text()
    idx = (DATA / 'index.json').read_text()
    wld = (DATA / 'world.json').read_text()
    i18 = (ROOT / 'src' / 'i18n.js').read_text()

    for name, blob in (('catalog.json', cat), ('index.json', idx),
                       ('world.json', wld), ('i18n.js', i18)):
        if '</script' in blob.lower():
            sys.exit(f'{name} contiene un tag di chiusura script: mi fermo.')

    body = (tpl.replace('__CATALOG__', cat).replace('__DEALS__', idx)
               .replace('__WORLD__', wld).replace('__I18N__', i18)
               .replace('__TP_MARKER__', TP_MARKER).replace('__TP_LINK__', TP_LINK)
               .replace('__TP_TRS__', TP_TRS).replace('__TP_CAMPAIGN__', TP_CAMPAIGN)
               .replace('__TP_P_FLIGHT__', TP_P_FLIGHT).replace('__TP_P_HOTEL__', TP_P_HOTEL)
               .replace('__TP_HOTEL_URL__', TP_HOTEL_URL)
               .replace('__TP_P_ACT__', TP_P_ACT).replace('__TP_C_ACT__', TP_C_ACT)
               .replace('__TP_ACT_URL__', TP_ACT_URL)
               .replace('__TP_DRIVE_URL__', TP_DRIVE_URL)
               .replace('__ADS_CLIENT__', ADS_CLIENT).replace('__ADS_SLOT__', ADS_SLOT))
    for ph in ('__CATALOG__', '__DEALS__', '__WORLD__', '__I18N__',
               '__TP_MARKER__', '__TP_LINK__', '__TP_TRS__', '__TP_CAMPAIGN__',
               '__TP_P_FLIGHT__', '__TP_P_HOTEL__', '__TP_HOTEL_URL__',
               '__TP_P_ACT__', '__TP_C_ACT__', '__TP_ACT_URL__',
               '__TP_DRIVE_URL__', '__ADS_CLIENT__', '__ADS_SLOT__'):
        if ph in body:
            sys.exit(f'segnaposto {ph} non sostituito nel template.')

    head = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Efficiency Life Flight</title>
<meta name="description" content="{DESC}">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#EDF2F8" media="(prefers-color-scheme: light)">
<meta name="color-scheme" content="dark light">
<link rel="canonical" href="{SITE}/">
<link rel="icon" href="{FAVICON}">
<link rel="apple-touch-icon" href="{FAVICON}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Efficiency Life">
<meta property="og:title" content="Efficiency Life Flight">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="{SITE}/">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:locale" content="it_IT">
<meta property="og:locale:alternate" content="en_GB">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Efficiency Life Flight">
<meta name="twitter:description" content="{DESC}">
<meta name="twitter:image" content="{SITE}/og.png">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"WebApplication","name":"Efficiency Life Flight",
"applicationCategory":"TravelApplication","operatingSystem":"Any","url":"{SITE}/",
"description":"{DESC}","offers":{{"@type":"Offer","price":"0","priceCurrency":"EUR"}},
"isPartOf":{{"@type":"WebSite","name":"Efficiency Life","url":"{SITE}/"}}}}
</script>
<style>html{{color-scheme:dark}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
"""

    full = head + body.split('\n', 1)[1] + '\n</body>\n</html>\n'
    full = full.replace('<link rel="preconnect"', '</head>\n<body>\n<link rel="preconnect"', 1)

    DIST.mkdir(exist_ok=True)
    (DIST / 'index.html').write_text(full)
    for f in PUBLIC.iterdir():
        if f.is_file():
            shutil.copy2(f, DIST / f.name)

    d = json.loads(idx)
    print(f"dist/index.html · {len(full):,} byte · {len(d['deals']):,} tariffe "
          f"· {len(d['counts'])} origini · rilevate il {d['observed']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
