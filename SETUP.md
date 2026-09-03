# Aggiornamento automatico — cosa fare su GitHub e Netlify

Oggi il sito è una fotografia del 2 settembre. Alla fine di questa procedura si
aggiorna **da solo ogni notte**, senza che tu faccia più nulla, e continua a
costare zero.

**Tempo: una quindicina di minuti. Nessun comando da digitare.**

---

## Come funziona, in tre righe

Ogni notte GitHub accende un computer per pochi minuti, interroga Travelpayouts
per i 238 aeroporti di partenza, ricostruisce l'indice tariffe, ricompila
`dist/index.html` e salva il risultato nel repository. Netlify vede il
salvataggio e pubblica la versione nuova. Poi il computer si spegne.

Il token API vive nei *Secrets* di GitHub: non è dentro nessun file, e chi guarda
il codice non lo vede.

---

## 1 · Crea il repository

Su **github.com** → pulsante **+** in alto a destra → **New repository**.

- **Repository name:** `efficiency-life-flight`
- **Visibility:** scegli tu. *Private* va benissimo — GitHub Actions funziona
  anche sui repository privati, con 2.000 minuti gratis al mese. Questo job ne
  consuma circa 3 al giorno, quindi ~90 al mese: sei ampiamente dentro.
- **Non** spuntare "Add a README" — carichi tu i file al passo successivo.

Poi **Create repository**.

---

## 2 · Carica i file

Nella pagina vuota che ti appare, clicca **uploading an existing file**.

Scompatta lo zip che ti ho mandato e **trascina dentro tutto il contenuto della
cartella** (non la cartella stessa: apri la cartella, seleziona tutto, trascina).

Devono comparire nell'elenco:

```
.github/workflows/nightly.yml     ← il job notturno
scripts/fetch_prices.py           ← raccoglie le tariffe
scripts/build.py                  ← ricompila il sito
src/app.html                      ← il template dell'interfaccia
data/catalog.json                 ← 917 aeroporti, 219 paesi
data/origins.json                 ← i 238 aeroporti da interrogare
data/index.json                   ← l'indice tariffe attuale
dist/                             ← il sito compilato che Netlify pubblica
public/                           ← og.png, robots.txt, sitemap, verifica Google
netlify.toml
```

Poi **Commit changes** in fondo alla pagina.

> **Se `.github` non compare fra i file caricati**, il tuo sistema l'ha nascosto
> perché il nome comincia con un punto. Rimedio: vai sul tab **Actions** del
> repository → **set up a workflow yourself** → cancella tutto quello che c'è
> nell'editor e incolla il contenuto di `.github/workflows/nightly.yml` (aprilo
> con Blocco note). Rinomina il file in `nightly.yml` e salva con **Commit
> changes**.

---

## 3 · Metti il token nei Secrets

Nel repository: **Settings** (in alto) → nel menu di sinistra **Secrets and
variables** → **Actions** → pulsante verde **New repository secret**.

- **Name:** `TP_TOKEN`
- **Secret:** il token Travelpayouts (quello che trovi in app.travelpayouts.com,
  Profilo → API token)

**Add secret**. Da qui in poi GitHub lo passa allo script senza mai mostrarlo,
nemmeno nei log.

---

## 4 · Collega Netlify al repository

Nel pannello Netlify del progetto: **Project configuration** → **Build & deploy**
→ **Continuous deployment** → **Link repository** (o *Set up continuous
deployment*).

Autorizza GitHub, scegli `efficiency-life-flight`, e quando ti chiede le
impostazioni di build:

| Campo | Valore |
|---|---|
| Branch to deploy | `main` |
| Build command | **lascialo vuoto** |
| Publish directory | `dist` |

Il comando di build resta vuoto di proposito: il sito è già compilato dentro
`dist/`, Netlify deve solo pubblicarlo. Niente da installare, deploy in pochi
secondi.

Da questo momento il trascinamento manuale dello zip non serve più: ogni
salvataggio su GitHub diventa una pubblicazione.

---

## 5 · Prova subito, senza aspettare la notte

Nel repository, tab **Actions** → nella colonna di sinistra **Indice notturno**
→ pulsante **Run workflow** → **Run workflow**.

Parte un'esecuzione: dura 2–4 minuti. Cliccandoci sopra vedi lo scorrere degli
aeroporti uno per uno e, alla fine, una riga come:

```
OK · 4310 tariffe · 226 origini · 991 destinazioni · 183 paesi
```

Se i dati sono cambiati rispetto a ieri, fa un commit e Netlify pubblica. Se non
è cambiato niente, scrive "Nessuna variazione" e si ferma: giusto così.

---

## Se qualcosa va storto

**`TP_TOKEN mancante`** → il secret non è stato salvato, o il nome ha un refuso.
Deve essere esattamente `TP_TOKEN`.

**`ABORT: solo N/238 origini`** → l'API ha risposto male a troppe richieste.
Lo script si ferma **di proposito senza toccare l'indice**: il sito continua a
mostrare i dati di ieri invece di svuotarsi. Rilancia il workflow più tardi.

**Il workflow gira ma Netlify non pubblica** → controlla che in Netlify il
*Publish directory* sia `dist` e il *Build command* vuoto.

**Il sito si aggiorna ma con pochi dati** → guarda il log del workflow: accanto a
ogni aeroporto c'è il numero di rotte trovate, e un `!` davanti a quelli che
hanno fallito.

---

## Modificare il sito d'ora in poi

L'interfaccia sta tutta in **`src/app.html`**. Modifichi quello, salvi, e alla
prossima esecuzione del workflow (o lanciandolo a mano) il sito si ricompila e si
pubblica.

Per una modifica immediata senza aspettare: dopo aver cambiato `src/app.html`,
lancia **Run workflow** dal tab Actions.

---

## Quando comprerai il dominio

Una sola riga da cambiare: in `scripts/build.py`, la variabile `SITE` in alto.
Poi rilancia il workflow. Sistema da solo il canonical, l'anteprima social e i
dati strutturati. Ricordati di aggiornare anche `public/robots.txt` e
`public/sitemap.xml`.
