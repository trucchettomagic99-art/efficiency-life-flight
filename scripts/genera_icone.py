#!/usr/bin/env python3
"""Ridisegna favicon e icone dell'applicazione dal marchio nuovo.

Il marchio di Efficiency Life e' la parola EFFICIE**n**CY in cui la n e' una
eta greca, e la sua gamba destra scende sotto la riga e gira a destra a fare la
**L** di LIFE: un segno solo che lega i due nomi. In un quadrato da sedici
pixel la parola non si legge, quindi l'icona porta solo quel segno — la stessa
curva, lo stesso spessore relativo, lo stesso blu.

Fino al 14 settembre 2026 le icone mostravano il marchio vecchio: la eta
attraversata da una linea orizzontale azzurra. Restava ovunque — scheda del
browser, schermata Home del telefono, segnalibri — mentre il sito aveva gia'
cambiato marchio.

Non gira di notte: le icone cambiano quando cambia il marchio, cioe' quasi
mai. Si lancia a mano dopo aver toccato il disegno:

    python scripts/genera_icone.py

Serve Chromium (playwright) per rasterizzare, e Pillow per il .ico.
"""
from __future__ import annotations
import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUBLIC = ROOT / 'public'

SFONDO = '#03070E'    # --void
SEGNO  = '#2E8DFF'    # --signal

# Lo stesso tracciato del marchio in src/app.html e src/home.html, traslato in
# modo che parta da x=0:
#   M0 42   la gamba sinistra, che sale
#   V16.5   fino sotto la spalla
#   c...    la spalla curva verso destra
#   V78     la gamba destra scende sotto la riga di base
#   h18     e gira: questo e' il piede della L
TRACCIATO = ('M0 42V16.5c0-2.6 2.1-4.5 4.7-4.5h11.6'
             'c6.6 0 11.7 5.2 11.7 11.8V78h18')

# Nel marchio lo spessore e' 8.4. Qui e' un po' piu' grosso: a sedici pixel un
# segno sottile sparisce nell'antialiasing, e la scheda del browser e' il
# posto in cui questa icona si vede piu' spesso.
SPESSORE = 9.6


def svg(lato: int, raggio_rel: float = 0.22) -> str:
    """Il monogramma centrato in un quadrato di `lato` pixel.

    `raggio_rel` a zero da' un quadrato netto: e' quello che vuole Apple, che
    applica la sua maschera per conto suo e su un'icona gia' stondata
    arrotonderebbe due volte.
    """
    s = SPESSORE / 2
    x0, x1 = 0 - s, 46.0          # l'ultimo tratto finisce a 46, estremita' netta
    y0, y1 = 12 - s, 78 + s
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = max(x1 - x0, y1 - y0) * 1.34        # aria attorno al segno
    vx, vy = cx - box / 2, cy - box / 2
    r = round(lato * raggio_rel, 2)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lato}" height="{lato}" '
        f'viewBox="0 0 {lato} {lato}">'
        f'<rect width="{lato}" height="{lato}" rx="{r}" ry="{r}" fill="{SFONDO}"/>'
        f'<svg width="{lato}" height="{lato}" viewBox="{vx:.2f} {vy:.2f} {box:.2f} {box:.2f}">'
        f'<path d="{TRACCIATO}" fill="none" stroke="{SEGNO}" stroke-width="{SPESSORE}" '
        f'stroke-linecap="butt" stroke-linejoin="miter"/>'
        f'</svg></svg>'
    )


# nome del file -> (lato, raggio relativo)
FILE = {
    'favicon-48x48.png':   (48,  0.22),
    'favicon-96x96.png':   (96,  0.22),
    'icon-192.png':        (192, 0.22),
    'icon-512.png':        (512, 0.22),
    'apple-touch-icon.png': (180, 0.0),   # iOS ci mette la sua maschera
}
ICO = (16, 32, 48)


async def disegna(pagina, lato: int, raggio: float, destinazione: pathlib.Path):
    await pagina.set_viewport_size({'width': lato, 'height': lato})
    await pagina.set_content(
        f'<body style="margin:0;background:transparent">{svg(lato, raggio)}</body>')
    await pagina.screenshot(path=str(destinazione), omit_background=True)


async def main() -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print('serve playwright: pip install playwright', file=sys.stderr)
        return 1

    eseguibile = pathlib.Path('/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            **({'executable_path': str(eseguibile)} if eseguibile.is_file() else {}))
        pagina = await (await browser.new_context(device_scale_factor=1)).new_page()

        for nome, (lato, raggio) in FILE.items():
            await disegna(pagina, lato, raggio, PUBLIC / nome)
            print(f'  {nome:22} {lato}x{lato}')

        temporanei = []
        for lato in ICO:
            t = PUBLIC / f'.ico-{lato}.png'
            await disegna(pagina, lato, 0.22, t)
            temporanei.append(t)
        await browser.close()

    from PIL import Image
    fotogrammi = [Image.open(t).convert('RGBA') for t in temporanei]
    fotogrammi[-1].save(PUBLIC / 'favicon.ico', format='ICO',
                        sizes=[(l, l) for l in ICO])
    for t in temporanei:
        t.unlink()
    print(f'  favicon.ico            {ICO}')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
