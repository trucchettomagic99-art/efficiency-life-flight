#!/usr/bin/env python3
"""Pagine indicizzabili per aeroporto, directory gerarchica e pagine di ingresso per lingua.

Genera:
- 1300 pagine aeroporto (/from/{iata}/ e /da/{iata}/) con related airports contestuali.
- Directory gerarchica aeroporti (/airports/ e /aeroporti/ con hub continentali).
- 36 landing statiche per ciascuna lingua (/lang/{path}/).
- Sitemap con <lastmod> reale basato sulle osservazioni effettive dei prezzi.
- Indice compatto ed elegante nella homepage con collegamento alla directory.

Gira dopo build.py, dallo stesso indice. Non tocca la rete.
"""
from __future__ import annotations
import json, pathlib, sys, datetime, html, importlib.util, shutil, math, re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DIST = ROOT / 'dist'

sys.path.insert(0, str(ROOT / 'scripts'))
import location_authority as la

spec = importlib.util.spec_from_file_location('b', ROOT / 'scripts' / 'build.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
SITE, TP_MARKER, TP_LINK = B.SITE, B.TP_MARKER, B.TP_LINK
TP_TRS, TP_CAMPAIGN, TP_P_FLIGHT = B.TP_TRS, B.TP_CAMPAIGN, B.TP_P_FLIGHT
TP_P_ACT, TP_C_ACT, TP_ACT_URL = B.TP_P_ACT, B.TP_C_ACT, B.TP_ACT_URL
PROSE = B.prose_data()['locales']

MIN_ROUTES_FOR_SEO_PAGE = 6
MIN_ROUTES = MIN_ROUTES_FOR_SEO_PAGE
TOP = 12

CONTINENT_MAP = {
    'Europa': {'slug_en': 'europe', 'slug_it': 'europa', 'name_en': 'Europe', 'name_it': 'Europa'},
    'Nord America': {'slug_en': 'north-america', 'slug_it': 'nord-america', 'name_en': 'North America', 'name_it': 'Nord America'},
    'America Latina & Caraibi': {'slug_en': 'latin-america', 'slug_it': 'america-latina', 'name_en': 'Latin America & Caribbean', 'name_it': 'America Latina e Caraibi'},
    'Asia': {'slug_en': 'asia', 'slug_it': 'asia', 'name_en': 'Asia', 'name_it': 'Asia'},
    'Medio Oriente': {'slug_en': 'middle-east', 'slug_it': 'medio-oriente', 'name_en': 'Middle East', 'name_it': 'Medio Oriente'},
    'Africa': {'slug_en': 'africa', 'slug_it': 'africa', 'name_en': 'Africa', 'name_it': 'Africa'},
    'Oceania': {'slug_en': 'oceania', 'slug_it': 'oceania', 'name_en': 'Oceania', 'name_it': 'Oceania'},
}
CONTINENT_ORDER = ['Europa', 'Nord America', 'America Latina & Caraibi', 'Asia', 'Medio Oriente', 'Africa', 'Oceania']

L = {
 'it': {
  'dir': 'da',
  'dir_root': 'aeroporti',
  'title': 'Voli economici da {airport_iata} | Miglior rapporto qualità-prezzo',
  'desc': 'Confronta le {n} migliori destinazioni in volo diretto da {airport}: prezzo, chilometri '
          'per euro e rapporto qualità-prezzo, per scoprire dove il tuo budget ti porta più lontano. '
          'Tariffe reali rilevate il {obs}.',
  'h1': 'Voli economici da {airport} con il miglior rapporto qualità-prezzo',
  'kicker': '{iata} · {airport}',
  'intro': "Da <b>{airport}</b> l'indice contiene <b>{n} destinazioni</b> raggiungibili con un volo "
           "diretto andata e ritorno, in <b>{k} paesi</b>. Qui sotto non sono ordinate per prezzo, ma per "
           "<b>chilometri per euro</b>: quanta distanza ti porti a casa per ogni euro speso. "
           "È un modo diverso di scegliere: non parti dalla meta, parti da quanto lontano vuoi arrivare.",
  'metodo': 'Il rapporto qualità-prezzo qui non giudica la compagnia aerea né il comfort a bordo: '
            'è quanto vale il viaggio rispetto a quanto costa. L’Efficiency Score mette insieme '
            'chilometri per euro, prezzo, distanza, durata del soggiorno e lo storico della rotta, '
            'cioè quanto quella tratta costa di solito nello stesso periodo.',
  'best': 'La meta col valore più alto è <b>{dest}</b> ({dc}, {country}): {km} km andata e ritorno a '
          '{price} €, cioè <b>{ratio} km per ogni euro</b> speso, partendo il {dep} e rientrando il {ret}.',
  'th': ['#', 'Destinazione', 'Paese', 'Date', 'Prezzo A/R', 'Km A/R', 'Km/€', 'Notti', ''],
  'cta': 'Apri il motore con {iata} già impostato',
  'ctaSub': 'Filtri, mappamondo, 36 lingue, 59 valute',
  'near': 'Aeroporti vicini e correlati',
  'h2': 'Le migliori {t} destinazioni da {iata}',
  'obs': "Tariffe rilevate il {obs} · voli diretti andata e ritorno · prezzi indicativi, "
         "da verificare sul sito dell'operatore prima di prenotare.",
  'book': 'Prenota',
  'act': 'Attività',
  'home': 'Efficiency Life Flight',
  'back': 'Torna al motore di ricerca',
  'lang_other': 'English',
 },
 'en': {
  'dir': 'from',
  'dir_root': 'airports',
  'title': 'Cheap flights from {airport_iata} | Best value',
  'desc': 'Compare the {n} best non-stop return flights from {airport}, ranked by price, kilometres '
          'per euro and real value — not just the lowest fare. Real fares observed on {obs}.',
  'h1': 'Cheap flights from {airport} with the best value',
  'kicker': '{iata} · {airport}',
  'intro': 'From <b>{airport}</b> the index holds <b>{n} destinations</b> reachable on a non-stop '
           'return flight, across <b>{k} countries</b>. Below they are not ranked by price but by '
           '<b>kilometres per euro</b>: how much distance you take home for every euro spent. It is a '
           'different way to choose — you do not start from the destination, you start from how far you want to go.',
  'metodo': 'Value here is not a judgement on the airline or the comfort on board: it is how much '
            'the trip is worth against what it costs. The Efficiency Score combines kilometres per '
            'euro, price, distance, length of stay and the route history — what that route usually '
            'costs at the same time of year.',
  'best': 'The best value is <b>{dest}</b> ({dc}, {country}): {km} km return for '
          '€{price}, that is <b>{ratio} km per euro</b>, leaving {dep} and coming back {ret}.',
  'th': ['#', 'Destination', 'Country', 'Dates', 'Return fare', 'Km return', 'Km/€', 'Nights', ''],
  'cta': 'Open the engine with {iata} preset',
  'ctaSub': 'Filters, globe, 36 languages, 59 currencies',
  'near': 'Nearby and related departure airports',
  'h2': 'The best {t} destinations from {iata}',
  'obs': 'Fares observed on {obs} · non-stop return · indicative prices, confirm on the '
         'operator\'s site before booking.',
  'book': 'Book',
  'act': 'Things to do',
  'home': 'Efficiency Life Flight',
  'back': 'Back to the search engine',
  'lang_other': 'Italiano',
 },
}

CSS = """*,*::before,*::after{box-sizing:border-box}
:root{--void:#03070E;--deck:#071120;--deck2:#0C1B2E;--rule:rgba(120,170,235,.16);
--rule-hi:rgba(120,170,235,.36);--ink:#EAF2FB;--ink-2:#9EB3CC;--ink-3:#66809D;
--signal:#2E8DFF;--signal-2:#5FE3FF;--signal-soft:rgba(46,141,255,.14);--alert:#FF2E46;color-scheme:dark}
@media(prefers-color-scheme:light){:root{--void:#EDF2F8;--deck:#fff;--deck2:#F4F8FD;
--rule:rgba(0,45,100,.14);--rule-hi:rgba(0,45,100,.3);--ink:#04121F;--ink-2:#3B5570;--ink-3:#68809A;
--signal:#0A54D6;--signal-2:#0B6F9C;--signal-soft:rgba(10,84,214,.09);--alert:#C8102E;color-scheme:light}}
body{margin:0;background:var(--void);color:var(--ink);font-size:16px;line-height:1.6;
font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--signal)}
.wrap{max-width:1060px;margin:0 auto;padding:0 clamp(16px,4vw,40px)}
.rail{border-bottom:1px solid var(--rule);background:var(--deck)}
.rail .wrap{display:flex;align-items:center;gap:14px;height:56px;flex-wrap:wrap}
/* Il marchio e' lo stesso disegno del motore e della home, non una versione
   ridotta: la eta greca al posto della N di EFFICIENCY, con la gamba che
   scende e gira a destra a fare la L di LIFE. Fino al 14 settembre 2026 qui
   c'era ancora il marchio vecchio — una eta attraversata da una linea — su
   milletrecento pagine aeroporto, sedici di directory e trentasei di lingua,
   cioe' quasi tutto il sito.
   La larghezza dei testi e' bloccata con textLength, quindi il tratto cade al
   posto giusto anche prima che Archivo sia arrivato. */
.mark{display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit}
.wordmark{display:block;height:2.55em;width:auto;font-family:Archivo,sans-serif;font-size:15px}
.wm-a{fill:var(--ink)}
.wm-b{fill:var(--ink-3)}
.wm-eta{stroke:var(--signal)}
a.mark:hover .wm-eta{stroke:var(--signal-2)}
a.mark:hover .wm-b{fill:var(--ink-2)}
a.mark:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
.mark em{font-style:normal;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:9.5px;
letter-spacing:.18em;color:var(--signal-2);border:1px solid var(--rule-hi);padding:2px 6px;
background:var(--signal-soft);align-self:center}
.rail .alt{margin-inline-start:auto;font-family:ui-monospace,monospace;font-size:10.5px;
letter-spacing:.16em;text-transform:uppercase;text-decoration:none;color:var(--ink-2)}
.lbl{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;letter-spacing:.2em;
text-transform:uppercase;color:var(--ink-3);margin:0}
.lbl.sig{color:var(--signal)}
h1{font-family:Archivo,"Arial Narrow",system-ui,sans-serif;font-size:clamp(26px,4.5vw,48px);
line-height:1.08;letter-spacing:-.03em;text-transform:uppercase;margin:12px 0 0;font-weight:800}
h2{font-family:Archivo,"Arial Narrow",system-ui,sans-serif;font-size:clamp(18px,2.4vw,26px);
text-transform:uppercase;letter-spacing:-.02em;margin:44px 0 14px}
header{padding:clamp(28px,5vw,56px) 0 26px;border-bottom:1px solid var(--rule);
background:linear-gradient(180deg,var(--deck2),transparent)}
.intro{max-width:70ch;color:var(--ink-2);margin:18px 0 0}
.intro b{color:var(--ink)}
.best{border:1px solid var(--rule-hi);border-inline-start:3px solid var(--alert);background:var(--deck);
padding:16px 20px;margin:22px 0 0;max-width:78ch;color:var(--ink-2)}
.best b{color:var(--ink)}
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:3px;margin-top:8px}
table{width:100%;border-collapse:collapse;min-width:720px;font-size:14.5px}
th{text-align:start;padding:11px 12px;border-bottom:1px solid var(--rule-hi);background:var(--deck);
font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;
color:var(--ink-3);font-weight:500;white-space:nowrap}
td{padding:11px 12px;border-bottom:1px solid var(--rule)}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--deck2)}
td.n{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:end;font-variant-numeric:tabular-nums;white-space:nowrap}
td.r{font-family:ui-monospace,monospace;color:var(--ink-3);width:44px}
tr:first-child td.r{color:var(--alert)}
td.p{color:var(--signal);font-weight:600}
td.k{color:var(--signal-2)}
s.deal{display:block;text-decoration:none;font-size:10.5px;letter-spacing:.06em;color:var(--ok,#37D399);margin-top:2px}
.dest{font-weight:600}
.code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:var(--ink-3);
margin-inline-start:8px;letter-spacing:.06em}
.go{display:inline-flex;flex-direction:column;gap:3px;text-decoration:none;background:var(--signal);
color:#fff;padding:15px 30px;border-radius:3px;margin:26px 0 0;font-family:Archivo,system-ui,sans-serif}
.go b{font-size:16px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}
.go span{font-size:12px;opacity:.82;letter-spacing:.02em}
.go-s{display:inline-block;text-decoration:none;border:1px solid var(--rule-hi);border-radius:2px;
padding:5px 12px;font-family:ui-monospace,monospace;font-size:10.5px;letter-spacing:.12em;
text-transform:uppercase;color:var(--signal);white-space:nowrap}
.go-s:hover{border-color:var(--signal);background:var(--signal-soft)}
.go-s.alt{color:var(--ink-3);margin-top:5px}
.go-s.alt:hover{color:var(--signal)}
td.n .go-s{display:block;text-align:center}
.near{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.near a{font-family:ui-monospace,monospace;font-size:11.5px;letter-spacing:.06em;text-decoration:none;
border:1px solid var(--rule-hi);padding:6px 11px;border-radius:2px;color:var(--ink-2)}
.near a:hover{border-color:var(--signal);color:var(--signal)}
.note{font-family:ui-monospace,monospace;font-size:11.5px;color:var(--ink-3);margin-top:26px;
line-height:1.7;max-width:80ch}
footer{border-top:1px solid var(--rule);margin-top:48px;padding:26px 0 40px;color:var(--ink-3);font-size:12.5px}
footer a{color:var(--ink-2)}

/* Breadcrumbs & Hub Directory styles */
.metodo{color:var(--ink-2);font-size:14px;line-height:1.75;max-width:80ch;margin:30px 0 0}
.crumb{font-family:ui-monospace,monospace;font-size:11px;color:var(--ink-3);margin-bottom:12px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.crumb a{color:var(--ink-2);text-decoration:none}
.crumb a:hover{color:var(--signal)}
.dir-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin:24px 0}
.dir-card{border:1px solid var(--rule-hi);border-radius:4px;padding:20px;background:var(--deck);text-decoration:none;color:inherit;transition:border-color .15s}
.dir-card:hover{border-color:var(--signal)}
.dir-card h3{font-family:Archivo,sans-serif;font-size:18px;margin:0 0 6px;color:var(--ink);text-transform:uppercase}
.dir-card p{margin:0;font-size:13px;color:var(--ink-2);line-height:1.5}
.dir-card .num{font-family:ui-monospace,monospace;font-size:11px;color:var(--signal);display:block;margin-top:10px}
.country-sec{margin:36px 0}
.country-sec h3{font-family:Archivo,sans-serif;font-size:18px;border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:14px;color:var(--ink)}
.ap-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.ap-item{display:flex;flex-direction:column;border:1px solid var(--rule);border-radius:3px;padding:10px 12px;background:var(--deck);text-decoration:none;color:inherit;transition:border-color .15s}
.ap-item:hover{border-color:var(--signal)}
.ap-item strong{font-family:ui-monospace,monospace;font-size:13px;color:var(--signal);letter-spacing:.05em}
.ap-item span{font-size:13px;font-weight:600;color:var(--ink);margin:2px 0}
.ap-item em{font-style:normal;font-family:ui-monospace,monospace;font-size:11px;color:var(--ink-3)}
.hub-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.hub-cta{font-size:13px;color:var(--signal);text-decoration:none;font-weight:600}
.hub-cta strong{color:var(--signal-2)}
.hub-continents,.hub-top{margin:8px 0;font-size:12.5px;line-height:1.8}
.lbl-s{font-family:ui-monospace,monospace;font-size:10px;text-transform:uppercase;letter-spacing:.15em;color:var(--ink-3);margin-inline-end:8px}
.hub-pill{display:inline-block;padding:3px 9px;border:1px solid var(--rule-hi);border-radius:2px;font-family:ui-monospace,monospace;font-size:11px;margin:2px 4px 2px 0;text-decoration:none;color:var(--ink-2)}
.hub-pill:hover{border-color:var(--signal);color:var(--signal)}
"""

def esc(x) -> str:
    return html.escape(str(x), quote=True)


# Il marchio, scritto una volta sola: qui stava copiato in quattro punti, e
# quattro copie di un disegno sono quattro versioni che prima o poi divergono.
MARCHIO = (
    '<svg class="wordmark" viewBox="0 0 296 96" role="img" '
    'aria-label="Efficiency Life" focusable="false">'
    '<text class="wm-a" x="0" y="42" font-size="42" font-weight="800" letter-spacing="1" '
    'textLength="150" lengthAdjust="spacingAndGlyphs">EFFICIE</text>'
    '<path class="wm-eta" d="M158 42V16.5c0-2.6 2.1-4.5 4.7-4.5h11.6c6.6 0 11.7 5.2 11.7 11.8V78h18" '
    'fill="none" stroke-width="8.4" stroke-linecap="butt" stroke-linejoin="miter"/>'
    '<text class="wm-a" x="194" y="42" font-size="42" font-weight="800" letter-spacing="1" '
    'textLength="60" lengthAdjust="spacingAndGlyphs">CY</text>'
    '<text class="wm-b" x="212" y="78" font-size="42" font-weight="500" letter-spacing="1" '
    'textLength="70" lengthAdjust="spacingAndGlyphs">IFE</text>'
    '</svg>'
)


def ld_briciole(passi) -> str:
    """BreadcrumbList di schema.org dagli stessi passi disegnati in pagina.

    Si costruisce con json.dumps e non con una f-string: i nomi degli scali
    arrivano dal catalogo del fornitore e contengono apostrofi, virgolette e
    accenti che a mano prima o poi rompono il JSON — e un JSON-LD rotto Google
    lo scarta in silenzio, senza dire niente.
    """
    return json.dumps({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'name': nome, 'item': href}
            for i, (nome, href) in enumerate(passi, 1)
        ],
    }, ensure_ascii=False)

def book_url(o: str, d: str, dep: str, ret: str, cur: str = 'eur') -> str:
    from urllib.parse import quote
    ddmm = lambda s: s[8:10] + s[5:7]
    url = f'https://www.aviasales.com/search/{o}{ddmm(dep)}{d}{ddmm(ret)}1?currency={cur}'
    if not TP_MARKER:
        return url
    url += f'&marker={quote(TP_MARKER)}'
    if not TP_P_FLIGHT:
        return url
    return (TP_LINK.replace('{marker}', quote(TP_MARKER))
                   .replace('{trs}', quote(TP_TRS))
                   .replace('{p}', quote(TP_P_FLIGHT))
                   .replace('{campaign}', quote(TP_CAMPAIGN))
                   .replace('{url}', quote(url, safe='')))

def act_url(city: str) -> str:
    from urllib.parse import quote
    if not (TP_MARKER and TP_P_ACT and TP_ACT_URL):
        return ''
    url = TP_ACT_URL.replace('{city}', quote(city))
    return (TP_LINK.replace('{marker}', quote(TP_MARKER))
                   .replace('{trs}', quote(TP_TRS))
                   .replace('{p}', quote(TP_P_ACT))
                   .replace('{campaign}', quote(TP_C_ACT))
                   .replace('{url}', quote(url, safe='')))

def fit_curve(rows):
    pts = [(math.log(r['km']), math.log(r['p'])) for r in rows if r['km'] > 80 and r['p'] > 0]
    if len(pts) < 200:
        return None
    def med(v):
        s = sorted(v); n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    use, a, b = pts, 0.0, 0.0
    for _ in range(3):
        n = len(use)
        mx = sum(x for x, _ in use) / n
        my = sum(y for _, y in use) / n
        sxy = sum((x - mx) * (y - my) for x, y in use)
        sxx = sum((x - mx) ** 2 for x, _ in use)
        if not sxx:
            return None
        b = sxy / sxx
        a = my - b * mx
        res = [y - (a + b * x) for x, y in pts]
        m = med(res)
        mad = med([abs(r - m) for r in res]) or 1e-9
        nxt = [pt for pt, r in zip(pts, res) if abs(r - m) <= 2.5 * 1.4826 * mad]
        if len(nxt) < 200:
            break
        use = nxt
    return (a, b)

CURVE = None

def deal_badge(r) -> str:
    v = deal_pct(r)
    return f'<s class="deal">−{v}%</s>' if v and v >= 25 else ''

def deal_pct(r) -> int:
    if not CURVE or r['km'] <= 80 or r['p'] <= 0:
        return 0
    ref = math.exp(CURVE[0]) * (r['km'] ** CURVE[1])
    if r['p'] >= ref * 0.95:
        return 0
    return round((1 - r['p'] / ref) * 100)

IT_CITY = {
 'Rome':'Roma','Milan':'Milano','Venice':'Venezia','Venezia':'Venezia','Florence':'Firenze',
 'Naples':'Napoli','Turin':'Torino','Genoa':'Genova','Padua':'Padova','Bolzano':'Bolzano',
 'Sevilla':'Siviglia','Seville':'Siviglia','Barcelona':'Barcellona','Lisbon':'Lisbona',
 'Athens':'Atene','Rhodes':'Rodi','Corfu':'Corfù','Crete':'Creta','Thessaloniki':'Salonicco',
 'Munich':'Monaco di Baviera','Cologne':'Colonia','Frankfurt':'Francoforte','Hamburg':'Amburgo',
 'Nuremberg':'Norimberga','Stuttgart':'Stoccarda','Dusseldorf':'Düsseldorf','Vienna':'Vienna',
 'Geneva':'Ginevra','Zurich':'Zurigo','Basel':'Basilea','Brussels':'Bruxelles',
 'Copenhagen':'Copenaghen','Stockholm':'Stoccolma','Oslo':'Oslo','Helsinki':'Helsinki',
 'Warsaw':'Varsavia','Krakow':'Cracovia','Prague':'Praga','Budapest':'Budapest',
 'Bucharest':'Bucarest','Sofia':'Sofia','Belgrade':'Belgrado','Zagreb':'Zagabria',
 'Dubrovnik':'Ragusa di Dalmazia','Split':'Spalato','Sarajevo':'Sarajevo','Skopje':'Skopje',
 'Tirana':'Tirana','London':'Londra','Edinburgh':'Edimburgo','Dublin':'Dublino',
 'Paris':'Parigi','Nice':'Nizza','Lyon':'Lione','Marseille':'Marsiglia','Bordeaux':'Bordeaux',
 'Toulouse':'Tolosa','Madrid':'Madrid','Malaga':'Malaga','Valencia':'Valencia','Alicante':'Alicante',
 'Palma de Mallorca':'Palma di Maiorca','Ibiza':'Ibiza','Porto':'Porto',
 'Tokyo':'Tokyo','Kyoto':'Kyoto','Osaka':'Osaka','Beijing':'Pechino','Shanghai':'Shanghai',
 'Hong Kong':'Hong Kong','Singapore':'Singapore','Bangkok':'Bangkok','Seoul':'Seul',
 'Cairo':'Il Cairo','Marrakesh':'Marrakech','Casablanca':'Casablanca','Tunis':'Tunisi',
 'Dubai':'Dubai','Abu Dhabi':'Abu Dhabi','Doha':'Doha','Istanbul':'Istanbul',
 'New York':'New York','Los Angeles':'Los Angeles','Chicago':'Chicago','San Francisco':'San Francisco',
 'Miami':'Miami','Boston':'Boston','Washington':'Washington','Toronto':'Toronto','Montreal':'Montréal',
 'Mexico City':'Città del Messico','Buenos Aires':'Buenos Aires','Rio de Janeiro':'Rio de Janeiro',
 'Sao Paulo':'San Paolo','Sydney':'Sydney','Melbourne':'Melbourne','Auckland':'Auckland',
 # Le citta' che location_authority riscrive in italiano dentro il catalogo:
 # senza il ritorno in inglese la pagina /from/ direbbe "from Mosca".
 'Moscow':'Mosca','Alexandria':'Alessandria','Beijing':'Pechino','Rome':'Roma',
}

# Le stesse coppie lette al contrario. Serve perche' dal 14 settembre
# location_authority riscrive il campo citta' del catalogo con il nome
# italiano ("Roma", "Londra", "Citta' del Messico"): senza questa tabella la
# pagina inglese si ritrovava "Cheap flights from Roma Fiumicino".
EN_CITY = {}
for _en, _it in IT_CITY.items():
    if _en != _it:
        EN_CITY.setdefault(_it, _en)

def cityname(name, lang):
    if lang == 'it':
        return IT_CITY.get(name, name)
    return EN_CITY.get(name, name)


# ── come si chiama uno scalo in un titolo ──────────────────────────────────
# Il catalogo del fornitore ha due campi, citta' e aeroporto, e nella meta' dei
# casi contengono la stessa identica stringa: su 1.834 scali, 919 hanno
# c == n, spesso nella forma "Abakan Airport". Incollarli come
# "{aeroporto}, {citta}" produceva "Abakan Airport, Abakan Airport", e per Roma
# produceva "Fiumicino, Roma" — che nessuno scrive e nessuno cerca.
#
# Le query che portano visite a questo sito, misurate in Search Console, sono
# fatte di nomi di citta': "voli dar es salaam", "voli cape town",
# "voli low cost parigi orly". Quindi la citta' viene prima, e il nome dello
# scalo si aggiunge solo quando serve a distinguerlo da un altro della stessa
# citta'. Per Roma servono due etichette, per Edimburgo ne basta una.
GENERICHE = re.compile(
    r'\b(international|intl\.?|airport|airfield|aerodrome|air\s?base|apt|'
    r'aeroporto|aeroport|aéroport)\b', re.I)

def _senza_generiche(nome: str) -> str:
    s = GENERICHE.sub(' ', str(nome or ''))
    # Il fornitore scrive "Yogyakarta, Java Island" e "Kirkenes Airport,
    # Hoeybuktmoen": dopo la virgola c'e' sempre la specifica geografica, mai
    # il nome che la gente cerca. Si taglia li'.
    s = s.split(',')[0]
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip(' -–—/,.')

def etichette_scali(catalog: dict) -> dict[str, str]:
    """iata -> nome naturale da mettere nei titoli, per tutto il catalogo.

    Tre regole, in quest'ordine:
    1. citta' e aeroporto perdono le parole generiche ("Airport", "Intl", ...);
    2. se la citta' ha un solo scalo, il nome della citta' basta e vince,
       perche' e' quello che la gente scrive nella casella di ricerca;
    3. se ne ha piu' d'uno si aggiunge la parte di nome che li distingue
       ("Roma Fiumicino", "Roma Ciampino"), a patto che sia corta: un nome
       lungo come "Mwalimu Julius K. Nyerere" non aiuta nessuno a riconoscere
       Dar es Salaam.
    Se due scali finiscono comunque con la stessa etichetta si aggiunge il
    codice IATA, cosi' due pagine non hanno mai lo stesso titolo.
    """
    per_citta: dict[tuple, list[str]] = defaultdict(list)
    base: dict[str, tuple[str, str]] = {}
    for a in catalog['airports']:
        citta = _senza_generiche(a.get('c'))
        scalo = _senza_generiche(a.get('n'))
        # certe righe hanno come "citta'" il codice IATA e basta
        if not citta or re.fullmatch(r'[A-Z]{2,3}', str(a.get('c', '')).strip()):
            citta = scalo or a['i']
        base[a['i']] = (citta, scalo)
        per_citta[(citta.casefold(), a.get('k'))].append(a['i'])

    fatte: dict[str, str] = {}
    for a in catalog['airports']:
        citta, scalo = base[a['i']]
        etichetta = citta
        if len(per_citta[(citta.casefold(), a.get('k'))]) > 1:
            resto = scalo
            # Si toglie il nome della citta' dalla testa del nome dello scalo,
            # in tutte le lingue in cui lo conosciamo: il catalogo scrive
            # "Pechino" nel campo citta' e "Beijing Capital" in quello
            # aeroporto, e senza questo si leggeva "Beijing Beijing Capital".
            for alias in sorted({citta, cityname(citta, 'it'), cityname(citta, 'en')},
                                key=len, reverse=True):
                if alias and resto.casefold().startswith(alias.casefold()):
                    resto = resto[len(alias):].strip(' -–—/,')
                    break
            # "New York John F. Kennedy" si legge; "Citta' del Messico
            # Licenciado Benito Juarez" no. Cinque parole in tutto e' il punto
            # in cui un titolo smette di essere un nome e diventa una targa.
            if (resto and resto.casefold() != citta.casefold()
                    and len(resto.split()) <= 3
                    and len(citta.split()) + len(resto.split()) <= 5):
                etichetta = f'{citta} {resto}'
        fatte[a['i']] = etichetta

    # ultimo controllo: nessuna etichetta ripetuta dentro lo stesso paese
    visti: dict[tuple, list[str]] = defaultdict(list)
    for i, e in fatte.items():
        visti[(e.casefold(), AP_PAESE.get(i))].append(i)
    for gruppo in visti.values():
        if len(gruppo) > 1:
            for i in gruppo:
                fatte[i] = f'{fatte[i]} ({i})'
    return fatte

AP_PAESE: dict[str, str] = {}
ETICHETTA: dict[str, str] = {}

def scalo_label(ap: dict, lang: str) -> str:
    """Il nome naturale dello scalo, con la citta' nella lingua della pagina.

    Si traduce solo la prima parte, che e' la citta': "Roma Fiumicino" diventa
    "Rome Fiumicino", non "Rome Seaside". Il nome dello scalo e' un nome
    proprio e resta quello vero in tutte le lingue.
    """
    e = ETICHETTA.get(ap['i'])
    if not e:
        e = _senza_generiche(ap.get('c')) or ap['i']
    citta = _senza_generiche(ap.get('c'))
    tradotta = cityname(citta, lang)
    if citta and tradotta != citta and e.startswith(citta):
        return tradotta + e[len(citta):]
    return e

COUNTRY: dict[str, str] = {}
COUNTRY_EN: dict[str, str] = {}


def compute_related_airports(good: dict, AP: dict, cat: dict, target_count: int = 12) -> dict[str, list[dict]]:
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    c_meta = {c['k']: c for c in cat['countries']}
    related_codes = {}

    for o in good:
        src = AP[o]
        lat1, lon1 = src['la'], src['lo']
        country = src['k']
        region = c_meta.get(country, {}).get('g', '')

        twins = []
        canonical_city = la.canonical_city_code(o)
        if canonical_city in la.CITY_TO_COMMERCIAL_AIRPORTS:
            for ap in la.CITY_TO_COMMERCIAL_AIRPORTS[canonical_city]:
                if ap != o and ap in good:
                    twins.append(ap)

        candidates = []
        for other in good:
            if other == o or other in twins:
                continue
            d = haversine(lat1, lon1, AP[other]['la'], AP[other]['lo'])
            is_same_c = (AP[other]['k'] == country)
            is_same_r = (c_meta.get(AP[other]['k'], {}).get('g', '') == region)
            tier = 0 if is_same_c else (1 if is_same_r else 2)
            if d < 300:
                tier = 0
            candidates.append((tier, d, -len(good[other]), other))
        candidates.sort()

        res = list(twins)
        for _, _, _, other in candidates:
            if len(res) >= target_count:
                break
            res.append(other)
        related_codes[o] = res[:target_count]

    # Two-way reinforcement for under-linked airports (<4 inlinks)
    inlinks = defaultdict(set)
    for o, targets in related_codes.items():
        for t in targets:
            inlinks[t].add(o)

    for o in good:
        if len(inlinks[o]) < 4:
            neighbors = sorted(
                good.keys(),
                key=lambda x: haversine(AP[o]['la'], AP[o]['lo'], AP[x]['la'], AP[x]['lo']) if x != o else 99999
            )
            for n in neighbors[:10]:
                if o not in related_codes[n] and len(related_codes[n]) < 16:
                    related_codes[n].append(o)
                    inlinks[o].add(n)
                if len(inlinks[o]) >= 4:
                    break

    return {o: [AP[x] for x in related_codes[o]] for o in good}


def page(lang: str, ap: dict, rows: list, places: dict, obs: str, others: list, reg_key: str = 'Europa') -> str:
    t = L[lang]
    other = 'en' if lang == 'it' else 'it'
    city = cityname(ap['c'], lang)
    iata = ap['i']
    ncountry = len({places[r['d']]['k'] for r in rows})
    best = rows[0]
    CN = COUNTRY if lang == 'it' else COUNTRY_EN
    # {airport} e' il nome naturale; {airport_iata} lo stesso con il codice,
    # ma senza ripeterlo se l'etichetta se lo porta gia' dietro perche' due
    # scali della stessa citta' finivano con lo stesso nome.
    nome_scalo = scalo_label(ap, lang)
    nome_con_codice = nome_scalo if nome_scalo.endswith(f'({iata})') else f'{nome_scalo} ({iata})'
    raw_fmt = dict(city=city, iata=iata, airport=nome_scalo, airport_iata=nome_con_codice,
                   n=len(rows), k=ncountry, obs=obs)
    fmt = {k: esc(v) if isinstance(v, str) else v for k, v in raw_fmt.items()}

    def date(s):
        d = datetime.date.fromisoformat(s)
        now_year = datetime.date.today().year
        if lang == 'it':
            return d.strftime('%d/%m/%Y') if d.year != now_year else d.strftime('%d/%m')
        return d.strftime('%d %b %Y') if d.year != now_year else d.strftime('%d %b')

    title = t['title'].format(**raw_fmt)
    desc = t['desc'].format(**raw_fmt)
    h1 = t['h1'].format(**raw_fmt)
    url = f"{SITE}/{t['dir']}/{iata.lower()}/"
    alt = f"{SITE}/{L[other]['dir']}/{iata.lower()}/"

    body = []
    for i, r in enumerate(rows[:TOP], 1):
        pl = places[r['d']]
        body.append(
            f'<tr><td class="r">{i:02d}</td>'
            f'<td><span class="dest">{esc(cityname(pl["n"], lang))}</span><span class="code">{r["d"]}</span></td>'
            f'<td>{esc(CN.get(pl["k"], pl["k"]))}</td>'
            f'<td class="n">{date(r["dep"])} – {date(r["ret"])}</td>'
            f'<td class="n p">{r["p"]} €{deal_badge(r)}</td>'
            f'<td class="n">{r["km"]*2:,}</td>'.replace(',', '.') +
            f'<td class="n k">{r["km"]*2/r["p"]:.1f}</td>'
            f'<td class="n">{r["n"]}</td>'
            f'<td class="n"><a class="go-s" rel="nofollow sponsored" target="_blank" '
            f'href="{esc(book_url(ap["i"], r["d"], r["dep"], r["ret"]))}">{esc(t["book"])}</a>'
            + (f'<a class="go-s alt" rel="nofollow sponsored" target="_blank" '
               f'href="{esc(act_url(cityname(pl["n"], lang)))}">{esc(t["act"])}</a>' if act_url("x") else '')
            + '</td></tr>')

    items = ','.join(
        '{"@type":"ListItem","position":%d,"name":"%s"}' % (i, esc(cityname(places[r['d']]['n'], lang)))
        for i, r in enumerate(rows[:TOP], 1))

    bp = places[best['d']]
    best_line = t['best'].format(
        dest=esc(cityname(bp['n'], lang)), dc=best['d'], country=esc(CN.get(bp['k'], bp['k'])),
        km=f"{best['km']*2:,}".replace(',', '.'), price=best['p'],
        ratio=f"{best['km']*2/best['p']:.1f}", dep=date(best['dep']), ret=date(best['ret']))

    near = ''.join(
        f'<a href="{SITE}/{t["dir"]}/{o["i"].lower()}/">{o["i"]} · {esc(cityname(o["c"], lang))}</a>'
        for o in others)

    dir_root = t['dir_root']
    cont_meta = CONTINENT_MAP.get(reg_key, CONTINENT_MAP['Europa'])
    cont_slug = cont_meta['slug_' + lang]
    cont_name = cont_meta['name_' + lang]

    briciole = [
        ('Home', f'{SITE}/'),
        ('Aeroporti' if lang == 'it' else 'Airports', f'{SITE}/{dir_root}/'),
        (cont_name, f'{SITE}/{dir_root}/{cont_slug}/'),
        (f"{raw_fmt['airport']} ({iata})", url),
    ]
    breadcrumb = ('<nav class="crumb" aria-label="'
                  + ('Percorso' if lang == 'it' else 'Breadcrumb') + '">'
                  + ' &rsaquo; '.join(
                      f'<span aria-current="page">{esc(nome)}</span>' if i == len(briciole) - 1
                      else f'<a href="{href}">{esc(nome)}</a>'
                      for i, (nome, href) in enumerate(briciole))
                  + '</nav>')
    # Le briciole disegnate servono al lettore; questo le rende leggibili anche
    # a Google, che senza dati strutturati non puo' mostrare il percorso al
    # posto dell'indirizzo nudo nei risultati.
    ld_breadcrumb = ld_briciole(briciole)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="{lang}" href="{url}">
<link rel="alternate" hreflang="{other}" href="{alt}">
<link rel="alternate" hreflang="x-default" href="{SITE}/{L['en']['dir']}/{iata.lower()}/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Efficiency Life">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Efficiency Life Flight: tariffe verificate in km per euro.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/og.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;800&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"{esc(title)}",
"description":"{esc(desc)}","url":"{url}","numberOfItems":{len(rows[:TOP])},
"itemListElement":[{items}]}}
</script>
<script type="application/ld+json">
{ld_breadcrumb}
</script>
</head>
<body>
<div class="rail"><div class="wrap">
  <a class="mark" href="{SITE}/">{MARCHIO}<em>Flight</em></a>
  <a class="alt" href="{alt}">{t['lang_other']}</a>
</div></div>

<header><div class="wrap">
  {breadcrumb}
  <p class="lbl sig">{esc(t['kicker'].format(**fmt))}</p>
  <h1>{esc(h1)}</h1>
  <p class="intro">{t['intro'].format(**fmt)}</p>
  <p class="best">{best_line}</p>
</div></header>

<main class="wrap">
  <h2>{esc(t['h2'].format(t=len(rows[:TOP]), iata=iata))}</h2>
  <div class="tw"><table>
    <thead><tr>{''.join(f'<th{" class=n" if i>3 else ""}>{esc(h)}</th>' for i,h in enumerate(t['th']))}</tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table></div>

  <a class="go" href="{SITE}/flight/#o={iata}&l={lang}">
    <b>{esc(t['cta'].format(**fmt))}</b><span>{esc(t['ctaSub'])}</span></a>

  <h2>{esc(t['near'])}</h2>
  <div class="near">{near}</div>

  <p class="metodo">{esc(t['metodo'])}</p>
  <p class="note">{esc(t['obs'].format(obs=obs))}</p>
</main>

<footer><div class="wrap">
  <a href="{SITE}/flight/">{esc(t['back'])}</a> · <a href="{SITE}/{dir_root}/">{"Tutti gli aeroporti" if lang == "it" else "All airports"}</a> · Travelpayouts / Aviasales · OurAirports
  · <a href="mailto:support@efficiency-life.com">support@efficiency-life.com</a>
</div></footer>
</body>
</html>
"""


def directory_index_page(lang: str, region_airports: dict, total_airports: int, total_countries: int, obs: str) -> str:
    other = 'en' if lang == 'it' else 'it'
    dir_root = 'aeroporti' if lang == 'it' else 'airports'
    other_dir_root = 'airports' if lang == 'it' else 'aeroporti'
    url = f"{SITE}/{dir_root}/"
    alt = f"{SITE}/{other_dir_root}/"

    title = ('Directory Aeroporti — Tutti i {n} aeroporti per continente e paese' if lang == 'it'
             else 'Airport Directory — All {n} departure airports by continent and country').format(n=total_airports)
    desc = ('Indice completo di tutti i {n} aeroporti di partenza in {k} paesi. '
            'Voli diretti andata e ritorno ordinati per chilometri per euro.').format(n=total_airports, k=total_countries)

    cards = []
    for reg_key in CONTINENT_ORDER:
        if reg_key not in region_airports:
            continue
        meta = CONTINENT_MAP[reg_key]
        slug = meta['slug_' + lang]
        name = meta['name_' + lang]
        aps = region_airports[reg_key]
        num_aps = len(aps)
        countries = len({a['k'] for a in aps})
        cards.append(
            f'<a class="dir-card" href="{SITE}/{dir_root}/{slug}/">'
            f'<h3>{esc(name)}</h3>'
            f'<p>{"Esplora rotte e offerte dirette da" if lang == "it" else "Explore non-stop routes and deals from"} '
            f'<b>{num_aps}</b> {"aeroporti in" if lang == "it" else "airports across"} <b>{countries}</b> {"paesi" if lang == "it" else "countries"}.</p>'
            f'<span class="num">{"Vedi aeroporti in" if lang == "it" else "View airports in"} {esc(name)} &rarr;</span>'
            f'</a>'
        )

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="{lang}" href="{url}">
<link rel="alternate" hreflang="{other}" href="{alt}">
<link rel="alternate" hreflang="x-default" href="{SITE}/airports/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;800&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="rail"><div class="wrap">
  <a class="mark" href="{SITE}/">{MARCHIO}<em>Flight</em></a>
  <a class="alt" href="{alt}">{'English' if lang == 'it' else 'Italiano'}</a>
</div></div>

<header><div class="wrap">
  <p class="lbl sig">EFFICIENCY LIFE · DIRECTORY</p>
  <h1>{'Directory Aeroporti' if lang == 'it' else 'Airport Directory'}</h1>
  <p class="intro">{esc(desc)}</p>
</div></header>

<main class="wrap">
  <h2>{'Scegli per Continente' if lang == 'it' else 'Browse by Continent'}</h2>
  <div class="dir-grid">{''.join(cards)}</div>
</main>

<footer><div class="wrap">
  <a href="{SITE}/flight/">{'Motore di ricerca voli' if lang == 'it' else 'Flight search engine'}</a> · Travelpayouts / Aviasales · OurAirports
  · <a href="mailto:support@efficiency-life.com">support@efficiency-life.com</a>
</div></footer>
</body>
</html>
"""


def continent_directory_page(lang: str, reg_key: str, airports_in_reg: list[dict], AP: dict, good: dict, cat: dict, obs: str) -> str:
    other = 'en' if lang == 'it' else 'it'
    dir_root = 'aeroporti' if lang == 'it' else 'airports'
    other_dir_root = 'airports' if lang == 'it' else 'aeroporti'

    meta = CONTINENT_MAP[reg_key]
    slug = meta['slug_' + lang]
    other_slug = meta['slug_' + other]
    name = meta['name_' + lang]

    url = f"{SITE}/{dir_root}/{slug}/"
    alt = f"{SITE}/{other_dir_root}/{other_slug}/"

    title = ('Aeroporti in {name} — Voli diretti e migliori destinazioni' if lang == 'it'
             else 'Airports in {name} — Non-stop flights and best destinations').format(name=name)
    desc = ('Elenco dei {n} aeroporti in {name} con rotte dirette andata e ritorno '
            'ordinate per chilometri per euro.').format(n=len(airports_in_reg), name=name)

    # Group airports by country
    c_meta = {c['k']: c for c in cat['countries']}
    by_country = defaultdict(list)
    for a in airports_in_reg:
        by_country[a['k']].append(a)

    # Sort countries by localized name
    def get_cname(c_code):
        c_info = c_meta.get(c_code, {})
        return c_info.get(lang) or c_info.get('en') or c_code

    sorted_countries = sorted(by_country.keys(), key=lambda c: get_cname(c))

    sections = []
    for c_code in sorted_countries:
        c_name = get_cname(c_code)
        c_aps = sorted(by_country[c_code], key=lambda a: -len(good[a['i']]))
        ap_links = []
        for a in c_aps:
            iata = a['i']
            routes = len(good[iata])
            city = cityname(a['c'], lang)
            dest_page = f"{SITE}/{L[lang]['dir']}/{iata.lower()}/"
            ap_links.append(
                f'<a class="ap-item" href="{dest_page}">'
                f'<strong>{iata}</strong>'
                f'<span>{esc(city)} · {esc(a["n"])}</span>'
                f'<em>{routes} {"destinazioni dirette" if lang == "it" else "non-stop destinations"}</em>'
                f'</a>'
            )
        sections.append(
            f'<div class="country-sec">'
            f'<h3>{esc(c_name)} ({len(c_aps)})</h3>'
            f'<div class="ap-list">{"".join(ap_links)}</div>'
            f'</div>'
        )

    briciole = [
        ('Home', f'{SITE}/'),
        ('Aeroporti' if lang == 'it' else 'Airports', f'{SITE}/{dir_root}/'),
        (name, url),
    ]
    breadcrumb = ('<nav class="crumb" aria-label="'
                  + ('Percorso' if lang == 'it' else 'Breadcrumb') + '">'
                  + ' &rsaquo; '.join(
                      f'<span aria-current="page">{esc(n)}</span>' if i == len(briciole) - 1
                      else f'<a href="{href}">{esc(n)}</a>'
                      for i, (n, href) in enumerate(briciole))
                  + '</nav>')
    ld_breadcrumb = ld_briciole(briciole)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="{lang}" href="{url}">
<link rel="alternate" hreflang="{other}" href="{alt}">
<link rel="alternate" hreflang="x-default" href="{SITE}/airports/{meta['slug_en']}/">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;800&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<script type="application/ld+json">
{ld_breadcrumb}
</script>
</head>
<body>
<div class="rail"><div class="wrap">
  <a class="mark" href="{SITE}/">{MARCHIO}<em>Flight</em></a>
  <a class="alt" href="{alt}">{'English' if lang == 'it' else 'Italiano'}</a>
</div></div>

<header><div class="wrap">
  {breadcrumb}
  <p class="lbl sig">EFFICIENCY LIFE · {esc(name.upper())}</p>
  <h1>{esc(title)}</h1>
  <p class="intro">{esc(desc)}</p>
</div></header>

<main class="wrap">
  {''.join(sections)}
</main>

<footer><div class="wrap">
  <a href="{SITE}/flight/">{'Motore di ricerca' if lang == 'it' else 'Flight search engine'}</a> · <a href="{SITE}/{dir_root}/">{"Tutti i continenti" if lang == "it" else "All continents"}</a> · Travelpayouts / Aviasales · OurAirports
  · <a href="mailto:support@efficiency-life.com">support@efficiency-life.com</a>
</div></footer>
</body>
</html>
"""


def locale_page(code: str, rows: list, places: dict, airports: dict, obs: str,
                tot_deals: int, tot_origins: int, tot_dests: int) -> str:
    meta = PROSE[code]
    title = meta['seo']['title']
    h1 = meta['seo'].get('h1') or title
    desc = meta['seo']['description']
    url = f"{SITE}/lang/{meta['path']}/"
    values = dict(
        deals=f"{tot_deals:,}".replace(',', ' '), origins=f"{tot_origins:,}".replace(',', ' '),
        destinations=f"{tot_dests:,}".replace(',', ' '), updateDate=obs,
    )
    summary = fill(meta['indexNote'], values)
    warning = fill(meta['privacy'][3][1], values)
    cards = ''.join(
        f'<div class="best"><b>{esc(head)}</b><br>{fill(body, values)}</div>'
        for head, body in meta['method'][:2])
    body = []
    items = []
    for i, r in enumerate(rows, 1):
        op = airports.get(r['o'], {'c': r['o']})
        dp = places.get(r['d'], {'n': r['d']})
        route_name = f'{op.get("c", r["o"])} ({r["o"]}) → {dp.get("n", r["d"])} ({r["d"]})'
        body.append(
            f'<tr><td class="r">{i:02d}</td><td><span class="dest">{esc(route_name)}</span></td>'
            f'<td class="n p">{r["p"]} €</td>'
            f'<td class="n">{r["km"] * 2:,}</td>'.replace(',', ' ') +
            f'<td class="n k">{r["km"] * 2 / r["p"]:.1f}</td></tr>')
        items.append({'@type':'ListItem', 'position':i, 'name':route_name})

    language_nav = ''.join(
        f'<a lang="{esc(other["hreflang"])}" hreflang="{esc(other["hreflang"])}" '
        f'href="{SITE}/lang/{esc(other["path"])}/">{esc(other["name"])}</a>'
        for other in PROSE.values())
    schema = json.dumps({
        '@context':'https://schema.org', '@type':'ItemList', 'name':title,
        'description':desc, 'url':url, 'numberOfItems':len(items),
        'itemListElement':items,
    }, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    return f"""<!doctype html>
<html lang="{esc(meta['hreflang'])}" dir="{esc(meta['dir'])}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{url}">
{alternate_links()}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Efficiency Life">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Efficiency Life Flight — {esc(desc)}">
<meta property="og:locale" content="{esc(meta['locale'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE}/og.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;800&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<script type="application/ld+json">{schema}</script>
</head>
<body>
<div class="rail"><div class="wrap">
  <a class="mark" href="{SITE}/">{MARCHIO}<em>Flight</em></a>
</div></div>
<header><div class="wrap">
  <p class="lbl sig">EFFICIENCY LIFE · FLIGHT</p>
  <h1>{esc(h1)}</h1>
  <p class="intro">{esc(desc)}</p>
  <p class="best">{summary}</p>
</div></header>
<main class="wrap">
  <div class="tw"><table aria-label="Efficiency Life Flight">
    <thead><tr><th>#</th><th>IATA</th><th class="n">€</th><th class="n">KM ↔</th><th class="n">KM/€</th></tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table></div>
  <a class="go" href="{SITE}/flight/#l={code}"><b>Efficiency Life Flight &rarr;</b></a>
  {cards}
  <p class="note">{warning}</p>
  <nav class="near" aria-label="Language">{language_nav}</nav>
</main>
<footer><div class="wrap">Travelpayouts / Aviasales · OurAirports · Natural Earth · <a href="mailto:support@efficiency-life.com">support@efficiency-life.com</a></div></footer>
</body>
</html>
"""


def fill(text: str, values: dict[str, object]) -> str:
    out = text
    for key, value in values.items():
        out = out.replace('{' + key + '}', esc(value))
    return out


def pagina_404() -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pagina non trovata — Efficiency Life</title>
<meta name="robots" content="noindex,follow">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>{CSS}
.e404{{max-width:52ch;margin:0 auto;padding:18vh 20px 10vh;text-align:center}}
.e404 .cod{{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:13px;letter-spacing:.2em;
  text-transform:uppercase;color:#2E8DFF}}
.e404 h1{{margin:14px 0 10px;font-size:clamp(28px,6vw,44px);line-height:1.05;letter-spacing:-.03em}}
.e404 p{{color:#9EB3CC;line-height:1.6;margin:0 0 26px}}
.e404 .vie{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.e404 .vie a{{display:inline-block;padding:11px 20px;border:1px solid rgba(120,170,235,.36);
  border-radius:3px;text-decoration:none;color:inherit}}
.e404 .vie a.primo{{background:#2E8DFF;border-color:#2E8DFF;color:#03070E;font-weight:600}}
</style>
</head>
<body>
<main class="e404">
  <div class="cod">Errore 404</div>
  <h1>Questa pagina non esiste.</h1>
  <p>L&#8217;indirizzo &egrave; sbagliato, oppure la pagina &egrave; stata
     tolta. Le tariffe invece ci sono tutte, e si aggiornano ogni notte.</p>
  <div class="vie">
    <a class="primo" href="/flight/">Cerca un volo</a>
    <a href="/">Torna alla home</a>
  </div>
</main>
</body>
</html>
"""


def extract_seo_substance(html_content: str) -> str:
    """Estrae l'impronta del contenuto SEO significativo escludendo le sole date di osservazione/rilevamento."""
    # 1. Rimuove il paragrafo note a pié pagina con la data di osservazione
    s = re.sub(r'<p class="note">.*?</p>', '', html_content, flags=re.DOTALL)
    # 2. Rimuove le clausole di data osservazione/rilevamento (IT ed EN) in meta description, og:description, ecc.
    s = re.sub(
        r'(?:Real fares observed on|Tariffe reali rilevate il|Tariffe reali osservate il|Tariffe rilevate il|Fares observed on)\s*[\d\-]+[^\.]*\.?',
        '',
        s,
        flags=re.IGNORECASE
    )
    # 3. Rimuove date ISO (YYYY-MM-DD) tipiche delle date tecniche di osservazione (senza intaccare date di viaggio come 22 Feb 2027)
    s = re.sub(r'\b202\d-[01]\d-[0-3]\d\b', '', s)
    # 4. Collassa spaziature multiple per confronto deterministico
    return re.sub(r'\s+', ' ', s).strip()


def resolve_page_lastmod(old_html: str | None, new_html: str, old_lastmod: str | None, new_obs: str) -> str:
    """Determina il lastmod in modo conservativo:
    - Se la pagina esisteva e il contenuto sostanziale è identico, conserva old_lastmod.
    - Se il contenuto sostanziale è cambiato (prezzi, destinazioni, ranking, rotte, ecc.) o la pagina è nuova, usa new_obs.
    """
    if not old_html or not old_lastmod:
        return new_obs
    if extract_seo_substance(old_html) == extract_seo_substance(new_html):
        return old_lastmod
    return new_obs


def alternate_links() -> str:
    rows = [
        f'<link rel="alternate" hreflang="{esc(meta["hreflang"])}" '
        f'href="{SITE}/lang/{esc(meta["path"])}/">'
        for meta in PROSE.values()
    ]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}/">')
    return chr(10).join(rows)


def main() -> int:
    idx = json.loads((DATA / 'index.json').read_text(encoding='utf-8'))
    cat = json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))
    AP = {a['i']: a for a in cat['airports']}
    places, obs = idx['places'], idx['observed']

    # le etichette naturali degli scali si calcolano una volta per tutte,
    # perche' per decidere "Roma Fiumicino" o solo "Edimburgo" serve sapere
    # quanti aeroporti ha quella citta' in tutto il catalogo
    AP_PAESE.update({a['i']: a.get('k') for a in cat['airports']})
    ETICHETTA.update(etichette_scali(cat))

    # Legge sitemap precedente se esiste per evitare churn ingiustificato di lastmod
    old_sitemap_path = DIST / 'sitemap.xml'
    old_lastmods = {}
    if old_sitemap_path.is_file():
        old_content = old_sitemap_path.read_text(encoding='utf-8')
        for b in re.findall(r'<url>(.*?)</url>', old_content, re.DOTALL):
            loc_m = re.search(r'<loc>(.*?)</loc>', b)
            lm_m = re.search(r'<lastmod>(.*?)</lastmod>', b)
            if loc_m and lm_m:
                old_lastmods[loc_m.group(1).strip()] = lm_m.group(1).strip()

    for c in cat['countries']:
        COUNTRY[c['k']] = c.get('it') or c.get('en') or c['k']
        COUNTRY_EN[c['k']] = c.get('en') or c.get('it') or c['k']

    global CURVE
    CURVE = fit_curve(idx['deals'])
    if CURVE:
        print(f'curva prezzo-distanza: p ~ {2.718281828 ** CURVE[0]:.2f} * km^{CURVE[1]:.3f}')

    by = {}
    for r in idx['deals']:
        if r['o'] in AP and r['d'] in places:
            by.setdefault(r['o'], []).append(r)

    good = {o: sorted(rs, key=lambda r: -(r['km'] * 2 / r['p']))
            for o, rs in by.items() if len(rs) >= MIN_ROUTES}
    if not good:
        print('nessun aeroporto con abbastanza rotte: non genero pagine', file=sys.stderr)
        return 1

    # Retire stale airport pages
    for folder in ('da', 'from'):
        for stale in (DIST / folder).glob('*/index.html'):
            if stale.parent.name.upper() not in good:
                stale.unlink()

    # 1. Calcola collegamenti interni contestuali e realistici
    c_meta = {c['k']: c for c in cat['countries']}
    related_map = compute_related_airports(good, AP, cat, target_count=12)

    # Continent buckets
    region_airports = defaultdict(list)
    for o in good:
        c_code = AP[o]['k']
        reg = c_meta.get(c_code, {}).get('g', 'Europa')
        if reg not in CONTINENT_MAP:
            reg = 'Europa'
        region_airports[reg].append(AP[o])

    order = sorted(good, key=lambda o: -len(good[o]))
    origin_lastmod = {}
    for o in good:
        origin_lastmod[o] = max(r.get('obs', obs) for r in good[o])

    continent_lastmod = {}
    for reg_key, aps in region_airports.items():
        continent_lastmod[reg_key] = max(origin_lastmod[a['i']] for a in aps)

    total_countries = len({AP[o]['k'] for o in good})

    # 1. Pagine aeroporto (/from/{IATA}/ e /da/{IATA}/) con lastmod conservativo
    made = []
    airport_resolved_lastmod = {}

    for o in order:
        others = related_map[o]
        c_code = AP[o]['k']
        reg_key = c_meta.get(c_code, {}).get('g', 'Europa')
        if reg_key not in CONTINENT_MAP:
            reg_key = 'Europa'

        obs_origin = origin_lastmod[o]

        for lang in ('it', 'en'):
            t = L[lang]
            url = f"{SITE}/{t['dir']}/{o.lower()}/"
            d = DIST / t['dir'] / o.lower()
            d.mkdir(parents=True, exist_ok=True)
            target_file = d / 'index.html'
            new_html = page(lang, AP[o], good[o], places, obs_origin, others, reg_key=reg_key)

            old_html = target_file.read_text(encoding='utf-8') if target_file.is_file() else None
            resolved_lm = resolve_page_lastmod(old_html, new_html, old_lastmods.get(url), obs_origin)

            target_file.write_text(new_html, encoding='utf-8')
            made.append(f"/{t['dir']}/{o.lower()}/")
            airport_resolved_lastmod[f"/{t['dir']}/{o.lower()}/"] = resolved_lm

    # 2. Directory Hub e Pagine di Continente con lastmod conservativo
    directory_made = []
    directory_resolved_lastmod = {}

    for lang in ('it', 'en'):
        dir_root = 'aeroporti' if lang == 'it' else 'airports'
        dir_url = f"{SITE}/{dir_root}/"
        dir_dir = DIST / dir_root
        dir_dir.mkdir(parents=True, exist_ok=True)
        dir_file = dir_dir / 'index.html'
        new_dir_html = directory_index_page(lang, region_airports, len(good), total_countries, obs)

        old_html = dir_file.read_text(encoding='utf-8') if dir_file.is_file() else None
        resolved_dir_lm = resolve_page_lastmod(old_html, new_dir_html, old_lastmods.get(dir_url), max(continent_lastmod.values()) if continent_lastmod else obs)

        dir_file.write_text(new_dir_html, encoding='utf-8')
        directory_made.append(f"/{dir_root}/")
        directory_resolved_lastmod[f"/{dir_root}/"] = resolved_dir_lm

        for reg_key in CONTINENT_ORDER:
            if reg_key not in region_airports:
                continue
            meta = CONTINENT_MAP[reg_key]
            slug = meta['slug_' + lang]
            cont_url = f"{SITE}/{dir_root}/{slug}/"
            sub_dir = dir_dir / slug
            sub_dir.mkdir(parents=True, exist_ok=True)
            cont_file = sub_dir / 'index.html'
            new_cont_html = continent_directory_page(lang, reg_key, region_airports[reg_key], AP, good, cat, obs)

            old_html = cont_file.read_text(encoding='utf-8') if cont_file.is_file() else None
            resolved_cont_lm = resolve_page_lastmod(old_html, new_cont_html, old_lastmods.get(cont_url), continent_lastmod.get(reg_key, obs))

            cont_file.write_text(new_cont_html, encoding='utf-8')
            directory_made.append(f"/{dir_root}/{slug}/")
            directory_resolved_lastmod[f"/{dir_root}/{slug}/"] = resolved_cont_lm

    # 3. Landing per lingua con lastmod conservativo
    ranked = sorted(idx['deals'], key=lambda r: -(r['km'] * 2 / r['p']))
    showcase, seen_origins = [], set()
    for r in ranked:
        if r['o'] in seen_origins or r['o'] not in AP or r['d'] not in places:
            continue
        showcase.append(r); seen_origins.add(r['o'])
        if len(showcase) == TOP:
            break
    locale_root = DIST / 'lang'
    locale_root.mkdir(parents=True, exist_ok=True)
    locale_made = []
    locale_resolved_lastmod = {}
    for code, meta in PROSE.items():
        lang_url = f"{SITE}/lang/{meta['path']}/"
        d = locale_root / meta['path']
        d.mkdir(parents=True, exist_ok=True)
        target_file = d / 'index.html'
        new_locale_html = locale_page(
            code, showcase, places, AP, obs, len(idx['deals']), len(idx['counts']),
            len({r['d'] for r in idx['deals']}))

        old_html = target_file.read_text(encoding='utf-8') if target_file.is_file() else None
        resolved_lang_lm = resolve_page_lastmod(old_html, new_locale_html, old_lastmods.get(lang_url), obs)

        target_file.write_text(new_locale_html, encoding='utf-8')
        locale_made.append(f"/lang/{meta['path']}/")
        locale_resolved_lastmod[f"/lang/{meta['path']}/"] = resolved_lang_lm

    # 4. Indice degli aeroporti dentro la home (dist/index.html)
    home = DIST / 'index.html'
    if home.is_file():
        h = home.read_text(encoding='utf-8')
        if '<!--HUB-->' in h:
            voci = []
            for lang in ('it', 'en'):
                dir_root = 'aeroporti' if lang == 'it' else 'airports'
                dir_lbl = 'Directory completa aeroporti' if lang == 'it' else 'Complete Airport Directory'
                hub_lbl = f'Tutti i {len(order)} aeroporti per continente e paese' if lang == 'it' else f'All {len(order)} airports by continent and country'
                top_hubs = [AP[x] for x in order[:10]]
                top_links = ' '.join(
                    f'<a href="/{L[lang]["dir"]}/{a["i"].lower()}/">{a["i"]} · {esc(cityname(a["c"], lang))}</a>'
                    for a in top_hubs
                )
                continents_links = ' '.join(
                    f'<a class="hub-pill" href="/{dir_root}/{CONTINENT_MAP[reg]["slug_" + lang]}/">'
                    f'{esc(CONTINENT_MAP[reg]["name_" + lang])} ({len(region_airports[reg])})</a>'
                    for reg in CONTINENT_ORDER if reg in region_airports
                )
                voci.append(
                    f'<nav class="hub" lang="{lang}" aria-label="{dir_lbl}">'
                    f'<div class="hub-head">'
                    f'<span class="lbl">{"Navigazione aeroporti" if lang == "it" else "Airport navigation"}</span>'
                    f'<a class="hub-cta" href="/{dir_root}/"><strong>{dir_lbl} &rarr;</strong> {hub_lbl}</a>'
                    f'</div>'
                    f'<div class="hub-continents"><span class="lbl-s">{"Continenti" if lang == "it" else "Continents"}:</span> {continents_links}</div>'
                    f'<div class="hub-top"><span class="lbl-s">{"Principali scali" if lang == "it" else "Major hubs"}:</span> {top_links}</div>'
                    f'</nav>'
                )
            lingue = ''.join(
                f'<a lang="{esc(meta["hreflang"])}" hreflang="{esc(meta["hreflang"])}" '
                f'href="/lang/{esc(meta["path"])}/">{esc(meta["name"])}</a> '
                for meta in PROSE.values())
            voci.append(f'<nav class="locale-index" aria-label="Language">{lingue}</nav>')
            home.write_text(h.replace('<!--HUB-->', ''.join(voci)), encoding='utf-8')
            print(f'indice nella home: directory + 7 continenti + 10 hub + {len(PROSE)} lingue')

    # 5. Risoluzione lastmod per Home e Flight con la stessa logica conservativa
    prev_home_file = DIST / '.prev_home.html'
    new_home_html = home.read_text(encoding='utf-8') if home.is_file() else ''
    old_home_html = prev_home_file.read_text(encoding='utf-8') if prev_home_file.is_file() else new_home_html
    home_lm = resolve_page_lastmod(old_home_html, new_home_html, old_lastmods.get(f'{SITE}/'), obs)
    if home.is_file():
        prev_home_file.write_text(new_home_html, encoding='utf-8')

    flight_file = DIST / 'flight' / 'index.html'
    prev_flight_file = DIST / '.prev_flight.html'
    new_flight_html = flight_file.read_text(encoding='utf-8') if flight_file.is_file() else ''
    old_flight_html = prev_flight_file.read_text(encoding='utf-8') if prev_flight_file.is_file() else new_flight_html
    flight_lm = resolve_page_lastmod(old_flight_html, new_flight_html, old_lastmods.get(f'{SITE}/flight/'), obs)
    if flight_file.is_file():
        prev_flight_file.write_text(new_flight_html, encoding='utf-8')

    # 6. Sitemap con lastmod conservativo dinamico
    urls = [
        f'  <url><loc>{SITE}/</loc><lastmod>{home_lm}</lastmod><priority>1.0</priority></url>',
        f'  <url><loc>{SITE}/flight/</loc><lastmod>{flight_lm}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>'
    ]

    for u in directory_made:
        urls.append(f'  <url><loc>{SITE}{u}</loc><lastmod>{directory_resolved_lastmod[u]}</lastmod><priority>0.8</priority></url>')

    for u in made:
        urls.append(f'  <url><loc>{SITE}{u}</loc><lastmod>{airport_resolved_lastmod[u]}</lastmod><priority>0.7</priority></url>')

    for u in locale_made:
        urls.append(f'  <url><loc>{SITE}{u}</loc><lastmod>{locale_resolved_lastmod[u]}</lastmod><priority>0.8</priority></url>')

    sxml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'] + urls + ['</urlset>', '']
    (DIST / 'sitemap.xml').write_text(chr(10).join(sxml), encoding='utf-8')

    preserved_ap = sum(1 for u in made if airport_resolved_lastmod[u] == old_lastmods.get(f'{SITE}{u}'))
    updated_ap = len(made) - preserved_ap
    print(f'lastmod aeroporti: {preserved_ap} conservati (contenuto invariato), {updated_ap} aggiornati')
    print(f'lastmod home: {home_lm} (conservato: {home_lm == old_lastmods.get(f"{SITE}/")}) · flight: {flight_lm} (conservato: {flight_lm == old_lastmods.get(f"{SITE}/flight/")})')

    (DIST / '404.html').write_text(pagina_404(), encoding='utf-8')

    size = sum(f.stat().st_size for f in DIST.rglob('index.html') if f.parent != DIST)
    print(f'{len(made) + len(directory_made) + len(locale_made)} pagine ({len(order)} aeroporti × 2 + '
          f'{len(directory_made)} directory + {len(locale_made)} landing lingua) · {size/1024/1024:.1f} MB '
          f'· sitemap con {len(urls)} indirizzi')
    if TP_MARKER:
        print('link di prenotazione: affiliati')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())