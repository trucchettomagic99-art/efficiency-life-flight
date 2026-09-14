import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_pages import extract_seo_substance, resolve_page_lastmod


class SeoSubstanceTests(unittest.TestCase):
    def setUp(self):
        # Sample IT page with observation date 2026-09-13
        self.it_sample_2026_09_13 = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Voli economici da Roma (FCO) — le destinazioni col miglior rapporto km/€</title>
<meta name="description" content="Le 156 migliori destinazioni in partenza da Fiumicino, Roma: voli diretti andata e ritorno ordinati per chilometri per euro, non per prezzo. Tariffe reali rilevate il 2026-09-13.">
<meta property="og:description" content="Le 156 migliori destinazioni in partenza da Fiumicino, Roma: voli diretti andata e ritorno ordinati per chilometri per euro, non per prezzo. Tariffe reali rilevate il 2026-09-13.">
<link rel="canonical" href="https://efficiency-life.com/da/fco/">
</head>
<body>
<main class="wrap">
  <h2>Le migliori 12 destinazioni da FCO</h2>
  <div class="tw"><table>
    <tbody>
      <tr><td class="r">01</td><td><span class="dest">Marrakech</span><span class="code">RAK</span></td><td>Marocco</td><td class="n">01/11 – 10/11</td><td class="n p">54.0 €</td><td class="n">4.252</td><td class="n k">78.7</td></tr>
      <tr><td class="r">02</td><td><span class="dest">Yerevan</span><span class="code">EVN</span></td><td>Armenia</td><td class="n">03/12 – 10/12</td><td class="n p">76.0 €</td><td class="n">5.378</td><td class="n k">70.8</td></tr>
    </tbody>
  </table></div>
  <h2>Aeroporti vicini e correlati</h2>
  <div class="near"><a href="https://efficiency-life.com/da/cia/">CIA · Roma</a><a href="https://efficiency-life.com/da/psr/">PSR · Pescara</a></div>
  <p class="note">Tariffe rilevate il 2026-09-13 · voli diretti andata e ritorno · prezzi indicativi.</p>
</main>
</body>
</html>"""

        # Sample IT page with observation date 2026-09-14 (only obs changed)
        self.it_sample_2026_09_14 = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Voli economici da Roma (FCO) — le destinazioni col miglior rapporto km/€</title>
<meta name="description" content="Le 156 migliori destinazioni in partenza da Fiumicino, Roma: voli diretti andata e ritorno ordinati per chilometri per euro, non per prezzo. Tariffe reali rilevate il 2026-09-14.">
<meta property="og:description" content="Le 156 migliori destinazioni in partenza da Fiumicino, Roma: voli diretti andata e ritorno ordinati per chilometri per euro, non per prezzo. Tariffe reali rilevate il 2026-09-14.">
<link rel="canonical" href="https://efficiency-life.com/da/fco/">
</head>
<body>
<main class="wrap">
  <h2>Le migliori 12 destinazioni da FCO</h2>
  <div class="tw"><table>
    <tbody>
      <tr><td class="r">01</td><td><span class="dest">Marrakech</span><span class="code">RAK</span></td><td>Marocco</td><td class="n">01/11 – 10/11</td><td class="n p">54.0 €</td><td class="n">4.252</td><td class="n k">78.7</td></tr>
      <tr><td class="r">02</td><td><span class="dest">Yerevan</span><span class="code">EVN</span></td><td>Armenia</td><td class="n">03/12 – 10/12</td><td class="n p">76.0 €</td><td class="n">5.378</td><td class="n k">70.8</td></tr>
    </tbody>
  </table></div>
  <h2>Aeroporti vicini e correlati</h2>
  <div class="near"><a href="https://efficiency-life.com/da/cia/">CIA · Roma</a><a href="https://efficiency-life.com/da/psr/">PSR · Pescara</a></div>
  <p class="note">Tariffe rilevate il 2026-09-14 · voli diretti andata e ritorno · prezzi indicativi.</p>
</main>
</body>
</html>"""

        # Sample EN page with observation date 2026-09-13
        self.en_sample_2026_09_13 = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cheap flights from Rome (FCO) — best destinations by km per euro</title>
<meta name="description" content="The 156 best destinations departing from Fiumicino, Rome: non-stop return flights ranked by kilometres per euro, not by price. Real fares observed on 2026-09-13.">
<meta property="og:description" content="The 156 best destinations departing from Fiumicino, Rome: non-stop return flights ranked by kilometres per euro, not by price. Real fares observed on 2026-09-13.">
<link rel="canonical" href="https://efficiency-life.com/from/fco/">
</head>
<body>
<main class="wrap">
  <h2>The top 12 destinations from FCO</h2>
  <div class="tw"><table>
    <tbody>
      <tr><td class="r">01</td><td><span class="dest">Marrakech</span><span class="code">RAK</span></td><td>Morocco</td><td class="n">01/11 – 10/11</td><td class="n p">54.0 €</td><td class="n">4.252</td><td class="n k">78.7</td></tr>
      <tr><td class="r">02</td><td><span class="dest">Yerevan</span><span class="code">EVN</span></td><td>Armenia</td><td class="n">03/12 – 10/12</td><td class="n p">76.0 €</td><td class="n">5.378</td><td class="n k">70.8</td></tr>
    </tbody>
  </table></div>
  <h2>Nearby and related airports</h2>
  <div class="near"><a href="https://efficiency-life.com/from/cia/">CIA · Rome</a><a href="https://efficiency-life.com/from/psr/">PSR · Pescara</a></div>
  <p class="note">Fares observed on 2026-09-13 · round-trip direct flights · indicative prices.</p>
</main>
</body>
</html>"""

        # Sample EN page with observation date 2026-09-14 (only obs changed)
        self.en_sample_2026_09_14 = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cheap flights from Rome (FCO) — best destinations by km per euro</title>
<meta name="description" content="The 156 best destinations departing from Fiumicino, Rome: non-stop return flights ranked by kilometres per euro, not by price. Real fares observed on 2026-09-14.">
<meta property="og:description" content="The 156 best destinations departing from Fiumicino, Rome: non-stop return flights ranked by kilometres per euro, not by price. Real fares observed on 2026-09-14.">
<link rel="canonical" href="https://efficiency-life.com/from/fco/">
</head>
<body>
<main class="wrap">
  <h2>The top 12 destinations from FCO</h2>
  <div class="tw"><table>
    <tbody>
      <tr><td class="r">01</td><td><span class="dest">Marrakech</span><span class="code">RAK</span></td><td>Morocco</td><td class="n">01/11 – 10/11</td><td class="n p">54.0 €</td><td class="n">4.252</td><td class="n k">78.7</td></tr>
      <tr><td class="r">02</td><td><span class="dest">Yerevan</span><span class="code">EVN</span></td><td>Armenia</td><td class="n">03/12 – 10/12</td><td class="n p">76.0 €</td><td class="n">5.378</td><td class="n k">70.8</td></tr>
    </tbody>
  </table></div>
  <h2>Nearby and related airports</h2>
  <div class="near"><a href="https://efficiency-life.com/from/cia/">CIA · Rome</a><a href="https://efficiency-life.com/from/psr/">PSR · Pescara</a></div>
  <p class="note">Fares observed on 2026-09-14 · round-trip direct flights · indicative prices.</p>
</main>
</body>
</html>"""

    def test_obs_date_only_preserves_substance_it(self):
        s1 = extract_seo_substance(self.it_sample_2026_09_13)
        s2 = extract_seo_substance(self.it_sample_2026_09_14)
        self.assertEqual(s1, s2)
        lm = resolve_page_lastmod(self.it_sample_2026_09_13, self.it_sample_2026_09_14, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-04')

    def test_obs_date_only_preserves_substance_en(self):
        s1 = extract_seo_substance(self.en_sample_2026_09_13)
        s2 = extract_seo_substance(self.en_sample_2026_09_14)
        self.assertEqual(s1, s2)
        lm = resolve_page_lastmod(self.en_sample_2026_09_13, self.en_sample_2026_09_14, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-04')

    def test_price_change_updates_substance_and_lastmod(self):
        modified = self.it_sample_2026_09_14.replace('54.0 €', '39.0 €')
        self.assertNotEqual(extract_seo_substance(self.it_sample_2026_09_13), extract_seo_substance(modified))
        lm = resolve_page_lastmod(self.it_sample_2026_09_13, modified, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-14')

    def test_ranking_change_updates_substance_and_lastmod(self):
        modified = self.it_sample_2026_09_14.replace('<td class="r">01</td>', '<td class="r">02-tmp</td>')
        modified = modified.replace('<td class="r">02</td>', '<td class="r">01</td>')
        modified = modified.replace('<td class="r">02-tmp</td>', '<td class="r">02</td>')
        self.assertNotEqual(extract_seo_substance(self.it_sample_2026_09_13), extract_seo_substance(modified))
        lm = resolve_page_lastmod(self.it_sample_2026_09_13, modified, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-14')

    def test_destination_change_updates_substance_and_lastmod(self):
        modified = self.it_sample_2026_09_14.replace('Marrakech', 'Casablanca').replace('RAK', 'CMN')
        self.assertNotEqual(extract_seo_substance(self.it_sample_2026_09_13), extract_seo_substance(modified))
        lm = resolve_page_lastmod(self.it_sample_2026_09_13, modified, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-14')

    def test_related_airports_change_updates_substance_and_lastmod(self):
        modified = self.it_sample_2026_09_14.replace(
            '<div class="near"><a href="https://efficiency-life.com/da/cia/">CIA · Roma</a><a href="https://efficiency-life.com/da/psr/">PSR · Pescara</a></div>',
            '<div class="near"><a href="https://efficiency-life.com/da/cia/">CIA · Roma</a><a href="https://efficiency-life.com/da/nap/">NAP · Napoli</a></div>'
        )
        self.assertNotEqual(extract_seo_substance(self.it_sample_2026_09_13), extract_seo_substance(modified))
        lm = resolve_page_lastmod(self.it_sample_2026_09_13, modified, '2026-09-04', '2026-09-14')
        self.assertEqual(lm, '2026-09-14')

    def test_home_and_flight_lastmod_resolution(self):
        home_v1 = '<html><body><h1>Efficiency Life</h1><div>Deals: 7,752</div><script>const OBSERVED="2026-09-13";</script></body></html>'
        home_v2 = '<html><body><h1>Efficiency Life</h1><div>Deals: 7,752</div><script>const OBSERVED="2026-09-14";</script></body></html>'
        home_v3_modified = '<html><body><h1>Efficiency Life</h1><div>Deals: 7,800</div><script>const OBSERVED="2026-09-14";</script></body></html>'

        # Only observation date changed -> old lastmod preserved
        self.assertEqual(resolve_page_lastmod(home_v1, home_v2, '2026-09-04', '2026-09-14'), '2026-09-04')
        # Substantive content changed -> updated to new obs
        self.assertEqual(resolve_page_lastmod(home_v1, home_v3_modified, '2026-09-04', '2026-09-14'), '2026-09-14')


if __name__ == '__main__':
    unittest.main()
