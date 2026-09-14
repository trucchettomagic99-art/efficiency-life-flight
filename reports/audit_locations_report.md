# Rapporto di Audit e Migrazione Geografica Aeroporti

Data esecuzione: 2026-09-14T12:28:03.888495

## Riepilogo Generale

- **Aeroporti Catalogo:** 1860 pre-migrazione -> **1834** post-migrazione (26 rimossi)
- **Origini Selezionabili:** 1860 -> **1834** origini commerciali reali
- **Tariffe Analizzate:** 24808 totali
  - **SAFE:** 24238 (97.7%)
  - **PROBABLY WRONG (Deduplicate / Collassate):** 310
  - **PROBABLY WRONG (Rimappate su scalo commerciale):** 162
  - **AMBIGUOUS (Quarantena):** 98
- **Tariffe Finali Pubblicate in Index:** **24181**

## Dettaglio Codici Anomali Trattati

| Codice | Ruolo Reale | Scalo Commerciale | SAFE | Deduplicati | Rimappati | Quarantena |
|:---|:---|:---|:---:|:---:|:---:|:---:|
| `CHI` | Città / Metropoli | `ORD/MDW` | 0 | 55 | 0 | 27 |
| `SIA` | General Aviation / Chiuso | `XIY` | 0 | 37 | 27 | 2 |
| `ORL` | General Aviation / Chiuso | `MCO` | 0 | 39 | 32 | 1 |
| `FMY` | General Aviation / Chiuso | `RSW` | 0 | 11 | 6 | 1 |
| `ANK` | General Aviation / Chiuso | `ESB` | 0 | 57 | 30 | 0 |
| `DKR` | General Aviation / Chiuso | `DSS` | 0 | 20 | 3 | 0 |
| `NHA` | General Aviation / Chiuso | `CXR` | 0 | 6 | 17 | 0 |
| `RTW` | General Aviation / Chiuso | `GSV` | 0 | 2 | 11 | 0 |
| `MES` | General Aviation / Chiuso | `KNO` | 0 | 5 | 3 | 0 |
| `ALY` | General Aviation / Chiuso | `HBE` | 0 | 1 | 4 | 0 |
| `MKC` | General Aviation / Chiuso | `MCI` | 0 | 5 | 1 | 1 |
| `SAC` | General Aviation / Chiuso | `SMF` | 0 | 9 | 5 | 0 |

## Hub Multi-Aeroporto Commerciali Preservati

- **Londra (`LON`):** `LHR`, `LGW`, `STN`, `LTN`, `LCY`, `SEN` rigorosamente preservati.
- **Parigi (`PAR`):** `CDG`, `ORY`, `BVA` preservati.
- **New York (`NYC`):** `JFK`, `LGA`, `EWR` preservati.
- **Milano (`MIL`):** `MXP`, `LIN`, `BGY` preservati.
- **Roma (`ROM`):** `FCO`, `CIA` preservati.
- **Tokyo (`TYO`):** `HND`, `NRT` preservati.

Nessun aeroporto commerciale distinto è stato indebitamente collassato o rimosso.
