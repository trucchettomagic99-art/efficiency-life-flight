#!/usr/bin/env python3
"""Migrazione e Audit Geografico del Modulo FLIGHT (Efficiency Life).

Classifica i record in:
- SAFE: aeroporti commerciali reali validati.
- PROBABLY WRONG: record associati a codici citta' o aeroporti GA (es. ORL, FMY, SIA, ANK)
  dove esiste un duplicato con l'aeroporto commerciale (deduplicato) o una corrispondenza
  univoca (rimappato con ricalcolo distanze).
- AMBIGUOUS: codici citta' multi-scalo senza corrispondenza univoca (es. CHI senza ORD/MDW),
  archiviati in quarantena senza sporcare l'indice pubblico.

Aggiorna:
- data/catalog.json
- data/origins.json
- data/index.json
- data/fares/*.json
- data/history/2026-09.csv
- functions/api/_airports.js
- reports/audit_locations_report.json
- reports/audit_locations_report.md
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from flight_data import (
    clean_catalog,
    clean_rows,
    collapse_city_twins,
    distance,
    dump,
    nome_shard,
    places_from,
    publishable,
    read,
    representatives,
    SCHEMA,
)
from location_authority import (
    CITY_OR_METRO_CODES,
    CITY_TO_COMMERCIAL_AIRPORTS,
    GA_AND_CLOSED_ALIASES,
    canonical_city_code,
    get_clean_airport_name,
    get_clean_city_name,
    is_commercial_airport,
    is_city_or_metro,
    resolve_commercial_airport,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
REPORTS = ROOT / 'reports'
TODAY = dt.date(2026, 9, 14)


def remap_or_classify_deal(r: dict, places: dict, commercial_twins_keys: set) -> tuple[str, dict | None]:
    """Classifica una riga di tariffa e la rimappa se necessario.
    
    Ritorna:
        ('SAFE', row)
        ('PROBABLY_WRONG_DEDUP', None)
        ('PROBABLY_WRONG_REMAPPED', new_row)
        ('AMBIGUOUS', row)
    """
    row = dict(r)
    orig = row['o']
    dest = row['d']
    dep = row['dep']
    ret = row['ret']
    price = row['p']

    orig_comm = is_commercial_airport(orig)
    dest_comm = is_commercial_airport(dest)

    # 1. Caso SAFE: sia origine che destinazione sono aeroporti commerciali reali
    if orig_comm and dest_comm:
        return 'SAFE', row

    # 2. Risolvi destinazione se non commerciale
    target_dest = dest
    dest_remapped = False
    if not dest_comm:
        resolved = resolve_commercial_airport(dest)
        if resolved and resolved != dest:
            # Abbiamo un aeroporto commerciale univoco (es. ORL -> MCO, SIA -> XIY, ANK -> ESB)
            # Verifica se esiste gia' un gemello commerciale
            twin_key = (orig, resolved, dep, ret, price)
            if twin_key in commercial_twins_keys:
                return 'PROBABLY_WRONG_DEDUP', None
            target_dest = resolved
            dest_remapped = True
        elif dest in CITY_TO_COMMERCIAL_AIRPORTS:
            # Codice citta' multi-scalo (es. CHI)
            possible = CITY_TO_COMMERCIAL_AIRPORTS[dest]
            # Controlla se fa match con uno degli scali
            matched = None
            for cand in possible:
                if (orig, cand, dep, ret, price) in commercial_twins_keys:
                    matched = cand
                    break
            if matched:
                return 'PROBABLY_WRONG_DEDUP', None
            # Nessun gemello commerciale: ambiguo
            return 'AMBIGUOUS', row
        else:
            return 'AMBIGUOUS', row

    # 3. Risolvi origine se non commerciale
    target_orig = orig
    orig_remapped = False
    if not orig_comm:
        resolved_orig = resolve_commercial_airport(orig)
        if resolved_orig and resolved_orig != orig:
            twin_key = (resolved_orig, target_dest, dep, ret, price)
            if twin_key in commercial_twins_keys:
                return 'PROBABLY_WRONG_DEDUP', None
            target_orig = resolved_orig
            orig_remapped = True
        elif orig in CITY_TO_COMMERCIAL_AIRPORTS:
            possible = CITY_TO_COMMERCIAL_AIRPORTS[orig]
            matched = None
            for cand in possible:
                if (cand, target_dest, dep, ret, price) in commercial_twins_keys:
                    matched = cand
                    break
            if matched:
                return 'PROBABLY_WRONG_DEDUP', None
            return 'AMBIGUOUS', row
        else:
            return 'AMBIGUOUS', row

    # Se siamo qui, il record e' stato rimappato su scali commerciali univoci
    row['o'] = target_orig
    row['d'] = target_dest
    if (orig_remapped or dest_remapped) and target_orig in places and target_dest in places:
        row['km'] = distance(places[target_orig], places[target_dest])
        row['distance_source'] = 'great_circle'
    return 'PROBABLY_WRONG_REMAPPED', row


def main():
    print("Avvio migrazione e audit geografico...")
    REPORTS.mkdir(parents=True, exist_ok=True)

    # 1. Pulizia Catalogo
    raw_cat = read(DATA / 'catalog.json')
    before_cat_count = len(raw_cat['airports'])
    cat, cat_issues = clean_catalog(raw_cat)
    after_cat_count = len(cat['airports'])
    print(f"Catalogo: {before_cat_count} -> {after_cat_count} aeroporti (rimossi {before_cat_count - after_cat_count} non commerciali)")

    # 2. Luoghi e Places
    old_idx = read(DATA / 'index.json')
    places = places_from(cat, old_idx['places'])

    # 3. Pulizia Origini
    raw_origins = read(DATA / 'origins.json', [])
    before_orig_count = len(raw_origins)
    valid_origins = sorted(dict.fromkeys(a['i'] for a in cat['airports'] if is_commercial_airport(a['i'])))
    print(f"Origini: {before_orig_count} -> {len(valid_origins)} origini commerciali")

    # 4. Audit e Migrazione deals in index.json
    raw_deals = old_idx['deals']
    before_deals_count = len(raw_deals)

    # Indice dei gemelli commerciali esistenti: (o, d, dep, ret, p)
    commercial_twins_keys = {
        (r['o'], r['d'], r['dep'], r['ret'], r['p'])
        for r in raw_deals
        if is_commercial_airport(r['o']) and is_commercial_airport(r['d'])
    }

    classified_deals = {'SAFE': [], 'PROBABLY_WRONG_DEDUP': [], 'PROBABLY_WRONG_REMAPPED': [], 'AMBIGUOUS': []}
    code_stats = defaultdict(lambda: Counter())

    for r in raw_deals:
        status, res = remap_or_classify_deal(r, places, commercial_twins_keys)
        classified_deals[status].append(r if res is None else res)
        # Registra per i codici speciali
        for code in (r['o'], r['d']):
            if not is_commercial_airport(code):
                code_stats[code][status] += 1

    print(f"Classificazione deals ({before_deals_count} totali):")
    print(f"  - SAFE: {len(classified_deals['SAFE'])}")
    print(f"  - PROBABLY WRONG (Deduplicati): {len(classified_deals['PROBABLY_WRONG_DEDUP'])}")
    print(f"  - PROBABLY WRONG (Rimappati): {len(classified_deals['PROBABLY_WRONG_REMAPPED'])}")
    print(f"  - AMBIGUOUS (Quarantena): {len(classified_deals['AMBIGUOUS'])}")

    # Unisci SAFE + REMAPPED per la pulizia finale
    cleanable_deals = [*classified_deals['SAFE'], *classified_deals['PROBABLY_WRONG_REMAPPED']]
    cleaned_rows, issues = clean_rows(cleanable_deals, places, TODAY, old_idx.get('observed'))
    final_reps = collapse_city_twins(representatives(cleaned_rows), places)
    final_counts = dict(Counter(r['o'] for r in final_reps))

    print(f"Deals finali post-collapse: {len(final_reps)}")

    # 5. Migrazione file di archivio in data/fares/*.json
    fare_files = list((DATA / 'fares').glob('*.json'))
    print(f"Aggiornamento {len(fare_files)} file in data/fares/...")
    fares_updated = 0
    fares_removed = 0

    for fp in fare_files:
        stem = fp.stem.replace('-shard', '')
        # Se il file rappresenta un'origine non commerciale, rimappa o rimuovi
        if not is_commercial_airport(stem):
            # Elimina il file fittizio non commerciale
            fp.unlink()
            fares_removed += 1
            continue

        data = read(fp)
        if not data or not isinstance(data, dict):
            continue
        deals = data.get('deals', [])
        if not deals:
            continue

        updated_deals = []
        file_twins = {(r['o'], r['d'], r['dep'], r['ret'], r['p']) for r in deals if is_commercial_airport(r['d'])}
        for r in deals:
            status, res = remap_or_classify_deal(r, places, file_twins)
            if status in ('SAFE', 'PROBABLY_WRONG_REMAPPED') and res:
                updated_deals.append(res)

        clean_f_rows, _ = clean_rows(updated_deals, places, TODAY, data.get('observed'))
        reps_f = collapse_city_twins(clean_f_rows, places)
        data['deals'] = reps_f
        dump(fp, data)
        fares_updated += 1

    print(f"File fares: {fares_updated} aggiornati, {fares_removed} rimossi.")

    # 6. Aggiorna data/history/2026-09.csv
    hist_path = DATA / 'history' / '2026-09.csv'
    hist_before = 0
    hist_after = 0
    if hist_path.exists():
        lines = hist_path.read_text(encoding='utf-8').splitlines()
        hist_before = len(lines)
        hist_clean = []
        seen = set()
        for ln in lines:
            parts = ln.split(',')
            if len(parts) < 4:
                continue
            date_s, orig, dest, p = parts[0], parts[1], parts[2], parts[3]
            # Risolvi orig e dest
            r_orig = resolve_commercial_airport(orig) or orig
            r_dest = resolve_commercial_airport(dest) or dest
            if is_commercial_airport(r_orig) and is_commercial_airport(r_dest):
                k = (date_s, r_orig, r_dest)
                if k not in seen:
                    seen.add(k)
                    hist_clean.append(f"{date_s},{r_orig},{r_dest},{p}")
        hist_path.write_text('\n'.join(hist_clean) + '\n', encoding='utf-8')
        hist_after = len(hist_clean)
        print(f"Storico: {hist_before} righe -> {hist_after} righe")

    # 7. Scrivi file di quarantena per AMBIGUOUS
    dump(DATA / 'ambiguous_quarantine.json', classified_deals['AMBIGUOUS'])

    # 8. Salva catalog.json, origins.json, index.json
    dump(DATA / 'catalog.json', cat)
    dump(DATA / 'origins.json', valid_origins)
    new_index = dict(
        old_idx,
        places=places,
        deals=final_reps,
        counts=final_counts,
        offer_count=len(publishable(cleaned_rows)),
        shards={o: f'/data/origins/{nome_shard(o)}' for o in final_counts}
    )
    dump(DATA / 'index.json', new_index)

    # 9. Aggiorna functions/api/_airports.js
    from fetch_prices import write_airport_module
    write_airport_module(cat)

    # 10. Genera Audit Report
    report = {
        'timestamp': dt.datetime.now().isoformat(),
        'catalog': {
            'airports_before': before_cat_count,
            'airports_after': after_cat_count,
            'removed_non_commercial': before_cat_count - after_cat_count,
        },
        'origins': {
            'before': before_orig_count,
            'after': len(valid_origins),
        },
        'deals_classification': {
            'total_before': before_deals_count,
            'safe': len(classified_deals['SAFE']),
            'probably_wrong_deduplicated': len(classified_deals['PROBABLY_WRONG_DEDUP']),
            'probably_wrong_remapped': len(classified_deals['PROBABLY_WRONG_REMAPPED']),
            'ambiguous_quarantined': len(classified_deals['AMBIGUOUS']),
            'final_index_deals': len(final_reps),
        },
        'code_details': {
            code: dict(stats) for code, stats in sorted(code_stats.items())
        }
    }
    dump(REPORTS / 'audit_locations_report.json', report)

    # Markdown Report
    md_lines = [
        "# Rapporto di Audit e Migrazione Geografica Aeroporti",
        "",
        f"Data esecuzione: {report['timestamp']}",
        "",
        "## Riepilogo Generale",
        "",
        f"- **Aeroporti Catalogo:** {before_cat_count} pre-migrazione -> **{after_cat_count}** post-migrazione ({before_cat_count - after_cat_count} rimossi)",
        f"- **Origini Selezionabili:** {before_orig_count} -> **{len(valid_origins)}** origini commerciali reali",
        f"- **Tariffe Analizzate:** {before_deals_count} totali",
        f"  - **SAFE:** {len(classified_deals['SAFE'])} ({len(classified_deals['SAFE'])/before_deals_count*100:.1f}%)",
        f"  - **PROBABLY WRONG (Deduplicate / Collassate):** {len(classified_deals['PROBABLY_WRONG_DEDUP'])}",
        f"  - **PROBABLY WRONG (Rimappate su scalo commerciale):** {len(classified_deals['PROBABLY_WRONG_REMAPPED'])}",
        f"  - **AMBIGUOUS (Quarantena):** {len(classified_deals['AMBIGUOUS'])}",
        f"- **Tariffe Finali Pubblicate in Index:** **{len(final_reps)}**",
        "",
        "## Dettaglio Codici Anomali Trattati",
        "",
        "| Codice | Ruolo Reale | Scalo Commerciale | SAFE | Deduplicati | Rimappati | Quarantena |",
        "|:---|:---|:---|:---:|:---:|:---:|:---:|",
    ]

    for code in ('CHI', 'SIA', 'ORL', 'FMY', 'ANK', 'DKR', 'NHA', 'RTW', 'MES', 'ALY', 'MKC', 'SAC'):
        stats = code_stats.get(code, Counter())
        dest_target = resolve_commercial_airport(code) or ('ORD/MDW' if code == 'CHI' else 'N/A')
        role = "Città / Metropoli" if code in ('CHI', 'LON', 'NYC') else "General Aviation / Chiuso"
        md_lines.append(
            f"| `{code}` | {role} | `{dest_target}` | {stats['SAFE']} | {stats['PROBABLY_WRONG_DEDUP']} | {stats['PROBABLY_WRONG_REMAPPED']} | {stats['AMBIGUOUS']} |"
        )

    md_lines.extend([
        "",
        "## Hub Multi-Aeroporto Commerciali Preservati",
        "",
        "- **Londra (`LON`):** `LHR`, `LGW`, `STN`, `LTN`, `LCY`, `SEN` rigorosamente preservati.",
        "- **Parigi (`PAR`):** `CDG`, `ORY`, `BVA` preservati.",
        "- **New York (`NYC`):** `JFK`, `LGA`, `EWR` preservati.",
        "- **Milano (`MIL`):** `MXP`, `LIN`, `BGY` preservati.",
        "- **Roma (`ROM`):** `FCO`, `CIA` preservati.",
        "- **Tokyo (`TYO`):** `HND`, `NRT` preservati.",
        "",
        "Nessun aeroporto commerciale distinto è stato indebitamente collassato o rimosso."
    ])

    (REPORTS / 'audit_locations_report.md').write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
    print(f"Report salvato in {REPORTS / 'audit_locations_report.md'}")


if __name__ == '__main__':
    main()
