"""Collaudo dell'archivio permanente.

Le parti che non richiedono pyarrow girano sempre, anche nel collaudo veloce
che precede la raccolta notturna. Il giro completo su Parquet gira solo dove
pyarrow c'e' — cioe' nel passo che archivia davvero — perche' installarlo a
ogni esecuzione di CI costerebbe piu' di quello che protegge.
"""
import datetime as dt
import importlib.util
import pathlib
import sys
import tempfile
import unittest

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
    return dict({'o': 'FCO', 'd': 'MAN', 'p': 40.0, 'dep': '2026-10-02',
                 'ret': '2026-10-05', 'dur': 320, 'km': 1700, 'n': 3,
                 'obs': '2026-09-15'}, **kw)


class DoveFinisconoIFile(unittest.TestCase):
    def test_percorso_in_stile_hive(self):
        # anno e mese nel percorso: DuckDB salta i mesi che non servono senza
        # nemmeno aprire i file.
        self.assertEqual(A.chiave(G('2026-09-15')),
                         'osservazioni/anno=2026/mese=09/2026-09-15.parquet')
        self.assertEqual(A.chiave(G('2027-01-03')),
                         'osservazioni/anno=2027/mese=01/2027-01-03.parquet')

    def test_un_giorno_un_file(self):
        giorni = [G('2026-09-15'), G('2026-09-16'), G('2026-10-01')]
        self.assertEqual(len({A.chiave(g) for g in giorni}), 3)


class CosaSiCarica(unittest.TestCase):
    """La regola che protegge l'archivio dal peggioramento."""

    FINESTRA = [G(f'2026-09-{n:02d}') for n in range(9, 16)]   # 9 → 15

    def test_archivio_vuoto_si_carica_tutto(self):
        self.assertEqual(A.da_caricare(self.FINESTRA, set()), self.FINESTRA)

    def test_il_giorno_fresco_si_riscrive_sempre(self):
        # Anche se c'e' gia': la raccolta di stanotte e' piu' completa di
        # quella di stamattina.
        tutti = {A.chiave(g) for g in self.FINESTRA}
        self.assertEqual(A.da_caricare(self.FINESTRA, tutti), [G('2026-09-15')])

    def test_i_giorni_vecchi_non_si_risovrascrivono_mai(self):
        # Nella finestra le righe vecchie sono state superate da osservazioni
        # piu' fresche: riscriverle sostituirebbe il dato buono con uno magro.
        tutti = {A.chiave(g) for g in self.FINESTRA}
        scelti = A.da_caricare(self.FINESTRA, tutti)
        for g in self.FINESTRA[:-1]:
            self.assertNotIn(g, scelti, f'{g} non doveva essere riscritto')

    def test_un_buco_si_richiude_da_solo(self):
        # E' il caso del guasto: una notte il caricamento fallisce, il giorno
        # resta mancante, la notte dopo viene ripreso senza che nessuno agisca.
        presenti = {A.chiave(g) for g in self.FINESTRA} - {A.chiave(G('2026-09-11'))}
        self.assertEqual(A.da_caricare(self.FINESTRA, presenti),
                         [G('2026-09-11'), G('2026-09-15')])

    def test_finestra_vuota_non_esplode(self):
        self.assertEqual(A.da_caricare([], set()), [])


class LetturaDeiCampi(unittest.TestCase):
    def test_le_date_si_leggono_e_quelle_rotte_diventano_vuote(self):
        self.assertEqual(A.data('2026-09-15'), G('2026-09-15'))
        self.assertEqual(A.data('2026-09-15T16:00:00+02:00'), G('2026-09-15'))
        for cattiva in (None, '', 'boh', '2026-13-45', 123):
            self.assertIsNone(A.data(cattiva), cattiva)

    def test_i_numeri_restano_dentro_il_tipo(self):
        # dur e km sono int16: un valore assurdo dalla fonte non deve far
        # saltare la scrittura dell'intera giornata.
        self.assertEqual(A.intero(320, 32767), 320)
        self.assertEqual(A.intero(999999, 32767), 32767)
        self.assertEqual(A.intero(-5, 32767), 0)
        for cattivo in (None, '', 'boh'):
            self.assertEqual(A.intero(cattivo, 32767), 0)


@unittest.skipUnless(C_E_PYARROW, 'pyarrow non installato')
class GiroCompletoSuParquet(unittest.TestCase):
    def test_i_campi_arrivano_dall_altra_parte(self):
        t = A.tabella([osservazione()])
        r = t.to_pylist()[0]
        self.assertEqual(r['o'], 'FCO')
        self.assertEqual(r['d'], 'MAN')
        self.assertEqual(r['p'], 40.0)
        self.assertEqual(r['dep'], G('2026-10-02'))   # <- il campo che si perdeva
        self.assertEqual(r['ret'], G('2026-10-05'))
        self.assertEqual(r['obs'], G('2026-09-15'))
        self.assertEqual(r['dur'], 320)
        self.assertEqual(r['km'], 1700)
        self.assertEqual(r['n'], 3)

    def test_lo_schema_e_quello_dichiarato(self):
        t = A.tabella([osservazione()])
        self.assertEqual([c.name for c in t.schema],
                         ['obs', 'o', 'd', 'dep', 'ret', 'p', 'dur', 'km', 'n'])

    def test_due_scritture_danno_lo_stesso_file(self):
        # Senza questo non si puo' piu' dire se un archivio e' cambiato
        # davvero o solo stato riscritto.
        righe = [osservazione(d='LHR', p=67), osservazione(), osservazione(d='ARN', p=91)]
        with tempfile.TemporaryDirectory() as tmp:
            a, b = pathlib.Path(tmp) / 'a.parquet', pathlib.Path(tmp) / 'b.parquet'
            A.scrivi(righe, a)
            A.scrivi(list(reversed(righe)), b)     # stesso insieme, ordine diverso
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_una_riga_senza_rientro_non_ferma_la_giornata(self):
        t = A.tabella([osservazione(ret=None), osservazione()])
        self.assertIsNone(t.to_pylist()[0]['ret'])
        self.assertEqual(len(t), 2)

    def test_il_file_si_rilegge(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'g.parquet'
            A.scrivi([osservazione(), osservazione(d='LHR')], f)
            letto = pq.read_table(f)
            self.assertEqual(len(letto), 2)
            self.assertEqual(sorted(r['d'] for r in letto.to_pylist()), ['LHR', 'MAN'])


if __name__ == '__main__':
    unittest.main()
