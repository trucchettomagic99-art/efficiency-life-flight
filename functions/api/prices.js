/**
 * EFFICIENCY LIFE — FLIGHT · prezzi in tempo reale (Cloudflare Pages Functions)
 *
 * Gemello di netlify/functions/prices.mjs. Stessa logica, stessa risposta: cambia
 * solo il modo in cui la piattaforma passa il token e mette in cache.
 *
 * Su Cloudflare Pages il percorso del file E' la rotta: questo file sta in
 * functions/api/prices.js e quindi risponde su /api/prices, esattamente come
 * prima. Il sito non si accorge del trasloco.
 *
 * Il token arriva da context.env.TP_TOKEN — una variabile del progetto Pages,
 * non una riga di questo file. Non e' nel codice della pagina e non arriva mai
 * al browser di chi visita.
 *
 * La cache la gestiamo a mano con caches.default: Cloudflare non mette in cache
 * le risposte delle funzioni di sua iniziativa, quindi senza queste righe ogni
 * visitatore sarebbe una chiamata all'API. Sei ore, come su Netlify.
 */

/* === MODELLO GENERATO DA build.py — non modificare a mano === */
const MODELLO = {"a":0.998497364530464,"b":0.5225265314558611,"curva":true,"pesi":{"kmpe":32,"deal":30,"price":15,"minpe":13,"itin":5,"rel":5},"scale":{"kmpe":[3.1885714285714286,78.85714285714286],"minpe":[0.5283911671924291,8.023255813953488],"price":[31,619],"deal":[0.21765448621382646,3.216249495195502]}};
/* === fine modello generato === */

/* Le tariffe in tempo reale non passano dal job notturno: arrivano qui e da
   qui vanno al browser. Se il punteggio lo calcolasse la pagina, la formula
   dovrebbe stare nella pagina — e allora tanto varrebbe non nasconderla.
   Percio' si valuta qui, sul server, con le stesse costanti che build.py
   scrive nel blocco qui sopra a ogni ricompilazione. */
const STAY = [[800,3,4],[2000,5,7],[4000,8,10],[7000,12,14],[1e9,15,21]];
function valuta(rows){
  const M = MODELLO;
  if(!M) return rows;
  const { a, b, curva, pesi, scale } = M;
  const tot = Object.values(pesi).reduce((x,y) => x+y, 0);
  const nz = (v,[lo,hi]) => hi === lo ? 1 : Math.max(0, Math.min(1, (v-lo)/(hi-lo)));
  for(const r of rows){
    const p = r.p;
    const atteso = curva && p > 0 && r.km > 0 ? Math.exp(a + b*Math.log(r.km)) : 0;
    r.x = atteso ? Math.round(atteso) : 0;
    if(!(p > 0)){ r.sc = 0; continue; }
    let s1 = 15, s2 = 21;
    for(const [lim,x,y] of STAY) if(r.km <= lim){ s1 = x; s2 = y; break; }
    const fuori = r.n < s1 ? s1 - r.n : r.n > s2 ? r.n - s2 : 0;
    const parti = { kmpe:nz(r.km*2/p, scale.kmpe), minpe:nz(r.dur/p, scale.minpe),
                    price:1 - nz(p, scale.price), deal:nz(atteso ? atteso/p : 1, scale.deal),
                    itin:Math.max(0, 1 - fuori/7), rel:.8 };
    r.sc = Math.round(100 * Object.entries(pesi).reduce((s,[k,w]) => s + w*parti[k], 0) / tot);
  }
  return rows;
}

const API = 'https://api.travelpayouts.com/aviasales/v3/get_latest_prices';
const MIN_NIGHTS = 2, MAX_NIGHTS = 30, MIN_PRICE = 10, MAX_ROWS = 60;
const CACHE_SECONDS = 6 * 60 * 60;

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
      // Un errore non va MAI messo in cache: se la fonte ha un singhiozzo di due
      // secondi e quella risposta finisce sulla CDN, il disservizio dura sei ore
      // invece che un istante — e solo per chi cerca da quell'unico aeroporto,
      // che e' il tipo di guasto piu' difficile da accorgersene.
      ...(status >= 400 ? { 'cache-control': 'no-store' } : {}),
      ...extra,
    },
  });

export async function onRequest(context) {
  const { request, env, waitUntil } = context;

  const token = env && env.TP_TOKEN;
  if (!token) {
    return json({ ok: false, error: 'TP_TOKEN non impostato nelle variabili d\'ambiente' }, 503);
  }

  const url = new URL(request.url);
  const q = url.searchParams;
  const origin = (q.get('origin') || '').toUpperCase();
  if (!/^[A-Z]{3}$/.test(origin)) {
    return json({ ok: false, error: 'origin deve essere un codice IATA di 3 lettere' }, 400);
  }

  // la valuta viene chiesta a monte: cosi' il prezzo e' quello reale del
  // mercato, non una nostra conversione con un cambio di ieri
  const cur = (q.get('currency') || 'eur').toLowerCase();
  if (!/^[a-z]{3}$/.test(cur)) {
    return json({ ok: false, error: 'currency deve essere un codice ISO di 3 lettere' }, 400);
  }

  // La chiave di cache e' costruita da noi con i soli due parametri che contano:
  // cosi' /api/prices?origin=FCO&currency=eur e la stessa richiesta con un
  // parametro pubblicitario appiccicato in coda condividono la stessa risposta.
  const cache    = caches.default;
  const cacheKey = new Request(`${url.origin}/api/prices?origin=${origin}&currency=${cur}`,
                              { method: 'GET' });
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const upstream = `${API}?origin=${origin}&currency=${cur}&period_type=year`
    + `&group_by=directions&one_way=false&limit=1000&token=${encodeURIComponent(token)}`;

  let payload;
  try {
    const res = await fetch(upstream, { signal: AbortSignal.timeout(20000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    payload = await res.json();
  } catch (e) {
    return json({ ok: false, error: String((e && e.message) || e) }, 502);
  }

  // MIN_PRICE e' pensato in euro; in yen o rupie 10 non vuol dire niente,
  // quindi la soglia scende a zero fuori dalle valute forti
  const minPrice = ['eur','usd','gbp','chf','cad','aud','sgd'].includes(cur) ? MIN_PRICE : 0;

  const best = new Map();
  for (const x of (payload && payload.data) || []) {
    if (x.number_of_changes !== 0 || !x.actual) continue;
    const price = Math.round((x.value || 0) * 100) / 100;
    const km = Math.round(x.distance || 0);
    if (price < minPrice || km <= 0) continue;

    const dep = String(x.depart_date || '').slice(0, 10);
    const ret = String(x.return_date || '').slice(0, 10);
    if (!dep || !ret) continue;

    const nights = Math.round((Date.parse(ret) - Date.parse(dep)) / 864e5);
    if (!(nights >= MIN_NIGHTS && nights <= MAX_NIGHTS)) continue;

    const prev = best.get(x.destination);
    if (!prev || price < prev.p) {
      best.set(x.destination, {
        o: origin, d: x.destination, p: price, dep, ret,
        dur: Math.round(x.duration || 0), km, n: nights, s: 'tp',
      });
    }
  }

  const deals = valuta([...best.values()]
    .sort((a, b) => (b.km * 2) / b.p - (a.km * 2) / a.p)
    .slice(0, MAX_ROWS));

  const out = json(
    { ok: true, origin, currency: cur.toUpperCase(),
      observed: new Date().toISOString().slice(0, 10), deals },
    200,
    { 'cache-control': `public, max-age=600, s-maxage=${CACHE_SECONDS}` },
  );

  // La copia per la cache va clonata: un corpo di risposta si legge una volta
  // sola, e quello originale deve restare intatto per il visitatore.
  if (waitUntil) waitUntil(cache.put(cacheKey, out.clone()));
  return out;
}
