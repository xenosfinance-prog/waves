/**
 * Cloudflare Pages Function — /sitemap-education.xml  (ADDED 2026-11-14, SEO / AI search)
 * Every Daily Education lesson (/daily-education?d=DATE), built live from
 * daily_education/index.json, with hreflang links to the pre-translated
 * versions in i18n/<lang>/daily_education/ when they exist.
 */
const SITE = 'https://xenosfinance.com';
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const LANGS = ['it', 'es', 'ru', 'uk'];

async function exists(context, path) {
  try {
    const r = await context.env.ASSETS.fetch(new URL(path, context.request.url), { method: 'HEAD' });
    return r.ok;
  } catch (_) { return false; }
}

export async function onRequestGet(context) {
  let posts = [];
  try {
    const r = await context.env.ASSETS.fetch(new URL('/daily_education/index.json', context.request.url));
    if (r.ok) posts = ((await r.json()).posts || []).filter(p => p && DATE_RE.test(p.date || ''));
  } catch (_) { /* empty sitemap */ }

  const urls = [`  <url><loc>${SITE}/daily-education</loc>${posts[0] ? `<lastmod>${posts[0].date}</lastmod>` : ''}<changefreq>daily</changefreq><priority>0.8</priority></url>`];
  // traduzioni: si controllano solo le 60 lezioni più recenti (limite di richieste della Function)
  const recent = posts.slice(0, 60);
  const avail = {};
  await Promise.all(recent.flatMap(p => LANGS.map(async l => {
    if (await exists(context, `/i18n/${l}/daily_education/${p.date}.json`)) (avail[p.date] = avail[p.date] || []).push(l);
  })));
  for (const p of posts) {
    const en = `${SITE}/daily-education?d=${p.date}`;
    const ls = (avail[p.date] || []).sort();
    const alt = ls.length
      ? `<xhtml:link rel="alternate" hreflang="en" href="${en.replace(/&/g, '&amp;')}"/>`
        + ls.map(l => `<xhtml:link rel="alternate" hreflang="${l}" href="${en}&amp;lang=${l}"/>`).join('')
        + `<xhtml:link rel="alternate" hreflang="x-default" href="${en}"/>`
      : '';
    urls.push(`  <url><loc>${en}</loc><lastmod>${p.date}</lastmod>${alt}<priority>0.6</priority></url>`);
    for (const l of ls) urls.push(`  <url><loc>${en}&amp;lang=${l}</loc><lastmod>${p.date}</lastmod>${alt}<priority>0.5</priority></url>`);
  }
  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join('\n')}\n</urlset>\n`,
    { headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=1800' } });
}
