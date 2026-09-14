import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from flight_data import (clean_catalog, clean_rows, collapse_city_twins, normalize,
                         public_rows, validate, representatives, migrate)
from fetch_prices import collect, RateLimiter, make_snapshot, append_history, Client

TODAY = dt.date(2026,9,9)
PLACES = {'FCO':{'n':'Rome','k':'IT','la':41.8,'lo':12.2},
          'MAN':{'n':'Manchester','k':'GB','la':53.4,'lo':-2.3}}

def fare(**kw):
    return dict({'o':'FCO','d':'MAN','p':40,'dep':'2026-10-02','ret':'2026-10-05',
                 'dur':320,'km':1700,'n':3,'obs':'2026-09-09'}, **kw)

def raw(**kw):
    return dict({'origin':'FCO','origin_airport':'FCO','destination':'MAN','destination_airport':'MAN',
                 'price':40,'departure_at':'2026-10-02T16:00:00+02:00',
                 'return_at':'2026-10-05T20:00:00+01:00','duration':320,
                 'transfers':0,'return_transfers':0}, **kw)

def latest_raw(**kw):
    return dict({'origin':'FCO','destination':'MAN','value':40,
                 'depart_date':'2026-10-02','return_date':'2026-10-05',
                 'duration':320,'distance':1700,'number_of_changes':0,
                 'actual':True,'found_at':'2026-09-09T08:00:00Z'}, **kw)

class FakeClient:
    def __init__(self,pages): self.pages=iter(pages); self.calls=[]
    def get(self,method,params):
        self.calls.append(dict(params)); p=next(self.pages)
        if isinstance(p,Exception): raise p
        return {'success':True,'data':p}

class FlightDataTests(unittest.TestCase):
    def test_catalog_dedup_and_membership(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        original=len(catalog['airports'])
        clean,issues=clean_catalog(catalog)
        codes=[a['i'] for a in clean['airports']]
        self.assertEqual(len(codes),len(set(codes)))
        self.assertLessEqual(len(codes),original)
        by={a['i']:a for a in clean['airports']}
        for c in clean['countries']:
            self.assertEqual(len(c['a']),len(set(c['a'])))
            self.assertTrue(all(by[i]['k']==c['k'] for i in c['a']))
        self.assertEqual(clean,clean_catalog(clean)[0])

    def test_both_legs_must_be_direct(self):
        for overrides in ({'return_transfers':1},{'return_transfers':None},{'transfers':False}):
            with self.assertRaises(ValueError): normalize(raw(**overrides),'FCO','dates',PLACES,TODAY)

    def test_dates_schema_and_distance(self):
        r=normalize(raw(),'FCO','dates',PLACES,TODAY)
        self.assertEqual(r['dur'],320)  # total, not doubled
        self.assertEqual(r['n'],3)
        self.assertEqual(r['direct_check'],'both_legs')
        self.assertTrue(1600<r['km']<1900)

    def test_reject_airport_alias_substitution(self):
        with self.assertRaises(ValueError): normalize(raw(origin_airport='CIA'),'FCO','dates',PLACES,TODAY)

    def test_city_aggregates_are_rejected_everywhere(self):
        places=dict(PLACES)
        places['LON']={'n':'London','k':'GB','la':51.5,'lo':-0.1,'t':'city'}
        with self.assertRaisesRegex(ValueError,'city_aggregate'):
            normalize(latest_raw(destination='LON'),'FCO','latest',places,TODAY)
        rows,issues=clean_rows([fare(d='LON')],places,TODAY)
        self.assertEqual(rows,[])
        self.assertEqual(issues['city_aggregate'],1)

    def test_low_price_kept_flagged(self):
        r=normalize(raw(price=8.99),'FCO','dates',PLACES,TODAY)
        self.assertEqual(r['p'],8.99)
        self.assertEqual(r['quality'],'low_price_review')

    def test_low_price_is_quarantined_from_public_outputs(self):
        low=validate(fare(p=9),PLACES,TODAY)
        normal=validate(fare(p=40,ret='2026-10-06'),PLACES,TODAY)
        self.assertEqual(len(clean_rows([low,normal],PLACES,TODAY)[0]),2)
        self.assertEqual(representatives([low]),[])
        self.assertEqual(public_rows([low]),[])
        self.assertEqual(public_rows([low,normal])[0]['p'],40)

    def test_invalid_rows_are_rejected(self):
        for overrides in ({'p':float('nan')},{'p':float('inf')},{'p':True},{'p':0},
                          {'dep':'2026-09-01'},{'ret':'2026-10-01'},
                          {'ret':'2026-12-10'},{'dep':'2029-10-02'},
                          {'obs':'2026-08-01'},{'obs':'2026-09-10'},
                          {'km':-1},{'d':'ZZZ'},{'dur':-1}):
            rows,issues=clean_rows([fare(**overrides)],PLACES,TODAY)
            self.assertEqual(rows,[], overrides)
            self.assertEqual(sum(issues.values()),1)

    def test_multiple_return_dates_survive(self):
        rows,_=clean_rows([fare(),fare(ret='2026-10-09')],PLACES,TODAY)
        self.assertEqual(len(rows),2)
        self.assertEqual(len(representatives(rows)),1)

    def test_newer_expensive_price_replaces_old_cheaper(self):
        rows,_=clean_rows([fare(p=20,obs='2026-09-08'),fare(p=50)],PLACES,TODAY)
        self.assertEqual(rows[0]['p'],50)

    def test_same_observation_prefers_both_leg_verification(self):
        rows,_=clean_rows([fare(p=20,endpoint='latest'),fare(p=50,endpoint='dates')],PLACES,TODAY)
        self.assertEqual(rows[0]['p'],50)

    # Due aeroporti della stessa citta', stessa tariffa: il fornitore la
    # attribuisce all'aeroporto principale sull'endpoint `latest` e a quello
    # vero sull'endpoint `dates`. Si tiene la riga verificata tratta per tratta.
    DUE_BRUXELLES = {'BLQ':{'n':'Bologna','k':'IT','la':44.5,'lo':11.3},
                     'BRU':{'n':'Brussels','k':'BE','la':50.5,'lo':4.3},
                     'CRL':{'n':'Brussels','k':'BE','la':50.3,'lo':4.3}}

    def gemelle(self, **extra):
        base = dict(o='BLQ', p=59, dep='2026-12-11', ret='2026-12-13', dur=205,
                    n=2, obs='2026-09-09')
        return [dict(base, d='BRU', km=835, direct_check='provider_aggregate', endpoint='latest'),
                dict(base, d='CRL', km=828, direct_check='both_legs', endpoint='dates', **extra)]

    def test_city_twin_keeps_the_verified_airport(self):
        tenute = collapse_city_twins(self.gemelle(), self.DUE_BRUXELLES)
        self.assertEqual([r['d'] for r in tenute], ['CRL'])

    def test_city_twin_survives_when_the_flights_really_differ(self):
        # Stessa citta' e stesso prezzo, ma durata diversa: sono due voli veri.
        righe = self.gemelle()
        righe[1]['dur'] = 240
        self.assertEqual(len(collapse_city_twins(righe, self.DUE_BRUXELLES)), 2)

    def test_far_apart_airports_are_never_collapsed(self):
        # Due destinazioni lontane nello stesso paese restano due destinazioni,
        # anche se per caso costano uguale negli stessi giorni. Dal 14 settembre
        # il giudizio viene dalla distanza, non dal nome della citta'.
        righe = self.gemelle()
        luoghi = dict(self.DUE_BRUXELLES, CRL={'n':'Ostenda','k':'BE','la':51.2,'lo':2.86})
        self.assertEqual(len(collapse_city_twins(righe, luoghi)), 2)

    def test_airports_in_different_countries_are_never_collapsed(self):
        # Basilea e Mulhouse sono a pochi chilometri ma in due stati diversi:
        # il paese resta una barriera, altrimenti si fondono frontiere vere.
        righe = self.gemelle()
        luoghi = dict(self.DUE_BRUXELLES, CRL={'n':'Brussels','k':'FR','la':50.3,'lo':4.3})
        self.assertEqual(len(collapse_city_twins(righe, luoghi)), 2)

    def test_lone_aggregate_row_is_kept(self):
        # Se la citta' ha una riga sola, anche non verificata, non si butta:
        # per molte destinazioni e' l'unico dato che abbiamo.
        sola = [self.gemelle()[0]]
        self.assertEqual([r['d'] for r in collapse_city_twins(sola, self.DUE_BRUXELLES)], ['BRU'])

    # ── i gemelli si riconoscono dai dati, non da un elenco scritto a mano ──
    # Citta' del Messico non era nella tabella di location_authority, e i sette
    # doppioni MEX/NLU passavano. Le coordinate ce le abbiamo per tutti.
    AREE = {
     'GDL': {'n':'Guadalajara','k':'MX','la':20.5218,'lo':-103.3111},
     'MEX': {'n':'Città del Messico','k':'MX','la':19.4363,'lo':-99.0721},
     'NLU': {'n':'Santa Lucia','k':'MX','la':19.7364,'lo':-99.0269},   # 33 km da MEX
     'FCO': {'n':'Roma','k':'IT','la':41.8003,'lo':12.2389},
     'MXP': {'n':'Milano','k':'IT','la':45.6306,'lo':8.7281},
     'BGY': {'n':'Bergamo','k':'IT','la':45.6739,'lo':9.7042},          # 76 km da MXP
     'LHR': {'n':'Londra','k':'GB','la':51.4700,'lo':-0.4543},
     'LGW': {'n':'Londra','k':'GB','la':51.1537,'lo':-0.1821},
     'JFK': {'n':'New York','k':'US','la':40.6413,'lo':-73.7781},
     'EWR': {'n':'New York','k':'US','la':40.6895,'lo':-74.1745},
     'LGA': {'n':'New York','k':'US','la':40.7769,'lo':-73.8740},
     'HND': {'n':'Tokyo','k':'JP','la':35.5494,'lo':139.7798},
     'NRT': {'n':'Tokyo','k':'JP','la':35.7647,'lo':140.3864},
     'ICN': {'n':'Seul','k':'KR','la':37.4602,'lo':126.4407},
    }

    def coppia(self, origine, a, b, dc_a, dc_b, **extra):
        base = dict(o=origine, p=58, dep='2026-10-10', ret='2026-10-14',
                    dur=190, n=4, obs='2026-09-14', km=900)
        base.update(extra)
        return [dict(base, d=a, direct_check=dc_a, endpoint='dates' if dc_a == 'both_legs' else 'latest'),
                dict(base, d=b, direct_check=dc_b, endpoint='dates' if dc_b == 'both_legs' else 'latest')]

    def test_two_verified_airports_of_one_city_both_survive(self):
        # MEX e NLU sono due aeroporti veri: se il fornitore verifica entrambi
        # tratta per tratta, non sta a noi cancellarne uno.
        for a, b, o in (('MEX','NLU','GDL'), ('MXP','BGY','FCO'), ('LHR','LGW','FCO'),
                        ('HND','NRT','ICN')):
            tenute = collapse_city_twins(self.coppia(o, a, b, 'both_legs', 'both_legs'), self.AREE)
            self.assertEqual({r['d'] for r in tenute}, {a, b}, f'{a}/{b} da {o}')

    def test_three_verified_airports_of_one_city_all_survive(self):
        righe = self.coppia('FCO', 'JFK', 'EWR', 'both_legs', 'both_legs')
        righe.append(dict(righe[0], d='LGA'))
        self.assertEqual({r['d'] for r in collapse_city_twins(righe, self.AREE)},
                         {'JFK', 'EWR', 'LGA'})

    def test_verified_row_beats_the_provider_aggregate_twin(self):
        # Il caso dei sette doppioni di Citta' del Messico del 14 settembre.
        tenute = collapse_city_twins(self.coppia('GDL', 'MEX', 'NLU',
                                                 'provider_aggregate', 'both_legs'), self.AREE)
        self.assertEqual([r['d'] for r in tenute], ['NLU'])

    def test_two_unverified_twins_collapse_to_one_row(self):
        # Nessuno dei due e' verificato a livello di aeroporto: e' la stessa
        # corsa raccontata due volte dall'aggregato del fornitore.
        tenute = collapse_city_twins(self.coppia('GDL', 'MEX', 'NLU',
                                                 'provider_aggregate', 'provider_aggregate'),
                                     self.AREE)
        self.assertEqual(len(tenute), 1)

    def test_dedup_does_not_need_the_manual_city_table(self):
        # Nessuno di questi codici sta in CITY_TO_COMMERCIAL_AIRPORTS: la
        # regola deve funzionare lo stesso, perche' guarda le coordinate.
        from location_authority import CITY_TO_COMMERCIAL_AIRPORTS, AIRPORT_TO_CITY_CODE
        for code in ('MEX', 'NLU'):
            self.assertNotIn(code, CITY_TO_COMMERCIAL_AIRPORTS)
            self.assertNotIn(code, AIRPORT_TO_CITY_CODE)
        tenute = collapse_city_twins(self.coppia('GDL', 'MEX', 'NLU',
                                                 'provider_aggregate', 'both_legs'), self.AREE)
        self.assertEqual(len(tenute), 1)

    def test_weekend_one_night_kept(self):
        self.assertEqual(validate(fare(ret='2026-10-03'),PLACES,TODAY)['n'],1)

    def test_stay_up_to_60_nights_kept(self):
        self.assertEqual(validate(fare(ret='2026-11-20'),PLACES,TODAY)['n'],49)

    def test_pagination_resume_after_failure(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            client=FakeClient([[raw()]*1000, ValueError('network')])
            first=collect(client,'FCO','dates',PLACES,TODAY,path,3)
            self.assertEqual(first['status'],'partial')
            client2=FakeClient([[raw(return_at='2026-10-07')]])
            second=collect(client2,'FCO','dates',PLACES,TODAY,path,3)
            self.assertEqual(client2.calls[0]['page'],2)
            self.assertEqual(second['status'],'ok')
            self.assertEqual(len(clean_rows(second['rows'],PLACES,TODAY)[0]),2)
            cached=collect(FakeClient([]),'FCO','dates',PLACES,TODAY,path,3)
            self.assertTrue(cached['resumed'])

    def test_short_latest_page_is_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            client=FakeClient([[latest_raw()]])
            result=collect(client,'FCO','latest',PLACES,TODAY,Path(d),2)
            self.assertEqual(result['status'],'ok')
            self.assertEqual(len(client.calls),1)
            self.assertEqual(client.calls[0]['page'],1)

    def test_repeated_page_does_not_loop(self):
        with tempfile.TemporaryDirectory() as d:
            client=FakeClient([[raw()]*1000,[raw()]*1000])
            result=collect(client,'FCO','dates',PLACES,TODAY,Path(d),5)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['issues']['repeated_page'],1)
            self.assertEqual(len(client.calls),2)

    def test_successful_empty_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            result=collect(FakeClient([[]]),'FCO','dates',PLACES,TODAY,Path(d),5)
            self.assertEqual(result['status'],'ok')
            self.assertEqual(result['rows'],[])

    def test_complete_failure_cannot_publish_retained_rows(self):
        old={'deals':[fare()], 'observed':'2026-09-09','places':PLACES}
        with self.assertRaises(ValueError):
            make_snapshot(old,[],[{'status':'error','rows':[]}],PLACES,TODAY)

    def test_empty_new_airports_do_not_trigger_fifty_percent_abort(self):
        old={'deals':[fare()], 'observed':'2026-09-09','places':PLACES}
        results=[{'status':'ok','rows':[fare()]}]+[{'status':'ok','rows':[]}]*9
        index,rows,_=make_snapshot(old,[],results,PLACES,TODAY)
        self.assertEqual(len(rows),1)
        self.assertEqual(index['counts'],{'FCO':1})

    def test_history_once_per_day_and_route_with_decimals(self):
        with tempfile.TemporaryDirectory() as d:
            append_history(Path(d),[fare(p=40.55),fare(p=60,ret='2026-10-07')],TODAY,PLACES)
            append_history(Path(d),[fare(p=45.15)],TODAY,PLACES)
            lines=(Path(d)/'history'/'2026-09.csv').read_text().splitlines()
            self.assertEqual(lines,['2026-09-09,FCO,MAN,45.15'])

    def test_rate_limit_and_cooldown(self):
        now=[0.0]
        def sleep(n): now[0]+=n
        limit=RateLimiter(240,lambda:now[0],sleep)
        limit.acquire(100); limit.acquire(100)
        self.assertAlmostEqual(now[0],.25)
        limit.defer(2); limit.acquire(100)
        self.assertAlmostEqual(now[0],2.25)

    def test_client_rejects_unsuccessful_json(self):
        from unittest.mock import patch, MagicMock
        client=Client('secret',10)
        response=MagicMock(); response.__enter__.return_value=response
        response.headers={}; response.read.return_value=b'{"success":false,"data":[]}'
        with patch('urllib.request.urlopen',return_value=response), patch.object(client.limits['dates'],'defer'):
            with self.assertRaisesRegex(ValueError,'retry_exhausted'):
                client.get('aviasales/v3/prices_for_dates',{'origin':'FCO'})

    def test_cleaning_keeps_valid_missing_countries(self):
        from flight_data import places_from
        catalog,_=clean_catalog(json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8')))
        places=places_from(catalog,{'DIL':{'n':'Dili','k':'TL','la':-8.56,'lo':125.56},
            'ECN':{'n':'Ercan','k':'NY','la':35.15,'lo':33.5},
            'SUI':{'n':'Sukhumi','k':'AB','la':42.87,'lo':41.12}})
        self.assertEqual(places['DIL']['k'],'TL')
        self.assertEqual(places['ECN']['k'],'CY')
        self.assertEqual(places['SUI']['k'],'GE')

    def test_shards_scored_by_same_global_model(self):
        import build
        index=[fare(),fare(p=80,ret='2026-10-09')]
        model=build.modello(index,{})
        one=[dict(index[0])]; two=[dict(r) for r in index]
        build.valuta(one,model,{}); build.valuta(two,model,{})
        self.assertEqual(one[0]['sc'],two[0]['sc'])
        self.assertEqual(one[0]['x'],two[0]['x'])

    def test_location_authority_typing(self):
        from location_authority import is_commercial_airport, is_city_or_metro, is_ga_or_non_commercial
        # Pure city / metropolitan codes are NOT commercial airports
        for code in ('CHI', 'LON', 'NYC', 'PAR', 'ROM', 'MIL', 'TYO'):
            self.assertTrue(is_city_or_metro(code), f'{code} should be recognized as city/metro')
            self.assertFalse(is_commercial_airport(code), f'{code} must not be a commercial airport')
        # General aviation / closed airports with commercial alternative
        for code in ('ORL', 'FMY', 'SIA', 'ANK', 'DKR', 'NHA', 'RTW', 'MES'):
            self.assertTrue(is_ga_or_non_commercial(code), f'{code} should be recognized as GA/closed alias')
            self.assertFalse(is_commercial_airport(code), f'{code} must not be a commercial airport')
        # Real commercial airports
        for code in ('ORD', 'MDW', 'LHR', 'LGW', 'JFK', 'EWR', 'CDG', 'ORY', 'MCO', 'RSW', 'XIY', 'ESB', 'DSS', 'PBI', 'FRU'):
            self.assertTrue(is_commercial_airport(code), f'{code} must be recognized as commercial airport')

    def test_location_authority_resolution(self):
        from location_authority import resolve_commercial_airport
        self.assertEqual(resolve_commercial_airport('ORL'), 'MCO')
        self.assertEqual(resolve_commercial_airport('FMY'), 'RSW')
        self.assertEqual(resolve_commercial_airport('SIA'), 'XIY')
        self.assertEqual(resolve_commercial_airport('ANK'), 'ESB')
        self.assertEqual(resolve_commercial_airport('DKR'), 'DSS')
        self.assertIsNone(resolve_commercial_airport('CHI'))  # Ambiguous: ORD or MDW
        self.assertEqual(resolve_commercial_airport('ORD'), 'ORD')

    def test_validate_rejects_city_and_ga_codes(self):
        places = dict(PLACES)
        places.update({
            'CHI': {'n': 'Chicago', 'k': 'US', 'la': 41.88, 'lo': -87.63, 't': 'city'},
            'ORL': {'n': 'Orlando', 'k': 'US', 'la': 28.54, 'lo': -81.33, 't': 'city'},
            'SIA': {'n': "Xi'an", 'k': 'CN', 'la': 34.27, 'lo': 108.95, 't': 'city'},
            'FMY': {'n': 'Fort Myers', 'k': 'US', 'la': 26.58, 'lo': -81.86, 't': 'city'},
        })
        for code in ('CHI', 'ORL', 'SIA', 'FMY'):
            with self.assertRaises(ValueError):
                validate(fare(d=code), places, TODAY)
            with self.assertRaises(ValueError):
                validate(fare(o=code), places, TODAY)

    def test_collapse_city_twins_deduplicates_ga_alias(self):
        orl_places = {'ATL': {'n': 'Atlanta', 'k': 'US', 'la': 33.64, 'lo': -84.42},
                      'MCO': {'n': 'Orlando', 'k': 'US', 'la': 28.43, 'lo': -81.31},
                      'ORL': {'n': 'Orlando Executive', 'k': 'US', 'la': 28.54, 'lo': -81.33}}
        base = dict(o='ATL', p=28, dep='2026-10-17', ret='2026-10-20', dur=208, km=651, obs='2026-09-14')
        r_orl = dict(base, d='ORL', direct_check='provider_aggregate', endpoint='latest')
        r_mco = dict(base, d='MCO', direct_check='both_legs', endpoint='dates')
        tenute = collapse_city_twins([r_orl, r_mco], orl_places)
        self.assertEqual(len(tenute), 1)
        self.assertEqual(tenute[0]['d'], 'MCO')

    def test_collapse_city_twins_preserves_multi_airport_commercial(self):
        lon_places = {'FCO': {'n': 'Rome', 'k': 'IT', 'la': 41.8, 'lo': 12.2},
                      'LHR': {'n': 'London', 'k': 'GB', 'la': 51.47, 'lo': -0.45},
                      'LGW': {'n': 'London', 'k': 'GB', 'la': 51.15, 'lo': -0.18}}
        base = dict(o='FCO', p=50, dep='2026-10-01', ret='2026-10-04', dur=150, obs='2026-09-14')
        r_lhr = dict(base, d='LHR', km=1440, direct_check='both_legs', endpoint='dates')
        r_lgw = dict(base, d='LGW', km=1410, direct_check='both_legs', endpoint='dates')
        tenute = collapse_city_twins([r_lhr, r_lgw], lon_places)
        self.assertEqual(len(tenute), 2)
        self.assertEqual({r['d'] for r in tenute}, {'LHR', 'LGW'})

    def test_clean_catalog_removes_non_commercial(self):
        fake_catalog = {
            'countries': [{'k': 'US', 'it': 'Stati Uniti', 'en': 'United States', 'g': 'Nord America', 'r': 1, 'a': ['ORD', 'CHI', 'ORL', 'MCO']}],
            'airports': [
                {'i': 'ORD', 'n': "O'Hare", 'c': 'Chicago', 'k': 'US', 'la': 41.97, 'lo': -87.90, 'tz': 'America/Chicago', 'r': 1},
                {'i': 'CHI', 'n': 'Chicago FSS', 'c': 'Chicago', 'k': 'US', 'la': 41.88, 'lo': -87.63, 'tz': 'America/Chicago', 'r': 999},
                {'i': 'ORL', 'n': 'Orlando Executive', 'c': 'Orlando', 'k': 'US', 'la': 28.54, 'lo': -81.33, 'tz': 'America/New_York', 'r': 999},
                {'i': 'MCO', 'n': 'Orlando International', 'c': 'Orlando', 'k': 'US', 'la': 28.43, 'lo': -81.31, 'tz': 'America/New_York', 'r': 2},
            ]
        }
        cleaned, issues = clean_catalog(fake_catalog)
        codes = [a['i'] for a in cleaned['airports']]
        self.assertIn('ORD', codes)
        self.assertIn('MCO', codes)
        self.assertNotIn('CHI', codes)
        self.assertNotIn('ORL', codes)
        us_country = next(c for c in cleaned['countries'] if c['k'] == 'US')
        self.assertEqual(us_country['a'], ['ORD', 'MCO'])

if __name__=='__main__': unittest.main()
