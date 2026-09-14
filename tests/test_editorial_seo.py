"""Collaudo SEO per proprieta', non per frasi.

La versione del 14 settembre 2026 confrontava le stringhe esatte: bastava
cambiare una virgola nel titolo della home perche' la pipeline si fermasse, e
il numero di indirizzi in sitemap era inchiodato a 1354 — cioe' aggiungere un
aeroporto rompeva il collaudo di una cosa che stava funzionando.

Qui si verifica invece cosa deve essere sempre vero, qualunque parola si
scelga: un solo H1, un canonical che punta all'indirizzo giusto, hreflang
reciproci, nessun noindex dove serve indicizzare, l'intento di ricerca
presente nella lingua della pagina, nessun nome ripetuto come
"Abakan Airport, Abakan Airport", e una sitemap che elenca esattamente le
pagine generate — ne' una di piu' ne' una di meno.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SRC = ROOT / "src"

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(ROOT))
import scripts.build as B          # noqa: E402
import scripts.build_pages as BP   # noqa: E402

SITE = "https://efficiency-life.com"
INTENTO = {'it': ('voli', 'volo'), 'en': ('flight', 'flights')}


def testo(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def uno(pattern: str, html: str, nome: str, test):
    trovati = re.findall(pattern, html, re.S)
    test.assertEqual(len(trovati), 1, f"{nome}: attesi 1, trovati {len(trovati)}")
    return trovati[0]


def titolo(html): return re.search(r'<title>(.*?)</title>', html, re.S).group(1)
def descrizione(html): return re.search(r'<meta name="description" content="(.*?)">', html, re.S).group(1)
def canonical(html): return re.search(r'<link rel="canonical" href="(.*?)">', html).group(1)


class ProprietaComuni:
    """Le regole che devono valere su ogni pagina indicizzabile."""

    def controlla_pagina(self, path: Path, url: str, lang: str):
        html = testo(path)
        con = f"{path.relative_to(DIST)}"

        # un solo H1, non vuoto
        h1 = uno(r'<h1[^>]*>(.*?)</h1>', html, f"{con}: H1", self)
        self.assertTrue(h1.strip(), f"{con}: H1 vuoto")

        # title e description presenti e sensati
        self.assertTrue(10 < len(titolo(html)) < 140, f"{con}: title fuori misura")
        self.assertTrue(50 < len(descrizione(html)) < 340, f"{con}: description fuori misura")

        # canonical esatto, e uno solo
        uno(r'<link rel="canonical"[^>]*>', html, f"{con}: canonical", self)
        self.assertEqual(canonical(html), url, f"{con}: canonical sbagliato")

        # niente noindex, niente keywords, lingua dichiarata
        self.assertNotIn('noindex', html, f"{con}: la pagina si esclude da sola")
        self.assertNotIn('<meta name="keywords"', html, f"{con}: meta keywords")
        self.assertIn(f'<html lang="{lang}"', html, f"{con}: lingua non dichiarata")

        # niente doppia escape di entita'
        self.assertNotIn('&amp;amp;', html, f"{con}: doppia escape")
        return html


class PagineAeroporto(ProprietaComuni, unittest.TestCase):
    CAMPIONE = ('fco', 'cia', 'lhr', 'edi', 'jfk', 'mxp', 'bgy', 'cpt')

    def pagine(self, quante=None):
        for lang, cartella in (('it', 'da'), ('en', 'from')):
            trovate = sorted((DIST / cartella).glob('*/index.html'))
            for p in (trovate[:quante] if quante else trovate):
                yield lang, cartella, p.parent.name, p

    def test_ogni_pagina_aeroporto_rispetta_le_regole(self):
        for lang, cartella, iata, p in self.pagine():
            with self.subTest(pagina=f'{cartella}/{iata}'):
                self.controlla_pagina(p, f'{SITE}/{cartella}/{iata}/', lang)

    def test_hreflang_reciproco_fra_le_due_lingue(self):
        for lang, cartella, iata, p in self.pagine():
            html = testo(p)
            altra = 'from' if cartella == 'da' else 'da'
            with self.subTest(pagina=f'{cartella}/{iata}'):
                self.assertIn(f'<link rel="alternate" hreflang="{lang}" href="{SITE}/{cartella}/{iata}/">', html)
                altro_lang = 'en' if lang == 'it' else 'it'
                self.assertIn(f'<link rel="alternate" hreflang="{altro_lang}" href="{SITE}/{altra}/{iata}/">', html)
                self.assertIn('hreflang="x-default"', html)

    def test_intento_di_ricerca_presente_nella_lingua_giusta(self):
        """Le uniche query che portano visite sono "voli <citta>" e
        "cheap flights from <citta>": la parola deve esserci, nel titolo."""
        for lang, cartella, iata, p in self.pagine():
            t = titolo(testo(p)).casefold()
            with self.subTest(pagina=f'{cartella}/{iata}'):
                self.assertTrue(any(w in t for w in INTENTO[lang]),
                                f'{cartella}/{iata}: titolo senza intento: {t}')
        # e l'intento economico, nella forma che la gente scrive
        self.assertIn('voli economici', titolo(testo(DIST/'da'/'fco'/'index.html')).casefold())
        self.assertIn('cheap flights', titolo(testo(DIST/'from'/'fco'/'index.html')).casefold())

    def test_il_nome_dello_scalo_non_si_ripete(self):
        """"Abakan Airport, Abakan Airport" non deve poter succedere.

        Si collauda l'etichetta da sola e non l'H1 intero, perche' li' la
        preposizione italiana confonde ("da Da Nang" non e' un doppione).
        Il controllo gira su tutto il catalogo, non sulle sole pagine uscite.
        """
        catalogo = json.loads((ROOT / 'data' / 'catalog.json').read_text(encoding='utf-8'))
        etichette = BP.etichette_scali(catalogo)
        self.assertGreater(len(etichette), 1000)
        generiche = re.compile(r'\b(airports?|aeroporto|aeroport|intl|international)\b', re.I)
        sorgente = {a['i']: f"{a.get('c','')} | {a.get('n','')}".casefold()
                    for a in catalogo['airports']}
        for iata, e in etichette.items():
            with self.subTest(scalo=iata):
                parole = re.sub(r'[(),]', ' ', e).split()
                for a, b in zip(parole, parole[1:]):
                    if a.casefold() == b.casefold():
                        # "Pago Pago" e' un nome vero; il doppione che cerchiamo
                        # e' quello che nasce incollando citta' e aeroporto.
                        self.assertIn(f'{a} {b}'.casefold(), sorgente[iata],
                                      f'{iata}: "{e}" ripete una parola')
                self.assertNotIn(',', e, f'{iata}: "{e}" incollato con la virgola')
                self.assertIsNone(generiche.search(e), f'{iata}: "{e}" contiene una parola generica')
                self.assertTrue(e.strip(), f'{iata}: etichetta vuota')
                self.assertLessEqual(len(e.split()), 6, f'{iata}: "{e}" e una targa, non un nome')

    def test_le_etichette_non_si_ripetono_fra_scali(self):
        catalogo = json.loads((ROOT / 'data' / 'catalog.json').read_text(encoding='utf-8'))
        etichette = BP.etichette_scali(catalogo)
        paese = {a['i']: a.get('k') for a in catalogo['airports']}
        visti = {}
        for iata, e in etichette.items():
            chiave = (e.casefold(), paese.get(iata))
            self.assertNotIn(chiave, visti, f'{iata} e {visti.get(chiave)}: stessa etichetta "{e}"')
            visti[chiave] = iata

    def test_titoli_e_h1_distinti_fra_pagine(self):
        for lang, cartella in (('it', 'da'), ('en', 'from')):
            visti = {}
            for p in sorted((DIST / cartella).glob('*/index.html')):
                t = titolo(testo(p))
                self.assertNotIn(t, visti, f'{cartella}: titolo uguale a {visti.get(t)}: {t}')
                visti[t] = p.parent.name

    def test_citta_nella_lingua_della_pagina(self):
        self.assertIn('Roma Fiumicino', titolo(testo(DIST/'da'/'fco'/'index.html')))
        self.assertIn('Rome Fiumicino', titolo(testo(DIST/'from'/'fco'/'index.html')))
        self.assertIn('Londra Heathrow', titolo(testo(DIST/'da'/'lhr'/'index.html')))
        self.assertIn('London Heathrow', titolo(testo(DIST/'from'/'lhr'/'index.html')))

    def test_la_pagina_dice_cosa_significa_il_valore(self):
        """"Rapporto qualita'-prezzo" non deve far pensare al comfort a bordo."""
        for f, parole in ((DIST/'da'/'fco'/'index.html', ('Efficiency Score', 'chilometri per euro', 'storico')),
                          (DIST/'from'/'fco'/'index.html', ('Efficiency Score', 'kilometres per', 'route history'))):
            html = testo(f)
            for w in parole:
                self.assertIn(w, html, f'{f.parent.name}: manca "{w}"')

    def test_breadcrumb_strutturato_valido(self):
        for lang, cartella, iata, p in self.pagine(quante=40):
            html = testo(p)
            blocchi = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)
            with self.subTest(pagina=f'{cartella}/{iata}'):
                tipi = {}
                for b in blocchi:
                    dato = json.loads(b)          # JSON non valido -> il test fallisce qui
                    tipi[dato['@type']] = dato
                self.assertIn('ItemList', tipi, 'ItemList sparito')
                self.assertIn('BreadcrumbList', tipi, 'BreadcrumbList mancante')
                passi = tipi['BreadcrumbList']['itemListElement']
                self.assertEqual([x['position'] for x in passi], list(range(1, len(passi) + 1)))
                self.assertEqual(passi[0]['item'], f'{SITE}/')
                self.assertEqual(passi[-1]['item'], f'{SITE}/{cartella}/{iata}/')
                for x in passi:
                    self.assertTrue(x['name'].strip())
                    self.assertTrue(x['item'].startswith(SITE))


class PagineDirectory(ProprietaComuni, unittest.TestCase):
    def test_directory_e_continenti(self):
        for lang, radice in (('it', 'aeroporti'), ('en', 'airports')):
            self.controlla_pagina(DIST / radice / 'index.html', f'{SITE}/{radice}/', lang)
            for sub in sorted((DIST / radice).glob('*/index.html')):
                self.controlla_pagina(sub, f'{SITE}/{radice}/{sub.parent.name}/', lang)

    def test_breadcrumb_strutturato_sui_continenti(self):
        for lang, radice in (('it', 'aeroporti'), ('en', 'airports')):
            for sub in sorted((DIST / radice).glob('*/index.html')):
                html = testo(sub)
                dati = [json.loads(b) for b in
                        re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)]
                bc = [d for d in dati if d.get('@type') == 'BreadcrumbList']
                self.assertEqual(len(bc), 1, f'{radice}/{sub.parent.name}: BreadcrumbList')
                self.assertEqual(bc[0]['itemListElement'][-1]['item'],
                                 f'{SITE}/{radice}/{sub.parent.name}/')


class LandingPerLingua(ProprietaComuni, unittest.TestCase):
    def test_trentasei_landing_coerenti_con_prose(self):
        prose = json.loads((SRC / "prose.json").read_text(encoding="utf-8"))['locales']
        self.assertEqual(len(prose), 36)
        for code, loc in prose.items():
            path = loc["path"]
            p = DIST / "lang" / path / "index.html"
            with self.subTest(lingua=code):
                self.assertTrue(p.is_file(), f'manca la landing {code}')
                # la lingua dichiarata e' l'hreflang, non la chiave interna:
                # il filippino sta sotto "tl" in prose.json ma esce come "fil"
                html = self.controlla_pagina(p, f'{SITE}/lang/{path}/', loc['hreflang'])
                # il testo viene da prose.json e da nessun'altra parte
                self.assertIn(BP.esc(loc['seo']['title']), html)
                self.assertIn(BP.esc(loc['seo']['h1']), html)
                self.assertIn(BP.esc(loc['seo']['description']), html)

    def test_prose_ha_titolo_h1_e_descrizione_in_tutte_le_lingue(self):
        locales = B.prose_data()["locales"]
        self.assertEqual(len(locales), 36)
        for code, loc in locales.items():
            seo = loc["seo"]
            self.assertTrue(len(seo.get("title", "")) > 10, code)
            self.assertTrue(len(seo.get("description", "")) > 20, code)
            self.assertTrue(len(seo.get("h1", "")) > 5, code)


class HomeEMotore(unittest.TestCase):
    def test_home_e_motore_hanno_titoli_e_canonical_propri(self):
        home = testo(DIST / "index.html")
        flight = testo(DIST / "flight" / "index.html")
        self.assertEqual(canonical(home), f'{SITE}/')
        self.assertEqual(canonical(flight), f'{SITE}/flight/')
        # due pagine, due descrizioni: se coincidono Google ne scarta una
        self.assertNotEqual(titolo(home), titolo(flight))
        self.assertNotEqual(descrizione(home), descrizione(flight))
        for html in (home, flight):
            self.assertNotIn('<meta name="keywords"', html)
            self.assertNotIn('noindex', html)
            self.assertTrue(10 < len(titolo(html)) < 140)

    def test_h1_della_home_e_traducibile(self):
        """Deve avere l'ancora che applyLang() riscrive: senza, resta italiano
        anche per chi legge in tedesco."""
        home = testo(DIST / "index.html")
        h1 = uno(r'<h1[^>]*>(.*?)</h1>', home, 'home: H1', self)
        self.assertIn('id="homeH1"', home)
        prose = json.loads((SRC / "prose.json").read_text(encoding="utf-8"))['locales']
        self.assertEqual(h1, prose['it']['seo']['h1'],
                         "l'H1 scritto nell'HTML deve essere lo stesso di prose.json['it']")
        sorgente = testo(SRC / 'home.html')
        self.assertIn("$('#homeH1').textContent = p.seo.h1", sorgente)

    def test_cluster_hreflang_completo_sulla_home(self):
        home = testo(DIST / "index.html")
        prose = json.loads((SRC / "prose.json").read_text(encoding="utf-8"))['locales']
        for loc in prose.values():
            self.assertIn(f'hreflang="{loc["hreflang"]}" href="{SITE}/lang/{loc["path"]}/"', home)
        self.assertIn('hreflang="x-default"', home)


class Sitemap(unittest.TestCase):
    def indirizzi(self):
        xml = testo(DIST / "sitemap.xml")
        return re.findall(r'<loc>(.*?)</loc>', xml)

    def pagine_generate(self):
        """Ogni index.html pubblicabile, dedotto da dist/ e non da un numero
        scritto a mano: aggiungere un aeroporto non deve rompere il collaudo."""
        attese = {f'{SITE}/', f'{SITE}/flight/'}
        for cartella in ('da', 'from', 'aeroporti', 'airports'):
            base = DIST / cartella
            if (base / 'index.html').is_file():
                attese.add(f'{SITE}/{cartella}/')
            for p in base.glob('*/index.html'):
                attese.add(f'{SITE}/{cartella}/{p.parent.name}/')
        for p in (DIST / 'lang').glob('*/index.html'):
            attese.add(f'{SITE}/lang/{p.parent.name}/')
        return attese

    def test_sitemap_elenca_esattamente_le_pagine_generate(self):
        elencati, attesi = set(self.indirizzi()), self.pagine_generate()
        self.assertEqual(elencati - attesi, set(), 'in sitemap ma non generate')
        self.assertEqual(attesi - elencati, set(), 'generate ma fuori dalla sitemap')

    def test_nessun_indirizzo_ripetuto(self):
        indirizzi = self.indirizzi()
        self.assertEqual(len(indirizzi), len(set(indirizzi)))

    def test_la_404_resta_fuori_dalla_sitemap_e_si_esclude(self):
        self.assertTrue((DIST / '404.html').is_file())
        self.assertIn('noindex', testo(DIST / '404.html'))
        self.assertNotIn(f'{SITE}/404.html', self.indirizzi())

    def test_ogni_lastmod_e_una_data_valida(self):
        import datetime
        for d in re.findall(r'<lastmod>(.*?)</lastmod>', testo(DIST / 'sitemap.xml')):
            datetime.date.fromisoformat(d)

    def test_la_soglia_delle_pagine_aeroporto_resta_sei(self):
        """MIN_ROUTES e' un patto con Google: sotto sei rotte la pagina e'
        povera e non va pubblicata. Se cambia, deve essere una decisione."""
        self.assertEqual(BP.MIN_ROUTES_FOR_SEO_PAGE, 6)
        self.assertEqual(BP.MIN_ROUTES, 6)


class Robots(unittest.TestCase):
    def test_gli_scomparti_dati_sono_fuori_dalla_scansione(self):
        r = testo(DIST / 'robots.txt')
        self.assertIn('Disallow: /data/', r)
        self.assertIn(f'Sitemap: {SITE}/sitemap.xml', r)

    def test_non_si_bloccano_risorse_che_servono_a_disegnare_la_pagina(self):
        r = testo(DIST / 'robots.txt')
        righe = [x.strip() for x in r.splitlines()
                 if x.strip().lower().startswith('disallow:')]
        self.assertEqual(righe, ['Disallow: /data/'])

    def test_le_pagine_non_prendono_contenuto_da_data(self):
        """Le pagine statiche non devono nemmeno provarci: se una di loro
        scaricasse /data/ per mostrare la classifica, bloccarlo la
        svuoterebbe."""
        for p in (DIST/'da'/'fco'/'index.html', DIST/'from'/'fco'/'index.html',
                  DIST/'lang'/'en'/'index.html', DIST/'aeroporti'/'index.html',
                  DIST/'index.html'):
            html = testo(p)
            self.assertNotIn('/data/', html, f'{p.name} dipende da /data/')
            self.assertNotIn('fetch(', html, f'{p.name} scarica qualcosa')


if __name__ == '__main__':
    unittest.main()
