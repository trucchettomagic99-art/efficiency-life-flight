#!/usr/bin/env python3
"""Controlli di regressione sul sito compilato, senza accesso alla rete."""
from __future__ import annotations

import html
import importlib.util
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'

spec = importlib.util.spec_from_file_location('build_config', ROOT / 'scripts' / 'build.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    locales = B.prose_data()['locales']
    require(len(locales) == 36, f'attese 36 lingue, trovate {len(locales)}')
    i18n = (ROOT / 'src' / 'i18n.js').read_text()
    meta_block = i18n.split('const LANG_META = [', 1)[1].split('];', 1)[0]
    short_codes = set(re.findall(r"\['([a-z]{2})'", meta_block))
    require(short_codes == set(locales),
            f'lingue brevi e testi lunghi non allineati: {sorted(short_codes ^ set(locales))}')

    root_path = DIST / 'index.html'
    require(root_path.is_file(), 'dist/index.html non esiste')
    root = root_path.read_text()
    head = root.split('</head>', 1)[0]
    require(not re.search(r'__[A-Z][A-Z0-9_]*__', root), 'segnaposto non sostituito nella home')
    require('const LANG_ALIAS = Object.freeze({fil:\'tl\'' in root,
            'alias fil-PH → Filipino assente')
    require("navigator.language||'en').slice(0,2)" not in root,
            'rilevamento lingua ancora limitato ai primi due caratteri')
    require(len(re.findall(r'<link rel="alternate" hreflang=', head)) == len(locales) + 1,
            'cluster hreflang incompleto nella home')

    scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', root, flags=re.S | re.I)
    app_script = next((script for script in scripts if '"use strict";' in script), '')
    require(bool(app_script), 'script principale non trovato nella home compilata')
    check = subprocess.run(['node', '--check'], input=app_script, text=True,
                           capture_output=True, check=False)
    require(check.returncode == 0, f'JavaScript non valido:\n{check.stderr}')

    sitemap_path = DIST / 'sitemap.xml'
    require(sitemap_path.is_file(), 'sitemap.xml non esiste')
    xml_root = ET.parse(sitemap_path).getroot()
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = {node.text for node in xml_root.findall('s:url/s:loc', ns)}

    rtl = {code for code, meta in locales.items() if meta['dir'] == 'rtl'}
    require(rtl == {'ar', 'fa', 'he', 'ur'}, f'insieme RTL inatteso: {sorted(rtl)}')
    for code, meta in locales.items():
        url = f'{B.SITE}/lang/{meta["path"]}/'
        page_path = DIST / 'lang' / meta['path'] / 'index.html'
        require(page_path.is_file(), f'landing mancante: {code}')
        page = page_path.read_text()
        page_head = page.split('</head>', 1)[0]
        require(f'<html lang="{meta["hreflang"]}" dir="{meta["dir"]}">' in page,
                f'lang/dir errati: {code}')
        require(f'<link rel="canonical" href="{url}">' in page_head,
                f'canonical errato: {code}')
        require(html.escape(meta['seo']['title']) in page_head, f'titolo SEO mancante: {code}')
        require(len(re.findall(r'<link rel="alternate" hreflang=', page_head)) == len(locales) + 1,
                f'cluster hreflang incompleto: {code}')
        require(url in urls, f'URL lingua assente dalla sitemap: {code}')
        require(not re.search(r'__[A-Z][A-Z0-9_]*__', page), f'segnaposto residuo: {code}')

    language_pages = list((DIST / 'lang').glob('*/index.html'))
    require(len(language_pages) == len(locales),
            f'landing lingua inattese: {len(language_pages)}')
    print(f'OK · home e JavaScript validi · {len(locales)} lingue · '
          f'{len(urls)} URL in sitemap · RTL e fil-PH verificati')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, ET.ParseError) as exc:
        print(f'ERRORE · {exc}', file=sys.stderr)
        raise SystemExit(1)
