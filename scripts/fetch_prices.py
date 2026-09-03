#!/usr/bin/env python3
"""EFFICIENCY LIFE — FLIGHT · raccolta notturna delle tariffe.

Interroga la cache prezzi Travelpayouts/Aviasales per ogni aeroporto di partenza
in data/origins.json, tiene solo i voli diretti andata e ritorno, e riscrive
data/index.json — l'indice che il sito incorpora.

Gira su GitHub Actions, dove la rete e' libera. Il token arriva dalla variabile
d'ambiente TP_TOKEN (segreto del repository), non e' mai scritto in un file.

Se una notte l'API non risponde, lo script NON sovrascrive l'indice esistente:
meglio dati di ieri che una pagina vuota.
"""
from __future__ import annotations
import json, os, sys, time, pathlib, datetime
from concurrent.futures import ThreadPoolExecutor
import urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'

TOKEN = os.environ.get('TP_TOKEN', '').strip()
if not TOKEN:
    sys.exit('TP_TOKEN mancante: aggiungilo nei Secrets del repository.')

API   = 'https://api.travelpayouts.com/aviasales/v3/get_latest_prices'
CITIES   = 'https://api.travelpayouts.com/data/en/cities.json'
AIRPORTS = 'https://api.travelpayouts.com/data/en/airports.json'

MIN_NIGHTS, MAX_NIGHTS = 2, 30      # esclude same-day e soggiorni assurdi
MIN_PRICE  = 10                     # sotto i 10 EUR sono errori di prezzo
PER_ORIGIN = 60                     # destinazioni tenute per aeroporto
WORKERS    = 6                      # richieste in parallelo: gentile con l'API


def get(url: str, tries: int = 3, timeout: int = 45):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'efficiency-life-flight/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:                      # rete, 5xx, rate limit
            last = e
            time.sleep(2 * (n + 1))
    raise RuntimeError(f'{url.split("?")[0]} non raggiungibile: {last}')


def fetch_origin(iata: str):
    url = (f'{API}?origin={iata}&currency=eur&period_type=year&group_by=directions'
           f'&one_way=false&limit=1000&token={TOKEN}')
    try:
        j = get(url)
    except Exception as e:
        print(f'  ! {iata}: {e}', flush=True)
        return iata, []

    rows = []
    for x in j.get('data') or []:
        if x.get('number_of_changes') != 0:   continue   # solo diretti
        if not x.get('return_at') and not x.get('return_date'): continue
        if not x.get('actual'):               continue
        price, dist = x.get('value') or 0, x.get('distance') or 0
        if price < MIN_PRICE or dist <= 0:    continue
        dep = (x.get('depart_date') or '')[:10]
        ret = (x.get('return_date') or '')[:10]
        if not (dep and ret):                 continue
        try:
            d0 = datetime.date.fromisoformat(dep)
            d1 = datetime.date.fromisoformat(ret)
        except ValueError:                    continue
        nights = (d1 - d0).days
        if not (MIN_NIGHTS <= nights <= MAX_NIGHTS): continue
        rows.append({'o': iata, 'd': x['destination'], 'p': int(round(price)),
                     'dep': dep, 'ret': ret, 'dur': int(x.get('duration') or 0),
                     'km': int(dist), 'n': nights, 's': 'tp'})

    # una riga per destinazione, la piu' economica; poi le migliori per km/euro
    best = {}
    for r in rows:
        k = r['d']
        if k not in best or r['p'] < best[k]['p']:
            best[k] = r
    out = sorted(best.values(), key=lambda r: -(r['km'] * 2 / r['p']))[:PER_ORIGIN]
    print(f'  {iata}: {len(out)} rotte', flush=True)
    return iata, out


def main() -> int:
    origins = json.loads((DATA / 'origins.json').read_text())
    catalog = json.loads((DATA / 'catalog.json').read_text())
    print(f'Interrogo {len(origins)} aeroporti di partenza…', flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(fetch_origin, origins))

    deals, counts = [], {}
    for iata, rows in results:
        if rows:
            deals += rows
            counts[iata] = len(rows)

    ok = len(counts)
    if ok < len(origins) * 0.5 or len(deals) < 500:
        print(f'ABORT: solo {ok}/{len(origins)} origini e {len(deals)} tariffe. '
              f'Tengo l\'indice precedente.', file=sys.stderr)
        return 1

    # anagrafica luoghi: nome, paese, coordinate per ogni codice citato
    places = {}
    try:
        for src in (AIRPORTS, CITIES):
            for p in get(src):
                c, co = p.get('code'), p.get('coordinates') or {}
                if c and co.get('lat') is not None:
                    places[c] = {'n': (p.get('name') or c).replace('|', ' '),
                                 'k': p.get('country_code') or '',
                                 'la': round(float(co['lat']), 2),
                                 'lo': round(float(co['lon']), 2)}
    except Exception as e:
        print(f'! anagrafica luoghi non scaricata ({e}); uso quella esistente', file=sys.stderr)
        places = json.loads((DATA / 'index.json').read_text()).get('places', {})

    for a in catalog['airports']:                     # gli scali del catalogo non mancano mai
        places.setdefault(a['i'], {'n': a['c'], 'k': a['k'], 'la': a['la'], 'lo': a['lo']})

    deals = [r for r in deals if r['d'] in places and r['o'] in places]
    used  = {r['o'] for r in deals} | {r['d'] for r in deals} | {a['i'] for a in catalog['airports']}
    places = {k: v for k, v in places.items() if k in used}
    counts = {}
    for r in deals:
        counts[r['o']] = counts.get(r['o'], 0) + 1

    out = {'observed': datetime.date.today().isoformat(),
           'sources': {'tp': 'travelpayouts/aviasales · get_latest_prices'},
           'places': places, 'deals': deals, 'counts': counts}
    (DATA / 'index.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))

    dest = len({r['d'] for r in deals})
    paesi = len({places[r['d']]['k'] for r in deals})
    print(f'\nOK · {len(deals)} tariffe · {len(counts)} origini · {dest} destinazioni · {paesi} paesi')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
