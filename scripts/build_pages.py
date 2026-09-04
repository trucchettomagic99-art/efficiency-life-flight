#!/usr/bin/env python3
"""Una pagina indicizzabile per ogni aeroporto di partenza.

Perche' esistono: il sito e' un'applicazione a pagina singola, e per Google
una pagina sola vale una porta d'ingresso sola. Queste sono 400 e passa porte:
leggere (una ventina di KB), statiche, con la classifica gia' scritta nel
codice HTML invece che costruita dal JavaScript, e ognuna risponde a una
ricerca diversa — "voli economici da Bergamo", "cheap flights from Manchester".

Da ciascuna si entra nell'applicazione con l'aeroporto gia' impostato.

Gira dopo build.py, dallo stesso indice. Non tocca la rete.
"""
from __future__ import annotations
import json, pathlib, sys, datetime, html, importlib.util

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DIST = ROOT / 'dist'

# riuso gli interruttori di build.py: un solo posto dove cambiarli
spec = importlib.util.spec_from_file_location('b', ROOT / 'scripts' / 'build.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
SITE, TP_MARKER, TP_LINK = B.SITE, B.TP_MARKER, B.TP_LINK
TP_TRS, TP_CAMPAIGN, TP_P_FLIGHT = B.TP_TRS, B.TP_CAMPAIGN, B.TP_P_FLIGHT
TP_P_ACT, TP_C_ACT, TP_ACT_URL = B.TP_P_ACT, B.TP_C_ACT, B.TP_ACT_URL

MIN_ROUTES = 6          # sotto questa soglia la pagina sarebbe povera: non la creo
TOP        = 12         # righe in tabella

L = {
 'it': {
  'dir': 'da',
  'title': 'Voli economici da {city} ({iata}) — le destinazioni col miglior rapporto km/€',
  'desc': 'Le {n} migliori destinazioni in partenza da {airport}: voli diretti andata e '
          'ritorno ordinati per chilometri per euro, non per prezzo. Tariffe reali rilevate il {obs}.',
  'h1': 'Voli economici da {city}',
  'kicker': '{iata} · {airport}',
  'intro': 'Da <b>{airport}</b> l\'indice contiene <b>{n} destinazioni</b> raggiungibili con un volo '
           'diretto andata e ritorno, in <b>{k} paesi</b>. Qui sotto non sono ordinate per prezzo, ma per '
           '<b>chilometri per euro</b>: quanta distanza ti porti a casa per ogni euro speso. È un modo '
           'diverso di scegliere — non parti dalla meta, parti da quanto lontano vuoi andare.',
  'best': 'La più conveniente è <b>{dest}</b> ({dc}, {country}): {km} km andata e ritorno a '
          '{price} €, cioè <b>{ratio} km per euro</b>, con partenza il {dep} e rientro il {ret}.',
  'th': ['#', 'Destinazione', 'Paese', 'Date', 'Prezzo A/R', 'Km A/R', 'Km/€', 'Notti', ''],
  'cta': 'Apri il motore con {iata} già impostato',
  'ctaSub': 'Filtri, mappamondo, 36 lingue, 59 valute',
  'near': 'Altri aeroporti di partenza',
  'h2': 'Le migliori {t} destinazioni da {iata}',
  'obs': 'Tariffe rilevate il {obs} · voli diretti andata e ritorno · prezzi indicativi, '
         'da verificare sul sito dell\'operatore prima di prenotare.',
  'book': 'Prenota',
  'act': 'Attività',
  'home': 'Efficiency Life Flight',
  'back': 'Torna al motore di ricerca',
  'lang_other': 'English',
 },
 'en': {
  'dir': 'from',
  'title': 'Cheap flights from {city} ({iata}) — best destinations by km per euro',
  'desc': 'The {n} best destinations departing from {airport}: non-stop return flights ranked by '
          'kilometres per euro, not by price. Real fares observed on {obs}.',
  'h1': 'Cheap flights from {city}',
  'kicker': '{iata} · {airport}',
  'intro': 'From <b>{airport}</b> the index holds <b>{n} destinations</b> reachable on a non-stop '
           'return flight, across <b>{k} countries</b>. Below they are not ranked by price but by '
           '<b>kilometres per euro</b>: how much distance you take home for every euro spent. It is a '
           'different way to choose — you do not start from the destination, you start from how far you want to go.',
  'best': 'The best value is <b>{dest}</b> ({dc}, {country}): {km} km return for '
          '€{price}, that is <b>{ratio} km per euro</b>, leaving {dep} and coming back {ret}.',
  'th': ['#', 'Destination', 'Country', 'Dates', 'Return fare', 'Km return', 'Km/€', 'Nights', ''],
  'cta': 'Open the engine with {iata} preset',
  'ctaSub': 'Filters, globe, 36 languages, 59 currencies',
  'near': 'Other departure airports',
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
.mark{font-family:Archivo,"Arial Narrow",system-ui,sans-serif;font-weight:800;font-size:15px;
letter-spacing:.14em;text-transform:uppercase;text-decoration:none;color:var(--ink);white-space:nowrap}
.mark s{text-decoration:none;color:var(--signal)}
.mark u{text-decoration:none;color:var(--ink-3);font-weight:500}
.mark em{font-style:normal;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:9.5px;
letter-spacing:.18em;color:var(--signal-2);border:1px solid var(--rule-hi);padding:2px 6px;
margin-inline-start:8px;background:var(--signal-soft)}
.rail .alt{margin-inline-start:auto;font-family:ui-monospace,monospace;font-size:10.5px;
letter-spacing:.16em;text-transform:uppercase;text-decoration:none;color:var(--ink-2)}
.lbl{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;letter-spacing:.2em;
text-transform:uppercase;color:var(--ink-3);margin:0}
.lbl.sig{color:var(--signal)}
h1{font-family:Archivo,"Arial Narrow",system-ui,sans-serif;font-size:clamp(28px,5vw,52px);
line-height:1;letter-spacing:-.03em;text-transform:uppercase;margin:12px 0 0;font-weight:800}
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
"""


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def book_url(o: str, d: str, dep: str, ret: str, cur: str = 'eur') -> str:
    """Aviasales sulla rotta esatta, dietro il redirect affiliato se configurato."""
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
    """Klook sulla citta' di destinazione, dietro il redirect affiliato."""
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
    """p ~ a * km^b sull'intero indice, minimi quadrati nei logaritmi con tre
    passate di sfoltimento robusto (mediana e MAD). E' la stessa curva che usa
    l'applicazione: le pagine per aeroporto devono dire la stessa cosa."""
    import math
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
    return f'<s class="deal">\u2212{v}%</s>' if v and v >= 25 else ''


def deal_pct(r):
    """Quanto la tariffa sta sotto il prezzo atteso per la sua distanza, in
    percento. Vuoto se la curva non e' stimabile."""
    import math
    if not CURVE or r['km'] <= 0:
        return None
    exp = math.exp(CURVE[0] + CURVE[1] * math.log(r['km']))
    return round((1 - r['p'] / exp) * 100)


def page(lang: str, ap: dict, rows: list, places: dict, obs: str, others: list) -> str:
    t = L[lang]
    other = 'en' if lang == 'it' else 'it'
    city = cityname(ap['c'], lang)
    iata = ap['i']
    ncountry = len({places[r['d']]['k'] for r in rows})
    best = rows[0]
    CN = COUNTRY if lang == 'it' else COUNTRY_EN
    fmt = dict(city=esc(city), iata=iata, airport=esc(f"{ap['n']}, {city}"),
               n=len(rows), k=ncountry, obs=obs)

    def date(s):
        d = datetime.date.fromisoformat(s)
        return d.strftime('%d/%m') if lang == 'it' else d.strftime('%d %b')

    title = t['title'].format(**fmt)
    desc  = t['desc'].format(**fmt)
    url   = f"{SITE}/{t['dir']}/{iata.lower()}/"
    alt   = f"{SITE}/{L[other]['dir']}/{iata.lower()}/"

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
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="dark light">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Efficiency Life">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"{esc(title)}",
"description":"{esc(desc)}","url":"{url}","numberOfItems":{len(rows[:TOP])},
"itemListElement":[{items}]}}
</script>
</head>
<body>
<div class="rail"><div class="wrap">
  <a class="mark" href="{SITE}/"><s>▲</s> Efficiency <u>Life</u><em>Flight</em></a>
  <a class="alt" href="{alt}">{t['lang_other']}</a>
</div></div>

<header><div class="wrap">
  <p class="lbl sig">{esc(t['kicker'].format(**fmt))}</p>
  <h1>{esc(t['h1'].format(**fmt))}</h1>
  <p class="intro">{t['intro'].format(**fmt)}</p>
  <p class="best">{best_line}</p>
</div></header>

<main class="wrap">
  <h2>{esc(t['h2'].format(t=len(rows[:TOP]), iata=iata))}</h2>
  <div class="tw"><table>
    <thead><tr>{''.join(f'<th{" class=n" if i>3 else ""}>{esc(h)}</th>' for i,h in enumerate(t['th']))}</tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table></div>

  <a class="go" href="{SITE}/#o={iata}&l={lang}">
    <b>{esc(t['cta'].format(**fmt))}</b><span>{esc(t['ctaSub'])}</span></a>

  <h2>{esc(t['near'])}</h2>
  <div class="near">{near}</div>

  <p class="note">{esc(t['obs'].format(obs=obs))}</p>
</main>

<footer><div class="wrap">
  <a href="{SITE}/">{esc(t['back'])}</a> · Travelpayouts / Aviasales · OurAirports
  · <a href="mailto:support@efficiency-life.com">support@efficiency-life.com</a>
</div></footer>
</body>
</html>
"""



# Le citta' nel catalogo sono in inglese. Per le pagine italiane conta:
# nessuno cerca "voli economici da Rome". Copro l'Italia per intero e le mete
# che in italiano hanno un nome proprio; per le altre l'inglese va benissimo.
IT_CITY = {
 'Rome':'Roma','Milan':'Milano','Venice':'Venezia','Venezia':'Venezia','Florence':'Firenze',
 'Naples':'Napoli','Turin':'Torino','Genoa':'Genova','Padua':'Padova','Bolzano':'Bolzano',
 'Sevilla':'Siviglia','Seville':'Siviglia','Barcelona':'Barcellona','Lisbon':'Lisbona',
 'Athens':'Atene','Rhodes':'Rodi','Corfu':'Corfù','Crete':'Creta','Thessaloniki':'Salonicco',
 'Munich':'Monaco di Baviera','Cologne':'Colonia','Frankfurt':'Francoforte','Hamburg':'Amburgo',
 'Nuremberg':'Norimberga','Stuttgart':'Stoccarda','Dusseldorf':'Düsseldorf','Vienna':'Vienna',
 'Prague':'Praga','Krakow':'Cracovia','Warsaw':'Varsavia','Wroclaw':'Breslavia',
 'Bucharest':'Bucarest','Sofia':'Sofia','Istanbul':'Istanbul','Ankara':'Ankara',
 'Zurich':'Zurigo','Geneva':'Ginevra','Basel':'Basilea','Berne':'Berna',
 'Copenhagen':'Copenaghen','Stockholm':'Stoccolma','Gothenburg':'Göteborg','Oslo':'Oslo',
 'Helsinki':'Helsinki','Reykjavik':'Reykjavík','Dublin':'Dublino','Cork':'Cork',
 'Edinburgh':'Edimburgo','London':'Londra','Birmingham':'Birmingham','Glasgow':'Glasgow',
 'Paris':'Parigi','Nice':'Nizza','Marseille':'Marsiglia','Lyon':'Lione','Toulouse':'Tolosa',
 'Bordeaux':'Bordeaux','Strasbourg':'Strasburgo','Brussels':'Bruxelles','Antwerp':'Anversa',
 'Amsterdam':'Amsterdam','Eindhoven':'Eindhoven','Luxembourg':'Lussemburgo',
 'Tirana':'Tirana','Belgrade':'Belgrado','Zagreb':'Zagabria','Split':'Spalato',
 'Dubrovnik':'Ragusa di Dalmazia','Sarajevo':'Sarajevo','Skopje':'Skopje','Podgorica':'Podgorica',
 'Ljubljana':'Lubiana','Bratislava':'Bratislava','Budapest':'Budapest','Kiev':'Kiev','Kyiv':'Kiev',
 'Moscow':'Mosca','Saint Petersburg':'San Pietroburgo','Riga':'Riga','Vilnius':'Vilnius',
 'Tallinn':'Tallinn','Minsk':'Minsk','Chisinau':'Chișinău','Yerevan':'Erevan','Tbilisi':'Tbilisi',
 'Baku':'Baku','Malta':'Malta','Valletta':'La Valletta','Larnaca':'Larnaca','Paphos':'Pafo',
 'Nicosia':'Nicosia','Tenerife':'Tenerife','Gran Canaria':'Gran Canaria','Mallorca':'Maiorca',
 'Palma de Mallorca':'Palma di Maiorca','Palma':'Palma di Maiorca','Ibiza':'Ibiza',
 'Malaga':'Malaga','Madrid':'Madrid','Valencia':'Valencia','Alicante':'Alicante','Bilbao':'Bilbao',
 'Porto':'Porto','Faro':'Faro','Funchal':'Funchal','Azores':'Azzorre',
 'Cairo':'Il Cairo','Marrakesh':'Marrakech','Marrakech':'Marrakech','Casablanca':'Casablanca',
 'Tangier':'Tangeri','Tunis':'Tunisi','Algiers':'Algeri','Sharm el Sheikh':'Sharm el Sheikh',
 'Hurghada':'Hurghada','Tel Aviv':'Tel Aviv','Amman':'Amman','Dubai':'Dubai',
 'Abu Dhabi':'Abu Dhabi','Doha':'Doha','Riyadh':'Riad','Jeddah':'Gedda','Muscat':'Mascate',
 'New York':'New York','Chicago':'Chicago','Los Angeles':'Los Angeles','Miami':'Miami',
 'Boston':'Boston','Washington':'Washington','San Francisco':'San Francisco',
 'Toronto':'Toronto','Montreal':'Montréal','Mexico City':'Città del Messico','Havana':'L\'Avana',
 'Sao Paulo':'San Paolo','Rio de Janeiro':'Rio de Janeiro','Buenos Aires':'Buenos Aires',
 'Lima':'Lima','Bogota':'Bogotà','Santiago':'Santiago del Cile',
 'Tokyo':'Tokyo','Osaka':'Osaka','Seoul':'Seul','Beijing':'Pechino','Shanghai':'Shanghai',
 'Guangzhou':'Canton','Hong Kong':'Hong Kong','Taipei':'Taipei','Bangkok':'Bangkok',
 'Singapore':'Singapore','Kuala Lumpur':'Kuala Lumpur','Jakarta':'Giacarta','Bali':'Bali',
 'Denpasar':'Bali','Manila':'Manila','Hanoi':'Hanoi','Ho Chi Minh City':'Ho Chi Minh',
 'New Delhi':'Nuova Delhi','Delhi':'Nuova Delhi','Mumbai':'Mumbai','Bengaluru':'Bangalore',
 'Sydney':'Sydney','Melbourne':'Melbourne','Auckland':'Auckland','Perth':'Perth',
 'Johannesburg':'Johannesburg','Cape Town':'Città del Capo','Nairobi':'Nairobi',
 'Addis Ababa':'Addis Abeba','Mauritius':'Maurizio','Seychelles':'Seychelles',
 'Dakar':'Dakar','Accra':'Accra','Lagos':'Lagos','Abidjan':'Abidjan','Bamako':'Bamako',
}
def cityname(name, lang):
    return IT_CITY.get(name, name) if lang == 'it' else name


COUNTRY: dict[str, str] = {}
COUNTRY_EN: dict[str, str] = {}


def main() -> int:
    idx = json.loads((DATA / 'index.json').read_text())
    cat = json.loads((DATA / 'catalog.json').read_text())
    AP = {a['i']: a for a in cat['airports']}
    places, obs = idx['places'], idx['observed']

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

    order = sorted(good, key=lambda o: -len(good[o]))
    made = []
    for o in order:
        # collegamenti interni: i dodici scali piu' ricchi, escluso se stesso.
        # Servono a Google per scoprire tutte le pagine senza sitemap.
        others = [AP[x] for x in order if x != o][:12]
        for lang in ('it', 'en'):
            d = DIST / L[lang]['dir'] / o.lower()
            d.mkdir(parents=True, exist_ok=True)
            (d / 'index.html').write_text(page(lang, AP[o], good[o], places, obs, others))
            made.append(f"/{L[lang]['dir']}/{o.lower()}/")

    # sitemap: la radice piu' tutte le pagine appena scritte
    today = datetime.date.today().isoformat()
    urls = [f'  <url><loc>{SITE}/</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>']
    urls += [f'  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod><priority>0.7</priority></url>'
             for u in made]
    (DIST / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) + '\n</urlset>\n')

    size = sum(f.stat().st_size for f in DIST.rglob('index.html') if f.parent != DIST)
    print(f'{len(made)} pagine ({len(order)} aeroporti × 2 lingue) · {size/1024/1024:.1f} MB '
          f'· sitemap con {len(urls)} indirizzi')
    if TP_MARKER:
        print('link di prenotazione: affiliati')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
