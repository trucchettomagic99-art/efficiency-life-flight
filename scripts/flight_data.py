"""Validation and storage shared by collection, migration and build (stdlib only)."""
from __future__ import annotations
import datetime as dt
import json
import math
import os
import pathlib
import re
from collections import Counter
try:
    from location_authority import (
        is_commercial_airport,
        is_city_or_metro,
        get_clean_city_name,
        get_clean_airport_name,
    )
except ImportError:
    from scripts.location_authority import (
        is_commercial_airport,
        is_city_or_metro,
        get_clean_city_name,
        get_clean_airport_name,
    )

SCHEMA = 2
MAX_AGE = 7
IATA = re.compile(r'^[A-Z]{3}$')

def dump(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def read(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default

def number(value):
    if isinstance(value, bool):
        raise ValueError('boolean_number')
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('nonfinite_number')
    return n

def date(value):
    return dt.date.fromisoformat(str(value)[:10])

def country(code, value):
    # Provider's NY for Ercan is not an ISO country code.
    if code == 'ECN' and value == 'NY': return 'CY'
    if code == 'SUI' and value == 'AB': return 'GE'
    return value

def valid_place(code, p, countries):
    try:
        return bool(IATA.fullmatch(code) and p['k'] in countries and
                    -90 <= number(p['la']) <= 90 and -180 <= number(p['lo']) <= 180)
    except (KeyError, TypeError, ValueError):
        return False

def clean_catalog(catalog):
    catalog = json.loads(json.dumps(catalog))
    # Valid countries/territories already appearing in fares but missing in
    # the original UI catalog. Preserve their offers by completing the catalog.
    additions = [('TL','Timor Est','Timor-Leste','Asia'),
                 ('SH',"Sant’Elena",'Saint Helena','Africa'),
                 ('EH','Sahara Occidentale','Western Sahara','Africa'),
                 ('CX','Isola di Natale','Christmas Island','Oceania')]
    existing = {c['k'] for c in catalog['countries']}
    for k, it, en, g in additions:
        if k not in existing:
            catalog['countries'].append({'k':k,'it':it,'en':en,'g':g,'r':len(catalog['countries'])+1,'a':[]})
    countries = {c['k'] for c in catalog['countries']}
    best, issues = {}, Counter()
    for original in catalog['airports']:
        a = dict(original)
        a['i'] = str(a.get('i', '')).strip().upper()
        # Solo veri aeroporti commerciali di linea possono restare nel catalogo pubblico.
        if not is_commercial_airport(a['i']):
            issues['non_commercial_airport'] += 1
            continue
        a['k'] = country(a['i'], a.get('k'))
        if not valid_place(a['i'], a, countries):
            issues['invalid_airport'] += 1
            continue
        clean_c = get_clean_city_name(a['i'], a.get('c'))
        clean_n = get_clean_airport_name(a['i'], a.get('n'))
        if clean_c: a['c'] = clean_c
        if clean_n: a['n'] = clean_n
        # Preserve the existing UI's BSL choice (Swiss airport identity).
        old = best.get(a['i'])
        if old:
            issues['duplicate_airport'] += 1
        if not old or (a['i'] == 'BSL' and a['k'] == 'CH') or (a['k'] == old['k'] and a.get('r', 999) < old.get('r', 999)):
            best[a['i']] = a
    out = {'airports': list(best.values()), 'countries': []}
    for c in catalog['countries']:
        row = dict(c)
        row['a'] = list(dict.fromkeys(i for i in c['a'] if i in best and best[i]['k'] == c['k']))
        row['a'] += [i for i, a in best.items() if a['k'] == c['k'] and i not in row['a']]
        out['countries'].append(row)
    return out, issues

def places_from(catalog, previous, airports=(), cities=()):
    countries = {c['k'] for c in catalog['countries']}
    places = {}
    for code, original in previous.items():
        p = dict(original); p['k'] = country(code, p.get('k'))
        if valid_place(code, p, countries):
            t = p.get('t', 'airport')
            if is_city_or_metro(code) or not is_commercial_airport(code):
                t = 'city'
            p['t'] = t
            clean_name = get_clean_city_name(code, p.get('n'))
            if clean_name: p['n'] = clean_name
            places[code] = p
    # City metadata is useful for names, but an exact airport record must win.
    # Keep the type so city aggregates (LON/PAR/TYO...) cannot masquerade as
    # airport-specific direct fares in the public index.
    for kind, items in (('city', cities), ('airport', airports)):
        for item in items:
            code = item.get('code', '')
            coord = item.get('coordinates') or {}
            raw_name = str(item.get('name') or code).replace('|', ' ')
            clean_name = get_clean_city_name(code, raw_name)
            t = kind
            if is_city_or_metro(code) or not is_commercial_airport(code):
                t = 'city'
            elif is_commercial_airport(code):
                t = 'airport'
            p = {'n': clean_name,
                 'k': country(code, item.get('country_code')),
                 'la': coord.get('lat'), 'lo': coord.get('lon'), 't': t}
            if valid_place(code, p, countries):
                p['la'], p['lo'] = float(p['la']), float(p['lo'])
                places[code] = p
    for a in catalog['airports']:
        if is_commercial_airport(a['i']):
            clean_name = get_clean_city_name(a['i'], a['c'])
            places[a['i']] = {'n': clean_name, 'k': a['k'], 'la': a['la'], 'lo': a['lo'], 't':'airport'}
    return places

def expand_catalog(catalog, places, airports, destinations):
    """Only destinations proven to be commercial airports may become new selectable origins."""
    known = {a['i'] for a in catalog['airports']}
    countries = {c['k']: c for c in catalog['countries']}
    for a in airports:
        code = a.get('code')
        if code in known or code not in destinations or code not in places:
            continue
        if a.get('iata_type') not in (None, 'airport'):
            continue
        if a.get('flightable') is False or not is_commercial_airport(code):
            continue
        p = places[code]
        if p['k'] not in countries or p.get('t') != 'airport':
            continue
        clean_name = get_clean_airport_name(code, a.get('name') or code)
        clean_city = get_clean_city_name(code, p['n'])
        catalog['airports'].append({'i': code, 'n': clean_name, 'c': clean_city,
                                   'k': p['k'], 'la': p['la'], 'lo': p['lo'],
                                   'tz': a.get('time_zone') or '', 'r': 999})
        countries[p['k']]['a'].append(code)
        known.add(code)
    return catalog

def distance(a, b):
    la, lb = math.radians(float(a['la'])), math.radians(float(b['la']))
    dl = math.radians(float(b['lo']) - float(a['lo']))
    h = math.sin((lb-la)/2)**2 + math.cos(la)*math.cos(lb)*math.sin(dl/2)**2
    return max(1, round(6371.0088 * 2 * math.asin(min(1, math.sqrt(max(0, h))))))

def validate(row, places, today):
    r = dict(row)
    if r.get('o') == r.get('d'):
        raise ValueError('same_place')
    if r.get('o') not in places or r.get('d') not in places:
        raise ValueError('unknown_place')
    if places[r['o']].get('t') in ('city', 'metro') or places[r['d']].get('t') in ('city', 'metro'):
        raise ValueError('city_aggregate')
    if not is_commercial_airport(r['o']) or not is_commercial_airport(r['d']):
        raise ValueError('city_aggregate')
    dep, ret, obs = date(r['dep']), date(r['ret']), date(r['obs'])
    if dep < today or dep > today + dt.timedelta(days=366):
        raise ValueError('departure_outside_horizon')
    if not 1 <= (ret-dep).days <= 60:
        raise ValueError('invalid_stay')
    if not 0 <= (today-obs).days <= MAX_AGE:
        raise ValueError('stale_observation')
    r['p'] = round(number(r['p']), 2)
    if r['p'] <= 0:
        raise ValueError('invalid_price')
    r['km'] = round(number(r['km']))
    r['dur'] = round(number(r.get('dur', 0)))
    if not 0 < r['km'] <= 20100 or not 0 <= r['dur'] <= 5760:
        raise ValueError('invalid_distance_duration')
    r.update(dep=dep.isoformat(), ret=ret.isoformat(), obs=obs.isoformat(), n=(ret-dep).days)
    # Low prices are possible, but are too error-prone to influence a public ranking.
    # Preserve them for later re-validation while keeping them quarantined.
    if r['p'] < 10:
        r['quality'] = 'low_price_review'
    r.pop('sc', None); r.pop('x', None)
    return r

def normalize(x, origin, endpoint, places, today):
    if not isinstance(x, dict):
        raise ValueError('invalid_row')
    if endpoint == 'dates':
        # Missing return-transfer information must not be assumed to mean direct.
        if type(x.get('transfers')) is not int or x['transfers'] != 0 or type(x.get('return_transfers')) is not int or x['return_transfers'] != 0:
            raise ValueError('not_confirmed_direct_roundtrip')
        o, d = x.get('origin_airport') or x.get('origin'), x.get('destination_airport') or x.get('destination')
        if o != origin:
            raise ValueError('different_origin_airport')
        if o not in places or d not in places:
            raise ValueError('unknown_place')
        r = {'o': o, 'd': d, 'p': x.get('price'), 'dep': x.get('departure_at'),
             'ret': x.get('return_at'), 'dur': x.get('duration') or 0,
             'km': distance(places[o], places[d]), 'distance_source': 'great_circle',
             'direct_check': 'both_legs'}
    else:
        if type(x.get('number_of_changes')) is not int or x['number_of_changes'] != 0 or x.get('actual') is not True:
            raise ValueError('not_actual_direct')
        if x.get('origin') != origin:
            raise ValueError('different_origin')
        d = x.get('destination')
        r = {'o': origin, 'd': d, 'p': x.get('value'),
             'dep': x.get('depart_date'), 'ret': x.get('return_date'),
             'dur': x.get('duration') or 0, 'km': x.get('distance') or 0,
             'direct_check': 'provider_aggregate'}
        if number(r['km']) <= 0 and origin in places and r['d'] in places:
            r['km'] = distance(places[origin], places[r['d']]); r['distance_source'] = 'great_circle'
        found = x.get('found_at')
        if found:
            if not 0 <= (today-date(found)).days <= MAX_AGE:
                raise ValueError('stale_source')
            r['found_at'] = str(found)
    r.update(obs=today.isoformat(), s='tp', endpoint=endpoint)
    return validate(r, places, today)

def key(r):
    return r['o'], r['d'], r['dep'], r['ret']

def clean_rows(rows, places, today, observed=None):
    best, issues = {}, Counter()
    for original in rows:
        try:
            row = dict(original)
            row.setdefault('obs', observed)
            r = validate(row, places, today)
            k = key(r); old = best.get(k)
            # A newer price replaces an older cheap price even when it increased.
            if not old or (r['obs'], r.get('endpoint') == 'dates', -r['p']) > (old['obs'], old.get('endpoint') == 'dates', -old['p']):
                best[k] = r
            if old:
                issues['duplicate_offer'] += 1
        except (ValueError, TypeError, KeyError, OverflowError) as e:
            issues[str(e) if isinstance(e, ValueError) else 'malformed_row'] += 1
    return sorted(best.values(), key=key), issues

# Windows non permette file che si chiamino come i suoi device storici, con
# qualunque estensione: PRN.json e' un nome illegale. PRN e' Pristina, e il
# file esiste davvero. Finche' il nome dipendeva dal sistema operativo, Linux
# in CI scriveva PRN.json e Windows PRN-shard.json, e i due si rincorrevano a
# ogni commit; peggio, un `git checkout` su Windows falliva proprio su quel
# percorso. Il suffisso ora e' incondizionato: un nome solo, ovunque.
RISERVATI = {'CON', 'PRN', 'AUX', 'NUL',
             *(f'COM{n}' for n in range(1, 10)), *(f'LPT{n}' for n in range(1, 10))}

def nome_shard(origin):
    return f'{origin}-shard.json' if origin.upper() in RISERVATI else f'{origin}.json'

def publishable(rows):
    """Rows safe to influence the public model, history and search results."""
    return [r for r in rows if r.get('quality') != 'low_price_review']

def representatives(rows):
    best = {}
    for r in publishable(rows):
        k = r['o'], r['d']
        if k not in best or r['p'] < best[k]['p']:
            best[k] = r
    return sorted(best.values(), key=key)

# Quanto ci fidiamo che il volo sia davvero diretto, e da li' quale riga vince.
FIDUCIA = {'both_legs': 2, 'provider_aggregate': 1}

# Due scali sono della stessa area urbana se stanno nello stesso paese e a
# meno di questa distanza. Cento chilometri copre ogni coppia vera che il
# fornitore confonde — Bruxelles/Charleroi 46, Città del Messico MEX/NLU 33,
# Milano MXP/BGY 80 — e non arriva a unire due citta' diverse abbastanza da
# avere voli propri. Non e' una soglia delicata: allargarla non cancella
# nulla di verificato, perche' due righe `both_legs` restano comunque
# entrambe (vedi collapse_city_twins).
GEMELLI_KM = 100

def stessa_area(a, b, places):
    """Se due aeroporti servono la stessa citta', dedotto dai dati che abbiamo.

    Fino al 14 settembre 2026 questo giudizio veniva da una tabella scritta a
    mano (`CITY_TO_COMMERCIAL_AIRPORTS`): funzionava per le citta' elencate e
    falliva in silenzio per tutte le altre. Città del Messico non c'era, e
    MEX/NLU — trentatre chilometri — passavano per destinazioni diverse,
    lasciando sette doppioni nell'indice.

    La distanza fra due punti e il paese li abbiamo gia' per ogni aeroporto,
    per tutti, senza doverli elencare. Il nome della citta' resta come secondo
    indizio: due scali con lo stesso nome sono la stessa area anche se il
    fornitore li mette un po' piu' lontani del dovuto.
    """
    pa, pb = places.get(a) or {}, places.get(b) or {}
    if not pa or not pb or pa.get('k') != pb.get('k'):
        return False
    if pa.get('n') and pa.get('n') == pb.get('n'):
        return True
    try:
        return distance(pa, pb) <= GEMELLI_KM
    except (TypeError, ValueError, KeyError):
        return False

def collapse_city_twins(rows, places):
    """Toglie la stessa tariffa quando il fornitore la attribuisce a due aeroporti.

    L'11 settembre la classifica da Bologna mostrava due volte Bruxelles allo
    stesso prezzo, con le stesse date e la stessa durata al minuto: una riga
    verso BRU (Zaventem) e una verso CRL (Charleroi), che distano
    quarantasei chilometri. Non erano due voli: era **lo stesso volo** visto da
    due interrogazioni diverse. L'endpoint `latest` restituisce una tariffa per
    citta' e la attribuisce all'aeroporto principale anche quando il volo parte
    dal secondario; l'endpoint `dates` restituisce lo stesso volo con
    l'aeroporto giusto, verificato tratta per tratta.

    Da qui la regola, in tre righe:

    1. Si guardano solo le righe che coincidono in tutto — stessa origine,
       stesso prezzo, stessa partenza, stesso rientro, stessa durata al minuto
       — e che vanno a due scali della stessa area urbana. Tutto il resto non
       si tocca: la durata identica e' il filtro che distingue «lo stesso volo
       raccontato due volte» da «due voli diversi lo stesso giorno».
    2. Se almeno una riga e' verificata tratta per tratta (`both_legs`) si
       tengono **tutte** le righe verificate, una per aeroporto. Heathrow e
       Gatwick sono due aeroporti veri: se entrambi risultano verificati non
       sta a noi decidere che uno dei due non esiste.
    3. Se nessuna e' verificata — sono tutti aggregati del fornitore, che per
       sua natura attribuisce la tariffa allo scalo principale — allora e' un
       doppione e ne resta una sola, la piu' affidabile.
    """
    gruppi = {}
    for r in rows:
        gruppi.setdefault((r['o'], (places.get(r['d']) or {}).get('k'),
                           r['p'], r['dep'], r['ret'], r['dur']), []).append(r)

    # A parita' di tutto, quale riga rappresenta l'aeroporto: prima la piu'
    # verificata, poi l'endpoint per date, poi il codice IATA — perche' due
    # esecuzioni sugli stessi dati devono produrre lo stesso indice.
    preferenza = lambda r: (FIDUCIA.get(r.get('direct_check'), 0),
                            r.get('endpoint') == 'dates', r['d'])

    tenute = []
    for insieme in gruppi.values():
        if len(insieme) == 1:
            tenute.append(insieme[0])
            continue

        # una riga per aeroporto, poi si raccolgono gli aeroporti vicini fra
        # loro: il gruppo puo' contenere scali di aree urbane diverse che per
        # caso hanno lo stesso prezzo nello stesso paese, e quelli non
        # c'entrano niente l'uno con l'altro.
        per_scalo = {}
        for r in insieme:
            if r['d'] not in per_scalo or preferenza(r) > preferenza(per_scalo[r['d']]):
                per_scalo[r['d']] = r

        aree = []
        for iata in sorted(per_scalo):
            for area in aree:
                if any(stessa_area(iata, altro, places) for altro in area):
                    area.append(iata)
                    break
            else:
                aree.append([iata])

        for area in aree:
            righe = [per_scalo[i] for i in area]
            if len(righe) == 1:
                tenute.append(righe[0])
                continue
            massima = max(FIDUCIA.get(r.get('direct_check'), 0) for r in righe)
            if massima >= FIDUCIA['both_legs']:
                # aeroporti distinti, tutti verificati: restano tutti
                tenute.extend(r for r in righe
                              if FIDUCIA.get(r.get('direct_check'), 0) == massima)
            else:
                # nessuno verificato a livello di aeroporto: e' un doppione
                tenute.append(max(righe, key=preferenza))

    return sorted(tenute, key=key)

def public_rows(rows):
    # Keep every distinct valid date pair, except quarantined observations.
    return [{k: r[k] for k in ('o','d','p','dep','ret','dur','km','n','obs','s','x','sc','hb') if k in r}
            for r in publishable(rows)]

def migrate(data, today):
    old = read(data / 'index.json')
    catalog, issues = clean_catalog(read(data / 'catalog.json'))
    places = places_from(catalog, old['places'])
    rows, rejected = clean_rows(old['deals'], places, today, old['observed'])
    issues.update(rejected)
    reps = collapse_city_twins(representatives(rows), places)
    index = dict(old, places=places, deals=reps, counts=dict(Counter(r['o'] for r in reps)))
    # Cleaning never pretends that old prices have just been observed.
    dump(data / 'catalog.json', catalog)
    dump(data / 'origins.json', sorted(dict.fromkeys(a['i'] for a in catalog['airports'] if is_commercial_airport(a['i']))))
    dump(data / 'index.json', index)
    return {'kept':len(rows), 'issues':dict(issues), 'origins':len(read(data/'origins.json'))}
