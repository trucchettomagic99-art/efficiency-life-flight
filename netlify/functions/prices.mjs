/**
 * EFFICIENCY LIFE — FLIGHT · prezzi in tempo reale
 *
 * Perche' esiste: l'API Travelpayouts non manda gli header CORS, quindi nessun
 * browser puo' interrogarla direttamente. Questa funzione gira sul server di
 * Netlify, dove il problema non esiste, e restituisce i dati gia' normalizzati
 * nel formato che il sito usa.
 *
 * Il token vive in una variabile d'ambiente del progetto Netlify (TP_TOKEN).
 * Non e' in questo file, non e' nel codice della pagina, non arriva mai al
 * browser di chi visita.
 *
 * La risposta resta in cache sulla CDN per sei ore: mille visitatori dello
 * stesso aeroporto generano una sola chiamata all'API.
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
      // Un errore non va MAI messo in cache. Se la fonte ha un singhiozzo di
      // due secondi e quella risposta finisce sulla CDN, il disservizio dura
      // sei ore invece che un istante — e solo per chi cerca da quell'unico
      // aeroporto, che e' il tipo di guasto piu' difficile da accorgersene.
      ...(status >= 400
        ? { 'cache-control': 'no-store', 'netlify-cdn-cache-control': 'no-store' }
        : {}),
      ...extra,
    },
  });

export default async (req) => {
  const token = process.env.TP_TOKEN;
  if (!token) {
    return json({ ok: false, error: 'TP_TOKEN non impostato nelle variabili d\'ambiente' }, 503);
  }

  const q = new URL(req.url).searchParams;
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

  const upstream = `${API}?origin=${origin}&currency=${cur}&period_type=year`
    + `&group_by=directions&one_way=false&limit=1000&token=${encodeURIComponent(token)}`;

  let payload;
  try {
    const res = await fetch(upstream, { signal: AbortSignal.timeout(20000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    payload = await res.json();
  } catch (e) {
    return json({ ok: false, error: String(e.message || e) }, 502);
  }

  // MIN_PRICE e' pensato in euro; in yen o rupie 10 non vuol dire niente,
  // quindi la soglia scende a zero fuori dalle valute forti
  const minPrice = ['eur','usd','gbp','chf','cad','aud','sgd'].includes(cur) ? MIN_PRICE : 0;

  const best = new Map();
  for (const x of payload?.data || []) {
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

  return json(
    { ok: true, origin, currency: cur.toUpperCase(),
      observed: new Date().toISOString().slice(0, 10), deals },
    200,
    {
      'cache-control': `public, max-age=600`,
      'netlify-cdn-cache-control': `public, s-maxage=${CACHE_SECONDS}, stale-while-revalidate=86400`,
      'netlify-vary': 'query=origin|currency',
    },
  );
};

export const config = { path: '/api/prices' };
