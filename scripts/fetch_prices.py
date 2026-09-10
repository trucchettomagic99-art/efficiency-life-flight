#!/usr/bin/env python3
"""Bounded, resumable collection of observed direct round-trip fares.

No live Search API is used. Defaults query every catalog origin, then collect
multiple date pairs from prices_for_dates. Token is only sent in a header.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import email.utils
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from flight_data import (SCHEMA, clean_catalog, clean_rows, dump, expand_catalog,
                         migrate, normalize, places_from, publishable, read,
                         representatives)

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://api.travelpayouts.com/'
METHODS = {'latest':'aviasales/v3/get_latest_prices', 'dates':'aviasales/v3/prices_for_dates'}
PAGE_SIZE = 1000

class BudgetExpired(Exception):
    pass

class FatalAPIError(Exception):
    pass

class RateLimiter:
    """Paced requests, shared across all worker threads for each endpoint."""
    def __init__(self, rpm, clock=time.monotonic, sleep=time.sleep):
        self.interval = 60 / rpm
        self.clock, self.sleep = clock, sleep
        self.next = 0
        self.lock = threading.Lock()

    def defer(self, seconds):
        with self.lock:
            self.next = max(self.next, self.clock() + max(0, seconds))

    def acquire(self, deadline):
        while True:
            with self.lock:
                now = self.clock()
                if now >= deadline:
                    raise BudgetExpired()
                delay = max(0, self.next-now)
                if not delay:
                    self.next = now+self.interval
                    return
            self.sleep(min(delay, 1, max(0, deadline-now)))

def retry_delay(headers):
    try:
        return max(1, float(headers.get('Retry-After') or headers.get('X-Rate-Limit-Reset') or 60))
    except ValueError:
        try:
            return max(1, email.utils.parsedate_to_datetime(headers['Retry-After']).timestamp()-time.time())
        except (KeyError, ValueError, TypeError):
            return 60

class Client:
    def __init__(self, token, seconds):
        self.token = token
        self.deadline = time.monotonic()+seconds
        self.limits = {k: RateLimiter(n) for k,n in [('latest',240), ('dates',480), ('metadata',120)]}
        self.stats = Counter()
        self.lock = threading.Lock()
        self.fatal = False

    def get(self, method, params=None):
        kind = next((k for k,v in METHODS.items() if method == v), 'metadata')
        limiter = self.limits[kind]
        url = BASE+method+('?' + urllib.parse.urlencode(params) if params else '')
        for attempt in range(3):
            if self.fatal:
                raise FatalAPIError('API authentication rejected')
            limiter.acquire(self.deadline)
            try:
                req = urllib.request.Request(url, headers={'X-Access-Token':self.token,
                    'Accept-Encoding':'gzip', 'User-Agent':'efficiency-life-flight/2.0'})
                with self.lock:
                    self.stats[kind] += 1
                with urllib.request.urlopen(req, timeout=min(25, max(1, self.deadline-time.monotonic()))) as res:
                    raw = res.read()
                    if res.headers.get('Content-Encoding') == 'gzip':
                        raw = gzip.decompress(raw)
                    if res.headers.get('X-Rate-Limit-Remaining') == '0':
                        limiter.defer(retry_delay(res.headers))
                    result = json.loads(raw)
                if isinstance(result, dict) and result.get('success') is not True:
                    raise ValueError('upstream_unsuccessful_response')
                return result
            except urllib.error.HTTPError as e:
                with self.lock:
                    self.stats['http_'+str(e.code)] += 1
                if e.code in (401,403):
                    self.fatal = True
                    raise FatalAPIError('API authentication rejected') from None
                if e.code == 429:
                    limiter.defer(retry_delay(e.headers))
                elif e.code >= 500:
                    limiter.defer(2**attempt)
                else:
                    raise ValueError('upstream_http_'+str(e.code)) from None
            except (OSError, ValueError):
                limiter.defer(2**attempt)
        raise ValueError('upstream_retry_exhausted')

def collect(client, origin, endpoint, places, today, checkpoint, max_pages):
    signature = hashlib.sha256(json.dumps([SCHEMA, origin, endpoint, max_pages, today.isoformat()], sort_keys=True).encode()).hexdigest()[:20]
    path = checkpoint / (signature+'.json')
    saved = read(path, {})
    rows = saved.get('rows', [])
    issues = Counter(saved.get('issues', {}))
    seen_pages = set(saved.get('pages', []))
    start = saved.get('next_page', 1)
    if saved.get('complete'):
        return {'origin':origin, 'endpoint':endpoint, 'status':'ok', 'rows':rows, 'issues':dict(issues), 'resumed':True}
    try:
        for page in range(start, max_pages+1):
            params = {'origin':origin, 'currency':'eur', 'one_way':'false', 'limit':PAGE_SIZE, 'page':page}
            if endpoint == 'latest':
                params.update(period_type='year', group_by='directions')
            else:
                params.update(direct='true', unique='false', sorting='price')
            payload = client.get(METHODS[endpoint], params)
            raw = payload.get('data')
            if raw == {}:
                raw = []
            if not isinstance(raw, list):
                raise ValueError('upstream_invalid_data')
            fingerprint = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
            complete = not raw or len(raw) < PAGE_SIZE
            if fingerprint in seen_pages and raw:
                issues['repeated_page'] += 1
                return {'origin':origin,'endpoint':endpoint,'status':'partial','rows':rows,'issues':dict(issues)}
            seen_pages.add(fingerprint)
            for item in raw:
                try:
                    rows.append(normalize(item, origin, endpoint, places, today))
                except (ValueError, TypeError, KeyError, OverflowError) as e:
                    issues[str(e) if isinstance(e, ValueError) else 'malformed_row'] += 1
            dump(path, {'rows':rows,'issues':dict(issues),'pages':sorted(seen_pages), 'next_page':page+1,'complete':complete})
            if complete:
                return {'origin':origin,'endpoint':endpoint,'status':'ok','rows':rows,'issues':dict(issues)}
        issues['page_cap'] += 1
        status = 'partial'
    except BudgetExpired:
        status = 'partial' if rows else 'deferred'
    except FatalAPIError:
        raise
    except ValueError as e:
        issues[str(e)] += 1
        status = 'partial' if rows else 'error'
    return {'origin':origin,'endpoint':endpoint,'status':status,'rows':rows,'issues':dict(issues)}

def make_snapshot(old, archived, results, places, today):
    """Merge observations, preserving source dates. Expired data never resurrects."""
    previous = []
    for r in old['deals']:
        previous.append(dict(r, obs=r.get('obs',old['observed'])))
    previous.extend(archived)
    fresh = [r for result in results for r in result['rows']]
    rows, issues = clean_rows([*previous, *fresh], places, today)
    public = publishable(rows)
    reps = representatives(rows)
    prior, _ = clean_rows(previous, places, today)
    prior_reps = representatives(prior)
    attempted = [r for r in results if r['status'] != 'deferred']
    good = [r for r in attempted if r['status'] in ('ok','partial')]
    fresh_origins = {r['o'] for r in fresh}
    prior_origins = {r['o'] for r in prior_reps}
    if not attempted or len(good) < .8*len(attempted) or not fresh:
        raise ValueError('collection_unhealthy: previous index retained')
    if prior_origins and len(fresh_origins & prior_origins) < .6*len(prior_origins):
        raise ValueError('existing_origin_coverage_drop: previous index retained')
    if len(reps) < max(1, .6*len(prior_reps)):
        raise ValueError('route_coverage_drop: previous index retained')
    counts = dict(Counter(r['o'] for r in reps))
    used = {r['o'] for r in rows} | {r['d'] for r in rows}
    index = {'schema':SCHEMA, 'observed':today.isoformat(),
             'sources':{'tp':'travelpayouts/aviasales · observed cache'},
             'places':{k:v for k,v in places.items() if k in used or k in old['places']},
             'deals':reps,'counts':counts,'offer_count':len(public),
             'shards':{o:f'/data/origins/{o}.json' for o in counts}}
    return index, rows, issues

def should_query_origin(origin: str, schedule: dict, today: dt.date, active_in_counts: bool) -> bool:
    """Smart scheduling: daily for active/confirmed origins; staggered for persistent empty origins."""
    if active_in_counts:
        return True
    info = schedule.get(origin)
    if not info:
        return True  # New origin: explore immediately
    empty_streak = info.get('consecutive_empty', 0)
    last_queried = info.get('last_queried')
    if not last_queried:
        return True
    try:
        days_since = (today - dt.date.fromisoformat(last_queried)).days
    except (ValueError, TypeError):
        return True
    if empty_streak < 3:
        return True
    origin_num = int(hashlib.md5(origin.encode('utf-8')).hexdigest()[:6], 16)
    if empty_streak < 10:
        return (days_since >= 3 and (today.toordinal() + origin_num) % 3 == 0) or days_since >= 6
    return (days_since >= 7 and (today.toordinal() + origin_num) % 7 == 0) or days_since >= 12


def append_history(data, rows, today):
    path = data/'history'/f'{today:%Y-%m}.csv'
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    fresh = representatives([r for r in rows if r['obs'] == today.isoformat()])
    keys = {f"{today},{r['o']},{r['d']}" for r in fresh}
    lines = [ln for ln in lines if ','.join(ln.split(',')[:3]) not in keys]
    lines += [f"{today},{r['o']},{r['d']},{r['p']}" for r in fresh]
    path.parent.mkdir(exist_ok=True)
    path.write_text('\n'.join(dict.fromkeys(lines))+'\n', encoding='utf-8')

def write_airport_module(catalog):
    """Generate the exact airport allow-list consumed by the Cloudflare live API."""
    codes = sorted({a.get('i') for a in catalog.get('airports', [])
                    if isinstance(a.get('i'), str) and len(a['i']) == 3})
    target = ROOT/'functions'/'api'/'_airports.js'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('/* generated by scripts/fetch_prices.py; do not edit */\n'
                      'export const AIRPORT_CODES = new Set(' +
                      json.dumps(codes, separators=(',', ':')) + ');\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean-only', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    parser.add_argument('--max-seconds', type=int, default=1080)
    parser.add_argument('--workers', type=int, default=3, choices=range(1,7))
    parser.add_argument('--dates-pages', type=int, default=5)
    parser.add_argument('--latest-pages', type=int, default=2)
    parser.add_argument('--origin-limit', type=int, default=0)
    args = parser.parse_args()
    if args.max_seconds < 1 or args.dates_pages < 1 or args.latest_pages < 1 or args.origin_limit < 0:
        parser.error('positive budgets and page counts required')
    today = dt.datetime.now(dt.timezone.utc).date()
    data = args.data_dir
    if args.clean_only:
        print(json.dumps(migrate(data, today)))
        return 0
    token = ''.join(os.environ.get('TP_TOKEN','').split())
    if not token:
        parser.error('TP_TOKEN missing; use --clean-only for offline migration')
    client = Client(token, args.max_seconds)
    old = read(data/'index.json')
    catalog, catalog_issues = clean_catalog(read(data/'catalog.json'))
    airports, cities, routes = [], [], []
    metadata_errors = []
    for name in ('airports','cities','routes'):
        try:
            values = client.get('data/'+('en/' if name != 'routes' else '')+name+'.json')
            if not isinstance(values,list):
                raise ValueError('invalid_metadata')
            if name == 'airports': airports = values
            if name == 'cities': cities = values
            if name == 'routes': routes = values
        except (ValueError, BudgetExpired) as e:
            metadata_errors.append(name+':'+str(e))
    places = places_from(catalog, old['places'], airports, cities)
    catalog = expand_catalog(catalog, places, airports, {r['d'] for r in old['deals']})
    configured = list(dict.fromkeys([*read(data/'origins.json',[]), *[a['i'] for a in catalog['airports']]]))
    configured = [o for o in configured if o in places]
    direct_origins = {r.get('departure_airport_iata') for r in routes if r.get('transfers') == 0}
    origins = sorted(configured, key=lambda o:(o not in old['counts'], o not in direct_origins, o))
    schedule = read(data/'origin_schedule.json', {})
    origins = [o for o in origins if should_query_origin(o, schedule, today, o in old['counts'])]
    established = [o for o in origins if o in old['counts']]
    new = [o for o in origins if o not in old['counts']]
    if new:
        offset = today.toordinal()%len(new); new = new[offset:]+new[:offset]
    origins = established+new
    if args.origin_limit: origins = origins[:args.origin_limit]
    checkpoint = ROOT/'.cache'/'fares-v2'/today.isoformat()
    checkpoint.mkdir(parents=True, exist_ok=True)
    print(f'Collecting {len(origins)} origins; {args.max_seconds}s budget; latest + dates', flush=True)
    results = []
    for endpoint, pages in [('latest',args.latest_pages), ('dates',args.dates_pages)]:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(lambda o:collect(client,o,endpoint,places,today,checkpoint,pages), origins):
                results.append(result)
                if result['status'] != 'deferred':
                    cap_msg = f" [CAP REACHED: {pages} pages]" if result.get('issues', {}).get('page_cap') else ""
                    print(f"{endpoint} {result['origin']}: {result['status']} {len(result['rows'])} offers{cap_msg}", flush=True)
    archived = []
    for path in (data/'fares').glob('*.json'):
        archived.extend(read(path,{}).get('deals',[]))
    page_cap_origins = sorted({r['origin'] for r in results if r.get('issues', {}).get('page_cap')})
    report = {'date':today.isoformat(),'schema':SCHEMA,'configured_origins':len(configured),
              'queried_origins':len(origins),'requests':dict(client.stats),
              'catalog_issues':dict(catalog_issues),'metadata_errors':metadata_errors,
              'page_cap_origins':page_cap_origins,
              'endpoints':dict(Counter(r['endpoint']+':'+r['status'] for r in results)),
              'rejections':dict(sum((Counter(r['issues']) for r in results),Counter()))}
    if page_cap_origins:
        print(f"[PAGE_CAP] Pagination cap reached for {len(page_cap_origins)} origins: {', '.join(page_cap_origins[:20])}", flush=True)
    try:
        index, rows, issues = make_snapshot(old, archived, results, places, today)
    except ValueError as e:
        report['published'] = False; report['error'] = str(e)
        dump(ROOT/'.cache'/'collection-report.json',report)
        print(str(e))
        return 1
    public = publishable(rows)
    report.update(published=True, offers=len(public), archived_offers=len(rows),
                  quarantined_offers=len(rows)-len(public), routes=len(index['deals']),
                  covered_origins=len(index['counts']), merge_issues=dict(issues),
                  date_variants=len(public)-len(index['deals']))
    stage = ROOT/'.cache'/'collection-stage'
    if stage.exists(): shutil.rmtree(stage)
    grouped = {}
    for r in rows: grouped.setdefault(r['o'],[]).append(r)
    for o, fares in grouped.items():
        dump(stage/'fares'/(o+'.json'), {'schema':SCHEMA,'origin':o,'deals':fares})
    dump(stage/'index.json',index)
    target = data/'fares'
    if target.exists(): shutil.rmtree(target)
    shutil.move(str(stage/'fares'),str(target))
    dump(data/'catalog.json',catalog)
    dump(data/'origins.json',configured)
    os.replace(stage/'index.json',data/'index.json')
    append_history(data,rows,today)
    write_airport_module(catalog)

    # Update origin schedule for smart night queries
    for o in origins:
        entry = schedule.setdefault(o, {'consecutive_empty': 0, 'last_queried': today.isoformat()})
        entry['last_queried'] = today.isoformat()
        has_offers = any(r['origin'] == o and len(r['rows']) > 0 for r in results)
        if has_offers:
            entry['consecutive_empty'] = 0
            entry['last_active'] = today.isoformat()
        else:
            entry['consecutive_empty'] = entry.get('consecutive_empty', 0) + 1
    dump(data/'origin_schedule.json', schedule)

    dump(data/'collection-report.json',report)
    dump(ROOT/'.cache'/'collection-report.json',report)
    print(json.dumps(report),flush=True)
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except FatalAPIError as e:
        print(str(e)); raise SystemExit(1)