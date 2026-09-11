import { AIRPORT_CODES } from './_airports.js';

/**
 * EFFICIENCY LIFE — FLIGHT · prezzi in tempo reale (Cloudflare Pages Functions)
 *
 * Il token resta sul server. Il LIVE usa la stessa Data API cache dell'indice,
 * ma aggiorna on-demand le origini selezionate. Il modello e' addestrato in EUR:
 * per valute diverse il frontend usa l'indice notturno e converte a schermo,
 * evitando di calcolare un punteggio con unita' monetarie incompatibili.
 */

/* === MODELLO GENERATO DA build.py — non modificare a mano === */
const MODELLO = {"a":0.2050357103604572,"b":0.6891011297713499,"curva":true,"pesi":{"kmpe":32,"deal":30,"price":15,"minpe":13,"itin":5,"rel":5},"scale":{"kmpe":[2.7937915742793793,65.8],"minpe":[0.41914191419141916,6.75],"price":[35.0,1242.0],"deal":[0.22828880367411666,4.101232285617033]}};
/* === fine modello generato === */

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
const MIN_NIGHTS = 1, MAX_NIGHTS = 60, MIN_PRICE_EUR = 10, MAX_ROWS = 60;
const CACHE_SECONDS = 6 * 60 * 60;

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
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
  if (!/^[A-Z]{3}$/.test(origin) || !AIRPORT_CODES.has(origin)) {
    return json({ ok: false, error: 'origin deve essere un aeroporto IATA supportato' }, 400);
  }

  const cur = (q.get('currency') || 'eur').toLowerCase();
  if (!/^[a-z]{3}$/.test(cur)) {
    return json({ ok: false, error: 'currency deve essere un codice ISO di 3 lettere' }, 400);
  }

  // Il modello e' stimato sui prezzi EUR dell'indice. Uno score calcolato
  // direttamente in GBP/USD/JPY cambierebbe artificialmente tutti i rapporti.
  // In quelle valute il frontend usa l'indice EUR e applica il proprio cambio.
  if (cur !== 'eur') {
    return json(
      { ok: true, origin, currency: cur.toUpperCase(),
        observed: new Date().toISOString().slice(0, 10), deals: [], mode: 'index_fx' },
      200,
      { 'cache-control': `public, max-age=600, s-maxage=${CACHE_SECONDS}` },
    );
  }

  const cache = caches.default;
  const cacheKey = new Request(`${url.origin}/api/prices?origin=${origin}&currency=eur`, { method: 'GET' });
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const upstream = `${API}?origin=${origin}&currency=eur&period_type=year`
    + `&group_by=directions&one_way=false&limit=1000`;

  let payload;
  try {
    const res = await fetch(upstream, {
      headers: { 'X-Access-Token': token },
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    payload = await res.json();
    if(payload.success !== true || (!Array.isArray(payload.data) &&
        !(payload.data && Object.keys(payload.data).length === 0))) throw new Error('Invalid upstream response');
  } catch (e) {
    return json({ ok: false, error: String((e && e.message) || e) }, 502);
  }

  const best = new Map();
  for (const x of (Array.isArray(payload.data) ? payload.data : [])) {
    // get_latest_prices is city-oriented. Only codes also present in the
    // validated airport catalog may enter the airport-specific public product.
    if (!AIRPORT_CODES.has(x.destination)) continue;
    if (x.number_of_changes !== 0 || !x.actual) continue;
    const price = Math.round((x.value || 0) * 100) / 100;
    const km = Math.round(x.distance || 0);
    if (!Number.isFinite(price) || !Number.isFinite(km) || price < MIN_PRICE_EUR || km <= 0) continue;

    const dep = String(x.depart_date || '').slice(0, 10);
    const ret = String(x.return_date || '').slice(0, 10);
    if (!dep || !ret || dep < new Date().toISOString().slice(0,10)) continue;

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
    { ok: true, origin, currency: 'EUR',
      observed: new Date().toISOString().slice(0, 10), deals },
    200,
    { 'cache-control': `public, max-age=600, s-maxage=${CACHE_SECONDS}` },
  );

  if (waitUntil) waitUntil(cache.put(cacheKey, out.clone()));
  return out;
}
