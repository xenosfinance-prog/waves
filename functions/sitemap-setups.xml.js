/**
 * Cloudflare Pages Function — /sitemap-setups.xml  (ADDED 2026-10-17, SEO)
 * Sitemap generata dal vivo con tutte le pagine /setups/<slug> presenti in
 * trading_ideas/ideas.json (stessi slug di functions/setups/[[path]].js).
 */
const SITE = 'https://xenosfinance.com';
const RAW = 'https://raw.githubusercontent.com/xenosfinance-prog/waves/main/trading_ideas/ideas.json';

function isLong(s) { return /^(BUY|LONG|BULL)/i.test(String(s.bias || '')); }
function slugOf(s) {
  const t = String(s.ticker || s.name || 'setup').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const id = String(s.id || '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 8);
  return `${t}-${isLong(s) ? 'long' : 'short'}-${String(s.timestamp || '').slice(0, 10)}-${id}`;
}

export async function onRequestGet(context) {
  let list = [];
  try {
    const r = await fetch(RAW, { cf: { cacheTtl: 300, cacheEverything: true } });
    if (r.ok) list = await r.json();
  } catch (_) { /* empty sitemap */ }
  if (!Array.isArray(list)) list = [];
  list = list.filter(s => s && s.timestamp && s.id).sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
  const urls = [`  <url><loc>${SITE}/trade-setups</loc>${list[0] ? `<lastmod>${String(list[0].timestamp).slice(0, 10)}</lastmod>` : ''}<changefreq>daily</changefreq><priority>0.8</priority></url>`]
    .concat(list.map(s => `  <url><loc>${SITE}/setups/${slugOf(s)}</loc><lastmod>${String(s.timestamp).slice(0, 10)}</lastmod><priority>0.6</priority></url>`));
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`,
    { headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=1800' } });
}
