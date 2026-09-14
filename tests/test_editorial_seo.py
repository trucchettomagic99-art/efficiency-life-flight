import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(ROOT))
import scripts.build as B
import scripts.build_pages as BP


class EditorialSeoTests(unittest.TestCase):
    def test_prose_validation(self):
        """Verify that prose_data() validates cleanly with title, h1, description for all 36 locales."""
        data = B.prose_data()
        locales = data["locales"]
        self.assertEqual(len(locales), 36)
        for code, loc in locales.items():
            seo = loc["seo"]
            self.assertIn("title", seo)
            self.assertIn("description", seo)
            self.assertIn("h1", seo)
            self.assertTrue(len(seo["title"]) > 10, f"Title too short for {code}")
            self.assertTrue(len(seo["description"]) > 20, f"Description too short for {code}")
            self.assertTrue(len(seo["h1"]) > 5, f"H1 too short for {code}")

    def test_home_page_seo(self):
        """Verify Home page title, h1, tagline, description, and canonical."""
        home_html = (DIST / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Migliori voli qualità-prezzo | Efficiency Life</title>", home_html)
        self.assertIn('content="Trova i voli con il miglior rapporto qualità-prezzo. Efficiency Life confronta migliaia di voli diretti andata e ritorno e li ordina per valore reale: scopri dove il tuo budget ti porta più lontano."', home_html)
        self.assertIn('<h1 class="h1">Trova i voli con il miglior rapporto qualità-prezzo</h1>', home_html)
        self.assertIn('Quanto ottieni,', home_html)
        self.assertIn('diviso quanto spendi.', home_html)
        self.assertIn('<link rel="canonical" href="https://efficiency-life.com/">', home_html)
        self.assertNotIn('<meta name="keywords"', home_html)

    def test_flight_page_seo(self):
        """Verify /flight/ page title, description, and canonical."""
        flight_html = (DIST / "flight" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Trova voli diretti per budget e km/€ | Efficiency Life Flight</title>", flight_html)
        self.assertIn('content="Trova voli diretti per budget e km/€ con Efficiency Life Flight: imposta l\'aeroporto di partenza e scopri le migliori offerte ordinate per valore reale."', flight_html)
        self.assertIn('<link rel="canonical" href="https://efficiency-life.com/flight/">', flight_html)
        self.assertNotIn('<meta name="keywords"', flight_html)

    def test_all_36_language_landings_seo(self):
        """Verify all 36 language landings have matching title, h1, meta description, and valid canonical."""
        prose = json.loads((SRC / "prose.json").read_text(encoding="utf-8"))
        for code, loc in prose["locales"].items():
            path = loc["path"]
            page_file = DIST / "lang" / path / "index.html"
            self.assertTrue(page_file.is_file(), f"Missing landing for {code}: {page_file}")
            content = page_file.read_text(encoding="utf-8")

            expected_title = loc["seo"]["title"]
            expected_h1 = loc["seo"]["h1"]
            expected_desc = loc["seo"]["description"]
            expected_canonical = f"https://efficiency-life.com/lang/{path}/"

            self.assertIn(f"<title>{BP.esc(expected_title)}</title>", content, f"Title mismatch in {code}")
            self.assertIn(f"<h1>{BP.esc(expected_h1)}</h1>", content, f"H1 mismatch in {code}")
            self.assertIn(f'content="{BP.esc(expected_desc)}"', content, f"Meta description mismatch in {code}")
            self.assertIn(f'<link rel="canonical" href="{expected_canonical}">', content, f"Canonical mismatch in {code}")
            self.assertNotIn('<meta name="keywords"', content)

    def test_airport_pages_italian_and_english(self):
        """Verify /da/{iata}/ and /from/{iata}/ titles, h1s, and descriptions."""
        # FCO
        fco_it = (DIST / "da" / "fco" / "index.html").read_text(encoding="utf-8")
        fco_en = (DIST / "from" / "fco" / "index.html").read_text(encoding="utf-8")

        self.assertIn("Migliori voli da Fiumicino, Roma per rapporto qualità-prezzo | FCO", fco_it)
        self.assertIn("<h1>I voli da Fiumicino, Roma con il miglior rapporto qualità-prezzo</h1>", fco_it)
        self.assertRegex(fco_it, r'<meta name="description" content="Le \d+ migliori destinazioni da Fiumicino, Roma: voli diretti ordinati per rapporto qualità-prezzo e chilometri per euro, non solo per prezzo\. Tariffe reali rilevate il \d{4}-\d{2}-\d{2}\.">')

        self.assertIn("Best-value flights from Fiumicino", fco_en)
        self.assertIn("FCO", fco_en)
        self.assertIn("<h1>Best-value flights from Fiumicino", fco_en)
        self.assertRegex(fco_en, r'<meta name="description" content="The \d+ best destinations from Fiumicino[^:]*: non-stop return flights ranked by real value and kilometres per euro, not just lowest price\. Real fares observed on \d{4}-\d{2}-\d{2}\.">')

        # No double escaping in airport pages
        self.assertNotIn("&amp;amp;", fco_it)
        self.assertNotIn("&amp;amp;", fco_en)
        self.assertNotIn('<meta name="keywords"', fco_it)
        self.assertNotIn('<meta name="keywords"', fco_en)

    def test_sitemap_url_count(self):
        """Verify sitemap count remains exactly 1354 URLs."""
        sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
        urls = re.findall(r'<loc>(.*?)</loc>', sitemap)
        self.assertEqual(len(urls), 1354, f"Expected 1354 URLs, found {len(urls)}")


if __name__ == '__main__':
    unittest.main()
