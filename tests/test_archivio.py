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
import os
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

# Il collaudo che precede la scrittura su R2 non puo' accontentarsi di prove
# saltate: sono proprio quelle che toccano Parquet e caricamento, cioe' tutto
# quello che rende un oggetto immutabile. Con questa variabile a 1 l'assenza di
# pyarrow diventa un errore rumoroso invece di tredici righe con la "s".
if os.environ.get('ARCHIVIO_RICHIEDE_PYARROW') == '1' and not C_E_PYARROW:
    raise RuntimeError(
        'ARCHIVIO_RICHIEDE_PYARROW=1 ma pyarrow non e\' installato: questo collaudo '
        'deve girare per intero prima di scrivere su R2, non saltare.')

G = lambda s: dt.date.fromisoformat(s)


def osservazione(**kw):
    """Una riga grezza come la scrive fetch_prices.py."""
    return dict({'o': 'FCO', 'd': 'MAN', 'p': 40.0, 'dep': '2026-10-02',
                 'ret': '2026-10-05', 'dur': 320, 'km': 1700, 'n': 3,
                 'obs': '2026-09-15', 's': 'tp', 'endpoint': 'dates',
                 'direct_check': 'both_legs', 'distance_source': 'great_circle'}, **kw)


def rapporto(**kw):
    """Un collection-report sano: quello vero del 15 settembre 2026.

    Gli undici `dates:partial` sono gli undici `page_cap_origins`, e si
    dimostra per sottrazione: 11 partial − 11 page_cap − 0 repeated_page − 0
    ValueError con righe = 0 interruzioni da budget. I due `:error` sono i due
    upstream_http_400, che non avevano prodotto righe.
    """
    return dict({'date': '2026-09-15', 'published': True,
                 'endpoints': {'latest:ok': 1539, 'dates:ok': 1528,
                               'dates:partial': 11, 'latest:error': 1, 'dates:error': 1},
                 'page_cap_origins': ['DME', 'GYD', 'IKT', 'IST', 'LED', 'OVB',
                                      'SVO', 'SVX', 'TAS', 'VKO', 'VVO'],
                 'budget_expired_origins': [],
                 'rejections': {'page_cap': 11, 'upstream_http_400': 2},
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


class TettoDellePagineControBudgetFinito(unittest.TestCase):
    """Due cause che si chiamavano tutte e due `partial`, e sono opposte.

    Il tetto delle pagine e' un limite che ci diamo noi: undici origini
    (DME, SVO, IST…) hanno piu' offerte di quante ne vogliamo leggere, e ogni
    notte ci fermiamo. Il budget finito e' una raccolta troncata a meta'.
    Finche' si guardava solo lo status, una notte troncata poteva essere
    archiviata per sempre come definitiva.
    """

    GIORNO = G('2026-09-15')

    def esito(self, rap, righe=362089):
        return A.completezza(rap, self.GIORNO, righe, Counter())

    def test_1_partial_da_tetto_pagine_resta_una_giornata_completa(self):
        ok, motivi = self.esito(rapporto())
        self.assertTrue(ok, motivi)

    def test_2_budget_finito_dopo_aver_raccolto_righe_rende_incompleta(self):
        # Il caso pericoloso: status 'partial' identico al tetto delle pagine,
        # ma la raccolta e' stata interrotta.
        ok, motivi = self.esito(rapporto(
            endpoints={'dates:ok': 900, 'dates:partial': 12, 'latest:ok': 1539},
            page_cap_origins=['DME', 'SVO', 'IST'],
            budget_expired_origins=['ZAG'],
            rejections={'page_cap': 11, 'budget_expired': 1}))
        self.assertFalse(ok)
        self.assertTrue(any('budget' in m for m in motivi), motivi)

    def test_3_budget_finito_prima_di_avere_righe_rende_incompleta(self):
        # Qui lo status e' 'deferred': lo prendevano gia' i controlli vecchi,
        # ma ora lo dichiara anche la causa esplicita.
        ok, motivi = self.esito(rapporto(
            endpoints={'dates:ok': 900, 'dates:deferred': 640},
            budget_expired_origins=['AAA', 'BBB', 'CCC']))
        self.assertFalse(ok)
        self.assertEqual(sum('budget' in m or 'rinviate' in m for m in motivi), 2, motivi)

    def test_4_tetto_pagine_senza_budget_non_fa_fallire(self):
        ok, motivi = self.esito(rapporto(
            page_cap_origins=['DME'] * 11, budget_expired_origins=[]))
        self.assertTrue(ok, motivi)

    def test_5_tetto_pagine_piu_budget_finito_rende_incompleta(self):
        ok, motivi = self.esito(rapporto(
            page_cap_origins=['DME', 'SVO'], budget_expired_origins=['ZAG', 'ZRH']))
        self.assertFalse(ok)
        self.assertTrue(any('ZAG' in m for m in motivi), motivi)

    def test_6_un_rapporto_vecchio_senza_la_causa_non_si_finalizza(self):
        # Prima del 15 settembre il campo non esisteva: se manca, non si puo'
        # sapere se la notte sia stata troncata, e nel dubbio non si archivia.
        vecchio = rapporto()
        del vecchio['budget_expired_origins']
        ok, motivi = self.esito(vecchio)
        self.assertFalse(ok)
        self.assertTrue(any('versione precedente' in m for m in motivi), motivi)

    def test_7_il_rapporto_vero_del_15_settembre_e_completo(self):
        vero = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'collection-report.json'
        if not vero.exists():
            self.skipTest('collection-report non presente')
        r = dict(json.loads(vero.read_text(encoding='utf-8')))
        e = r['endpoints']
        partial = sum(v for k, v in e.items() if k.endswith(':partial'))
        errori = sum(v for k, v in e.items() if k.endswith(':error'))
        rej = r.get('rejections', {})
        # La prova per sottrazione: ogni partial deve avere una causa nota.
        valueerror_con_righe = max(0, rej.get('upstream_http_400', 0) - errori)
        residuo = (partial - rej.get('page_cap', 0) - rej.get('repeated_page', 0)
                   - valueerror_con_righe)
        self.assertEqual(residuo, 0,
                         f'{residuo} partial senza causa nota: potrebbero essere budget finito')
        r.setdefault('budget_expired_origins', [])
        ok, motivi = A.completezza(r, G(r['date']), 362089, Counter())
        self.assertTrue(ok, motivi)


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


class VolumiVeriNonStimati(unittest.TestCase):
    """Il numero di righe si legge, non si deduce dal peso del file.

    Prima si stimava `peso / 5,4 byte`. Ma 5,4 byte a riga e' la
    comprimibilita' di *una* notte: una notte con molte rotte ripetute
    comprime meglio, e sarebbe sembrata piu' piccola di quanto fosse — cioe'
    avrebbe fatto scattare l'allarme proprio quando i dati erano buoni.
    """

    def secchio(self, giornate):
        s3 = R2Finto()
        for giorno, righe, peso, extra in giornate:
            s3.oggetti[A.chiave(G(giorno))] = {
                'ContentLength': peso,
                'Metadata': dict({'rows': str(righe), 'complete': 'true',
                                  'schema': 'v1', 'day': giorno}, **extra)}
        return s3

    def test_13_si_usano_i_row_count_dei_metadati(self):
        s3 = self.secchio([('2026-09-10', 300000, 1_600_000, {}),
                           ('2026-09-11', 310000, 1_650_000, {}),
                           ('2026-09-12', 320000, 1_700_000, {})])
        self.assertEqual(A.volumi_recenti(s3, 'b', G('2026-09-15')),
                         [300000, 310000, 320000])

    def test_14_la_comprimibilita_non_cambia_il_conteggio(self):
        # Stesse righe, pesi molto diversi: il volume dichiarato non si muove.
        magro = self.secchio([('2026-09-10', 300000, 400_000, {}),
                              ('2026-09-11', 300000, 4_000_000, {}),
                              ('2026-09-12', 300000, 1_700_000, {})])
        self.assertEqual(A.volumi_recenti(magro, 'b', G('2026-09-15')),
                         [300000, 300000, 300000])

    def test_si_ignora_il_giorno_che_stiamo_archiviando(self):
        s3 = self.secchio([('2026-09-14', 300000, 1_600_000, {}),
                           ('2026-09-15', 999999, 1_900_000, {})])
        self.assertEqual(A.volumi_recenti(s3, 'b', G('2026-09-15')), [300000])

    def test_si_ignorano_le_giornate_incomplete_o_di_altro_schema(self):
        s3 = self.secchio([('2026-09-10', 300000, 1_600_000, {}),
                           ('2026-09-11', 11, 9_000, {'complete': 'false'}),
                           ('2026-09-12', 22, 9_000, {'schema': 'v2'}),
                           ('2026-09-13', 310000, 1_650_000, {})])
        self.assertEqual(A.volumi_recenti(s3, 'b', G('2026-09-15')), [300000, 310000])

    def test_una_riga_di_metadati_rotta_si_salta_senza_fermare_tutto(self):
        s3 = self.secchio([('2026-09-10', 300000, 1_600_000, {}),
                           ('2026-09-13', 310000, 1_650_000, {})])
        s3.oggetti[A.chiave(G('2026-09-11'))] = {'ContentLength': 5, 'Metadata': {'rows': 'boh'}}
        self.assertEqual(A.volumi_recenti(s3, 'b', G('2026-09-15')), [300000, 310000])

    def test_15_meno_di_tre_storici_resta_prudente(self):
        s3 = self.secchio([('2026-09-13', 310000, 1_650_000, {})])
        storici = A.volumi_recenti(s3, 'b', G('2026-09-15'))
        anomalo, nota = A.sotto_la_norma(42, storici)
        self.assertFalse(anomalo, 'senza storia non si giudica')
        self.assertIn('nessun confronto', nota)


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
    """La macchina a stati: quando si scrive, quando no, e cosa si ripara.

    Una giornata archiviata e' una COPPIA — Parquet e manifesto. Il buco che
    queste prove chiudono: se il Parquet passava e il manifesto no, la notte
    dopo il codice vedeva l'impronta uguale, diceva "gia' archiviato" e se ne
    andava. Il manifesto restava mancante per sempre, perche' nessuna
    esecuzione successiva avrebbe piu' avuto motivo di guardarlo.
    """

    GIORNO = G('2026-09-15')

    def prepara(self, cartella, righe_grezze=None, completa=True):
        righe, anomalie = A.normalizza(righe_grezze or [osservazione(),
                                                        osservazione(d='LHR', p=67)])
        return A._scheletro(self.GIORNO, righe, anomalie, Counter({self.GIORNO: len(righe)}),
                            completa, [] if completa else ['finta incompletezza'],
                            pathlib.Path(cartella), rapporto())

    def etichette_giuste(self, m, **cambia):
        return dict({'logical-hash': m['impronta_logica'], 'rows': str(m['righe']),
                     'schema': 'v1', 'day': m['giorno'], 'complete': 'true'}, **cambia)

    def oggetto(self, m, **cambia):
        return {'ContentLength': 1234, 'Metadata': self.etichette_giuste(m, **cambia),
                'Corpo': b'{}'}

    # ── creazione ───────────────────────────────────────────────────────────
    def test_giornata_completa_crea_la_coppia(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK', dett)
            self.assertIn(A.chiave(self.GIORNO), s3.oggetti)
            self.assertIn(A.chiave_manifesto(self.GIORNO), s3.oggetti)
            e = s3.oggetti[A.chiave(self.GIORNO)]['Metadata']
            self.assertEqual(e['logical-hash'], m['impronta_logica'])
            self.assertEqual(e['rows'], str(m['righe']))
            self.assertEqual((e['currency'], e['schema']), ('EUR', 'v1'))

    def test_9_il_manifesto_appena_caricato_viene_verificato(self):
        # Se R2 accetta il PUT ma restituisce altro alla rilettura, il passo
        # deve fallire invece di dichiarare l'archivio a posto.
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            vero_put = s3.put_object

            def put_bugiardo(Bucket, Key, Body, Metadata=None, **kw):
                if Key.endswith('.manifest.json'):
                    Metadata = dict(Metadata or {}, rows='1')      # mente sul conteggio
                return vero_put(Bucket=Bucket, Key=Key, Body=Body, Metadata=Metadata, **kw)
            s3.put_object = put_bugiardo
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertIn('rows', dett)

    # ── la coppia ───────────────────────────────────────────────────────────
    def test_4_coppia_presente_e_coerente_e_un_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto({A.chiave(self.GIORNO): self.oggetto(m),
                          A.chiave_manifesto(self.GIORNO): self.oggetto(m)})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK')
            self.assertIn('coerenti', dett)
            self.assertEqual(s3.scritture, [], 'niente da riscrivere')

    def test_5_parquet_presente_e_manifesto_mancante_lo_ricrea(self):
        # E' il buco vero: prima qui si usciva con OK e il manifesto non
        # sarebbe piu' tornato.
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto({A.chiave(self.GIORNO): self.oggetto(m)})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK', dett)
            self.assertIn(A.chiave_manifesto(self.GIORNO), s3.oggetti)
            self.assertEqual(s3.scritture, [A.chiave_manifesto(self.GIORNO)],
                             'si scrive SOLO il manifesto, il Parquet non si tocca')
            scritto = json.loads(s3.oggetti[A.chiave_manifesto(self.GIORNO)]['Corpo'])
            self.assertIn('ricreato', scritto['note'])
            self.assertEqual(scritto['logical_content_hash'], m['impronta_logica'])

    def test_6_manifesto_presente_ma_incoerente_e_un_errore(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            sbagliato = self.oggetto(m, rows='7')
            s3 = R2Finto({A.chiave(self.GIORNO): self.oggetto(m),
                          A.chiave_manifesto(self.GIORNO): sbagliato})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.scritture, [], 'non si sistema al buio')
            self.assertEqual(s3.oggetti[A.chiave_manifesto(self.GIORNO)], sbagliato)

    def test_7_manifesto_senza_parquet_e_uno_stato_incoerente(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto({A.chiave_manifesto(self.GIORNO): self.oggetto(m)})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.scritture, [], 'ne scrivo ne cancello')
            self.assertIn('incoerente', dett)

    def test_8_e_17_contenuto_diverso_gia_presente_non_si_sovrascrive(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            prima = self.oggetto(m, **{'logical-hash': 'a' * 64})
            s3 = R2Finto({A.chiave(self.GIORNO): prima})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.scritture, [], 'nessuna scrittura')
            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)], prima, 'intatto')
            self.assertIn('--sostituisci-giorno', dett, 'e si dice come si ripara')

    def test_parquet_creato_e_manifesto_fallito_non_e_un_successo(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            vero_put = s3.put_object

            def put_che_rifiuta_il_manifesto(Bucket, Key, Body, Metadata=None, **kw):
                if Key.endswith('.manifest.json'):
                    raise s3._errore('InternalError', 500)
                return vero_put(Bucket=Bucket, Key=Key, Body=Body, Metadata=Metadata, **kw)
            s3.put_object = put_che_rifiuta_il_manifesto
            with self.assertRaises(Exception):
                A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                           pathlib.Path(tmp), True, None, None)
            # e la volta dopo, con R2 sano, il manifesto si ricrea da solo
            s3.put_object = vero_put
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO OK', dett)
            self.assertIn(A.chiave_manifesto(self.GIORNO), s3.oggetti)

    # ── incompleta ──────────────────────────────────────────────────────────
    def test_giornata_incompleta_non_crea_il_definitivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp, completa=False)
            s3 = R2Finto()
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), False, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertNotIn(A.chiave(self.GIORNO), s3.oggetti)
            self.assertNotIn(A.chiave_manifesto(self.GIORNO), s3.oggetti)
            self.assertIn(f'{A.STAGING}/{self.GIORNO}.parquet', s3.oggetti,
                          'ma i dati non si buttano: vanno in staging')

    # ── concorrenza ─────────────────────────────────────────────────────────
    def test_18_la_precondizione_regge_se_qualcuno_scrive_nel_frattempo(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            s3 = R2Finto()
            originale = s3.head_object

            def head_poi_crea(Bucket, Key, **kw):
                try:
                    return originale(Bucket=Bucket, Key=Key, **kw)
                finally:
                    if Key == A.chiave(self.GIORNO) and Key not in s3.oggetti:
                        s3.oggetti[Key] = self.oggetto(m, **{'logical-hash': 'z' * 64})
            s3.head_object = head_poi_crea
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m,
                                     pathlib.Path(tmp), True, None, None)
            self.assertEqual(esito, 'ARCHIVIO FALLITO')
            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)]['Metadata']['logical-hash'],
                             'z' * 64, 'l\'oggetto dell\'altro non e\' stato toccato')

    # ── riparazione ─────────────────────────────────────────────────────────
    def test_10_11_12_la_sostituzione_conserva_tutto_e_lascia_traccia(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, m = self.prepara(tmp)
            vecchio_p = self.oggetto(m, **{'logical-hash': 'a' * 64})
            vecchio_p['Corpo'] = b'parquet vecchio'
            vecchio_m = self.oggetto(m, **{'logical-hash': 'a' * 64})
            vecchio_m['Corpo'] = b'{"vecchio": true}'
            s3 = R2Finto({A.chiave(self.GIORNO): vecchio_p,
                          A.chiave_manifesto(self.GIORNO): vecchio_m})
            esito, dett = A.pubblica(s3, 'b', self.GIORNO, parquet, m, pathlib.Path(tmp),
                                     True, str(self.GIORNO), 'recuperato dalla storia di git')
            self.assertEqual(esito, 'ARCHIVIO OK', dett)

            messi_da_parte = sorted(k for k in s3.oggetti if k.startswith(A.SUPERATI))
            self.assertEqual(len(messi_da_parte), 2,
                             'si conservano sia il Parquet sia il manifesto precedenti')
            self.assertTrue(any(k.endswith('.parquet') for k in messi_da_parte))
            self.assertTrue(any(k.endswith('.manifest.json') for k in messi_da_parte))
            self.assertEqual(s3.oggetti[messi_da_parte[1]]['Corpo'], b'parquet vecchio')

            self.assertEqual(s3.oggetti[A.chiave(self.GIORNO)]['Metadata']['logical-hash'],
                             m['impronta_logica'])
            nota = json.loads(s3.oggetti[A.chiave_manifesto(self.GIORNO)]['Corpo'])['note']
            self.assertIn('a' * 64, nota, 'impronta superata')
            self.assertIn(m['impronta_logica'], nota, 'impronta nuova')
            self.assertIn('recuperato dalla storia di git', nota, 'motivo')
            self.assertIn(A.SUPERATI, nota, 'dove sta la copia precedente')
            self.assertRegex(nota, r'\d{8}T\d{6}Z', 'quando')

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


class IlFlussoCollaudaPrimaDiScrivere(unittest.TestCase):
    """Test 16: il cancello prima di R2 esiste, e non si puo' saltare.

    Questa e' una prova sul flusso, non sul codice, e serve per una ragione
    precisa: l'ordine dei passi in nightly.yml e' una garanzia, e le garanzie
    che vivono solo in un file YAML si perdono al primo riordino distratto.
    Una volta e' gia' successo — i test completi stavano dopo l'archiviazione.
    """

    NOTTURNO = (ROOT / '.github' / 'workflows' / 'nightly.yml').read_text(encoding='utf-8')
    CI = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')

    def test_il_collaudo_dell_archivio_precede_la_scrittura(self):
        collaudo = self.NOTTURNO.index("-p 'test_archivio.py'")
        scrittura = self.NOTTURNO.index('python scripts/archivio.py')
        self.assertLess(collaudo, scrittura,
                        'i test dell\'archivio devono stare PRIMA di archivio.py')

    def test_il_collaudo_pretende_pyarrow_invece_di_saltare(self):
        prima = self.NOTTURNO[:self.NOTTURNO.index('python scripts/archivio.py')]
        self.assertIn("ARCHIVIO_RICHIEDE_PYARROW: '1'", prima)
        self.assertIn("ARCHIVIO_RICHIEDE_PYARROW: '1'", self.CI)

    def test_le_librerie_sono_fissate_e_uguali_nei_due_flussi(self):
        blocco = "pip install --quiet 'pyarrow==25.0.1' 'boto3~=1.43'"
        self.assertIn(blocco, self.NOTTURNO)
        self.assertIn(blocco, self.CI)

    def test_l_esito_dell_archivio_rende_rosso_il_flusso(self):
        self.assertIn("steps.archivio.outcome", self.NOTTURNO)
        esito = self.NOTTURNO.index('Esito dell\'archivio')
        commit = self.NOTTURNO.index('Committa se qualcosa e\' cambiato')
        self.assertLess(commit, esito, 'il sito si pubblica prima di diventare rossi')


if __name__ == '__main__':
    unittest.main()
