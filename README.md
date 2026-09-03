# EFFICIENCY LIFE — FLIGHT

### Il modulo voli della piattaforma Efficiency Life

Sito statico, un solo file. Nessun server, nessun dominio, nessun database sono
necessari per farlo funzionare: apri `index.html` con un doppio clic e funziona,
già pieno di dati. Tutto il resto qui sotto è opzionale e serve solo a farlo crescere.

---

## 1. Cosa c'è nella cartella

| File | Cosa fa | Serve subito? |
|---|---|---|
| `index.html` | Il sito completo: indice tariffe, catalogo, motore di scoring, interfaccia IT/EN. Un solo file, zero dipendenze a parte i font Google. | **sì** |
| `og.png` | L'anteprima che compare quando qualcuno condivide il link su WhatsApp, Slack, X, LinkedIn. | sì, se pubblichi |
| `netlify.toml` / `_headers` | Header di sicurezza e cache. Già configurati: non vanno toccati. | sì, se pubblichi |
| `robots.txt` / `sitemap.xml` | Per farsi indicizzare da Google. Dentro c'è un indirizzo segnaposto da sostituire col tuo dominio. | sì, se pubblichi |
| `worker.js` | Proxy Cloudflare, serve solo per aggiornare i prezzi in automatico (punto 5). | no |
| `README.md` | Questo file. | — |

**Dentro `index.html`, incorporati:**

- **4.243 tariffe reali** andata e ritorno, solo voli diretti, rilevate il 2 settembre 2026
- **225 aeroporti di partenza** in **108 paesi**
- **988 destinazioni** in **182 paesi**
- catalogo di **917 aeroporti** in **219 paesi e territori**, con coordinate reali

Nessun prezzo è stimato, modellato o generato. Ogni riga è una osservazione con
fonte e data. Dove non c'è rilevazione, il sito lo dichiara e rimanda alla
ricerca live invece di riempire il vuoto.

---

## 2. Top 10 dall'Italia — rilevazione 02.09.2026

Voli **diretti**, **andata e ritorno**, partenze entro un anno, dai 20 maggiori
aeroporti italiani verso destinazioni estere. Pesi di default:
km/€ 45 · min/€ 25 · prezzo 15 · itinerario 10 · affidabilità 5.

| # | Rotta | Destinazione | Prezzo A/R | Km (a/r) | **Km/€** | Volo | Date | Soggiorno | Punti |
|---|---|---|---:|---:|---:|---:|---|---:|---:|
| 01 | BRI → EVN | Erevan, Armenia | 40 € | 4 648 | **116,2** | 3h40 | 6–13 feb 2027 | 8–10 notti | 99 |
| 02 | MXP → RAK | Marrakech, Marocco | 38 € | 4 246 | **111,7** | 3h25 | 14–20 feb 2027 | 8–10 notti | 97 |
| 03 | NAP → EVN | Erevan, Armenia | 49 € | 5 066 | **103,4** | 3h52 | 16–23 feb 2027 | 8–10 notti | 90 |
| 04 | BLQ → RMO | Chișinău, Moldavia | 30 € | 2 770 | **92,3** | 2h25 | 28 ott – 12 nov 2026 | 5–7 notti | 87 |
| 05 | VCE → EVN | Erevan, Armenia | 55 € | 5 324 | **96,8** | 4h02 | 31 gen – 14 feb 2027 | 8–10 notti | 86 |
| 06 | TRN → RMO | Chișinău, Moldavia | 35 € | 3 280 | **93,7** | 2h42 | 27 set – 4 ott 2026 | 5–7 notti | 86 |
| 07 | MXP → TIA | Tirana, Albania | 24 € | 2 002 | **83,4** | 2h00 | 17–22 ott 2026 | 5–7 notti | 84 |
| 08 | TSF → TIA | Tirana, Albania | 19 € | 1 532 | **80,6** | 1h35 | 15–20 nov 2026 | 3–4 notti | 83 |
| 09 | MXP → BUH | Bucarest, Romania | 32 € | 2 730 | **85,3** | 2h22 | 15–19 ott 2026 | 5–7 notti | 82 |
| 10 | PSA → TIA | Tirana, Albania | 21 € | 1 606 | **76,5** | 1h42 | 24 set – 16 ott 2026 | 5–7 notti | 81 |

**Il vincitore in una riga.** Erevan da Bari: 4 648 km di volo andata e ritorno
per 40 €, cioè **0,86 centesimi al chilometro**, su un diretto di 3h40 verso il
Caucaso in bassa stagione. È il miglior rapporto distanza/prezzo di tutta
l'Europa mediterranea in questo indice.

**Fuori dall'Italia**, i due migliori rapporti al mondo sono entrambi da
Stoccolma: **ARN → Skopje a 23 €** (3 966 km a/r, 172 km/€) e **ARN → Trapani a
33 €** (4 896 km a/r, 148 km/€). Sono nel sito: seleziona Svezia → ARN.

---

## 3. Come si usa

**Console in alto** — paese e aeroporto di partenza (il numero accanto a ogni
scalo è quante tariffe ha nell'indice), finestra di partenza (30/60/90/120/150/180
giorni e oltre, selezionabili anche più di una), distanza massima, budget,
ipotesi bagaglio, ordinamento.

**Pesi del punteggio** — la seconda riga della console è il motore di ranking
esposto: sposta i cursori e la classifica si riordina in tempo reale. Se ti
interessa solo il km/€, porta quel peso a 60 e gli altri a 0.

**Soggiorno proporzionato** — le notti suggerite scalano con la distanza:

```
≤   800 km → 3–4 notti      ≤ 4 000 km →  8–10 notti
≤ 2 000 km → 5–7 notti      ≤ 7 000 km → 12–14 notti
                             > 7 000 km → 15–21 notti
```

**Bagaglio** — nessuna delle due fonti dichiara se il bagaglio da stiva è
incluso. Invece di indovinare, il sito scrive `n.d.` e ti dà un cursore che
applica un'assunzione uniforme (es. +35 €) a tutte le tariffe e ricalcola il
punteggio. Così vedi come cambia la classifica quando il bagaglio conta davvero.

**Atlante** — i 219 paesi ordinati per traffico passeggeri, per regione. Il
numero accanto a ogni paese diventa azzurro con un ▸ quando dal tuo aeroporto
ci sono tariffe verso quel paese. Clicca un paese: a destra compaiono tutti i
suoi scali ordinati per distanza, ciascuno con un pulsante che apre la ricerca
live "ovunque da qui" su Google Flights — funziona per tutti i 917 aeroporti,
anche quelli senza tariffe memorizzate.

**Giorno / Notte** — tema chiaro e scuro, come i display di bordo.

---

## 4. Metterlo online

Tre strade, dalla più veloce alla più definitiva. Non sono alternative: puoi
farle in sequenza.

### A — Subito, senza registrarti da nessuna parte

Il sito è già pubblicato come **artifact su claude.ai**. È privato: lo vedi solo
tu. Per aprirlo agli altri apri la pagina e usa il **menu di condivisione in alto
a destra**: ti dà un link che chiunque può aprire, senza account e senza
installare nulla. Zero secondi di lavoro, zero costi.

Il limite: l'indirizzo è di claude.ai, non tuo, e la pubblicità non si può
attivare lì. Va benissimo per farlo vedere a qualcuno oggi; non è la casa
definitiva del progetto.

### B — Un sito vero, gratis, in un minuto — Netlify Drop

1. Vai su **`app.netlify.com/drop`**
2. Trascina la cartella intera (non solo `index.html`: servono anche `og.png`,
   `netlify.toml`, `robots.txt`, `sitemap.xml`)
3. Dopo qualche secondo hai un indirizzo tipo `melodic-tartufo-a1b2c3.netlify.app`
   con HTTPS già attivo

Il sito è online per chiunque nel mondo. Per **tenerlo** e poterlo aggiornare
serve un account gratuito Netlify (email + password, o login con GitHub): te lo
chiede lui subito dopo il caricamento. Da lì, in *Site settings → Change site
name*, puoi scegliere un nome più presentabile, per esempio
`efficiencylife-flight.netlify.app`.

Se preferisci Cloudflare, **`pages.cloudflare.com`** funziona allo stesso modo e
il file `_headers` è già lì per quello.

**Nota:** l'account devi crearlo tu, di persona — non è qualcosa che posso fare
al posto tuo. Se mi dici quando sei loggato, posso guidarti passo passo dentro
il pannello.

### C — Il tuo dominio

Un dominio costa circa 10 €/anno. `efficiencylife.com` sarebbe la scelta
naturale, con il modulo voli su `flight.efficiencylife.com` o
`efficiencylife.com/flight`: così quando arrivano Stay, Rail e gli altri, la
struttura è già pronta.

Dove comprarlo: **Cloudflare Registrar** (lo vende a prezzo di costo, senza
rinnovi gonfiati) o **Namecheap**. Poi in Netlify: *Domain settings → Add custom
domain*, incolli il nome, e Netlify ti dice quali due record DNS impostare.
Dieci minuti, e il certificato HTTPS si genera da solo.

**Dopo aver comprato il dominio, tre sostituzioni da fare:** cerca
`efficiencylife-flight.netlify.app` dentro `index.html`, `robots.txt` e
`sitemap.xml` e mettici il tuo indirizzo. Servono per l'anteprima social e per
l'indicizzazione su Google.

### Cosa succede quando il sito è online

- **Condivisione con stato.** Il pulsante *Condividi* nella barra copia un link
  che contiene la vista corrente: aeroporto, finestre, filtri, perfino i pesi
  del punteggio. Chi lo apre vede esattamente la tua classifica. È il modo in
  cui il sito si diffonde da solo.
- **Anteprima social.** `og.png` fa comparire la card con headline e globo
  quando il link viene incollato in chat o sui social.
- **Indicizzazione.** Dopo la pubblicazione, registra il sito su
  **Google Search Console** e invia `sitemap.xml`: è gratis e serve perché la
  gente ti trovi cercando "voli economici da [città]".

## 5. Aggiornare i prezzi

Qui c'è una cosa tecnica importante che ho verificato sul campo.

**L'API Travelpayouts non manda gli header CORS.** L'ho provata dal browser da
due origini diverse: la richiesta parte e il server risponde, ma il browser
blocca la lettura. Significa che nessun sito statico può interrogarla
direttamente, con o senza token. Non è un problema di configurazione: è come
funziona quell'API.

Ci sono quindi due modi per tenere i prezzi freschi.

**A — Proxy Cloudflare (tempo reale, 3 minuti, gratis).**

```bash
npm i -g wrangler
wrangler init elf-proxy           # scegli "Hello World Worker"
# sostituisci src/index.js con worker.js
wrangler secret put TP_TOKEN      # incolla il token Travelpayouts
wrangler deploy
```

Poi nel sito, sezione **Aggiorna**, incolla l'indirizzo che wrangler ti
restituisce. Il badge in alto passa da `INDICE` a `LIVE` e la classifica si
ricostruisce con prezzi del momento. Il Worker mette in cache 6 ore, quindi
mille visitatori generano una sola chiamata all'API. Il token vive dentro il
Worker: chi apre il sito non lo vede mai.

**B — Indice notturno (nessun runtime, ancora più veloce).**

Un job schedulato su GitHub Actions (gratis) che ogni notte interroga
Travelpayouts per i 225 scali, ricalcola l'indice e riscrive `index.html`. Il
sito resta statico e istantaneo, i dati sono freschi ogni mattina, e non c'è
nessuna chiamata API quando qualcuno visita. È esattamente la pipeline che ho
usato per costruire l'indice attuale, solo automatizzata. È la strada che
consiglio appena il progetto va avanti.

---

## 6. Monetizzazione

Gli spazi sono già nel codice. Cerca `SPONSOR BAY` in `index.html`: ogni slot è
un `<div class="bay">` con un commento HTML che dice cosa incollarci.

| Slot | Posizione | Formato |
|---|---|---|
| `#ad-leaderboard` | sotto la Top 10 | 970×90 / 728×90 responsive |
| in-feed (×2) | fra la 3ª e la 4ª riga, e fra la 7ª e l'8ª | native / 336×280 |
| `#ad-rect` | sezione Aggiorna | 300×250 |

**Tre flussi, in ordine di resa per un sito di viaggi:**

1. **Affiliazione voli — la principale.** Lo stesso account Travelpayouts è anche
   il programma di affiliazione: aggiungi il tuo `marker` ai link di
   prenotazione e prendi una commissione su ogni biglietto venduto. Su un sito
   di offerte rende molto più della pubblicità display, perché l'utente arriva
   già con l'intenzione di comprare. Nel codice, le funzioni `sky()` e `kayak()`
   sono i punti in cui aggiungere i parametri affiliato.
2. **Display advertising.** Google AdSense (approvazione in 1–2 settimane, serve
   contenuto reale e una privacy policy) o Ezoic/Mediavine sopra una certa
   soglia di traffico. Script una volta nell'`<head>`, tag `<ins>` dentro ogni
   `.bay`.
3. **Affiliazione hotel.** Booking.com e Hotelscombined via Travelpayouts: una
   destinazione trovata è una notte da prenotare. È la monetizzazione più
   naturale del prodotto e la aggiungerei subito dopo i voli.

Prima di attivare la pubblicità in Europa servono comunque una **privacy policy**
e un **banner di consenso cookie** (Cookiebot o Iubenda hanno piani gratuiti).
Senza, AdSense in UE non approva.

---

## 7. Dove può arrivare

**Fase 1 — dove siamo.** Indice statico di 4.243 tariffe reali, 225 origini,
scoring trasparente e regolabile, copertura live via deep link per tutti i 917
aeroporti. Costo: zero.

**Fase 2 — indice notturno** (1–2 giorni). Il punto 5B. Dati freschi ogni
mattina, ancora a costo zero. È il salto di qualità più grande rispetto a oggi.

**Fase 3 — storico** (1–2 settimane, ~5 €/mese di VPS). Un database che conserva
le rilevazioni. Con lo storico puoi fare la cosa che nessun aggregatore fa bene:
dire **"questo prezzo è basso"** invece di **"questo prezzo è 40 €"**. Un
percentile su 90 giorni di storia della rotta vale più di qualunque filtro. Da
lì nascono gli avvisi email ("Erevan da Bari è sotto il 10° percentile") che
sono anche il modo migliore per costruire una lista di iscritti — e una lista
vale più della pubblicità display.

**Fase 4 — personalizzazione.** Aeroporto di casa memorizzato, destinazioni già
visitate escluse, "portami dove non sono mai stato entro 60 €".

---

## 8. Cosa mi serve da te

1. **Un account GitHub**, se vuoi la fase 2. Nient'altro: il token Travelpayouts
   ce l'ho già.
2. **Il dominio.** il nome è deciso. Da verificare la disponibilità di
   `efficiencylife.com` (o `.it`) prima di stampare qualsiasi cosa.
3. **Quali lingue ti servono.** Ora IT ed EN. Aggiungerne è meccanico (il
   dizionario è un unico oggetto `T` in fondo al file), ma dimmi quali mercati
   ti interessano davvero.
4. **Quanti aeroporti di partenza vuoi.** Adesso 225, scelti come i due maggiori
   scali dei primi 110 paesi più i 20 italiani. Portarli a 600–800 è una
   questione di tempo di raccolta, non di codice.

---

## 9. Note tecniche

- **Fonti.** `travelpayouts/aviasales · get_latest_prices` (cache prezzi reali,
  fornisce distanza e tempo di volo a/r insieme alla tariffa) e una rilevazione
  manuale su `google flights explore` per Fiumicino e Malpensa. Ogni riga porta
  la sua fonte; nella classifica le righe Google hanno il bordo verde.
- **Filtri applicati alla raccolta:** solo voli diretti, solo andata e ritorno,
  soggiorno fra 2 e 30 notti, una sola riga per coppia origine-destinazione (la
  più economica), tariffe sotto i 10 € scartate come errori di prezzo.
- **Distanze:** fornite dalla fonte per le tariffe, calcolate con la formula
  dell'emisenoverso per l'Atlante e per il globo. Le rotte disegnate sul globo
  sono ortodromiche vere, interpolate con lo slerp sferico.
- **Tempi di volo:** la fonte pubblica il tempo totale andata e ritorno; il sito
  mostra la metà, etichettata "a tratta".
- **Prezzi a livello di città:** "Londra 35 €" significa il più basso fra
  Heathrow, Gatwick, Stansted e Luton. I link di verifica usano lo stesso codice
  città, quindi la ricerca si apre coerente.
- **Nomi:** i paesi sono localizzati con `Intl.DisplayNames`; le città hanno una
  tabella italiana per le destinazioni più comuni e restano in inglese per le
  altre.
- **localStorage:** solo tema e indirizzo del proxy, entrambi in try/catch. Il
  sito funziona anche se il browser li blocca.
- **Accessibilità:** contrasti AA in entrambi i temi, focus visibile, rispetto di
  `prefers-reduced-motion` (il globo si ferma).
- **Ricostruire i dati:** `build_data.py` (catalogo), `build_deals2.py` (indice
  tariffe), `build.py` (inietta i JSON nel template `app.html`). Per aggiungere
  aeroporti si tocca solo il dizionario `AIRPORTS` in `build_data.py`.

---

## 10. La piattaforma

Il nome porta con sé una promessa: **Efficiency Life** non è un sito di voli, è
un insieme di moduli che applicano lo stesso principio — *massimo ottenuto per
euro speso* — a categorie diverse. **Flight** è il primo, ed è quello che rende
il principio più evidente, perché il chilometro è un'unità che tutti capiscono.

La barra in cima al sito mostra già i moduli previsti, disattivati:

| Modulo | Metrica che ordina | Cosa serve per farlo |
|---|---|---|
| **Flight** ✅ | km per euro, minuti di volo per euro | fatto |
| **Stay** | notti per euro pesate sulla qualità, o m² per euro | API hotel — è nello stesso account Travelpayouts |
| **Rail** | km per euro su ferrovia | dati Trenitalia/Italo, o l'API aperta di Deutsche Bahn |
| **Drive** | km per euro a noleggio, carburante incluso | API autonoleggio, sempre via Travelpayouts |
| **Energy** | kWh per euro | tariffe ARERA — dominio completamente diverso |

L'architettura è già predisposta per questo. Il motore di scoring
(normalizzazione, pesi regolabili, punteggio composito) non sa nulla di voli:
prende righe che hanno un costo e una o più metriche di "quanto ottieni", e le
ordina. Aggiungere **Stay** significa scrivere un nuovo caricatore di dati e
cambiare le etichette, non riscrivere il motore.

Un consiglio pratico, però: **non aprirei un secondo modulo finché Flight non ha
traffico.** Un prodotto che fa una cosa sola e la fa in modo riconoscibile si
diffonde; cinque moduli a metà no. Quando Flight avrà i suoi primi mille
visitatori al mese sapremo anche quale modulo chiedono per primo — e
probabilmente sarà Stay, perché chi ha appena trovato un volo per Erevan ha
immediatamente bisogno di dormirci.

---

*Efficiency Life Flight è uno strumento di ricerca indipendente. Non vende biglietti, non è
un'agenzia di viaggi, e i prezzi cambiano ogni giorno: verifica sempre sul sito
dell'operatore prima di prenotare.*
