"""Validation and storage shared by collection, migration and build (stdlib only)."""
from __future__ import annotations
import datetime as dt
import json
import math
import os
import pathlib
import re
from collections import Counter

SCHEMA = 2
MAX_AGE = 7
IATA = re.compile(r'^[A-Z]{3}$')

def dump(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    os.replace(tmp, path)

def read(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text())
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
        a['k'] = country(a['i'], a.get('k'))
        if not valid_place(a['i'], a, countries):
            issues['invalid_airport'] += 1
            continue
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
            places[code] = p
    # City metadata is useful for names, but an exact airport record must win.
    # Keep the type so city aggregates (LON/PAR/TYO...) cannot masquerade as
    # airport-specific direct fares in the public index.
    for kind, items in (('city', cities), ('airport', airports)):
        for item in items:
            code = item.get('code', '')
            coord = item.get('coordinates') or {}
            p = {'n': str(item.get('name') or code).replace('|', ' '),
                 'k': country(code, item.get('country_code')),
                 'la': coord.get('lat'), 'lo': coord.get('lon'), 't': kind}
            if valid_place(code, p, countries):
                p['la'], p['lo'] = float(p['la']), float(p['lo'])
                places[code] = p
    for a in catalog['airports']:
        places[a['i']] = {'n': a['c'], 'k': a['k'], 'la': a['la'], 'lo': a['lo'], 't':'airport'}
    return places

def expand_catalog(catalog, places, airports, destinations):
    """Only destinations proven to be airports may become new selectable origins."""
    known = {a['i'] for a in catalog['airports']}
    countries = {c['k']: c for c in catalog['countries']}
    for a in airports:
        code = a.get('code')
        if code in known or code not in destinations or code not in places:
            continue
        if a.get('iata_type') not in (None, 'airport'):
            continue
        p = places[code]
        if p['k'] not in countries:
            continue
        catalog['airports'].append({'i': code, 'n': a.get('name') or code, 'c': p['n'],
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
    if places[r['o']].get('t') == 'city' or places[r['d']].get('t') == 'city':
        raise ValueError('city_aggregate')
    dep, ret, obs = date(r['dep']), date(r['ret']), date(r['obs'])
    if dep < today or dep > today + dt.timedelta(days=366):
        raise ValueError('departure_outside_horizon')
    if not 1 <= (ret-dep).days <= 30:
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

def public_rows(rows):
    # Keep every distinct valid date pair, except quarantined observations.
    return [{k: r[k] for k in ('o','d','p','dep','ret','dur','km','n','obs','s','x','sc') if k in r}
            for r in publishable(rows)]

def migrate(data, today):
    old = read(data / 'index.json')
    catalog, issues = clean_catalog(read(data / 'catalog.json'))
    places = places_from(catalog, old['places'])
    rows, rejected = clean_rows(old['deals'], places, today, old['observed'])
    issues.update(rejected)
    reps = representatives(rows)
    index = dict(old, places=places, deals=reps, counts=dict(Counter(r['o'] for r in reps)))
    # Cleaning never pretends that old prices have just been observed.
    dump(data / 'catalog.json', catalog)
    dump(data / 'origins.json', list(dict.fromkeys([*read(data/'origins.json', []), *[a['i'] for a in catalog['airports']]])))
    dump(data / 'index.json', index)
    return {'kept':len(rows), 'issues':dict(issues), 'origins':len(read(data/'origins.json'))}
