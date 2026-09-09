# Raccolta tariffe v2

La raccolta usa soltanto la Data API Aviasales/Travelpayouts (cache di ricerche).
Non interroga la Search API in background e non garantisce disponibilità live.

## Flusso

1. Pulisce il catalogo: un codice IATA per aeroporto, coordinate finite, paesi
   coerenti e liste degli aeroporti di ciascun paese riallineate.
2. Interroga tutte le origini configurate e tutti gli aeroporti del catalogo.
   Le destinazioni già osservate diventano origini soltanto se riconosciute
   nell'anagrafica aeroporti del provider. La lista routes.json aiuta a dare
   priorità ma non esclude aeroporti nuovi o stagionali.
3. get_latest_prices conserva la copertura preesistente. prices_for_dates con
   unique=false aggiunge combinazioni partenza/ritorno e controlla separatamente
   zero scali in entrambe le direzioni.
4. Ogni tariffa ha data di acquisizione, endpoint e livello di verifica del volo
   diretto; found_at viene conservato quando il provider lo restituisce.
5. Il prezzo più recente sostituisce quello precedente della stessa combinazione,
   anche quando è più alto. A parità di osservazione preferisce il controllo di
   entrambi i voli, poi il prezzo più basso. Date diverse restano separate.
6. Scarta prezzi non positivi/non finiti, date invalide o passate, soggiorni fuori
   1–30 notti, partenze oltre 366 giorni e rilevazioni più vecchie di 7 giorni.
   Prezzi sotto 10 EUR restano con un indicatore di revisione nell'archivio.
7. Mantiene al massimo 7 giorni di osservazioni valide. La cache del provider non
   è inventario completo: un risultato vuoto non prova che una rotta non esista.

## File

| File | Uso |
| --- | --- |
| data/index.json | Una tariffa rappresentativa per rotta, conteggi e luoghi |
| data/fares/IATA.json | Tutte le date valide e provenienza, per origine |
| dist/data/origins/IATA-hash.json | Date con punteggio, caricate solo se selezionate |
| data/history/YYYY-MM.csv | Un minimo per rotta e giorno di acquisizione |
| data/collection-report.json | Contatori, scarti, paginazione, errori e copertura |
| .cache/fares-v2/YYYY-MM-DD/ | Checkpoint per pagina, fuori dal sito e da git |

Il modello viene stimato sull'indice delle rotte; le date aggiuntive ricevono
il punteggio con lo stesso modello, evitando di sovrappesare le rotte con più date.
Il browser filtra tutte le date caricate, poi mostra il miglior prezzo per
destinazione. LIVE sostituisce solo lo stesso itinerario (origine, destinazione,
partenza e ritorno). Se una richiesta fallisce resta disponibile l'indice incluso.

## Limiti e avvio

Il workflow parte ogni notte alle 03:20 UTC, su modifica ai sorgenti di main e
sul branch di verifica codex/expand-flight-data. Il primo avvio sul branch
verifica la raccolta senza modificare main. Il segreto TP_TOKEN resta in GitHub
Actions e viene inviato in X-Access-Token, mai negli URL o nel rapporto.

```bash
python -m unittest discover -s tests -v
node tests/test_browser_data.cjs
python scripts/fetch_prices.py --clean-only
python scripts/fetch_prices.py
python scripts/build.py
python scripts/build_pages.py
python scripts/check_build.py
```

Budget predefiniti: 18 minuti, 3 worker; 240 richieste/minuto per latest,
480 per dates e 120 per metadati. Si rispettano anche i cooldown del provider
e gli errori 429. Massimo 2 pagine latest e 5 pages dates per origine;
le risposte troncate sono segnalate come partial/page_cap, non complete.
Ogni pagina dates contiene al massimo 1000 record. Non si promette un numero
prefissato di offerte: dipende dalla copertura effettiva della cache.

Opzioni: --max-seconds, --workers, --latest-pages, --dates-pages,
--origin-limit (solo per campioni controllati), --data-dir.
--clean-only non usa il token e non aggiorna la data delle vecchie tariffe.

Checkpoint salvati dopo ogni pagina e ripristinati dalla cache Actions per
lo stesso giorno/branch; gli aeroporti esplorati ruotano per evitare esclusioni
permanenti quando il budget scade. Un'autenticazione respinta ferma la raccolta.
Il precedente indice resta intatto in caso di errore generalizzato, mancato
aggiornamento di almeno il 60% delle origini precedentemente coperte o forte
perdita di rotte. Gli aeroporti nuovi con risposta vuota non causano un falso
allarme. Nessun vecchio prezzo viene marcato come osservato oggi senza richiesta.

Il commit dei dati avviene dopo build e controlli. Se main cambia durante il job,
git push fallisce anziché sovrascrivere il lavoro concorrente. Il rapporto viene
conservato anche come artifact Actions. Le pagine SEO richiedono la soglia di
rotte già prevista dal generatore; quelle non più idonee vengono ritirate.

Fonti: https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API
e https://support.travelpayouts.com/hc/en-us/articles/4402565416594-API-rate-limits
