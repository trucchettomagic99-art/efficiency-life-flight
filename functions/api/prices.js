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

  const deals = [...best.values()]
    .sort((a, b) => (b.km * 2) / b.p - (a.km * 2) / a.p)
    .slice(0, MAX_ROWS);

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
