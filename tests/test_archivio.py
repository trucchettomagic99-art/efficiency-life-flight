"""Collaudo dell'archivio permanente.

Quello che non richiede pyarrow gira sempre, anche nel collaudo veloce che
precede la raccolta notturna: sono le regole che decidono *se* e *dove* si
scrive, cioe' le uniche che possono rovinare un archivio immutabile. Il giro
completo su Parquet gira dove pyarrow c'e' — nel passo che archivia davvero.

Le prove sul caricamento usano un R2 finto: un dizionario che si comporta come
il servizio per le sole quattro chiamate che facciamo (head, put, copy, list),
compresa la precondizione `If-None-Match: *`. Serve a provare la macchina a
stati senza rete, che e' esattamente la parte che non si puo' collaudare in
produzione senza sporcare l'archivio.
"""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

spec = importlib.util.spec_from_file_location('archivio', ROOT / 'scripts' / 'archivio.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

try:
    import pyarrow  # noqa: F401
    import pyarrow.parquet  # noqa: F401
    C_E_PYARROW = True
except ImportError:
    C_E_PYARROW = False

G = lambda s: dt.date.fromisoformat(s)


def osservazione(**kw):
    """Una riga grezza come la scrive fetch_prices.py."""
    return dict({'o': 'FCO', 'd': 'MAN', 'p': 40.0, 'dep': '2026-10-02',
                 'ret': '2026-10-05', 'dur': 320, 'km': 1700, 'n': 3,
                 'obs': '2026-09-15', 's': 'tp', 'endpoint': 'dates',
                 'direct_check': 'both_legs', 'distance_source': 'great_circle'}, **kw)


def rapporto(**kw):
    """Un collection-report sano."""
    return dict({'date': '2026-09-15', 'published': True,
                 'endpoints': {'latest:ok': 1539, 'dates:ok': 1528,
                               'dates:partial': 11, 'latest:error': 1, 'dates:error': 1},
                 'queried_origins': 1540, 'covered_origins': 1410}, **kw)


# ══ G. il percorso dice di che schema e' ════════════════════════════════════

class DoveFinisconoIFile(unittest.TestCase):
    def test_il_percorso_contiene_la_versione_dello_schema(self):
        self.assertEqual(
            A.chiave(G('2026-09-15')),
            'osservazioni/schema=v1/anno=2026/mese=09/2026-09-15.parquet')
        self.assertIn('schema=v1', A.chiave(G('2027-01-03')))

    def test_anno_e_mese_permettono_la_potatura(self):
        self.assertEqual(A.chiave(G('2027-01-03')),
                         'osservazioni/schema=v1/anno=2027/mese=01/2027-01-03.parquet')

    def test_il_manifesto_sta_accanto_al_parquet(self):
        self.assertEqual(A.chiave_manifesto(G('2026-09-15')),
                         'osservazioni/schema=v1/anno=2026/mese=09/2026-09-15.manifest.json')

    def test_un_giorno_un_file(self):
        giorni = [G('2026-09-15'), G('2026-09-16'), G('2026-10-01')]
        self.assertEqual(len({A.chiave(g) for g in giorni}), 3)


# ══ A/B. il tempo ═══════════════════════════════════════════════════════════

class ComeSiLeggeIlTempo(unittest.TestCase):
    """`obs` oggi e' una data pura: fetch_prices scrive `now(utc).date()`.

    Non c'e' nessuna ora da conservare — nelle 630.629 righe del 15 settembre
    `obs` e' lungo dieci caratteri in tutte. Inventarne una (T00:00:00Z)
    sarebbe una misura falsa. Quello che si puo' garantire e' che se un giorno
    arrivasse un istante, verrebbe normalizzato in UTC e segnalato, non
    tagliato di nascosto.
    """

    def test_una_data_pura_resta_una_data(self):
        self.assertEqual(A.giorno_di('2026-09-15'), (G('2026-09-15'), False))

    def test_un_istante_con_fuso_si_normalizza_in_utc_e_si_segnala(self):
        # 00:30 a Roma (+02:00) e' ancora il giorno prima in UTC: tagliare la
        # stringa avrebbe dato il 15, il fuso dice 14.
        giorno, con_ora = A.giorno_di('2026-09-15T00:30:00+02:00')
        self.assertEqual(giorno, G('2026-09-14'))
        self.assertTrue(con_ora, 'il cambio di formato deve essere segnalato')

    def test_un_istante_senza_fuso_si_legge_come_utc(self):
        self.assertEqual(A.giorno_di('2026-09-15T23:00:00')[0], G('2026-09-15'))

    def test_una_data_illeggibile_non_diventa_un_giorno_qualsiasi(self):
        for cattiva in (None, '', 'boh', '2026-13-45', 123, [], {}):
            self.assertEqual(A.giorno_di(cattiva), (None, False), cattiva)

    def test_found_at_conserva_l_istante_in_utc(self):
        m = A.istante_di('2026-09-15T04:12:33Z')
        self.assertEqual(m.year, 2026)
        self.assertEqual((m.hour, m.minute, m.second), (4, 12, 33))
        self.assertEqual(m.tzinfo, dt.timezone.utc)
        self.assertEqual(A.istante_di('2026-09-15T06:12:33+02:00'), m)

    def test_found_at_si_tronca_al_millisecondo_una_volta_sola(self):
        m = A.istante_di('2026-09-15T04:12:33.987654Z')
        self.assertEqual(m.microsecond, 987000)

    def test_dep_e_ret_restano_date(self):
        r, _ = A.normalizza([osservazione()])
        self.assertIsInstance(r[0]['dep'], dt.date)
        self.assertNotIsInstance(r[0]['dep'], dt.datetime)
        self.assertEqual(r[0]['dep'], G('2026-10-02'))
        self.assertEqual(r[0]['ret'], G('2026-10-05'))


# ══ C. il denaro ════════════════════════════════════════════════════════════

class ComeSiLeggeIlPrezzo(unittest.TestCase):
    def test_gli_euro_diventano_centesimi_esatti(self):
        self.assertEqual(A.centesimi(40.0), 4000)
        self.assertEqual(A.centesimi(67), 6700)
        self.assertEqual(A.centesimi('11416.00'), 1141600)

    def test_i_decimali_che_in_binario_non_esistono(self):
        # int(0.1*100) fa 10 per fortuna; int(0.29*100) fa 28 per sfortuna.
        # Passando dal testo si legge la cifra che si vede.
        self.assertEqual(A.centesimi(0.29), 29)
        self.assertEqual(A.centesimi(1.15), 115)
        self.assertEqual(A.centesimi(8.87), 887)
        for euro, atteso in ((0.1, 10), (0.2, 20), (0.3, 30), (2.675, None)):
            self.assertEqual(A.centesimi(euro), atteso, euro)

    def test_un_prezzo_impossibile_non_diventa_un_numero(self):
        for cattivo in (None, '', 'boh', 0, -5, 3.14159, True, False):
            self.assertIsNone(A.centesimi(cattivo), cattivo)

    def test_una_riga_senza_prezzo_valido_viene_esclusa_e_contata(self):
        righe, anomalie = A.normalizza([osservazione(p=None), osservazione()])
        self.assertEqual(len(righe), 1)
        self.assertEqual(anomalie['riga_esclusa_prezzo_non_rappresentabile'], 1)


# ══ D/E. i valori mancanti e quelli impossibili ═════════════════════════════

class ValoriMancantiEImpossibili(unittest.TestCase):
    def test_mancante_diventa_nullo_non_zero(self):
        righe, _ = A.normalizza([osservazione(dur=None, km=None, n=None)])
        self.assertIsNone(righe[0]['dur'])
        self.assertIsNone(righe[0]['km'])
        self.assertIsNone(righe[0]['n'])

    def test_un_valore_impossibile_non_viene_troncato_al_massimo(self):
        # Troncare 999999 a 32767 scriverebbe nell'archivio un numero mai
        # osservato, indistinguibile da una misura vera.
        righe, anomalie = A.normalizza([osservazione(dur=99_999_999_999, km=-3)])
        self.assertIsNone(righe[0]['dur'])
        self.assertIsNone(righe[0]['km'])
        self.assertEqual(anomalie['dur_fuori_scala'], 1)
        self.assertEqual(anomalie['km_fuori_scala'], 1)
        self.assertNotIn(32767, righe[0].values())

    def test_durata_zero_significa_non_lo_so(self):
        # normalize() a monte fa `x.get('duration') or 0`: uno zero non
        # distingue "dura zero minuti", che non esiste, da "non me l'ha detto".
        righe, anomalie = A.normalizza([osservazione(dur=0)])
        self.assertIsNone(righe[0]['dur'])
        self.assertEqual(anomalie['dur_zero_letto_come_ignoto'], 1)

    def test_i_numeri_buoni_restano_quelli(self):
        righe, anomalie = A.normalizza([osservazione()])
        self.assertEqual((righe[0]['dur'], righe[0]['km'], righe[0]['n']), (320, 1700, 3))
        self.assertEqual(dict(anomalie), {})


# ══ F. i campi dell'osservazione ════════════════════════════════════════════

class TuttiICampiSopravvivono(unittest.TestCase):
    """La prima versione ne teneva nove su quindici.

    `endpoint` e `direct_check` erano stati esclusi come "costanti": misurati
    sui dati veri hanno due valori ciascuno, e `direct_check` e' l'unica
    dimensione di qualita' che abbiamo (verificato su entrambe le tratte,
    oppure dichiarato dal fornitore). Tenerli tutti costa il 2,2%.
    """

    def test_le_quindici_colonne_ci_sono_tutte(self):
        self.assertEqual(A.COLONNE, ('obs', 'o', 'd', 'dep', 'ret', 'p_cents',
                                     'dur', 'km', 'n', 'endpoint', 'direct_check',
                                     'distance_source', 'src', 'found_at', 'quality'))

    def test_i_campi_che_prima_si_buttavano(self):
        righe, _ = A.normalizza([osservazione(found_at='2026-09-15T04:12:33Z',
                                              quality='low_price_review')])
        r = righe[0]
        self.assertEqual(r['endpoint'], 'dates')
        self.assertEqual(r['direct_check'], 'both_legs')
        self.assertEqual(r['distance_source'], 'great_circle')
        self.assertEqual(r['src'], 'tp')
        self.assertEqual(r['quality'], 'low_price_review')
        self.assertIsNotNone(r['found_at'])

    def test_distance_source_assente_significa_distanza_del_fornitore(self):
        # Non e' un buco: l'endpoint `latest` porta la propria distanza e
        # allora il campo non viene scritto. Il nullo e' il secondo valore.
        grezza = osservazione()
        del grezza['distance_source']
        righe, _ = A.normalizza([grezza])
        self.assertIsNone(righe[0]['distance_source'])

    def test_i_campi_del_collettore_non_archiviati_sono_solo_questi(self):
        # Se fetch_prices aggiunge un campo nuovo, questa prova lo fa notare
        # invece di lasciarlo sparire in silenzio.
        noti = {'o', 'd', 'p', 'dep', 'ret', 'dur', 'km', 'obs', 'n', 's',
                'endpoint', 'direct_check', 'distance_source', 'found_at', 'quality'}
        archiviati_da = {'p': 'p_cents', 's': 'src'}
        mancano = noti - set(A.COLONNE) - set(archiviati_da)
        self.assertEqual(mancano, set(), f'campi non archiviati: {mancano}')


# ══ N. l'impronta logica ════════════════════════════════════════════════════

class ImprontaLogica(unittest.TestCase):
    def test_lo_stesso_insieme_in_ordine_diverso_da_la_stessa_impronta(self):
        righe, _ = A.normalizza([osservazione(d='LHR', p=67), osservazione(),
                                 osservazione(d='ARN', p=91)])
        self.assertEqual(A.impronta(righe), A.impronta(list(reversed(righe))))

    def test_una_riga_diversa_da_un_impronta_diversa(self):
        a, _ = A.normalizza([osservazione()])
        b, _ = A.normalizza([osservazione(p=41)])
        self.assertNotEqual(A.impronta(a), A.impronta(b))

    def test_un_nullo_non_si_confonde_con_una_stringa_vuota(self):
        a, _ = A.normalizza([osservazione(dur=None)])
        b, _ = A.normalizza([osservazione(dur=0)])
        self.assertEqual(A.impronta(a), A.impronta(b))   # entrambi ignoti: stesso dato
        c, _ = A.normalizza([osservazione(dur=1)])
        self.assertNotEqual(A.impronta(a), A.impronta(c))

    def test_e_un_hash_e_non_dipende_da_pyarrow(self):
        righe, _ = A.normalizza([osservazione()])
        self.assertEqual(len(A.impronta(righe)), 64)
        self.assertEqual(A.impronta([]), A.impronta([]))


# ══ H/I/Q. la raccolta e' finita davvero? ═══════════════════════════════════

class QuandoLaRaccoltaECompleta(unittest.TestCase):
    GIORNO = G('2026-09-15')

    SANO = object()

    def completo(self, rap=SANO, righe=362089, anomalie=None):
        return A.completezza(rapporto() if rap is self.SANO else rap,
                             self.GIORNO, righe, anomalie or Counter())

    def test_una_raccolta_sana_e_completa(self):
        ok, motivi = self.completo()
        self.assertTrue(ok, motivi)
        self.assertEqual(motivi, [])

    def test_il_tetto_delle_pagine_non_e_incompletezza(self):
        # Undici origini (DME, SVO, IST...) lo raggiungono ogni notte: e' un
        # limite strutturale noto. Trattarlo da guasto farebbe fallire sempre.
        ok, motivi = self.completo(rapporto(page_cap_origins=['DME', 'SVO', 'IST'],
                                            endpoints={'dates:partial': 11, 'dates:ok': 1528,
                                                       'latest:ok': 1539}))
        self.assertTrue(ok, motivi)

    def test_le_origini_rinviate_sono_incompletezza(self):
        # "deferred" = budget dei 1.080 secondi esaurito prima di arrivarci:
        # e' esattamente la giornata monca.
        ok, motivi = self.completo(rapporto(endpoints={'dates:ok': 900, 'dates:deferred': 640}))
        self.assertFalse(ok)
        self.assertTrue(any('rinviate' in m for m in motivi), motivi)

    def test_una_raccolta_non_pubblicata_non_si_finalizza(self):
        ok, motivi = self.completo(rapporto(published=False))
        self.assertFalse(ok)
        self.assertTrue(any('published' in m for m in motivi), motivi)

    def test_il_rapporto_deve_parlare_di_questo_giorno(self):
        # Se fetch_prices e' fallito, data/fares e' quello di ieri e il
        # rapporto pure: non c'e' niente da finalizzare per oggi.
        ok, motivi = self.completo(rapporto(date='2026-09-14'))
        self.assertFalse(ok)
        self.assertTrue(any('2026-09-14' in m for m in motivi), motivi)

    def test_troppi_errori_sono_incompletezza(self):
        ok, motivi = self.completo(rapporto(endpoints={'dates:ok': 900, 'dates:error': 300}))
        self.assertFalse(ok)
        self.assertTrue(any('errori' in m for m in motivi), motivi)

    def test_senza_rapporto_non_si_finalizza(self):
        for assente in (None, 'boh', []):
            ok, motivi = self.completo(assente)
            self.assertFalse(ok, assente)

    def test_uno_scomparto_illeggibile_impedisce_il_definitivo(self):
        # Di quell'origine, quella notte, non sappiamo niente: la giornata non
        # puo' dirsi completa solo perche' il resto e' andato bene.
        ok, motivi = self.completo(anomalie=Counter({'scomparto_illeggibile': 1}))
        self.assertFalse(ok)
        self.assertTrue(any('illeggibili' in m for m in motivi), motivi)

    def test_zero_righe_non_e_una_giornata(self):
        ok, _ = self.completo(righe=0)
        self.assertFalse(ok)


class SecondaLineaSulVolume(unittest.TestCase):
    def test_senza_storia_non_si_giudica(self):
        anomalo, _ = A.sotto_la_norma(362089, [])
        self.assertFalse(anomalo)
        anomalo, _ = A.sotto_la_norma(1, [300000, 310000])
        self.assertFalse(anomalo, 'due giorni non fanno una mediana')

    def test_un_volume_normale_passa(self):
        anomalo, _ = A.sotto_la_norma(350000, [300000, 310000, 320000, 330000])
        self.assertFalse(anomalo)

    def test_un_crollo_di_volume_ferma_il_definitivo(self):
        anomalo, nota = A.sotto_la_norma(40000, [300000, 310000, 320000, 330000])
        self.assertTrue(anomalo)
        self.assertIn('mediana', nota)


# ══ la finestra: quale giorno si archivia ═══════════════════════════════════

class QualeGiornoSiArchivia(unittest.TestCase):
    def scrivi_finestra(self, cartella, per_giorno):
        for origine, (giorno, quante) in per_giorno.items():
            (cartella / f'{origine}.json').write_text(json.dumps({
                'schema': 2, 'origin': origine,
                'deals': [osservazione(o=origine, d=f'D{i:02d}', obs=giorno)
                          for i in range(quante)]}), encoding='utf-8')

    def test_si_prende_il_giorno_piu_fresco_e_si_ignorano_gli_altri(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp)
            self.scrivi_finestra(c, {'AAA': ('2026-09-09', 3), 'BBB': ('2026-09-15', 5),
                                     'CCC': ('2026-09-14', 4)})
            giorno, righe, conteggi, _ = A.osservazioni(oggi=G('2026-09-15'), cartella=c)
            self.assertEqual(giorno, G('2026-09-15'))
            self.assertEqual(len(righe), 5, 'in memoria solo il giorno bersaglio')
            self.assertEqual(sum(conteggi.values()), 12, 'ma contati tutti')

    def test_una_rilevazione_nel_futuro_non_diventa_il_giorno_fresco(self):
        # Un orologio sbagliato non deve poter far buttare il giorno vero.
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp)
            self.scrivi_finestra(c, {'AAA': ('2026-09-15', 5), 'ZZZ': ('2027-01-01', 2)})
            giorno, righe, _, anomalie = A.osservazioni(oggi=G('2026-09-15'), cartella=c)
            self.assertEqual(giorno, G('2026-09-15'))
            self.assertEqual(len(righe), 5)
            self.assertEqual(anomalie['obs_nel_futuro'], 2)

    def test_uno_scomparto_corrotto_si_segnala_e_non_finge(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp)
            self.scrivi_finestra(c, {'AAA': ('2026-09-15', 5)})
            (c / 'ROTTO.json').write_text('{ questo non e" json', encoding='utf-8')
            giorno, righe, _, anomalie = A.osservazioni(oggi=G('2026-09-15'), cartella=c)
            self.assertEqual(len(righe), 5)
            self.assertEqual(anomalie['scomparto_illeggibile'], 1)
            ok, motivi = A.completezza(rapporto(), giorno, len(righe), anomalie)
            self.assertFalse(ok, 'la giornata non puo dirsi completa')

    def test_si_puo_chiedere_un_giorno_preciso(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp)
            self.scrivi_finestra(c, {'AAA': ('2026-09-09', 3), 'BBB': ('2026-09-15', 5)})
            giorno, righe, _, _ = A.osservazioni(giorno=G('2026-09-09'),
                                                 oggi=G('2026-09-15'), cartella=c)
            self.assertEqual((giorno, len(righe)), (G('2026-09-09'), 3))


# ══ H/I/J/K/L. la macchina a stati del caricamento ══════════════════════════

class R2Finto:
    """Il minimo che serve per provare le regole: quattro chiamate e una
    precondizione. Registra tutto quello che riceve, cosi' le prove possono
    dire non solo cosa e' successo ma cosa NON e' stato scritto."""

    def __init__(self, oggetti=None):
        self.oggetti = dict(oggetti or {})
        self.scritture = []

    def _errore(self, codice, stato):
        from botocore.exceptions import ClientError
        return ClientError({'Error': {'Code': codice},
                            'ResponseMetadata': {'HTTPStatusCode': stato}}, 'op')

    def head_object(self, Bucket, Key, **kw):
        if Key not in self.oggetti:
            raise self._errore('404', 404)
        return self.oggetti[Key]

    def put_object(self, Bucket, Key, Body, Metadata=None, **kw):
        if kw.get('IfNoneMatch') == '*' and Key in self.oggetti:
            raise self._errore('PreconditionFailed', 412)
        corpo = Body.read() if hasattr(Body, 'read') else Body
        self.oggetti[Key] = {'ContentLength': len(corpo),
                             'Metadata': dict(Metadata or {}),
                             'ETag': '"' + __import__('hashlib').md5(corpo).hexdigest() + '"',
                             'Corpo': corpo}
        self.scritture.append(Key)
        return {}

    def copy_object(self, Bucket, Key, CopySource, **kw):
        self.oggetti[Key] = dict(self.oggetti[CopySource['Key']])
        self.scritture.append(Key)
        return {}

    def list_objects_v2(self, Bucket, Prefix, **kw):
        return {'Contents': [{'Key': k, 'Size': v['ContentLength']}
                             for k, v in sorted(self.oggetti.items()) if k.startswith(Prefix)],
                'IsTruncated': False}


@unittest.skipUnless(C_E_PYARROW, 'pyarrow non installato')
class CaricamentoSuR2(unittest.TestCase):
    GIORNO = G('2026-09-15')

    def prepara(self, cartella, righe_grezze=None, completa=True):
        righe, anomalie = A.normalizza(righe_grezze or [osservazione(), osservazione(d='LHR', p=67)])
        return A._scheletro(self.GIORNO, righe, anomalie, Counter({self.GIORNO: len(righe)}),
                            completa, [] if completa else ['finta incompletezza'],
                            pathlib.Path(cartella), rapporto())

    def test_giornata_completa_crea_il_definitivo_e_il_manifesto(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK', dett)
            self.assertIn(A.chiave(self.GIORNO), s3.oggetti)
            self.assertIn(A.chiave_manifesto(self.GIORNO), s3.oggetti)
            etichette = s3.oggetti[A.chiave(self.GIORNO)]['Metadata']
            self.assertEqual(etichette['logical-hash'], m['impronta_logica'])
            self.assertEqual(etichette['rows'], str(m['righe']))
            self.assertEqual(etichette['currency'], 'EUR')
            self.assertEqual(etichette['schema'], 'v1')

    def test_giornata_incompleta_non_crea_il_definitivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp, completa=False)
            s3 = R2Finto()
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), False, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertNotIn(A.chiave(self.GIORNO), s3.oggetti)
            self.assertIn(f'{A.STAGING}/{self.GIORNO}.parquet', s3.oggetti,
                          'ma i dati non si buttano: vanno in staging')

    def test_stesso_contenuto_gia_presente_e_un_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto({A.chiave(self.GIORNO): {
                'ContentLength': 1, 'Metadata': {'logical-hash': m['impronta_logica']}}})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK')
            self.assertIn('identico', dett)
            self.assertEqual(s3.scritture, [], 'niente da riscrivere')

    def test_contenuto_diverso_gia_presente_e_un_errore_senza_sovrascrittura(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            prima = {'ContentLength': 1, 'Metadata': {'logical-hash': 'a' * 64}}
            s3 = R2Finto({A.chiave(self.GIORNO): prima})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.scritture, [], 'nessuna scrittura')
            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)], prima, 'intatto')
            self.assertIn('--sostituisci-giorno', dett, 'e si dice come si ripara')

    def test_la_precondizione_regge_anche_se_qualcuno_scrive_nel_frattempo(self):
        # head dice "non c'e'", ma fra head e put un'altra esecuzione crea
        # l'oggetto: If-None-Match lo rifiuta lato server.
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            originale = s3.head_object

            def head_poi_crea(Bucket, Key, **kw):
                try:
                    return originale(Bucket=Bucket, Key=Key, **kw)
                finally:
                    if Key == A.chiave(self.GIORNO) and Key not in s3.oggetti:
                        s3.oggetti[Key] = {'ContentLength': 9, 'Metadata': {'logical-hash': 'z' * 64}}
            s3.head_object = head_poi_crea
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)]['Metadata']['logical-hash'],
                             'z' * 64, 'l\'oggetto dell\'altro non e\' stato toccato')

    def test_la_sostituzione_mette_da_parte_la_versione_precedente(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto({A.chiave(self.GIORNO): {
                'ContentLength': 9, 'Metadata': {'logical-hash': 'a' * 64}, 'Corpo': b'vecchio'}})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m, pathlib.Path(tmp),
                                     True, str(self.GIORNO), 'recuperato dalla storia di git')
            self.assertEqual(esito, 'ARCHIVIO OK', dett)
            messi_da_parte = [k for k in s3.oggetti if k.startswith(A.SUPERATI)]
            self.assertEqual(len(messi_da_parte), 1, 'la vecchia versione e conservata')
            self.assertEqual(s3.oggetti[messi_da_parte[0]]['Metadata']['logical-hash'], 'a' * 64)
            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)]['Metadata']['logical-hash'],
                             m['impronta_logica'])
            manifesto = json.loads(s3.oggetti[A.chiave_manifesto(self.GIORNO)]['Corpo'])
            self.assertIn('recuperato dalla storia di git', manifesto['note'])
            self.assertIn('a' * 64, manifesto['note'], 'e si scrive quale impronta e stata superata')

    def test_la_sostituzione_di_un_giorno_inesistente_non_si_fa(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            esito, _ = A.pubblica(s3, 'b', self.GIORNO, parquet, m, pathlib.Path(tmp),
                                  True, str(self.GIORNO), 'motivo')
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.scritture, [])

    def test_serve_un_motivo_scritto_per_sostituire(self):
        import contextlib, io
        with contextlib.redirect_stderr(io.StringIO()) as rumore:
            with self.assertRaises(SystemExit):
                A.main(['--sostituisci-giorno', '2026-09-15'])
        self.assertIn('--motivo', rumore.getvalue())


class BootstrapDiUnArchivioVuoto(unittest.TestCase):
    """Con R2 vuoto NON si prendono i sette giorni della finestra.

    I sei precedenti sono gia' impoveriti: `clean_rows()` tiene, per ogni
    (o, d, dep, ret), solo l'osservazione piu' recente, quindi le righe vecchie
    vengono superate. Misurato il 15 settembre: 362.089 righe per il giorno
    fresco contro 14.621 per quello di sei giorni prima. Archiviarli come
    definitivi vorrebbe dire congelare una versione monca al posto di quella
    buona, che e' ancora recuperabile dalla storia di git.
    """

    def test_si_finalizza_un_giorno_solo(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = pathlib.Path(tmp)
            for origine, giorno in [('AAA', '2026-09-09'), ('BBB', '2026-09-12'),
                                    ('CCC', '2026-09-15')]:
                (c / f'{origine}.json').write_text(json.dumps({'deals': [
                    osservazione(o=origine, obs=giorno)]}), encoding='utf-8')
            giorno, righe, conteggi, _ = A.osservazioni(oggi=G('2026-09-15'), cartella=c)
            self.assertEqual(giorno, G('2026-09-15'))
            self.assertEqual(len(righe), 1)
            self.assertEqual(len(conteggi), 3, 'gli altri si vedono, ma non si archiviano')


# ══ O/P. il giro completo su Parquet ════════════════════════════════════════

@unittest.skipUnless(C_E_PYARROW, 'pyarrow non installato')
class GiroCompletoSuParquet(unittest.TestCase):
    def test_i_valori_tornano_indietro_tutti_uguali(self):
        grezza = osservazione(found_at='2026-09-15T04:12:33Z', quality='low_price_review')
        righe, _ = A.normalizza([grezza])
        r = A.tabella(righe).to_pylist()[0]
        self.assertEqual(r['obs'], G('2026-09-15'))
        self.assertEqual((r['o'], r['d']), ('FCO', 'MAN'))
        self.assertEqual(r['dep'], G('2026-10-02'))
        self.assertEqual(r['ret'], G('2026-10-05'))
        self.assertEqual(r['p_cents'], 4000)
        self.assertEqual((r['dur'], r['km'], r['n']), (320, 1700, 3))
        self.assertEqual(r['endpoint'], 'dates')
        self.assertEqual(r['direct_check'], 'both_legs')
        self.assertEqual(r['distance_source'], 'great_circle')
        self.assertEqual(r['src'], 'tp')
        self.assertEqual(r['quality'], 'low_price_review')
        self.assertEqual(r['found_at'], A.istante_di('2026-09-15T04:12:33Z'))

    def test_lo_schema_e_quello_dichiarato(self):
        righe, _ = A.normalizza([osservazione()])
        t = A.tabella(righe)
        self.assertEqual([c.name for c in t.schema], list(A.COLONNE))
        tipi = {c.name: str(c.type) for c in t.schema}
        self.assertEqual(tipi['p_cents'], 'int32', 'il denaro non e un float')
        self.assertNotIn('float', tipi['p_cents'])
        self.assertEqual(tipi['obs'], 'date32[day]')
        self.assertEqual(tipi['dep'], 'date32[day]')
        self.assertEqual(tipi['o'], 'string', 'tipo logico stabile, non dictionary Arrow')
        self.assertEqual(tipi['found_at'], 'timestamp[ms, tz=UTC]')

    def test_i_nulli_restano_nulli_anche_dopo_il_file(self):
        import pyarrow.parquet as pq
        righe, _ = A.normalizza([osservazione(dur=None, km=None, n=None), osservazione()])
        with tempfile.TemporaryDirectory() as tmp:
            f = A.scrivi(righe, pathlib.Path(tmp) / 'g.parquet')
            letto = pq.read_table(f).to_pylist()
        nulli = [r for r in letto if r['dur'] is None]
        self.assertEqual(len(nulli), 1)
        self.assertIsNone(nulli[0]['km'])
        self.assertIsNone(nulli[0]['n'])

    def test_due_scritture_danno_lo_stesso_file_nello_stesso_ambiente(self):
        righe, _ = A.normalizza([osservazione(d='LHR', p=67), osservazione(),
                                 osservazione(d='ARN', p=91)])
        with tempfile.TemporaryDirectory() as tmp:
            a = A.scrivi(righe, pathlib.Path(tmp) / 'a.parquet')
            b = A.scrivi(list(reversed(righe)), pathlib.Path(tmp) / 'b.parquet')
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_il_manifesto_dice_tutto_quello_che_serve_fra_dieci_anni(self):
        righe, anomalie = A.normalizza([osservazione(), osservazione(dur=0)])
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = A._scheletro(G('2026-09-15'), righe, anomalie,
                                      Counter({G('2026-09-15'): 2}), True, [],
                                      pathlib.Path(tmp), rapporto())
            scritto = json.loads((pathlib.Path(tmp) / '2026-09-15.manifest.json').read_text())
            for campo in ('archive_schema_version', 'collection_date', 'collection_complete',
                          'currency', 'row_count', 'logical_content_hash', 'file_sha256',
                          'file_bytes', 'generated_at_utc', 'git_sha', 'github_run_id',
                          'pyarrow_version', 'columns', 'anomalies', 'window_rows_per_day',
                          'collection_report'):
                self.assertIn(campo, scritto, campo)
            self.assertEqual(scritto['archive_schema_version'], 'v1')
            self.assertEqual(scritto['currency'], 'EUR')
            self.assertEqual(scritto['row_count'], 2)
            self.assertEqual(scritto['logical_content_hash'], A.impronta(righe))
            self.assertEqual(scritto['anomalies']['dur_zero_letto_come_ignoto'], 1)
            self.assertEqual(scritto['file_sha256'], A.sha_file(parquet))
            self.assertEqual(scritto['pyarrow_version'], pyarrow.__version__)


if __name__ == '__main__':
    unittest.main()
