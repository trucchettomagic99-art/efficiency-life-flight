/**
 * VECTOR — proxy Travelpayouts per Cloudflare Workers.
 *
 * Serve a due cose:
 *   1. tenere il token API fuori dal codice sorgente del sito;
 *   2. mettere in cache le risposte, così mille visitatori generano una sola
 *      chiamata all'API invece di mille.
 *
 * Deploy (gratuito, ~3 minuti):
 *   npm i -g wrangler
 *   wrangler init vector-proxy      # scegli "Hello World Worker"
 *   # sostituisci src/index.js con questo file
 *   wrangler secret put TP_TOKEN    # incolla il token quando lo chiede
 *   wrangler deploy
 *
 * Poi nel sito, in index.html, cerca la funzione fetchLive() e sostituisci
 * l'URL con:  https://vector-proxy.<tuo-sottodominio>.workers.dev/prices?origin=FCO
 * (il token non serve più lato browser).
 */

const ALLOWED_ORIGINS = [
  'https://esempio.com',          // ← metti qui il dominio del tuo sito
  'http://localhost:8000',
];
const CACHE_SECONDS = 60 * 60 * 6;   // i prezzi cache di Travelpayouts si muovono lentamente

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin') || '';
    const cors = {
      'Access-Control-Allow-Origin': ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
      'Access-Control-Allow-Methods': 'GET,OPTIONS',
      'Vary': 'Origin',
    };
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    if (url.pathname !== '/prices') return new Response('Not found', { status: 404, headers: cors });

    const iata = (url.searchParams.get('origin') || '').toUpperCase();
    if (!/^[A-Z]{3}$/.test(iata)) {
      return json({ success: false, error: 'origin deve essere un codice IATA di 3 lettere' }, 400, cors);
    }
    const currency = (url.searchParams.get('currency') || 'eur').toLowerCase();
    if (!/^[a-z]{3}$/.test(currency)) {
      return json({ success: false, error: 'currency non valida' }, 400, cors);
    }

    // cache edge: una sola chiamata upstream per (origine, valuta) ogni 6 ore
    const cacheKey = new Request(`https://vector.cache/${iata}/${currency}`, request);
    const cache = caches.default;
    const hit = await cache.match(cacheKey);
    if (hit) {
      const r = new Response(hit.body, hit);
      Object.entries(cors).forEach(([k, v]) => r.headers.set(k, v));
      r.headers.set('X-Vector-Cache', 'HIT');
      return r;
    }

    const upstream = new URL('https://api.travelpayouts.com/aviasales/v3/prices_for_dates');
    upstream.searchParams.set('origin', iata);
    upstream.searchParams.set('currency', currency);
    upstream.searchParams.set('direct', 'true');
    upstream.searchParams.set('one_way', 'false');
    upstream.searchParams.set('sorting', 'price');
    upstream.searchParams.set('unique', 'true');
    upstream.searchParams.set('limit', '1000');

    let payload;
    try {
      const res = await fetch(upstream, { headers: { 'X-Access-Token': env.TP_TOKEN } });
      if (!res.ok) throw new Error('upstream HTTP ' + res.status);
      payload = await res.json();
    } catch (e) {
      return json({ success: false, error: String(e.message || e) }, 502, cors);
    }

    const out = json(payload, 200, {
      ...cors,
      'Cache-Control': `public, max-age=${CACHE_SECONDS}`,
      'X-Vector-Cache': 'MISS',
    });
    ctx.waitUntil(cache.put(cacheKey, out.clone()));
    return out;
  },
};

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
  });
}
