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
SITE = 'https://efficiencylife-flight.netlify.app'

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

    for name, blob in (('catalog.json', cat), ('index.json', idx)):
        if '</script' in blob.lower():
            sys.exit(f'{name} contiene un tag di chiusura script: mi fermo.')

    body = tpl.replace('__CATALOG__', cat).replace('__DEALS__', idx)
    if '__CATALOG__' in body or '__DEALS__' in body:
        sys.exit('segnaposto non sostituiti nel template.')

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
