#!/usr/bin/env python3
"""Scrive l'archivio permanente delle osservazioni su Cloudflare R2.

Perche' esiste
--------------
Fino al 15 settembre 2026 l'unica cosa che sopravviveva a una settimana era
`data/history/*.csv`: una riga per rotta al giorno, quattro campi. Il resto —
le date di partenza e rientro, la durata, tutte le combinazioni di date che non
erano la piu' economica — spariva con la finestra di sette giorni di
`MAX_AGE`. Su 362.089 osservazioni raccolte in una notte ne restavano 21.198:
il 94% buttato.

Non era un problema di spazio. In Parquet un'osservazione costa **sei byte**, e
una notte intera pesa meno di due megabyte. Era un problema di struttura:
archivio e piano di lavoro erano gli stessi file, quindi si pagavano e si
perdevano insieme.

Qui l'archivio diventa una cosa separata:

    osservazioni/anno=2026/mese=09/2026-09-15.parquet

Un file al giorno, **scritto una volta e mai piu' riscritto**. E' questa
l'immutabilita' che rende tutto economico: l'oggetto si memorizza una volta e
nessuna notte successiva lo tocca.

Il campo per cui vale la pena
-----------------------------
`dep`, la data di partenza. Senza quella non si puo' chiedere *quanto conviene
prenotare in anticipo* — la distanza fra `obs` e `dep` — che e' la domanda piu'
preziosa del settore e quella che oggi non si puo' nemmeno formulare. Ne'
*quanto costa questa rotta a novembre*, che vuole la stagionalita' sulla data
di viaggio e non su quella di rilevazione.

Si ripara da solo
-----------------
`data/fares/` contiene sempre gli ultimi sette giorni. Ogni notte lo script
confronta quella finestra con quello che c'e' gia' su R2 e carica i giorni che
mancano. Se una notte il caricamento fallisce — rete, credenziali scadute — la
notte dopo recupera da solo, senza che nessuno se ne accorga. E' anche il
motivo per cui un guasto qui non e' un'emergenza: c'e' una settimana di margine.

Un giorno gia' presente su R2 non viene mai risovrascritto. La versione
caricata il giorno stesso e' la piu' completa: nelle notti successive le stesse
righe vengono superate da osservazioni piu' fresche e la finestra ne conserva
meno. Riscrivere vorrebbe dire sostituire il dato buono con uno piu' magro.

    python scripts/archivio.py                 carica su R2
    python scripts/archivio.py --solo-locale D scrive in D, senza rete
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
FARES = ROOT / 'data' / 'fares'
PREFISSO = 'osservazioni'

ATTESI = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET')


# ── lo schema ────────────────────────────────────────────────────────────────
# Nove colonne, scelte una volta e poi stabili: un archivio che cambia forma
# ogni mese non e' un archivio. `o` e `d` sono dizionari perche' sono 1.400
# codici ripetuti su milioni di righe, e il formato colonnare li scrive una
# volta sola invece che a ogni riga.
#
# Fuori restano `s`, `endpoint`, `direct_check` e `distance_source`: oggi hanno
# un solo valore utile ciascuno, e una colonna costante e' rumore che costa
# spazio e non risponde a niente. Si aggiungono il giorno in cui avranno
# davvero piu' di un valore.
def schema():
    import pyarrow as pa
    return pa.schema([
        ('obs', pa.date32()),                              # quando l'abbiamo vista
        ('o',   pa.dictionary(pa.int16(), pa.string())),   # aeroporto di partenza
        ('d',   pa.dictionary(pa.int16(), pa.string())),   # aeroporto di arrivo
        ('dep', pa.date32()),                              # partenza   <- si perdeva
        ('ret', pa.date32()),                              # rientro    <- si perdeva
        ('p',   pa.float32()),                             # prezzo in euro
        ('dur', pa.int16()),                               # minuti di volo
        ('km',  pa.int16()),                               # distanza
        ('n',   pa.int8()),                                # notti
    ])


def data(valore):
    try:
        return dt.date.fromisoformat(str(valore)[:10])
    except (TypeError, ValueError):
        return None


def intero(valore, massimo):
    try:
        return max(0, min(massimo, int(valore or 0)))
    except (TypeError, ValueError):
        return 0


def leggi_finestra() -> dict[dt.date, list]:
    """Tutte le osservazioni negli scomparti, raggruppate per giorno di rilevazione."""
    per_giorno = defaultdict(list)
    for f in sorted(glob.glob(str(FARES / '*.json'))):
        try:
            pacchetto = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'  scomparto illeggibile, saltato: {pathlib.Path(f).name} ({e})')
            continue
        for r in pacchetto.get('deals', []):
            giorno = data(r.get('obs'))
            if giorno:
                per_giorno[giorno].append(r)
    return per_giorno


def tabella(righe):
    """Le righe di un giorno, in ordine deterministico.

    L'ordine conta: due esecuzioni sugli stessi dati devono produrre lo stesso
    file byte per byte, altrimenti non si puo' piu' dire se un archivio e'
    cambiato davvero o solo stato riscritto.
    """
    import pyarrow as pa
    righe = sorted(righe, key=lambda r: (r.get('o') or '', r.get('d') or '',
                                         str(r.get('dep') or ''), str(r.get('ret') or ''),
                                         r.get('p') or 0))
    return pa.Table.from_pydict({
        'obs': [data(r.get('obs')) for r in righe],
        'o':   [r.get('o') for r in righe],
        'd':   [r.get('d') for r in righe],
        'dep': [data(r.get('dep')) for r in righe],
        'ret': [data(r.get('ret')) for r in righe],
        'p':   [float(r.get('p') or 0) for r in righe],
        'dur': [intero(r.get('dur'), 32767) for r in righe],
        'km':  [intero(r.get('km'), 32767) for r in righe],
        'n':   [intero(r.get('n'), 127) for r in righe],
    }, schema=schema())


def scrivi(righe, destinazione: pathlib.Path) -> int:
    import pyarrow.parquet as pq
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabella(righe), destinazione,
                   compression='zstd', compression_level=9)
    return destinazione.stat().st_size


def chiave(giorno: dt.date) -> str:
    """Percorso in stile Hive: DuckDB salta i mesi che non servono senza aprirli."""
    return f'{PREFISSO}/anno={giorno:%Y}/mese={giorno:%m}/{giorno:%Y-%m-%d}.parquet'


def da_caricare(giorni, presenti: set[str]) -> list[dt.date]:
    """Quali giorni della finestra vanno scritti su R2.

    Due regole, e la seconda e' quella che protegge l'archivio:

    1. il giorno piu' recente si scrive **sempre** — e' la raccolta appena
       fatta, la versione piu' completa che di quel giorno esistera' mai;
    2. i giorni precedenti si scrivono **solo se mancano**. Nella finestra sono
       ormai piu' magri di quando furono raccolti, perche' le loro righe sono
       state superate da osservazioni piu' fresche: risovrascriverli
       significherebbe sostituire il dato buono con uno peggiore.

    La seconda regola e' anche quella che ripara i guasti: se una notte il
    caricamento fallisce, il giorno resta mancante e la notte dopo viene
    ripreso da sola, finche' resta dentro i sette giorni della finestra.
    """
    if not giorni:
        return []
    fresco = max(giorni)
    return [g for g in sorted(giorni) if g == fresco or chiave(g) not in presenti]


def cliente():
    mancanti = [k for k in ATTESI if not os.environ.get(k)]
    if mancanti:
        print('MANCANO le variabili:', ', '.join(mancanti))
        return None, None
    import boto3
    from botocore.config import Config
    v = {k: os.environ[k].strip() for k in ATTESI}
    s3 = boto3.client(
        's3', endpoint_url=f"https://{v['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=v['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=v['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        config=Config(signature_version='s3v4', retries={'max_attempts': 3}))
    return s3, v['R2_BUCKET']


def gia_su_r2(s3, secchio) -> set[str]:
    chiavi, token = set(), None
    while True:
        extra = {'ContinuationToken': token} if token else {}
        risposta = s3.list_objects_v2(Bucket=secchio, Prefix=PREFISSO + '/', **extra)
        for o in risposta.get('Contents', []):
            chiavi.add(o['Key'])
        if not risposta.get('IsTruncated'):
            return chiavi
        token = risposta.get('NextContinuationToken')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--solo-locale', metavar='CARTELLA',
                    help='scrive i file qui invece di caricarli, senza toccare la rete')
    args = ap.parse_args()

    print('— lettura della finestra —')
    per_giorno = leggi_finestra()
    if not per_giorno:
        print('nessuna osservazione in data/fares: non c\'e\' niente da archiviare')
        return 1
    totale = sum(len(v) for v in per_giorno.values())
    print(f'  {totale:,} osservazioni su {len(per_giorno)} giorni '
          f'({min(per_giorno)} → {max(per_giorno)})')

    if args.solo_locale:
        base = pathlib.Path(args.solo_locale)
        print('\n— scrittura locale —')
        for giorno in sorted(per_giorno):
            peso = scrivi(per_giorno[giorno], base / chiave(giorno))
            print(f'  {giorno}  {len(per_giorno[giorno]):>7,} righe  {peso/1e6:6.2f} MB')
        return 0

    s3, secchio = cliente()
    if not s3:
        return 1

    print('\n— cosa c\'e\' gia\' —')
    try:
        presenti = gia_su_r2(s3, secchio)
    except Exception as e:
        print(f'  impossibile elencare l\'archivio: {type(e).__name__}: {e}')
        return 1
    print(f'  {len(presenti)} giorni gia\' archiviati')

    fresco = max(per_giorno)
    da_fare = da_caricare(per_giorno, presenti)
    if not da_fare:
        print('\nniente da caricare: l\'archivio e\' gia\' allineato')
        return 0

    print(f'\n— caricamento ({len(da_fare)} giorni) —')
    import tempfile
    caricati = byte = 0
    with tempfile.TemporaryDirectory() as tmp:
        for giorno in da_fare:
            locale = pathlib.Path(tmp) / f'{giorno}.parquet'
            peso = scrivi(per_giorno[giorno], locale)
            nota = 'stanotte' if giorno == fresco else 'recupero'
            try:
                s3.upload_file(str(locale), secchio, chiave(giorno))
            except Exception as e:
                print(f'  FALLITO  {giorno}  — {type(e).__name__}: {e}')
                print('\nLa finestra tiene sette giorni: la prossima notte riprova da sola.')
                return 1
            caricati += 1
            byte += peso
            print(f'  OK  {giorno}  {len(per_giorno[giorno]):>7,} righe  '
                  f'{peso/1e6:6.2f} MB  ({nota})')

    print(f'\n— esito —\n  {caricati} giorni caricati, {byte/1e6:.2f} MB in tutto')
    print(f'  archivio: {len(presenti | {chiave(g) for g in da_fare})} giorni')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
