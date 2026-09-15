#!/usr/bin/env python3
"""Archivio permanente delle osservazioni, su Cloudflare R2.

Perche' esiste
--------------
Fino al 15 settembre 2026 l'unica cosa che sopravviveva a una settimana era
`data/history/*.csv`: una riga per rotta al giorno, quattro campi. Il resto —
le date di partenza e rientro, la durata, la verifica di volo diretto, tutte le
combinazioni di date che non erano la piu' economica — spariva con la finestra
di sette giorni di `MAX_AGE`. Su 362.089 osservazioni raccolte in una notte ne
restavano 21.198: il 94% buttato.

Non era un problema di spazio. In Parquet un'osservazione costa **sei byte**, e
una notte intera pesa meno di due megabyte. Era un problema di struttura:
archivio e piano di lavoro erano gli stessi file, quindi si pagavano e si
perdevano insieme.

Qui l'archivio diventa una cosa separata, versionata e immutabile:

    osservazioni/schema=v1/anno=2026/mese=09/2026-09-15.parquet
    osservazioni/schema=v1/anno=2026/mese=09/2026-09-15.manifest.json

Un file al giorno, **creato una volta e mai sovrascritto** — non per disciplina
ma per costruzione: la scrittura usa `If-None-Match: *`, che R2 supporta, e
quindi fallisce se l'oggetto esiste gia'.

Le regole, in ordine di importanza
----------------------------------
1. **Si finalizza solo il giorno appena raccolto, e solo se la raccolta e'
   completa.** La completezza non e' una soglia inventata: viene dal rapporto
   che `fetch_prices.py` scrive nella stessa esecuzione. Vedi `completezza()`.

2. **Un giorno vecchio mancante non si ricostruisce dalla finestra.**
   `data/fares/` e' una finestra mobile e `clean_rows()` tiene, per ogni
   (o, d, dep, ret), solo l'osservazione piu' recente: i giorni vecchi dentro
   la finestra sono progressivamente *impoveriti*. Misurato il 15 settembre:
   362.089 righe per il giorno fresco, 64.063 per quello prima, 14.621 per
   quello di sei giorni prima. Ricostruirli da qui vorrebbe dire archiviare
   come definitiva una versione monca. Si recuperano dalla storia di git, con
   `--sostituisci-giorno`, quando si potra' dimostrare che sono completi.

3. **Niente trasformazioni silenziose.** Un valore che non si puo'
   rappresentare fedelmente diventa NULL e viene contato nel manifesto; non
   viene mai troncato al massimo del tipo ne' finto a zero. Una riga che non si
   puo' nemmeno collocare nel tempo viene esclusa e contata.

4. **L'identita' del dato e' l'impronta logica**, non i byte del Parquet. Due
   versioni di pyarrow possono scrivere file diversi con lo stesso contenuto:
   quello che conta e' lo SHA-256 delle righe normalizzate in ordine canonico.

Uso
---
    python scripts/archivio.py                    finalizza il giorno fresco
    python scripts/archivio.py --solo-locale D    scrive in D, senza rete
    python scripts/archivio.py --elenco           cosa c'e' gia' su R2
    python scripts/archivio.py --giorno G         lavora su un altro giorno
                                                  della finestra (mai final)
    python scripts/archivio.py --sostituisci-giorno G --motivo "..."
                                                  riparazione esplicita e
                                                  manuale: mette da parte la
                                                  versione precedente e la
                                                  sostituisce
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation

ROOT = pathlib.Path(__file__).resolve().parent.parent
FARES = ROOT / 'data' / 'fares'
RAPPORTO = ROOT / 'data' / 'collection-report.json'
COPIA_LOCALE = ROOT / '.cache' / 'archivio'

SCHEMA = 'v1'
PREFISSO = f'osservazioni/schema={SCHEMA}'
STAGING = f'staging/schema={SCHEMA}'
SUPERATI = f'superati/schema={SCHEMA}'
VALUTA = 'EUR'

ATTESI = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET')

# Sotto questa frazione della mediana dei giorni gia' archiviati la giornata
# non si finalizza, anche se il rapporto la dichiara completa. E' la seconda
# linea di difesa: il rapporto dice se la raccolta ha finito il suo lavoro, non
# se il lavoro ha prodotto qualcosa di sensato.
FRAZIONE_MINIMA = 0.5


# ── lo schema, versione 1 ────────────────────────────────────────────────────
# Quindici colonne. La prima versione ne aveva nove: buttava `endpoint`,
# `direct_check`, `distance_source`, `s`, `found_at` e `quality` perche' li
# credevo costanti. Misurati sui dati veri non lo erano:
#
#   endpoint       'dates' | 'latest'
#   direct_check   'both_legs' | 'provider_aggregate'   <- quanto ci fidiamo
#                                                          che sia diretto
#   distance_source 'great_circle' | assente (distanza del fornitore)
#   found_at       quando il FORNITORE ha visto la tariffa (0,82% delle righe)
#   quality        'low_price_review' per le righe in quarantena
#
# Tenerli tutti costa **42 KB a notte, il 2,2%**. Buttarli costava la
# possibilita' di distinguere una tariffa verificata su entrambe le tratte da
# una dichiarata dal fornitore — cioe' l'unica dimensione di qualita' che
# abbiamo. Una colonna costante in Parquet comprime a quasi niente; un campo
# perso non torna.
#
# `o` e `d` restano `string` come tipo logico: la compressione a dizionario la
# fa Parquet da solo (`use_dictionary`), e cosi' lo schema non dipende da come
# Arrow rappresenta i dizionari in memoria. Misurato: stessa dimensione al
# millesimo, e un file che qualsiasi lettore apre allo stesso modo.
COLONNE = ('obs', 'o', 'd', 'dep', 'ret', 'p_cents', 'dur', 'km', 'n',
           'endpoint', 'direct_check', 'distance_source', 'src',
           'found_at', 'quality')


def schema():
    import pyarrow as pa
    return pa.schema([
        ('obs',             pa.date32()),                      # giorno di rilevazione, UTC
        ('o',               pa.string()),                      # aeroporto di partenza
        ('d',               pa.string()),                      # aeroporto di arrivo
        ('dep',             pa.date32()),                      # data di partenza
        ('ret',             pa.date32()),                      # data di rientro
        ('p_cents',         pa.int32()),                       # prezzo in centesimi di EUR
        ('dur',             pa.int32()),                       # minuti di volo; NULL = ignoto
        ('km',              pa.int32()),                       # distanza in km
        ('n',               pa.int16()),                       # notti
        ('endpoint',        pa.string()),                      # 'dates' | 'latest'
        ('direct_check',    pa.string()),                      # 'both_legs' | 'provider_aggregate'
        ('distance_source', pa.string()),                      # 'great_circle' | NULL
        ('src',             pa.string()),                      # fonte, oggi 'tp'
        ('found_at',        pa.timestamp('ms', tz='UTC')),     # quando l'ha vista il fornitore
        ('quality',         pa.string()),                      # 'low_price_review' se in quarantena
    ])


# ── lettura dei valori, senza mentire ────────────────────────────────────────

def giorno_di(valore):
    """(data, aveva_ora). None se non e' una data leggibile.

    `obs` oggi e' sempre una data pura di dieci caratteri — `fetch_prices.py`
    scrive `datetime.now(utc).date().isoformat()`, e nella finestra del 15
    settembre tutte le 630.629 righe sono cosi'. Non c'e' nessuna ora da
    conservare: inventarne una sarebbe peggio che non averla.

    Se un giorno la raccolta cominciasse a scrivere un istante, questa
    funzione lo normalizza in UTC invece di tagliarlo, e segnala che e'
    successo — cosi' il cambiamento si vede nel manifesto invece di sparire.
    """
    if not isinstance(valore, str) or not valore:
        return None, False
    testo = valore.strip()
    try:
        return dt.date.fromisoformat(testo), False
    except ValueError:
        pass
    istante = istante_di(testo)
    if istante is None:
        return None, False
    return istante.date(), True


def istante_di(valore):
    """Un istante UTC, o None. Un fuso assente si legge come UTC e basta."""
    if not isinstance(valore, str) or not valore:
        return None
    testo = valore.strip().replace('Z', '+00:00').replace('z', '+00:00')
    try:
        momento = dt.datetime.fromisoformat(testo)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=dt.timezone.utc)
    momento = momento.astimezone(dt.timezone.utc)
    # La colonna e' al millisecondo: si tronca qui, una volta sola, cosi' il
    # valore impronta e il valore scritto sono lo stesso valore. Altrimenti
    # l'impronta direbbe una cosa e il file un'altra, e a distanza di mesi non
    # si capirebbe quale delle due mente.
    return momento.replace(microsecond=(momento.microsecond // 1000) * 1000)


def centesimi(valore):
    """Il prezzo in centesimi, esatto. None se non lo e'.

    Passa dal testo: `int(0.1 * 100)` fa 10 per fortuna e 10 invece di 11 per
    sfortuna, perche' 0.1 in binario non esiste. `Decimal(str(v))` legge la
    cifra che si vede.
    """
    if isinstance(valore, bool) or valore is None:
        return None
    try:
        esatto = Decimal(str(valore)) * 100
    except (InvalidOperation, ValueError, TypeError):
        return None
    if esatto != esatto.to_integral_value():      # piu' di due decimali
        return None
    intero = int(esatto)
    if not 0 < intero <= 2_147_483_647:
        return None
    return intero


def numero(valore, minimo, massimo):
    """Un intero dentro i limiti, oppure None. Mai troncato al massimo.

    Troncare 999.999 a 32.767 scriverebbe nell'archivio un numero che nessuno
    ha mai osservato, indistinguibile da una misura vera. NULL dice quello che
    e' successo davvero: il valore c'era ma non si puo' rappresentare.
    """
    if isinstance(valore, bool) or valore is None:
        return None
    try:
        intero = int(valore)
    except (TypeError, ValueError):
        return None
    return intero if minimo <= intero <= massimo else None


def testo(valore):
    if valore is None:
        return None
    if not isinstance(valore, str):
        return None
    valore = valore.strip()
    return valore or None


def normalizza(grezze):
    """Le righe grezze in righe d'archivio, piu' il conto di cosa non tornava.

    Le anomalie non sono errori da nascondere: finiscono nel manifesto, cosi'
    fra due anni si sapra' che quel giorno tre righe avevano una durata
    impossibile, invece di leggere tre durate impossibili credendole vere.
    """
    righe, anomalie = [], Counter()
    for g in grezze:
        obs, con_ora = giorno_di(g.get('obs'))
        if obs is None:
            anomalie['riga_esclusa_obs_illeggibile'] += 1
            continue
        if con_ora:
            anomalie['obs_con_ora_normalizzata_utc'] += 1

        p = centesimi(g.get('p'))
        if p is None:
            anomalie['riga_esclusa_prezzo_non_rappresentabile'] += 1
            continue

        o, d = testo(g.get('o')), testo(g.get('d'))
        if not o or not d:
            anomalie['riga_esclusa_senza_aeroporti'] += 1
            continue

        dep, _ = giorno_di(g.get('dep'))
        ret, _ = giorno_di(g.get('ret'))
        if dep is None:
            anomalie['dep_illeggibile'] += 1
        if ret is None:
            anomalie['ret_illeggibile'] += 1

        # `dur` arriva da `x.get('duration') or 0`: uno zero non distingue "il
        # volo dura zero minuti", che non esiste, da "il fornitore non l'ha
        # detto". Nell'archivio diventa NULL, che e' la seconda.
        dur = numero(g.get('dur'), 1, 2_147_483_647)
        if dur is None and g.get('dur') not in (None, 0):
            anomalie['dur_fuori_scala'] += 1
        elif g.get('dur') == 0:
            anomalie['dur_zero_letto_come_ignoto'] += 1

        km = numero(g.get('km'), 1, 2_147_483_647)
        if km is None and g.get('km') is not None:
            anomalie['km_fuori_scala'] += 1

        n = numero(g.get('n'), 0, 32767)
        if n is None and g.get('n') is not None:
            anomalie['notti_fuori_scala'] += 1

        trovata = None
        if g.get('found_at') is not None:
            trovata = istante_di(g.get('found_at'))
            if trovata is None:
                anomalie['found_at_illeggibile'] += 1

        righe.append({'obs': obs, 'o': o, 'd': d, 'dep': dep, 'ret': ret,
                      'p_cents': p, 'dur': dur, 'km': km, 'n': n,
                      'endpoint': testo(g.get('endpoint')),
                      'direct_check': testo(g.get('direct_check')),
                      'distance_source': testo(g.get('distance_source')),
                      'src': testo(g.get('s')),
                      'found_at': trovata,
                      'quality': testo(g.get('quality'))})
    return righe, anomalie


# ── lettura della finestra ───────────────────────────────────────────────────

def osservazioni(giorno=None, oggi=None, cartella=None):
    """Le righe grezze di un solo giorno, in una passata sola.

    Tiene in memoria soltanto il giorno bersaglio: quando ne incontra uno piu'
    recente butta quello di prima e ricomincia. Misurato sul 15 settembre, la
    lettura passa da 708 MB a 422 MB, perche' il giorno fresco e' 362.089
    righe su 630.629 e gli altri sei non servono mai. Il picco complessivo
    resta intorno agli 870 MB: normalizzazione e tabella Arrow tengono ognuna
    la propria copia. Si potrebbe normalizzare durante la lettura e scendere
    ancora, ma su un runner da 16 GB non e' un problema che valga un
    rimescolamento del codice prima della prima esecuzione vera.

    Ritorna (bersaglio, righe, conteggi_per_giorno, anomalie).
    """
    cartella = pathlib.Path(cartella) if cartella else FARES
    oggi = oggi or dt.datetime.now(dt.timezone.utc).date()
    bersaglio, tenute = giorno, []
    conteggi, anomalie = Counter(), Counter()
    for f in sorted(cartella.glob('*.json')):
        try:
            pacchetto = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            # Uno scomparto illeggibile non e' un dettaglio: significa che di
            # quell'origine, quella notte, non sappiamo niente. Si conta, si
            # dice, e la giornata non viene dichiarata completa.
            anomalie['scomparto_illeggibile'] += 1
            print(f'  scomparto ILLEGGIBILE, saltato: {f.name} ({type(e).__name__})')
            continue
        if not isinstance(pacchetto, dict):
            anomalie['scomparto_illeggibile'] += 1
            print(f'  scomparto ILLEGGIBILE, saltato: {f.name} (non e\' un oggetto)')
            continue
        for r in pacchetto.get('deals') or []:
            if not isinstance(r, dict):
                anomalie['riga_non_oggetto'] += 1
                continue
            g, _ = giorno_di(r.get('obs'))
            if g is None:
                anomalie['obs_illeggibile'] += 1
                continue
            if g > oggi:
                # Una rilevazione nel futuro e' un orologio sbagliato, non un
                # dato: non deve poter diventare "il giorno fresco" e far
                # buttare quello vero.
                anomalie['obs_nel_futuro'] += 1
                continue
            conteggi[g] += 1
            if giorno is None and (bersaglio is None or g > bersaglio):
                bersaglio, tenute = g, []
            if g == bersaglio:
                tenute.append(r)
    return bersaglio, tenute, conteggi, anomalie


# ── identita' del dato ───────────────────────────────────────────────────────

def _canonica(r) -> str:
    """Una riga come testo stabile: nessun float, nessun ordine di chiavi."""
    def v(k):
        x = r[k]
        if x is None:
            return ''
        if isinstance(x, dt.datetime):
            return x.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        if isinstance(x, dt.date):
            return x.isoformat()
        return str(x)
    return '\t'.join(v(k) for k in COLONNE)


def impronta(righe) -> str:
    """SHA-256 del contenuto, indipendente da pyarrow, zstd e ordine.

    Le righe diventano testo canonico, il testo si ordina, l'ordinamento si
    impronta. Due esecuzioni sugli stessi dati danno la stessa impronta anche
    se una libreria cambia versione e scrive byte diversi — ed e' questa
    l'identita' che serve per dire "il giorno su R2 e' lo stesso che ho qui".
    """
    h = hashlib.sha256()
    for linea in sorted(_canonica(r) for r in righe):
        h.update(linea.encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()


def tabella(righe):
    """Le righe in ordine deterministico, nello schema dichiarato."""
    import pyarrow as pa
    righe = sorted(righe, key=lambda r: (
        r['o'], r['d'],
        r['dep'] or dt.date.min, r['ret'] or dt.date.min,
        r['p_cents'], r['endpoint'] or '', r['direct_check'] or ''))
    return pa.Table.from_pydict({c: [r[c] for r in righe] for c in COLONNE},
                                schema=schema())


def scrivi(righe, destinazione: pathlib.Path) -> pathlib.Path:
    import pyarrow.parquet as pq
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    # `use_dictionary=True` su tutte le colonne, non solo su quelle di testo:
    # `dep` e `ret` hanno 352 valori distinti su 362.089 righe e il dizionario
    # le riduce piu' della sola compressione. Misurato: 1,97 MB contro 2,02 se
    # lo si limita alle stringhe. Ed e' Parquet a farlo, non il tipo Arrow —
    # cosi' lo schema logico resta `string` e qualunque lettore lo apre uguale.
    pq.write_table(tabella(righe), destinazione,
                   compression='zstd', compression_level=9, use_dictionary=True)
    return destinazione


def sha_file(percorso: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(percorso, 'rb') as f:
        for pezzo in iter(lambda: f.read(1 << 20), b''):
            h.update(pezzo)
    return h.hexdigest()


# ── dove vanno le cose ───────────────────────────────────────────────────────

def chiave(giorno: dt.date, radice: str = PREFISSO) -> str:
    """Percorso in stile Hive, con la versione dello schema davanti.

    `schema=v1` e' una chiave di partizione come le altre: DuckDB la espone
    come colonna e la usa per potare, quindi il giorno in cui esistera' un
    `schema=v2` lo storico non diventera' ambiguo — si legge una versione, o
    entrambe sapendo quale e' quale.
    """
    return f'{radice}/anno={giorno:%Y}/mese={giorno:%m}/{giorno:%Y-%m-%d}.parquet'


def chiave_manifesto(giorno: dt.date, radice: str = PREFISSO) -> str:
    return chiave(giorno, radice)[:-len('.parquet')] + '.manifest.json'


# ── la raccolta e' finita davvero? ───────────────────────────────────────────

def completezza(rapporto, giorno: dt.date, righe: int, anomalie) -> tuple[bool, list[str]]:
    """Se la giornata si puo' dichiarare completa, e altrimenti perche' no.

    Niente percentuali inventate: i segnali vengono dal rapporto che
    `fetch_prices.py` scrive in `data/collection-report.json` **nella stessa
    esecuzione** che ha riscritto `data/fares/`. Sono, in ordine di forza:

      date              il giorno che il rapporto descrive. Se non e' quello
                        che stiamo archiviando, la finestra non e' stata
                        riscritta stanotte e non c'e' niente da finalizzare.
      published         `make_snapshot()` ha superato i propri controlli di
                        salute (copertura origini, copertura rotte, quota di
                        risultati buoni). Se e' falso, `fetch_prices.py` esce
                        con 1 e `data/fares/` resta quello di ieri.
      endpoints[*:deferred]
                        una origine "deferred" significa budget dei 1.080
                        secondi esaurito prima di arrivarci. E' ESATTAMENTE il
                        caso della giornata monca: la raccolta e' stata
                        interrotta, non e' finita.
      endpoints[*:error]
                        un errore sporadico capita; una quota alta no.

    NON sono segnali di incompletezza, e vanno lasciati stare:
      page_cap_origins  undici origini raggiungono ogni notte il tetto delle
                        pagine (DME, SVO, IST...). E' un limite strutturale
                        noto, non un guasto: alzarlo a regola farebbe fallire
                        ogni notte.
      rejections        sono le righe scartate dai filtri, cioe' il lavoro che
                        il collettore deve fare.
      metadata_errors   degradano i nomi, non le tariffe.
    """
    motivi = []
    if not isinstance(rapporto, dict):
        return False, ['manca data/collection-report.json: non si puo\' sapere '
                       'se la raccolta ha finito']

    data_rapporto = rapporto.get('date')
    if data_rapporto != giorno.isoformat():
        motivi.append(f'il rapporto descrive {data_rapporto!r}, non {giorno.isoformat()!r}: '
                      'la finestra non e\' stata riscritta da questa raccolta')
    if rapporto.get('published') is not True:
        motivi.append(f'published={rapporto.get("published")!r}: la raccolta non ha '
                      'superato i propri controlli di salute')

    punti = rapporto.get('endpoints') or {}
    rinviate = sum(v for k, v in punti.items() if k.endswith(':deferred'))
    if rinviate:
        motivi.append(f'{rinviate} origini rinviate per budget esaurito: la raccolta '
                      'e\' stata interrotta, non e\' finita')
    tentate = sum(v for k, v in punti.items() if not k.endswith(':deferred'))
    errori = sum(v for k, v in punti.items() if k.endswith(':error'))
    if tentate and errori > 0.02 * tentate:
        motivi.append(f'{errori} errori su {tentate} tentativi ({100*errori/tentate:.1f}%): '
                      'sopra il 2% accettabile')

    if anomalie.get('scomparto_illeggibile'):
        motivi.append(f'{anomalie["scomparto_illeggibile"]} scomparti illeggibili in '
                      'data/fares: di quelle origini non sappiamo niente')
    if not righe:
        motivi.append('nessuna osservazione per questo giorno')

    return not motivi, motivi


def sotto_la_norma(righe: int, storici: list[int]) -> tuple[bool, str]:
    """Seconda linea: il volume regge il confronto con i giorni gia' archiviati?

    Il rapporto dice se la raccolta ha finito il suo lavoro. Questo dice se il
    lavoro ha prodotto qualcosa di plausibile. Sono domande diverse e servono
    tutte e due; questa da sola non basterebbe, perche' un volume normale non
    dimostra che non manchi mezza Europa.
    """
    storici = [n for n in storici if n > 0]
    if len(storici) < 3:
        return False, 'meno di tre giorni archiviati: nessun confronto possibile'
    mediana = sorted(storici)[len(storici) // 2]
    soglia = int(FRAZIONE_MINIMA * mediana)
    if righe < soglia:
        return True, (f'{righe:,} righe contro una mediana di {mediana:,} '
                      f'({100*righe/mediana:.0f}%, minimo {int(FRAZIONE_MINIMA*100)}%)')
    return False, f'{righe:,} righe, mediana {mediana:,} ({100*righe/mediana:.0f}%)'


# ── R2 ───────────────────────────────────────────────────────────────────────

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


def elenco(s3, secchio, radice=PREFISSO) -> dict:
    """Le chiavi gia' presenti sotto un prefisso, con dimensione."""
    trovate, token = {}, None
    while True:
        extra = {'ContinuationToken': token} if token else {}
        risposta = s3.list_objects_v2(Bucket=secchio, Prefix=radice + '/', **extra)
        for o in risposta.get('Contents', []):
            trovate[o['Key']] = o['Size']
        if not risposta.get('IsTruncated'):
            return trovate
        token = risposta.get('NextContinuationToken')


def descrizione(s3, secchio, chiave_oggetto):
    """I metadati di un oggetto, o None se non c'e'."""
    from botocore.exceptions import ClientError
    try:
        return s3.head_object(Bucket=secchio, Key=chiave_oggetto)
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise


def etichette(m: dict) -> dict:
    """I metadati utente da appendere all'oggetto: solo ASCII, solo stringhe."""
    return {'schema': SCHEMA, 'day': m['giorno'], 'rows': str(m['righe']),
            'logical-hash': m['impronta_logica'], 'sha256': m['sha256_file'],
            'currency': VALUTA, 'generated': m['generato'],
            'git': m.get('git_sha') or '', 'run': m.get('github_run_id') or '',
            'pyarrow': m['pyarrow'], 'complete': 'true' if m['completa'] else 'false'}


def carica(s3, secchio, percorso, destinazione, m, solo_se_assente=True):
    """Mette l'oggetto su R2 e poi controlla che ci sia arrivato intero.

    `If-None-Match: *` e' la parte che rende l'immutabilita' una proprieta' e
    non una promessa: R2 la supporta, e se l'oggetto esiste gia' la scrittura
    viene rifiutata dal server. Due esecuzioni sovrapposte non possono
    sostituire un archivio definitivo nemmeno per sbaglio.
    """
    from botocore.exceptions import ClientError
    condizione = {'IfNoneMatch': '*'} if solo_se_assente else {}
    with open(percorso, 'rb') as f:
        try:
            s3.put_object(Bucket=secchio, Key=destinazione, Body=f,
                          ContentType='application/vnd.apache.parquet',
                          Metadata=etichette(m), **condizione)
        except ClientError as e:
            codice = e.response.get('Error', {}).get('Code', '')
            stato = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            if solo_se_assente and (codice in ('PreconditionFailed', 'ConditionalRequestConflict')
                                    or stato in (412, 409)):
                return False, 'esisteva gia\' (creazione condizionale rifiutata)'
            if codice in ('NotImplemented', 'InvalidRequest') and solo_se_assente:
                # Se un giorno R2 smettesse di accettare la precondizione,
                # meglio dirlo che scrivere senza protezione.
                return False, f'creazione condizionale non supportata ({codice})'
            raise

    # Verifica dopo la scrittura: che `put_object` non abbia sollevato
    # eccezioni non dimostra che l'oggetto sia arrivato intero.
    testa = descrizione(s3, secchio, destinazione)
    if testa is None:
        return False, 'caricato ma non rileggibile'
    atteso = percorso.stat().st_size
    if testa.get('ContentLength') != atteso:
        return False, f'dimensione diversa: {testa.get("ContentLength")} invece di {atteso}'
    remoti = {k.lower(): v for k, v in (testa.get('Metadata') or {}).items()}
    if remoti.get('logical-hash') != m['impronta_logica']:
        return False, 'impronta logica diversa nei metadati dell\'oggetto'
    if remoti.get('rows') != str(m['righe']):
        return False, 'numero di righe diverso nei metadati dell\'oggetto'
    # L'ETag di R2, per un caricamento in un pezzo solo, e' l'MD5 del
    # contenuto. Non e' garantito in generale (i multipart hanno un'altra
    # forma), quindi si confronta solo quando ha la forma giusta.
    etag = (testa.get('ETag') or '').strip('"')
    if len(etag) == 32 and all(c in '0123456789abcdef' for c in etag.lower()):
        md5 = hashlib.md5()
        with open(percorso, 'rb') as f:
            for pezzo in iter(lambda: f.read(1 << 20), b''):
                md5.update(pezzo)
        if md5.hexdigest() != etag.lower():
            return False, 'ETag diverso dall\'MD5 del file caricato'
    return True, 'verificato'


# ── manifesto ────────────────────────────────────────────────────────────────

def manifesto(giorno, righe, anomalie, conteggi, completa, motivi, percorso,
              rapporto, nota=None) -> dict:
    import pyarrow as pa
    return {
        'archive_schema_version': SCHEMA,
        'collection_date': giorno.isoformat(),
        'collection_complete': bool(completa),
        'collection_incomplete_reasons': motivi,
        'currency': VALUTA,
        'row_count': len(righe),
        'logical_content_hash': impronta(righe),
        'file_sha256': sha_file(percorso),
        'file_bytes': percorso.stat().st_size,
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'git_sha': os.environ.get('GITHUB_SHA', ''),
        'github_run_id': os.environ.get('GITHUB_RUN_ID', ''),
        'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT', ''),
        'pyarrow_version': pa.__version__,
        'columns': list(COLONNE),
        'anomalies': dict(sorted(anomalie.items())),
        'window_rows_per_day': {g.isoformat(): n for g, n in sorted(conteggi.items())},
        'collection_report': {k: rapporto.get(k) for k in
                              ('date', 'published', 'configured_origins', 'queried_origins',
                               'covered_origins', 'offers', 'archived_offers',
                               'quarantined_offers', 'routes', 'endpoints')}
        if isinstance(rapporto, dict) else None,
        'note': nota,
    }


def _scheletro(giorno, righe, anomalie, conteggi, completa, motivi, cartella, rapporto, nota=None):
    """Scrive il Parquet e il manifesto in una cartella locale."""
    cartella.mkdir(parents=True, exist_ok=True)
    parquet = scrivi(righe, cartella / f'{giorno}.parquet')
    m = manifesto(giorno, righe, anomalie, conteggi, completa, motivi, parquet, rapporto, nota)
    m['giorno'] = m['collection_date']
    m['righe'] = m['row_count']
    m['impronta_logica'] = m['logical_content_hash']
    m['sha256_file'] = m['file_sha256']
    m['generato'] = m['generated_at_utc']
    m['pyarrow'] = m['pyarrow_version']
    m['completa'] = m['collection_complete']
    (cartella / f'{giorno}.manifest.json').write_text(
        json.dumps({k: v for k, v in m.items() if k in _CHIAVI_MANIFESTO},
                   indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    return parquet, m


_CHIAVI_MANIFESTO = ('archive_schema_version', 'collection_date', 'collection_complete',
                     'collection_incomplete_reasons', 'currency', 'row_count',
                     'logical_content_hash', 'file_sha256', 'file_bytes',
                     'generated_at_utc', 'git_sha', 'github_run_id', 'github_run_attempt',
                     'pyarrow_version', 'columns', 'anomalies', 'window_rows_per_day',
                     'collection_report', 'note')


# ── riepilogo per chi guarda ─────────────────────────────────────────────────

def riepilogo(testo_md: str):
    print(testo_md)
    percorso = os.environ.get('GITHUB_STEP_SUMMARY')
    if percorso:
        try:
            with open(percorso, 'a', encoding='utf-8') as f:
                f.write(testo_md + '\n')
        except OSError:
            pass


# ── il programma ─────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Archivio permanente su Cloudflare R2.')
    ap.add_argument('--solo-locale', metavar='CARTELLA',
                    help='scrive i file qui, senza toccare la rete')
    ap.add_argument('--elenco', action='store_true',
                    help='mostra cosa c\'e\' gia\' nell\'archivio e si ferma')
    ap.add_argument('--giorno', metavar='AAAA-MM-GG',
                    help='lavora su questo giorno della finestra invece che sul piu\' fresco')
    ap.add_argument('--sostituisci-giorno', metavar='AAAA-MM-GG',
                    help='riparazione manuale: mette da parte il definitivo esistente '
                         'e lo sostituisce. Richiede --motivo.')
    ap.add_argument('--motivo', help='perche\' si sta sostituendo un giorno definitivo')
    args = ap.parse_args(argv)

    if args.sostituisci_giorno and not args.motivo:
        ap.error('--sostituisci-giorno richiede --motivo: una sostituzione senza '
                 'spiegazione scritta non e\' una riparazione, e\' una perdita')

    s3 = secchio = None
    if not args.solo_locale:
        s3, secchio = cliente()
        if not s3:
            return 1

    if args.elenco:
        presenti = elenco(s3, secchio)
        parquet = {k: v for k, v in presenti.items() if k.endswith('.parquet')}
        print(f'{len(parquet)} giorni definitivi, {sum(parquet.values())/1e6:.2f} MB')
        for k in sorted(parquet):
            print(f'  {k}  {parquet[k]/1e6:6.3f} MB')
        stag = elenco(s3, secchio, STAGING)
        if stag:
            print(f'\n{len([k for k in stag if k.endswith(".parquet")])} giorni in attesa '
                  f'(staging), mai finalizzati:')
            for k in sorted(stag):
                print(f'  {k}')
        return 0

    scelto = args.sostituisci_giorno or args.giorno
    giorno_chiesto = None
    if scelto:
        try:
            giorno_chiesto = dt.date.fromisoformat(scelto)
        except ValueError:
            ap.error(f'data non valida: {scelto!r}')

    print('— lettura della finestra —')
    giorno, grezze, conteggi, anomalie_lettura = osservazioni(giorno_chiesto)
    if giorno is None or not grezze:
        print('nessuna osservazione utilizzabile in data/fares')
        return 1
    print(f'  {sum(conteggi.values()):,} osservazioni su {len(conteggi)} giorni '
          f'({min(conteggi)} → {max(conteggi)})')
    print(f'  giorno da archiviare: {giorno} — {len(grezze):,} osservazioni')

    righe, anomalie = normalizza(grezze)
    grezze.clear()          # le righe grezze non servono piu': libera prima di Arrow
    anomalie.update(anomalie_lettura)
    if anomalie:
        print('\n— anomalie (tutte registrate nel manifesto) —')
        for k, v in sorted(anomalie.items()):
            print(f'  {k}: {v:,}')

    try:
        rapporto = json.loads(RAPPORTO.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        rapporto = None

    completa, motivi = completezza(rapporto, giorno, len(righe), anomalie)

    # Seconda linea: il volume, confrontato con i giorni gia' archiviati. La
    # mediana non va tenuta da nessuna parte — e' nei manifesti che abbiamo
    # gia' su R2, e l'elenco lo facciamo comunque.
    storici = []
    if s3:
        presenti = elenco(s3, secchio)
        for k, peso in presenti.items():
            if k.endswith('.parquet') and not k.endswith(f'{giorno}.parquet'):
                storici.append(peso)
        # Il peso e' un buon sostituto del numero di righe: 5,4 byte a riga,
        # stabile, e non richiede di scaricare tutti i manifesti.
        storici = [int(p / 5.4) for p in storici]
    anomalo, nota_volume = sotto_la_norma(len(righe), storici)
    if anomalo:
        completa = False
        motivi.append('volume fuori norma: ' + nota_volume)

    print('\n— completezza della raccolta —')
    print(f'  {nota_volume}')
    if completa:
        print('  COMPLETA: la raccolta ha finito il suo lavoro')
    else:
        print('  INCOMPLETA:')
        for m in motivi:
            print(f'    · {m}')

    # Il file si costruisce sempre: anche una giornata incompleta va conservata
    # da qualche parte, perche' e' l'unica copia di quelle osservazioni.
    cartella = pathlib.Path(args.solo_locale) if args.solo_locale else COPIA_LOCALE
    parquet, m = _scheletro(giorno, righe, anomalie, conteggi, completa, motivi,
                            cartella, rapporto, args.motivo)
    print(f'\n— file costruito —')
    print(f'  {parquet}  {len(righe):,} righe  {parquet.stat().st_size/1e6:.2f} MB '
          f'({parquet.stat().st_size/max(1,len(righe)):.1f} byte/riga)')
    print(f'  impronta logica: {m["impronta_logica"][:16]}…')

    if args.solo_locale:
        return 0

    esito, dettaglio = pubblica(s3, secchio, giorno, parquet, m, cartella,
                                completa, args.sostituisci_giorno, args.motivo)

    riepilogo('\n'.join([
        '',
        f'### Archivio permanente — {giorno}',
        '',
        f'| | |',
        f'|---|---|',
        f'| esito | **{esito}** |',
        f'| dettaglio | {dettaglio} |',
        f'| righe | {len(righe):,} |',
        f'| dimensione | {parquet.stat().st_size/1e6:.2f} MB |',
        f'| impronta logica | `{m["impronta_logica"]}` |',
        f'| raccolta completa | {"si" if completa else "NO"} |',
        *([f'| perche\' no | {"; ".join(motivi)} |'] if motivi else []),
        *([f'| anomalie | {", ".join(f"{k}={v}" for k, v in sorted(anomalie.items()))} |']
          if anomalie else []),
        '',
    ]))
    return 0 if esito == 'ARCHIVIO OK' else 1


def pubblica(s3, secchio, giorno, parquet, m, cartella, completa, sostituzione, motivo):
    """Il passaggio da file locale a oggetto definitivo, con le sue regole."""
    from botocore.exceptions import ClientError
    finale = chiave(giorno)
    manifesto_finale = chiave_manifesto(giorno)
    locale_manifesto = cartella / f'{giorno}.manifest.json'

    def metti_manifesto(destinazione, condizionale):
        with open(locale_manifesto, 'rb') as f:
            extra = {'IfNoneMatch': '*'} if condizionale else {}
            try:
                s3.put_object(Bucket=secchio, Key=destinazione, Body=f,
                              ContentType='application/json', Metadata=etichette(m), **extra)
            except ClientError as e:
                if not condizionale:
                    raise
                codice = e.response.get('Error', {}).get('Code', '')
                stato = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
                if codice not in ('PreconditionFailed', 'ConditionalRequestConflict') \
                        and stato not in (412, 409):
                    raise

    try:
        esistente = descrizione(s3, secchio, finale)
    except ClientError as e:
        return 'ARCHIVIO FALLITO', f'R2 non risponde: {e.response.get("Error", {}).get("Code")}'

    # ── riparazione esplicita ────────────────────────────────────────────────
    if sostituzione:
        if not esistente:
            return 'ARCHIVIO FALLITO', (f'{finale} non esiste: non c\'e\' niente da '
                                        'sostituire. Senza --sostituisci-giorno sarebbe '
                                        'una creazione normale.')
        vecchia = (esistente.get('Metadata') or {}).get('logical-hash', '?')
        marca = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        riparo = f'{SUPERATI}/{giorno}/{marca}.parquet'
        s3.copy_object(Bucket=secchio, Key=riparo,
                       CopySource={'Bucket': secchio, 'Key': finale},
                       MetadataDirective='COPY')
        print(f'  versione precedente messa da parte: {riparo}')
        m['note'] = (f'sostituisce la versione con impronta {vecchia}; '
                     f'copia conservata in {riparo}; motivo: {motivo}')
        locale_manifesto.write_text(
            json.dumps({k: v for k, v in m.items() if k in _CHIAVI_MANIFESTO},
                       indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        ok, dett = carica(s3, secchio, parquet, finale, m, solo_se_assente=False)
        if not ok:
            return 'ARCHIVIO FALLITO', f'sostituzione non riuscita: {dett}'
        metti_manifesto(manifesto_finale, condizionale=False)
        return 'ARCHIVIO OK', (f'giorno sostituito su richiesta esplicita. '
                               f'vecchia impronta {vecchia[:16]}…, '
                               f'nuova {m["impronta_logica"][:16]}…')

    # ── giornata incompleta: mai definitiva ──────────────────────────────────
    if not completa:
        chiave_staging = f'{STAGING}/{giorno}.parquet'
        try:
            carica(s3, secchio, parquet, chiave_staging, m, solo_se_assente=False)
            metti_manifesto(f'{STAGING}/{giorno}.manifest.json', condizionale=False)
            dove = f'messa al sicuro in {chiave_staging}'
        except ClientError as e:
            dove = f'NON salvata nemmeno in staging ({e.response.get("Error", {}).get("Code")})'
        return 'ARCHIVIO FALLITO', (f'raccolta incompleta: niente definitivo. {dove}. '
                                    'Il Parquet e\' anche fra gli artifact del flusso.')

    # ── il definitivo esiste gia' ────────────────────────────────────────────
    if esistente:
        gia = (esistente.get('Metadata') or {}).get('logical-hash')
        if gia == m['impronta_logica']:
            return 'ARCHIVIO OK', 'gia\' archiviato, contenuto identico: niente da fare'
        return 'ARCHIVIO FALLITO', (
            f'{finale} esiste gia\' con un contenuto DIVERSO '
            f'(archiviata {str(gia)[:16]}…, ora {m["impronta_logica"][:16]}…). '
            'Non lo sovrascrivo. Se la versione nuova e\' davvero migliore: '
            f'python scripts/archivio.py --sostituisci-giorno {giorno} --motivo "..."')

    # ── creazione, atomica ───────────────────────────────────────────────────
    try:
        ok, dett = carica(s3, secchio, parquet, finale, m, solo_se_assente=True)
    except ClientError as e:
        return 'ARCHIVIO FALLITO', f'caricamento rifiutato: {e.response.get("Error", {}).get("Code")}'
    if not ok:
        return 'ARCHIVIO FALLITO', f'creazione non riuscita: {dett}'
    metti_manifesto(manifesto_finale, condizionale=True)
    return 'ARCHIVIO OK', f'giorno creato e {dett}'


if __name__ == '__main__':
    raise SystemExit(main())
