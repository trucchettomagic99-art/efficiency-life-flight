#!/usr/bin/env python3
"""Inietta catalogo e indice tariffe nel template e scrive dist/.

Non tocca la rete: prende quello che c'e' in data/ e produce il sito. Puo'
girare in locale (`python scripts/build.py`) o dentro GitHub Actions subito
dopo fetch_prices.py.
"""
import datetime, json, math, pathlib, re, shutil, sys

ROOT   = pathlib.Path(__file__).resolve().parent.parent
DATA   = ROOT / 'data'
PUBLIC = ROOT / 'public'
DIST   = ROOT / 'dist'
PROSE  = ROOT / 'src' / 'prose.json'

LANG_CODES = ('en','zh','hi','es','ar','fr','bn','pt','ru','ur','id','de','ja','tr','ko','vi','it',
              'fa','th','pl','nl','uk','ro','el','cs','sv','hu','he','ms','ta','sw','da','no','fi',
              'bg','tl')


def fx_date() -> str:
    """Legge la data dei cambi dalla fonte usata anche dall'applicazione."""
    source = (ROOT / 'src' / 'i18n.js').read_text()
    match = re.search(r"const FX_DATE\s*=\s*['\"]([^'\"]+)['\"]", source)
    if not match:
        sys.exit('i18n.js: costante FX_DATE non trovata')
    return match.group(1)

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
# 3.09.2026 — il redirect tp.media/r rispondeva "Forbidden" a qualunque link:
# gli strumenti partner erano disattivati perche' mancavano i dati anagrafici
# richiesti dalla normativa pubblicitaria. Compilati quelli, il redirect
# funziona e i codici programma tornano al loro posto. Collaudato: la rotta
# FCO-RAK atterra su aviasales.com con marker=772942 e identificativo di clic.
TP_P_FLIGHT  = '4114'            # Aviasales
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
TP_P_ACT     = '4110'            # Klook — collaudato: la ricerca "Marrakech"
TP_C_ACT     = '137'             # atterra con aff_pid=772942 attaccato
TP_ACT_URL   = 'https://www.klook.com/search/result/?query={city}&search_scope=main_search'
# Travelpayouts Drive — lo script con cui il circuito verifica il sito. Vive
# dietro il banner di consenso insieme alla pubblicita': si carica solo dopo un
# si' esplicito. Svuota questa riga per toglierlo del tutto.
TP_DRIVE_URL = 'https://emrldtp.com/NTY5ODA5.js?t=569809'

ADS_CLIENT = ''
ADS_SLOT   = ''


# La radice non descrive piu' il motore ma la piattaforma: se le due pagine
# avessero la stessa descrizione Google ne sceglierebbe una e scarterebbe
# l'altra come doppione.
DESC_HOME = ("Efficiency Life misura quanto ottieni per quanto spendi. Flight, il primo "
             "modulo, ordina migliaia di tariffe aeree reali per chilometri per euro: "
             "tu fissi il budget, il motore trova fin dove puo' portarti.")
DESC = ("Efficiency Life Flight ordina migliaia di tariffe aeree reali per chilometri "
        "per euro invece che per prezzo: scegli l'aeroporto di partenza, la destinazione "
        "la trova il motore.")
# L'eta in linea resta per i browser moderni, ma NON basta: Google mostra
# l'icona accanto al risultato solo se Googlebot-Image riesce a SCARICARE un
# file, e un data: URI non e' un file da scaricare. In piu' l'SVG non e' fra i
# formati che accetta (BMP, GIF, ICO, PNG, JPEG, PPM, TIFF). Da qui i file
# veri in public/: favicon.ico, icon-192.png, apple-touch-icon.png. Senza,
# nei risultati compare il mappamondo grigio.
FAVICON = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='4' fill='%2303070E'/><path d='M6.4 8.6h4.1v2.6c1.6-2 3.9-3.1 6.5-3.1 4.3 0 7.2 2.8 7.2 7.6V30h-4.1V16.4c0-2.9-1.7-4.6-4.4-4.6-2.8 0-5.2 2-5.2 5.4V23H6.4Z' fill='%232E8DFF'/><path d='M3.5 23.9h25' stroke='%235FE3FF' stroke-width='2.2' stroke-linecap='round'/></svg>"


def history_stats(days: int = 90, min_obs: int = 5) -> dict:
    """Riassume lo storico dei prezzi in una mappa rotta -> [n, p10, mediana].

    Ogni notte `fetch_prices.py` aggiunge una riga per rotta in data/history/.
    Qui si guardano gli ultimi tre mesi e si calcolano due numeri per rotta: il
    decimo percentile e la mediana. Servono al sito per dire "questo prezzo e'
    nel 10% piu' basso degli ultimi 90 giorni" — l'unica informazione che
    nessun aggregatore mostra, e che non si puo' copiare in fretta perche' non
    si compra: si accumula una notte alla volta.

    Finche' lo storico e' corto la mappa esce quasi vuota e il sito non mostra
    nulla: meglio niente che una statistica su tre osservazioni.
    """
    d = DATA / 'history'
    if not d.is_dir():
        return {}
    limite = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    serie: dict[str, list[int]] = {}
    for f in sorted(d.glob('*.csv')):
        for ln in f.read_text().splitlines():
            parti = ln.split(',')
            if len(parti) != 4 or parti[0] < limite:
                continue
            try:
                serie.setdefault(f'{parti[1]}-{parti[2]}', []).append(float(parti[3]))
            except ValueError:
                continue
    out = {}
    for rotta, v in serie.items():
        if len(v) < min_obs:
            continue
        v.sort()
        n = len(v)
        p10 = v[max(0, int(round(0.10 * (n - 1))))]
        med = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2
        out[rotta] = [n, p10, med]
    return out


def prose_data() -> dict:
    """Carica e valida la sola fonte dei testi lunghi e delle pagine lingua."""
    data = json.loads(PROSE.read_text())
    locales = data.get('locales', {})
    if set(locales) != set(LANG_CODES):
        missing = sorted(set(LANG_CODES) - set(locales))
        extra = sorted(set(locales) - set(LANG_CODES))
        sys.exit(f'prose.json: lingue mancanti={missing}, inattese={extra}')
    paths, hreflangs = set(), set()
    index_vars = {'fareCount','observed','originCount','destCount','languageCount','currencyCount'}
    allowed_vars = index_vars | {'fxDate'}
    for code in LANG_CODES:
        row = locales[code]
        required = ('name','path','hreflang','locale','dir','consent','indexNote','method','privacy','seo')
        absent = [k for k in required if k not in row]
        if absent:
            sys.exit(f'prose.json: {code} senza {absent}')
        if row['dir'] not in ('ltr','rtl') or len(row['method']) != 10 or len(row['privacy']) != 4:
            sys.exit(f'prose.json: struttura non valida per {code}')
        if set(row['consent']) != {'accept','decline','preferences','body'}:
            sys.exit(f'prose.json: consenso incompleto per {code}')
        if set(row['seo']) != {'title','description'}:
            sys.exit(f'prose.json: SEO incompleta per {code}')
        if row['path'] in paths or row['hreflang'] in hreflangs:
            sys.exit(f'prose.json: percorso o hreflang duplicato per {code}')
        paths.add(row['path']); hreflangs.add(row['hreflang'])
        found_index_vars = set(re.findall(r'\{([a-zA-Z]+)\}', row['indexNote']))
        if found_index_vars != index_vars:
            sys.exit(f'prose.json: segnaposto indice non validi per {code}: {sorted(found_index_vars)}')
        texts = [row['consent']['body'], row['seo']['title'], row['seo']['description']]
        texts += [text for group in ('method','privacy') for cell in row[group] for text in cell]
        found_vars = set().union(*(set(re.findall(r'\{([a-zA-Z]+)\}', text)) for text in texts))
        if not found_vars <= allowed_vars:
            sys.exit(f'prose.json: segnaposto inattesi per {code}: {sorted(found_vars - allowed_vars)}')
        if not any('{fxDate}' in body for _, body in row['method']):
            sys.exit(f'prose.json: data cambi assente dal metodo per {code}')
        for group in ('method','privacy'):
            if any(not isinstance(cell, list) or len(cell) != 2 or not all(cell) for cell in row[group]):
                sys.exit(f'prose.json: riquadro {group} non valido per {code}')
    return data


# ══════════════════════════════════════════════════════════════════════
# IL MODELLO — vive qui, non nel browser
# ══════════════════════════════════════════════════════════════════════
# Prima la curva prezzo-distanza, le scale del punteggio e i pesi stavano
# nel sorgente della pagina: chiunque aprisse "visualizza sorgente" li
# leggeva. Adesso il calcolo si fa qui, una volta a notte, dentro GitHub
# Actions, e alla pagina arrivano soltanto due numeri gia' pronti per riga:
# il prezzo atteso e il punteggio. Il browser ordina e filtra, non modella.
#
# Non e' solo riservatezza: e' anche piu' veloce. Il browser non stima piu'
# una regressione su cinquemila punti a ogni apertura, e non ricalcola il
# punteggio a ogni ricerca.

STAY = [(800, 3, 4), (2000, 5, 7), (4000, 8, 10), (7000, 12, 14), (10**9, 15, 21)]
PESI = {'kmpe': 32, 'deal': 30, 'price': 15, 'minpe': 13, 'itin': 5, 'rel': 5}


def _mediana(v: list) -> float:
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def curva(deals: list) -> tuple[float, float] | None:
    """Legge di potenza p = a * km^b, stimata nei logaritmi.

    Tre passate di potatura con mediana e MAD: un errore di prezzo, che nei
    dati aerei c'e' sempre, altrimenti piega la retta per tutti.
    """
    pts = [(math.log(r['km']), math.log(r['p']))
           for r in deals if r.get('km', 0) > 80 and r.get('p', 0) > 0]
    if len(pts) < 200:
        return None
    uso, a, b = pts, 0.0, 0.0
    for _ in range(3):
        n = len(uso)
        mx = sum(x for x, _ in uso) / n
        my = sum(y for _, y in uso) / n
        sxy = sum((x - mx) * (y - my) for x, y in uso)
        sxx = sum((x - mx) ** 2 for x, _ in uso)
        if not sxx:
            return None
        b = sxy / sxx; a = my - b * mx
        res = [y - (a + b * x) for x, y in pts]
        m = _mediana(res)
        mad = _mediana([abs(r - m) for r in res]) or 1e-9
        taglio = 2.5 * 1.4826 * mad
        nxt = [pt for pt, r in zip(pts, res) if abs(r - m) <= taglio]
        if len(nxt) < 200:
            break
        uso = nxt
    return a, b


def _q(v: list, k: float) -> float:
    v = sorted(v)
    return v[min(len(v) - 1, max(0, round(k * (len(v) - 1))))]


def modello(deals: list, hist: dict) -> dict:
    """Curva, scale e pesi: tutto quello che serve per dare un voto."""
    c = curva(deals)
    a, b = c if c else (0.0, 0.0)
    kmpe, minpe, price, deal = [], [], [], []
    for r in deals:
        if not r.get('p'):
            continue
        atteso = math.exp(a + b * math.log(r['km'])) if c and r['km'] > 0 else 0
        kmpe.append(r['km'] * 2 / r['p']); minpe.append(r['dur'] / r['p'])
        price.append(r['p']); deal.append(atteso / r['p'] if atteso else 1)
    banda = lambda v: [_q(v, .02), _q(v, .98)] if v else [0, 1]
    return {'a': a, 'b': b, 'curva': bool(c), 'pesi': PESI,
            'scale': {'kmpe': banda(kmpe), 'minpe': banda(minpe),
                      'price': banda(price), 'deal': banda(deal)}}


def valuta(deals: list, m: dict, hist: dict) -> None:
    """Scrive su ogni riga il prezzo atteso (x) e il punteggio (sc)."""
    a, b, sc, pesi = m['a'], m['b'], m['scale'], m['pesi']
    tot = sum(pesi.values())

    def nz(v, banda):
        lo, hi = banda
        return 1.0 if hi == lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))

    for r in deals:
        p = r.get('p') or 0
        atteso = math.exp(a + b * math.log(r['km'])) if m['curva'] and r['km'] > 0 and p else 0
        r['x'] = round(atteso) if atteso else 0
        if not p:
            r['sc'] = 0
            continue
        for limite, s1, s2 in STAY:
            if r['km'] <= limite:
                break
        fuori = s1 - r['n'] if r['n'] < s1 else r['n'] - s2 if r['n'] > s2 else 0
        h = hist.get(f"{r['o']}-{r['d']}")
        parti = {'kmpe': nz(r['km'] * 2 / p, sc['kmpe']),
                 'minpe': nz(r['dur'] / p, sc['minpe']),
                 'price': 1 - nz(p, sc['price']),
                 'deal': nz(atteso / p if atteso else 1, sc['deal']),
                 'itin': max(0.0, 1 - fuori / 7),
                 'rel': 1.0 if h and h[0] >= 5 else .8}
        r['sc'] = round(100 * sum(pesi[k] * v for k, v in parti.items()) / tot)


MARCA_A = '/* === MODELLO GENERATO DA build.py — non modificare a mano === */'
MARCA_B = '/* === fine modello generato === */'


def inietta_modello(m: dict) -> bool:
    """Mette le stesse costanti nella funzione Cloudflare.

    Le tariffe in tempo reale non passano da qui: arrivano all'utente
    dall'API attraverso /api/prices, e vanno valutate la'. Stesso modello,
    stesso codice, ma su un server: nel browser non ci arriva comunque.
    """
    f = ROOT / 'functions' / 'api' / 'prices.js'
    if not f.is_file():
        return False
    src = f.read_text()
    if MARCA_A not in src or MARCA_B not in src:
        return False
    blocco = (MARCA_A + '\nconst MODELLO = ' +
              json.dumps(m, separators=(',', ':')) + ';\n' + MARCA_B)
    i, j = src.index(MARCA_A), src.index(MARCA_B) + len(MARCA_B)
    nuovo = src[:i] + blocco + src[j:]
    if nuovo == src:
        return False
    f.write_text(nuovo)
    return True


def main() -> int:
    tpl = (ROOT / 'src' / 'app.html').read_text()
    cat = (DATA / 'catalog.json').read_text()
    idx = (DATA / 'index.json').read_text()
    wld = (DATA / 'world.json').read_text()
    i18 = (ROOT / 'src' / 'i18n.js').read_text()
    prose_obj = prose_data()
    prose = json.dumps(prose_obj, ensure_ascii=False, separators=(',', ':'))
    # Il motore non ha piu' le schede di Metodo e Trasparenza: da quando sono
    # passate sulla home, di questi testi gli servono solo il banner del
    # consenso e il titolo. Le duemila parole per trentasei lingue le portava
    # in giro per niente — cinquanta kilobyte compressi su ogni apertura.
    prose_motore = json.dumps(
        {**prose_obj,
         'locales': {c: {'consent': r['consent'], 'seo': {'title': r['seo']['title']}}
                     for c, r in prose_obj['locales'].items()}},
        ensure_ascii=False, separators=(',', ':'))
    storico = history_stats()
    hist = json.dumps(storico, separators=(',', ':'))

    # Il modello si stima qui e i suoi due risultati — prezzo atteso e
    # punteggio — entrano nella pagina come numeri. La formula no.
    dati = json.loads(idx)
    M = modello(dati['deals'], storico)
    valuta(dati['deals'], M, storico)
    # All date variants use the same model as route representatives. The
    # browser downloads only the selected origins, never the complete archive.
    from flight_data import public_rows
    shard_dir = DIST / 'data' / 'origins'
    shard_dir.mkdir(parents=True, exist_ok=True)
    shards = {}
    for origin in dati.get('shards', {}):
        source = DATA / 'fares' / (origin + '.json')
        if not source.is_file():
            raise ValueError(f'archive missing for {origin}')
        packet = json.loads(source.read_text())
        valuta(packet['deals'], M, storico)
        packet['deals'] = public_rows(packet['deals'])
        content = json.dumps(packet, separators=(',', ':'), allow_nan=False)
        import hashlib
        version = hashlib.sha256(content.encode()).hexdigest()[:16]
        filename = f'{origin}-{version}.json'
        (shard_dir / filename).write_text(content)
        shards[origin] = '/data/origins/' + filename
    # Remove old generations from this build. Cached old HTML falls back to
    # its embedded representatives if an old shard no longer exists.
    wanted = {p.rsplit('/', 1)[-1] for p in shards.values()}
    for path in shard_dir.glob('*.json'):
        if path.name not in wanted:
            path.unlink()
    if shards:
        dati['shards'] = shards
    dati['deals'] = public_rows(dati['deals'])

    # ── quanto indice entra DENTRO la pagina ──────────────────────────
    # Con 1.328 origini l'indice completo pesava 3,1 MB e la pagina apriva in
    # ventitre secondi su un telefono di fascia media: misurato, non temuto.
    # Ma nessuno ha bisogno delle duecento rotte da Novosibirsk mentre parte
    # da Roma. Dentro la pagina restano le origini piu' servite, poche righe
    # ciascuna: bastano alla classifica d'apertura, al nastro e a coprire il
    # caso in cui la rete non risponda. Tutto il resto arriva dallo scomparto
    # dell'aeroporto scelto, che il browser scarica appena cerchi — ed e' il
    # dato completo, con tutte le date.
    INLINE_ORIGINI, INLINE_PER_ORIGINE = 400, 20
    per_origine = {}
    for r in dati['deals']:
        per_origine.setdefault(r['o'], []).append(r)
    # I conteggi mostrati nell'elenco dei paesi devono restare quelli VERI,
    # non quelli delle righe incorporate: si prendono qui, prima di tagliare.
    dati['ndest'] = len({r['d'] for r in dati['deals']})
    luoghi = dati.get('places') or {}
    dcounts = {}
    for r in dati['deals']:
        k = (luoghi.get(r['d']) or {}).get('k')
        if k:
            dcounts[k] = dcounts.get(k, 0) + 1
    dati['dcounts'] = dcounts
    grandi = sorted(per_origine, key=lambda o: -len(per_origine[o]))[:INLINE_ORIGINI]
    dentro = []
    for o in grandi:
        righe = sorted(per_origine[o], key=lambda r: -(r.get('sc') or 0))
        dentro += righe[:INLINE_PER_ORIGINE]
    intere = len(dati['deals'])
    dati['deals'] = dentro
    idx = json.dumps(dati, separators=(',', ':'))
    print(f"indice nella pagina: {len(dentro):,} righe di {intere:,} "
          f"({len(grandi)} origini x {INLINE_PER_ORIGINE}); il resto negli scomparti")
    if M['curva']:
        print(f"curva prezzo-distanza: p ~ {math.exp(M['a']):.2f} * km^{M['b']:.3f}")
    else:
        print('curva non stimabile: prezzo atteso assente su tutte le righe')
    print('modello nella funzione live:',
          'aggiornato' if inietta_modello(M) else 'invariato')

    for name, blob in (('catalog.json', cat), ('index.json', idx),
                       ('world.json', wld), ('i18n.js', i18), ('prose.json', prose)):
        if '</script' in blob.lower():
            sys.exit(f'{name} contiene un tag di chiusura script: mi fermo.')

    body = (tpl.replace('__CATALOG__', cat).replace('__DEALS__', idx)
               .replace('__WORLD__', wld).replace('__I18N__', i18).replace('__PROSE__', prose_motore)
               .replace('__HIST__', hist)
               .replace('__TP_MARKER__', TP_MARKER).replace('__TP_LINK__', TP_LINK)
               .replace('__TP_TRS__', TP_TRS).replace('__TP_CAMPAIGN__', TP_CAMPAIGN)
               .replace('__TP_P_FLIGHT__', TP_P_FLIGHT).replace('__TP_P_HOTEL__', TP_P_HOTEL)
               .replace('__TP_HOTEL_URL__', TP_HOTEL_URL)
               .replace('__TP_P_ACT__', TP_P_ACT).replace('__TP_C_ACT__', TP_C_ACT)
               .replace('__TP_ACT_URL__', TP_ACT_URL)
               .replace('__TP_DRIVE_URL__', TP_DRIVE_URL)
               .replace('__ADS_CLIENT__', ADS_CLIENT).replace('__ADS_SLOT__', ADS_SLOT))
    for ph in ('__CATALOG__', '__DEALS__', '__WORLD__', '__I18N__', '__PROSE__', '__HIST__',
               '__TP_MARKER__', '__TP_LINK__', '__TP_TRS__', '__TP_CAMPAIGN__',
               '__TP_P_FLIGHT__', '__TP_P_HOTEL__', '__TP_HOTEL_URL__',
               '__TP_P_ACT__', '__TP_C_ACT__', '__TP_ACT_URL__',
               '__TP_DRIVE_URL__', '__ADS_CLIENT__', '__ADS_SLOT__'):
        if ph in body:
            sys.exit(f'segnaposto {ph} non sostituito nel template.')

    alternates = '\n'.join(
        f'<link rel="alternate" hreflang="{row["hreflang"]}" href="{SITE}/lang/{row["path"]}/">'
        for row in prose_obj['locales'].values())
    alternates += f'\n<link rel="alternate" hreflang="x-default" href="{SITE}/">'
    og_alternates = '\n'.join(
        f'<meta property="og:locale:alternate" content="{row["locale"]}">'
        for code, row in prose_obj['locales'].items() if code != 'it')

    def testa(titolo: str, descr: str, percorso: str, alt: str, ld: str) -> str:
        """La testa HTML, uguale per le due pagine tranne dove deve differire.

        Canonical e og:url puntano ciascuno alla propria pagina: sono le due
        righe che dicono a Google che / e /flight/ sono due cose diverse e non
        una copia dell'altra. Sbagliarle qui significa vederne sparire una."""
        return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titolo}</title>
<meta name="description" content="{descr}">
<meta name="theme-color" content="#03070E" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#EDF2F8" media="(prefers-color-scheme: light)">
<meta name="color-scheme" content="dark light">
<link rel="canonical" href="{SITE}{percorso}">
{alt}
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192">
<link rel="icon" href="{FAVICON}" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Efficiency Life">
<meta property="og:title" content="{titolo}">
<meta property="og:description" content="{descr}">
<meta property="og:url" content="{SITE}{percorso}">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:locale" content="it_IT">
{og_alternates}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{titolo}">
<meta name="twitter:description" content="{descr}">
<meta name="twitter:image" content="{SITE}/og.png">
<script type="application/ld+json">
{ld}
</script>
<style>html{{color-scheme:dark}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
"""

    def pagina(testa_html: str, corpo: str) -> str:
        out = testa_html + corpo.split('\n', 1)[1] + '\n</body>\n</html>\n'
        return out.replace('<link rel="preconnect"', '</head>\n<body>\n<link rel="preconnect"', 1)

    DIST.mkdir(exist_ok=True)

    # ── il motore, su /flight/ ─────────────────────────────────────────
    # Fino al 9 settembre stava sulla radice. Le hreflang restano puntate
    # alle landing di lingua, che sono la porta d'ingresso del sito.
    ld_flight = (f'{{"@context":"https://schema.org","@type":"WebApplication",'
                 f'"name":"Efficiency Life Flight","applicationCategory":"TravelApplication",'
                 f'"operatingSystem":"Any","url":"{SITE}/flight/","description":"{DESC}",'
                 f'"offers":{{"@type":"Offer","price":"0","priceCurrency":"EUR"}},'
                 f'"isPartOf":{{"@type":"WebSite","name":"Efficiency Life","url":"{SITE}/"}}}}')
    motore = pagina(testa('Efficiency Life Flight', DESC, '/flight/', alternates, ld_flight), body)
    (DIST / 'flight').mkdir(exist_ok=True)
    (DIST / 'flight' / 'index.html').write_text(motore)

    # ── la home di marca, sulla radice ────────────────────────────────
    # Riceve il foglio di stile del motore invece di averne uno suo: una
    # sola sorgente, nessuna deriva fra le due pagine.
    stile = re.search(r'<style>\n(.*?)\n</style>', tpl, re.S)
    if not stile:
        sys.exit('non trovo il blocco <style> in app.html')
    d = json.loads(idx)
    # I numeri della home sono quelli VERI dell'archivio, non quelli delle
    # righe rimaste dentro la pagina del motore dopo il taglio.
    nd = d.get('ndest') or len({r['d'] for r in d['deals']})
    n_tariffe = d.get('offer_count') or len(d['deals'])
    best = max((r['km'] * 2 / r['p'] for r in d['deals'] if r.get('p')), default=0)
    hm = (ROOT / 'src' / 'home.html').read_text()
    hm = (hm.replace('__STYLE__', stile.group(1))
            .replace('__I18N__', i18).replace('__PROSE__', prose)
            .replace('__ST_AIR__', f"{len(d['counts']):,}".replace(',', '.'))
            .replace('__ST_DEST__', f"{nd:,}".replace(',', '.'))
            .replace('__ST_FARE__', f"{n_tariffe:,}".replace(',', '.'))
            .replace('__ST_BEST__', f"{best:.0f} km/€")
            .replace('__OBSERVED__', d['observed'])
            .replace('__ADS_CLIENT__', ADS_CLIENT)
            .replace('__TP_DRIVE_URL__', TP_DRIVE_URL))
    for ph in ('__STYLE__', '__I18N__', '__PROSE__', '__ST_AIR__', '__ST_DEST__',
               '__ST_FARE__', '__ST_BEST__', '__OBSERVED__'):
        if ph in hm:
            sys.exit(f'segnaposto {ph} non sostituito in home.html.')
    ld_home = (f'{{"@context":"https://schema.org","@type":"WebSite",'
               f'"name":"Efficiency Life","url":"{SITE}/","description":"{DESC_HOME}"}}')
    home = pagina(testa('Efficiency Life', DESC_HOME, '/', alternates, ld_home), hm)
    (DIST / 'index.html').write_text(home)

    for f in PUBLIC.iterdir():
        if f.is_file():
            shutil.copy2(f, DIST / f.name)

    nh = len(json.loads(hist))
    print(f"storico: {nh} rotte con almeno 5 rilevazioni negli ultimi 90 giorni")
    print(f"dist/flight/index.html · {len(motore):,} byte · {len(d['deals']):,} tariffe "
          f"· {len(d['counts'])} origini · rilevate il {d['observed']}")
    print(f"dist/index.html (home) · {len(home):,} byte")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
