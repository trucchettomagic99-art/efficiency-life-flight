#!/usr/bin/env python3
"""Genera public/og.png — l'anteprima che si vede quando il link viene condiviso.

Perche' esiste questo script e non un'immagine disegnata a mano: quella che
c'era prima era dipinta pixel per pixel con numeri scritti dentro il codice, e
il 10 settembre mostrava una tariffa **che non esisteva** (Bergamo-Lisbona a
38 EUR e 103,7 km/€, quando la piu' economica in archivio era 58 EUR e 59,4
km/€), il titolo vecchio del sito e "21.900+ tariffe osservate" dove le
tariffe erano trecentosessantamila. Su un sito che promette "nessun prezzo e'
stimato o generato", l'unica immagine che la gente vede prima di entrare
conteneva un prezzo inventato.

Qui i numeri e l'esempio arrivano da data/index.json e il titolo da
src/i18n.js: non possono discostarsi dal sito, perche' sono lo stesso dato.
Gira nel flusso notturno, quindi non puo' nemmeno invecchiare.

    python scripts/genera_og.py [--font-css percorso.css]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
USCITA = ROOT / 'public' / 'og.png'


def testi_it() -> dict:
    """Le stesse stringhe che il sito mostra in italiano, lette dal vocabolario."""
    src = (ROOT / 'src' / 'i18n.js').read_text(encoding='utf-8')
    keys = json.loads('[' + re.search(r'const KEYS = \[(.*?)\];', src, re.S).group(1) + ']')
    riga = re.search(r'^it:(\[.*?\]),?$', src, re.M).group(1)
    vals = json.loads(riga)
    return dict(zip(keys, vals))


MESI = ('gen', 'feb', 'mar', 'apr', 'mag', 'giu',
        'lug', 'ago', 'set', 'ott', 'nov', 'dic')
MESI_LUNGHI = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
               'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')


def data_breve(iso: str) -> str:
    a, m, g = (int(x) for x in iso.split('-'))
    return f'{g} {MESI[m - 1]}'


def data_lunga(iso: str) -> str:
    a, m, g = (int(x) for x in iso.split('-'))
    return f'{g} {MESI_LUNGHI[m - 1]} {a}'


def numeri() -> dict:
    idx = json.loads((DATA / 'index.json').read_text(encoding='utf-8'))
    deals = idx['deals']
    luoghi = idx.get('places', {})

    # L'esempio dev'essere una tariffa VERA e ancora credibile fra qualche
    # giorno, perche' le anteprime restano in cache sui social per settimane.
    # Quindi: solo le cinquanta origini piu' servite, prezzo dai venti euro in
    # su (sotto ci sono gli errori di prezzo della fonte) e almeno tre
    # rilevazioni sulla stessa rotta, cosi' non finisce in vetrina un lampo
    # visto una volta sola. Fra quelle, il miglior km/euro: e' esattamente cio'
    # che il sito classifica.
    per_origine: dict[str, int] = {}
    for r in deals:
        per_origine[r['o']] = per_origine.get(r['o'], 0) + 1
    grandi = set(sorted(per_origine, key=lambda o: -per_origine[o])[:50])
    candidate = [r for r in deals
                 if r['o'] in grandi and r.get('p', 0) >= 20 and r.get('km', 0) > 0
                 and (r.get('n') or 0) >= 3]
    if not candidate:
        sys.exit('nessuna tariffa adatta come esempio')
    ex = max(candidate, key=lambda r: r['km'] * 2 / r['p'])

    def nome(iata: str) -> str:
        return (luoghi.get(iata) or {}).get('n') or iata

    quando = data_breve(ex['dep'])
    if ex.get('ret'):
        quando += ' – ' + data_breve(ex['ret'])

    mille = lambda n: f'{n:,}'.replace(',', '.')
    return {
        'osservate': data_lunga(idx['observed']),
        'origini': mille(len(idx['counts'])),
        'destinazioni': mille(idx.get('ndest') or len({r['d'] for r in deals})),
        'tariffe': mille(idx.get('offer_count') or len(deals)),
        'ex_da': f"{nome(ex['o'])} ({ex['o']})",
        'ex_a': f"{nome(ex['d'])} ({ex['d']})",
        'ex_km': mille(ex['km'] * 2),
        'ex_quando': quando,
        'ex_prezzo': f"{round(ex['p'])} €",
        'ex_kmpe': f"{ex['km'] * 2 / ex['p']:.1f}".replace('.', ',') + ' km/€',
    }


PAGINA = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400;700&display=swap">
<style>
*{box-sizing:border-box}
html,body{margin:0;width:1200px;height:630px;overflow:hidden}
body{background:#03070E;color:#EAF2FB;font-family:"IBM Plex Sans",system-ui,sans-serif;
  position:relative}
/* lo stesso alone del sito dietro il globo */
.alone{position:absolute;right:-120px;top:-40px;width:760px;height:760px;border-radius:50%;
  background:radial-gradient(circle,rgba(46,141,255,.20),rgba(46,141,255,0) 62%)}
.dentro{position:relative;padding:44px 56px}
.testa{display:flex;align-items:center;gap:22px}
.marchio{display:flex;align-items:center;gap:12px;font-family:Archivo,sans-serif;font-weight:800;
  font-size:27px;letter-spacing:.12em;text-transform:uppercase;white-space:nowrap}
.marchio u{text-decoration:none;color:#66809D;font-weight:500}
.mods{display:flex;gap:4px;margin-left:6px}
.mod{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:#66809D;padding:5px 12px;border:1px solid transparent;border-radius:2px}
.mod.on{color:#EAF2FB;border-color:rgba(120,170,235,.36);background:rgba(46,141,255,.14);
  box-shadow:inset 0 -2px 0 #2E8DFF}
.occhiello{margin-top:52px;font-family:"JetBrains Mono",monospace;font-size:13px;
  letter-spacing:.18em;text-transform:uppercase;color:#2E8DFF}
h1{font-family:Archivo,sans-serif;font-weight:800;font-size:60px;line-height:.96;
  letter-spacing:-.035em;text-transform:uppercase;margin:16px 0 0;max-width:15ch}
h1 s{text-decoration:none;display:block;color:#2E8DFF}
.lede{margin:20px 0 0;max-width:46ch;font-size:19px;line-height:1.45;color:#9EB3CC}
.numeri{position:absolute;left:56px;bottom:44px;display:flex;gap:0;
  border:1px solid rgba(120,170,235,.16)}
.n{padding:14px 24px;border-right:1px solid rgba(120,170,235,.16)}
.n:last-child{border-right:0}
.n b{display:block;font-family:"JetBrains Mono",monospace;font-weight:700;font-size:27px;
  letter-spacing:-.01em}
.n span{display:block;margin-top:3px;font-family:"JetBrains Mono",monospace;font-size:10px;
  letter-spacing:.14em;text-transform:uppercase;color:#66809D}
/* la tariffa d'esempio: e' una riga vera dell'indice di stanotte */
.esempio{position:absolute;right:56px;bottom:44px;width:430px;background:#071120;
  border:1px solid rgba(120,170,235,.36);border-left:3px solid #FF2E46;padding:18px 22px}
.esempio .rotta{font-family:Archivo,sans-serif;font-weight:700;font-size:19px;letter-spacing:-.01em}
.esempio .sotto{margin-top:5px;font-family:"JetBrains Mono",monospace;font-size:11.5px;
  letter-spacing:.06em;color:#66809D}
.esempio .riga{margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.esempio .prezzo{font-family:"JetBrains Mono",monospace;font-weight:700;font-size:30px;color:#2E8DFF}
.esempio .tag{font-family:"JetBrains Mono",monospace;font-size:12px;letter-spacing:.06em;
  color:#5FE3FF;border:1px solid rgba(120,170,235,.36);padding:5px 10px;white-space:nowrap}
</style></head><body>
<div class="alone"></div>
<div class="dentro">
  <div class="testa">
    <div class="marchio">
      <svg width="34" height="34" viewBox="0 0 32 32"><path d="M6.4 8.6h4.1v2.6c1.6-2 3.9-3.1 6.5-3.1 4.3 0 7.2 2.8 7.2 7.6V30h-4.1V16.4c0-2.9-1.7-4.6-4.4-4.6-2.8 0-5.2 2-5.2 5.4V23H6.4Z" fill="#2E8DFF"/><path d="M3 23.9h26" stroke="#5FE3FF" stroke-width="1.9" stroke-linecap="round" opacity=".55"/></svg>
      Efficiency <u>Life</u>
    </div>
    <div class="mods">
      <span class="mod on">Flight</span><span class="mod">Stay</span><span class="mod">Rail</span>
      <span class="mod">Drive</span><span class="mod">Energy</span>
    </div>
  </div>
  <div class="occhiello">{OCCHIELLO}</div>
  <h1>{H1A}<s>{H1B}</s></h1>
  <p class="lede">{LEDE}</p>
</div>
<div class="numeri">
  <div class="n"><b>{ORIGINI}</b><span>{L_AIR}</span></div>
  <div class="n"><b>{DESTINAZIONI}</b><span>{L_DEST}</span></div>
  <div class="n"><b>{TARIFFE}</b><span>{L_FARE}</span></div>
  <div class="n"><b>36</b><span>Lingue</span></div>
</div>
<div class="esempio">
  <div class="rotta">{EX_DA} → {EX_A}</div>
  <div class="sotto">{EX_KM} KM A/R · {L_DIRETTO} · {EX_QUANDO}</div>
  <div class="riga"><span class="prezzo">{EX_PREZZO}</span>
    <span class="tag">{EX_KMPE}</span></div>
</div>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--font-css', help='foglio con i caratteri incorporati, per girare senza rete')
    args = ap.parse_args()

    t, n = testi_it(), numeri()
    html = PAGINA
    for chiave, valore in {
        '{OCCHIELLO}': f"{t['obs']} {n['osservate']} · {t['direct']}",
        '{H1A}': t['h1a'], '{H1B}': t['h1b'], '{LEDE}': t['lede'],
        '{ORIGINI}': n['origini'], '{DESTINAZIONI}': n['destinazioni'], '{TARIFFE}': n['tariffe'],
        '{L_AIR}': t['st_air'], '{L_DEST}': t['st_dest'], '{L_FARE}': t['st_fare'],
        '{L_DIRETTO}': t['direct'],
        '{EX_DA}': n['ex_da'], '{EX_A}': n['ex_a'], '{EX_KM}': n['ex_km'],
        '{EX_QUANDO}': n['ex_quando'],
        '{EX_PREZZO}': n['ex_prezzo'], '{EX_KMPE}': n['ex_kmpe'],
    }.items():
        html = html.replace(chiave, str(valore))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('serve playwright: pip install playwright')

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1200, 'height': 630}, device_scale_factor=1)
        page.set_content(html, wait_until='load')
        if args.font_css:
            page.add_style_tag(content=pathlib.Path(args.font_css).read_text(encoding='utf-8'))
        # I caratteri arrivano dopo il markup: senza questa attesa lo scatto
        # esce con il ripiego di sistema e le righe vanno a capo dove capita.
        try:
            page.wait_for_function('document.fonts.status === "loaded"', timeout=15000)
        except Exception:
            print('avviso: i caratteri non si sono caricati, scatto col ripiego')
        page.wait_for_timeout(400)
        USCITA.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(USCITA), clip={'x': 0, 'y': 0, 'width': 1200, 'height': 630})
        browser.close()

    print(f"public/og.png · {USCITA.stat().st_size/1024:.0f} KB · esempio reale "
          f"{n['ex_da']} → {n['ex_a']} a {n['ex_prezzo']} ({n['ex_kmpe']})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
