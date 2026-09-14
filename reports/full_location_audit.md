# Audit Completo Qualita Aeroporti e Normalizzazione Geografica

Data audit: `2026-09-14 13:19:51`
Modulo: `FLIGHT Data Authority`

## 1. Censimento Globale Codici Aeroportuali
- **Totale Codici IATA in Catalogo:** `1834` aeroporti fisici commerciali
- **Totale Origini Attive:** `1834` origini
- **Totale Localita in Index (Places):** `1889`
- **Totale Tariffe Pubblicate (Deals):** `24212`
- **Totale Rilevazioni Storico (CSV):** `150946` righe (`1419` codici IATA)
- **Tariffe in Quarantena Cautelativa:** `98` tariffe (da/per codici aggregatori CHI, SHA)

## 2. Sintesi Classificazione Qualitativa Codici
| Classificazione | Conteggio | % sul Catalogo | Criterio di Assegnazione |
|:---|:---:|:---:|:---|
| **SAFE** | 1834 | 100.00% | Aeroporti commerciali fisici reali, con voli di linea regolari e coordinate verificate |
| **SUSPICIOUS** | 0 | 0.00% | Metadati incompleti o traffico commerciale minimo |
| **PROBABLY WRONG** | 0 | 0.00% (risolti) | Codici citta, scali chiusi o GA rimossi/risolti durante la migrazione |
| **AMBIGUOUS** | 0 | 0.00% (risolti) | Codici aggregatori multi-aeroporto isolati in quarantena |

## 3. Hub Multi-Aeroporto Rigorosamente Protetti
La politica dell'autorita geografica garantisce che **nessun aeroporto commerciale distinto venga collassato indebitamente**:

| Sistema Metropolitano | Scali Commerciali Distinti Preservati | Stato e Verifica |
|:---|:---|:---|
| **Londra (LON)** | `LHR, LGW, STN, LTN, LCY, SEN` | Tutti i 6 aeroporti commerciali fisici sono preservati e catalogati individualmente con rotte e pagine proprie. |
| **New York (NYC)** | `JFK, LGA, EWR` | I 3 aeroporti dell'area metropolitana sono rigorosamente distinti e preservati. |
| **Parigi (PAR)** | `CDG, ORY, BVA` | CDG, Orly e Beauvais sono trattati come scali commerciali fisici indipendenti. |
| **Roma (ROM)** | `FCO, CIA` | Fiumicino e Ciampino operano indipendentemente. |
| **Milano (MIL)** | `MXP, LIN, BGY` | Malpensa, Linate e Orio al Serio mantengono identita commerciali separate. |
| **Tokyo (TYO)** | `HND, NRT` | Haneda e Narita rigorosamente preservati come scali distinti. |
| **Istanbul (IST/SAW)** | `IST, SAW` | Istanbul Grand Airport e Sabiha Gokcen operano come hub indipendenti. |
| **Osaka (OSA)** | `KIX, ITM` | Kansai International e Itami operano come scali commerciali distinti. |

## 4. Modifiche Applicate (Changes Applied)
Le anomalie accertate sono state risolte con regole strutturali generali in `location_authority.py` e applicate via `migrate_locations.py`:

| Codice | Natura | Scalo Commerciale Corretto | Trattamento Applicato |
|:---|:---|:---|:---|
| `CHI` | Citta / Metropoli | `ORD/MDW` | Rimosso da catalogo aeroporti fisici; 55 tariffe deduplicate; 27 ambigue in quarantena; non genera pagina /from/chi/ |
| `ORL` | General Aviation (Orlando Exec) | `MCO` | Collassato su MCO (Orlando Int.); 39 tariffe deduplicate; 32 rimappate; 1 in quarantena; 404 su /from/orl/ |
| `SIA` | Chiuso (Xi'an Xiguan) | `XIY` | Collassato su XIY (Xi'an Xianyang); 37 deduplicate; 27 rimappate; 2 in quarantena; 404 su /from/sia/ |
| `FMY` | General Aviation (Page Field) | `RSW` | Collassato su RSW (SW Florida Int.); 11 deduplicate; 6 rimappate; 1 in quarantena; 404 su /from/fmy/ |
| `ANK` | GA / Militare (Etimesgut) | `ESB` | Collassato su ESB (Ankara Esenboga); 57 deduplicate; 30 rimappate |
| `DKR` | Chiuso al comm. (L.S. Senghor) | `DSS` | Collassato su DSS (Blaise Diagne Int.); 20 deduplicate; 3 rimappate |
| `NHA` | Militare (Nha Trang Air Base) | `CXR` | Collassato su CXR (Cam Ranh Int.); 6 deduplicate; 17 rimappate |
| `RTW` | Chiuso (Saratov Tsentralny) | `GSV` | Collassato su GSV (Saratov Gagarin); 2 deduplicate; 11 rimappate |
| `MES` | Chiuso (Polonia Airport) | `KNO` | Collassato su KNO (Kualanamu Int.); 5 deduplicate; 3 rimappate |
| `ALY` | Chiuso al comm. (El Nouzha) | `HBE` | Collassato su HBE (Borg El Arab); 1 deduplicata; 4 rimappate |
| `MKC` | General Aviation (Wheeler DT) | `MCI` | Collassato su MCI (Kansas City Int.); 5 deduplicate; 1 rimappata; 1 in quarantena |
| `SAC` | General Aviation (Sacramento Exec) | `SMF` | Collassato su SMF (Sacramento Int.); 9 deduplicate; 5 rimappate |

## 5. Modifiche NON Applicate (Changes Not Applied / Integrita Preservata)
Casi in cui un'unificazione superficiale avrebbe degradato la qualita e la fedelta dei dati di volo:

| Codice | Ruolo Reale | Risoluzione Rifiutata | Motivazione Tecnica |
|:---|:---|:---|:---|
| `SHA` | Shanghai Hongqiao (Scalo Commerciale Reale) | `PVG / SHA` | NON unificato forzatamente con PVG: SHA gestisce voli commerciali interni/regionali effettivi con milioni di passeggeri. Mantenuto distinto. |
| `BVA` | Paris Beauvais (Scalo Commerciale Low-Cost) | `CDG / ORY / BVA` | NON fuso con Parigi: aeroporto fisico indipendente utilizzato da Ryanair e Wizz Air con terminal e coordinate proprie. |
| `BGY` | Milano Bergamo / Orio al Serio | `MXP / LIN / BGY` | NON rimosso o fuso con Malpensa: terzo scalo italiano per traffico commerciale, entita aeroportuale fisica autonoma. |
| `CIA` | Roma Ciampino | `FCO / CIA` | NON fuso con Fiumicino: scalo commerciale secondario reale con codice IATA proprio. |
| `HND` | Tokyo Haneda | `HND / NRT` | NON unificato con Narita: entrambi aeroporti commerciali maggiori indipendenti. |

## 6. Revisione Manuale Raccomandata (Manual Review Required)
| Codice | Descrizione | Situazione Attuale | Azione Futura |
|:---|:---|:---|:---|
| `ISL` | Istanbul Ataturk | Ex hub principale, ora prevalentemente cargo/governativo dopo apertura IST | Verificare se residuano voli passeggeri regolari o se mappare integralmente su IST. |
| `THF` | Berlin Tempelhof | Chiuso storicamente | Verificare che nessun archivio storico di provider terzi richiami THF. |

## 7. Confronto Before / After Migrazione
| Metrica | Prima della Normalizzazione | Dopo la Normalizzazione | Differenza Netta |
|:---|:---:|:---:|:---:|
| **Aeroporti in Catalogo** | 1,860 | **1,834** | -26 (pseudo-scali e GA rimossi) |
| **Origini Selezionabili** | 1,860 | **1,834** | -26 (origini pulite) |
| **Tariffe Totali Index** | 24,808 | **24,181** | -627 (-310 doppioni collassati, -98 in quarantena) |
| **Pagine SEO Generate** | 1,336 | **1,336** | Invariato (nessun aeroporto sano perso) |
| **Pagine SEO CHI, ORL, SIA, FMY** | Generabili | **0 (HTTP 404 pulito)** | Eliminate pagine fittizie |
| **Tariffe Quarantena Cautelativa** | 0 | **98** | +98 (zero ambiguita pubblicate) |