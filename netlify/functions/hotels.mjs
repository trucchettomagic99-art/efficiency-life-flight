/**
 * EFFICIENCY LIFE — FLIGHT · sonda sul listino alberghi
 *
 * Non serve al sito: serve a rispondere a una domanda che non voglio dare per
 * scontata — il token Travelpayouts apre anche i prezzi degli hotel, e in che
 * forma? Prova una serie di indirizzi documentati, uno per uno, e riferisce
 * cosa ha risposto davvero ciascuno: stato, numero di righe, quali campi
 * contiene la prima riga, e un campione.
 *
 * Il token non compare MAI nella risposta: viene sostituito con *** in ogni
 * indirizzo restituito. Questa funzione e' pubblica come le altre, e una
 * chiave in chiaro in una pagina pubblica sarebbe una chiave regalata.
 *
 * Da cancellare quando avremo deciso come costruire l'indice alberghi:
 * e' uno strumento diagnostico, non un pezzo del prodotto.
 *
 *   /api/hotels?city=Rome&in=2026-11-09&out=2026-11-14
 */

const TIMEOUT = 15000;
const SAMPLE_CHARS = 900;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 1), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
      'cache-control': 'no-store',
    },
  });

/** toglie il token da qualunque stringa, comunque sia scritto */
const hide = (s, token) => String(s).split(token).join('***');

async function probe(name, url, token) {
  const started = Date.now();
  const out = { name, url: hide(url, token) };
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(TIMEOUT),
      headers: { accept: 'application/json', 'user-agent': 'efficiency-life-flight/1.0' },
    });
    out.status = res.status;
    out.ms = Date.now() - started;
    const text = await res.text();
    out.bytes = text.length;

    let data;
    try { data = JSON.parse(text); }
    catch { out.parsed = false; out.sample = hide(text.slice(0, SAMPLE_CHARS), token); return out; }

    out.parsed = true;
    const rows = Array.isArray(data) ? data
               : Array.isArray(data?.results) ? data.results
               : Array.isArray(data?.hotels) ? data.hotels
               : null;

    if (rows) {
      out.shape = Array.isArray(data) ? 'array' : 'oggetto con lista';
      out.rows = rows.length;
      if (rows.length) {
        out.fields = Object.keys(rows[0]).sort();
        out.first = JSON.parse(hide(JSON.stringify(rows[0]), token));
      }
    } else if (data && typeof data === 'object') {
      out.shape = 'oggetto';
      out.fields = Object.keys(data).sort().slice(0, 40);
      out.sample = hide(JSON.stringify(data).slice(0, SAMPLE_CHARS), token);
    }
  } catch (e) {
    out.error = hide(String(e.message || e), token);
    out.ms = Date.now() - started;
  }
  return out;
}

export default async (req) => {
  const token = process.env.TP_TOKEN;
  if (!token) return json({ ok: false, error: 'TP_TOKEN non impostato' }, 503);

  const q = new URL(req.url).searchParams;
  const city = (q.get('city') || 'Rome').slice(0, 60);
  const cur = (q.get('currency') || 'eur').toLowerCase().slice(0, 3);

  // date di prova: fra un mese, cinque notti — se non vengono passate
  const iso = (d) => d.toISOString().slice(0, 10);
  const base = new Date(Date.now() + 30 * 864e5);
  const checkIn = q.get('in') || iso(base);
  const checkOut = q.get('out') || iso(new Date(Date.parse(checkIn) + 5 * 864e5));

  const e = encodeURIComponent;
  const t = e(token);

  // Gli indirizzi da provare. Alcuni saranno sbagliati: e' il punto della sonda.
  const targets = [
    ['cache · prezzi per citta e date',
     `https://engine.hotellook.com/api/v2/cache.json?location=${e(city)}&currency=${cur}` +
     `&checkIn=${e(checkIn)}&checkOut=${e(checkOut)}&limit=25&token=${t}`],

    ['lookup · risoluzione del nome citta',
     `https://engine.hotellook.com/api/v2/lookup.json?query=${e(city)}&lang=en` +
     `&lookFor=both&limit=5&token=${t}`],

    ['prices/halted · listino esteso',
     `https://engine.hotellook.com/api/v2/prices/halted.json?location=${e(city)}` +
     `&checkIn=${e(checkIn)}&checkOut=${e(checkOut)}&currency=${cur}&token=${t}`],

    ['static/hotels · anagrafica alberghi',
     `https://engine.hotellook.com/api/v2/static/hotels.json?language=en&token=${t}`],

    ['travelpayouts · prezzi hotel',
     `https://api.travelpayouts.com/v2/prices/latest?currency=${cur}&limit=5&token=${t}`],
  ];

  const results = [];
  for (const [name, url] of targets) results.push(await probe(name, url, token));

  const working = results.filter(r => r.status === 200 && r.parsed);
  return json({
    ok: true,
    domanda: 'il token apre il listino alberghi, e in che forma?',
    parametri: { city, checkIn, checkOut, currency: cur },
    funzionanti: working.map(r => r.name),
    risultati: results,
  });
};

export const config = { path: '/api/hotels' };
