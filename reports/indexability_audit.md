# Audit Tecnico Indexability, Crawling & Search Console

Data esecuzione: `2026-09-14 15:22:27`
Dominio: `https://efficiency-life.com`

## 1. Nuova Diagnosi Search Console (Analisi Export Reale 406 URL)
> [!IMPORTANT]
> **Analisi Dati Reali GSC:** L'analisi puntuale del file esportato da Google Search Console rivela:
> - **185 URL** `/da/{IATA}/`
> - **185 URL** `/from/{IATA}/`
> - **36 URL** `/lang/{lingua}/`
> - **Totale Esatto: 406 URL**
>
> Per **tutti i 406 URL**, la data di ultima scansione registrata da GSC è `1970-01-01` (assenza totale di scansione eseguita).
> Inoltre, `Grafico.csv` mostra che tutti e 406 URL sono entrati simultaneamente nello stato il **04/09/2026**.
> In quella data esatta, la sitemap generata conteneva precisamente: **1 Home + 370 Pagine Aeroporto (185 × 2) + 36 Landing Lingua = 407 URL**.
> **Deduzione Fondamentale:** Google ha scoperto in blocco l'intera sitemap del 4 settembre, indicizzando la home e accodando i restanti 406 URL come *Discovered - currently not indexed*. Tra di essi figurano hub mondiali di primissimo piano (**FCO, LHR, JFK, DXB, IST, ATL, ORD, LAX, HND, AMS, CDG, FRA**).
> Questo dimostra che la soglia delle 6–9 rotte **non era la causa primaria** del mancato crawl.

## 2. Confronto Prima / Dopo le Riforme Strutturali
| Metrica Strutturale | Prima della Riforma | Dopo la Riforma | Miglioramento Netto |
|:---|:---:|:---:|:---|
| **Pagine Aeroporto SEO** | 1,300 | **1,300** | Preservate al 100% (soglia MIN_ROUTES=6 mantenuta) |
| **Pagine Directory Hub (/airports/, /aeroporti/)** | 0 | **16** | +16 pagine (2 hub + 14 continentali con breadcrumbs) |
| **Total Sitemap URLs** | 1,338 | **1354** | +16 directory URLs |
| **Link Uscenti dalla Homepage** | 1,336 link grezzi | **~72 link strutturati** | -94.6% (eliminato spammy footer link cloud) |
| **Inlink Minimi per Aeroporto** | 1 (solo footer home) | **6** | Nessun nodo isolato |
| **Inlink Medi per Aeroporto** | 2.0 (1 home + 1 twin) | **14.1** | +12.1 inlink contestuali per scalo |
| **Inlink Mediani per Aeroporto** | 2.0 | **14.0** | Distribuzione PageRank uniforme |
| **Pagine con <= 2 Inlink** | 1,276 (98.2%) | **0 (0.0%)** | 100% degli aeroporti fortemente collegati |
| **Click Depth Medio dalla Home** | 1.0 (tramite footer spam) | **1.98** | Navigazione editoriale pulita Home → Continente → Aeroporto |
| **Click Depth Massimo** | 1 | **2** | Entro i limiti ideali (≤ 3-4 click) |
| **Sitemap `<lastmod>` Logic** | Data odierna fittizia su tutti | **Conservativo & Dinamico per Sostanza SEO** | Zero churn fittizio di lastmod; aggiornamento reale su modifiche dati |

## 3. Sintesi Classificazione Indexability
| Classificazione | Conteggio | % sul Totale | Descrizione / Implicazione |
|:---|:---:|:---:|:---|
| **INDEXABLE_OK** | 1354 | 99.8% | URL conformi, con canonical valido, hreflang e forte linking |
| **WEAK_INTERNAL_LINKING** | 0 | 0.0% | Risolto: nessun aeroporto debolmente collegato |
| **ORPHAN** | 1 | 0.1% | 1 file `googleb83b...html` (token verifica Search Console) |
| **THIN_CONTENT** | 0 | 0.0% | Nessuna pagina sotto la soglia minima di 6 rotte |
| **CANONICAL_ERRORS** | 0 | 0.0% | 100% self-canonical conformi |
| **HREFLANG_ERRORS** | 0 | 0.0% | 100% reciprocità it/en e fallback x-default |
| **REDIRECTS (nel campione live)** | 0 | 0.0% | Zero redirect rilevati nel campione sitemap |
| **HTTP 404 / 410 (nel campione live)** | 0 | 0.0% | Zero errori 404 rilevati nel campione sitemap |
| **SERVER ERRORS (5xx / 429)** | 0 | 0.0% | Zero errori server rilevati |

## 4. Distribuzione Pagine per Volume Rotte Reali
| Fascia Rotte | N. Aeroporti | N. Pagine (/from/ + /da/) | % sul Totale | Stato Qualitativo |
|:---|:---:|:---:|:---:|:---|
| **6 – 9 rotte** | 154 | 308 | 23.7% | Pagine mantenute attive e conformi |
| **10 – 19 rotte** | 171 | 342 | 26.3% | Volume solido |
| **20 – 49 rotte** | 172 | 344 | 26.5% | Volume alto |
| **50+ rotte** | 153 | 306 | 23.5% | Grandi hub internazionali |
| **Totale** | **650** | **1,300** | **100.0%** | |

## 5. Audit Performance Live del Server (Edge Cloudflare) — Doppio Profilo (Browser vs Googlebot)
- **Campioni testati live:** `34` pagine attive testate su entrambi i profili.
- **Browser probes:** `34/34 200` (100.0%)
- **Googlebot probes:** `34/34 200` (100.0%)
- **Browser/Googlebot mismatches:** `0`
- **Verifica Cloaking & WAF:** Nessuna discrepanza rilevata. Cloudflare Edge tratta Googlebot e Browser in modo identico e trasparente: status code identici, catene redirect identiche, canonical tag identici, meta robots identici e content-length identici.
- **Conteggio codici Browser:** `200 OK`: 34 | `3xx`: 0 | `404`: 0 | `429`: 0 | `5xx`: 0 | `Errori`: 0
- **Tempo medio TTFB:** Browser `184.9 ms` · Googlebot `174.3 ms` (Eccellente, < 200 ms)
- **Compressione:** `gzip` attiva su tutte le risposte
- **Cloudflare Edge Cache:** `cf-cache-status: HIT` o `REVALIDATED` / `DYNAMIC`
- **Tasso di errore 5xx / 429:** `0.0%`

### Confronto Dettagliato Browser vs Googlebot:

| URL | Browser Status | Googlebot Status | Final URL | Canonical Match | Meta Robots | Dimensione (B / G) | Discrepanze |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `/` | **200** | **200** | Match | Match | `index, follow` | 372822B / 372822B | 0 |
| `/flight/` | **200** | **200** | Match | Match | `index, follow` | 1991101B / 1991101B | 0 |
| `/airports/` | **200** | **200** | Match | Match | `index, follow` | 12294B / 12294B | 0 |
| `/aeroporti/` | **200** | **200** | Match | Match | `index, follow` | 12225B / 12225B | 0 |
| `/airports/europe/` | **200** | **200** | Match | Match | `index, follow` | 59732B / 59732B | 0 |
| `/aeroporti/europa/` | **200** | **200** | Match | Match | `index, follow` | 58978B / 58978B | 0 |
| `/from/fco/` | **200** | **200** | Match | Match | `index, follow` | 24555B / 24555B | 0 |
| `/da/fco/` | **200** | **200** | Match | Match | `index, follow` | 24637B / 24637B | 0 |
| `/from/lhr/` | **200** | **200** | Match | Match | `index, follow` | 24472B / 24472B | 0 |
| `/da/lhr/` | **200** | **200** | Match | Match | `index, follow` | 24546B / 24546B | 0 |
| `/from/jfk/` | **200** | **200** | Match | Match | `index, follow` | 24580B / 24580B | 0 |
| `/da/jfk/` | **200** | **200** | Match | Match | `index, follow` | 24683B / 24683B | 0 |
| `/from/dxb/` | **200** | **200** | Match | Match | `index, follow` | 24439B / 24439B | 0 |
| `/da/dxb/` | **200** | **200** | Match | Match | `index, follow` | 24517B / 24517B | 0 |
| `/from/ist/` | **200** | **200** | Match | Match | `index, follow` | 24556B / 24556B | 0 |
| `/da/ist/` | **200** | **200** | Match | Match | `index, follow` | 24626B / 24626B | 0 |
| `/from/cdg/` | **200** | **200** | Match | Match | `index, follow` | 24656B / 24656B | 0 |
| `/da/cdg/` | **200** | **200** | Match | Match | `index, follow` | 24744B / 24744B | 0 |
| `/from/hnd/` | **200** | **200** | Match | Match | `index, follow` | 24284B / 24284B | 0 |
| `/da/hnd/` | **200** | **200** | Match | Match | `index, follow` | 24366B / 24366B | 0 |
| `/from/ams/` | **200** | **200** | Match | Match | `index, follow` | 24729B / 24729B | 0 |
| `/da/ams/` | **200** | **200** | Match | Match | `index, follow` | 24818B / 24818B | 0 |
| `/from/fra/` | **200** | **200** | Match | Match | `index, follow` | 24700B / 24700B | 0 |
| `/da/fra/` | **200** | **200** | Match | Match | `index, follow` | 24787B / 24787B | 0 |
| `/from/mad/` | **200** | **200** | Match | Match | `index, follow` | 24612B / 24612B | 0 |
| `/da/mad/` | **200** | **200** | Match | Match | `index, follow` | 24698B / 24698B | 0 |
| `/from/aho/` | **200** | **200** | Match | Match | `index, follow` | 20937B / 20937B | 0 |
| `/da/aho/` | **200** | **200** | Match | Match | `index, follow` | 21027B / 21027B | 0 |
| `/from/abz/` | **200** | **200** | Match | Match | `index, follow` | 19422B / 19422B | 0 |
| `/da/abz/` | **200** | **200** | Match | Match | `index, follow` | 19505B / 19505B | 0 |
| `/from/bhd/` | **200** | **200** | Match | Match | `index, follow` | 19543B / 19543B | 0 |
| `/da/bhd/` | **200** | **200** | Match | Match | `index, follow` | 19612B / 19612B | 0 |
| `/from/ace/` | **200** | **200** | Match | Match | `index, follow` | 20169B / 20169B | 0 |
| `/da/ace/` | **200** | **200** | Match | Match | `index, follow` | 20254B / 20254B | 0 |

## 6. Verifica Pagine Rimosse e Redirect
| URL Testato | Risposta HTTP Live | Valutazione |
|:---|:---:|:---|
| `/from/chi/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `/da/chi/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `/from/orl/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `/from/sia/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `/from/fmy/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `/from/ank/` | **HTTP 404** | 404 pulito (aeroporto de-indicizzato correttamente) |
| `https://www.efficiency-life.com/` | **HTTP 200** -> https://efficiency-life.com/ | Redirect canonico intenzionale |
| `https://www.efficiency-life.com/flight/` | **HTTP 200** -> https://efficiency-life.com/flight/ | Redirect canonico intenzionale |
| `http://efficiency-life.com/` | **HTTP 200** -> https://efficiency-life.com/ | Redirect canonico intenzionale |
| `https://efficiency-life.com/flight` | **HTTP 200** -> https://efficiency-life.com/flight/ | Redirect canonico intenzionale |
| `https://efficiency-life.com/from/fco` | **HTTP 200** -> https://efficiency-life.com/from/fco/ | Redirect canonico intenzionale |