/**
 * Cloudflare Pages Function — /sitemap-blog.xml  (ADDED 2026-11-08, SEO)
 *
 * Problem it fixes: blog articles were listed in the static sitemap.xml,
 * which nobody regenerates when a new article is published — 71 of the
 * 325 articles (all the newest) were missing from it.
 *
 * What it does: builds the blog sitemap live from articles/index.json, so
 * every article is listed the moment it is published. Articles that have
 * an Italian version (i18n/it/articles/index.json, made by the "Italian
 * translations" Action) also get their Italian URL (?slug=…&lang=it), with
 * hreflang pairs linking the two languages.
 * 2026-11-14: same for Spanish, Russian and Ukrainian (i18n/<lang>/articles/index.json).
 */
const SITE = 'https://xenosfinance.com';
const SLUG_RE = /^[A-Za-z0-9_-]{1,120}$/;

async function loadJson(context, path) {
  try {
    const r = context.env && context.env.ASSETS
      ? await context.env.ASSETS.fetch(new URL(path, context.request.url))
      : await fetch(new URL(path, context.request.url));
    if (r.ok) return await r.json();
  } catch (_) { /* fall through */ }
  return null;
}

const xmlEsc = s => String(s).replace(/&/g, '&amp;');

export async function onRequestGet(context) {
  let list = await loadJson(context, '/articles/index.json');
  const LANGS = ['it', 'es', 'ru', 'uk'];
  const tr = {};
  await Promise.all(LANGS.map(async l => { tr[l] = (await loadJson(context, `/i18n/${l}/articles/index.json`)) || {}; }));
  if (!Array.isArray(list)) list = [];
  list = list.filter(a => a && a.slug && SLUG_RE.test(a.slug));

  const day = a => String(a.publishedAt || a.date || '').slice(0, 10);
  const newest = list.map(day).filter(Boolean).sort().pop();
  const urls = [`  <url><loc>${SITE}/XenosBlog</loc>${newest ? `<lastmod>${newest}</lastmod>` : ''}<changefreq>daily</changefreq><priority>0.8</priority></url>`];

  for (const a of list) {
    const en = `${SITE}/XenosBlog?slug=${encodeURIComponent(a.slug)}`;
    const lm = /^\d{4}-\d{2}-\d{2}$/.test(day(a)) ? `<lastmod>${day(a)}</lastmod>` : '';
    const avail = LANGS.filter(l => tr[l][a.slug]);
    if (avail.length) {
      const alt = `<xhtml:link rel="alternate" hreflang="en" href="${xmlEsc(en)}"/>`
        + avail.map(l => `<xhtml:link rel="alternate" hreflang="${l}" href="${xmlEsc(`${en}&lang=${l}`)}"/>`).join('')
        + `<xhtml:link rel="alternate" hreflang="x-default" href="${xmlEsc(en)}"/>`;
      urls.push(`  <url><loc>${xmlEsc(en)}</loc>${lm}${alt}<priority>0.6</priority></url>`);
      for (const l of avail) urls.push(`  <url><loc>${xmlEsc(`${en}&lang=${l}`)}</loc>${lm}${alt}<priority>0.6</priority></url>`);
    } else {
      urls.push(`  <url><loc>${xmlEsc(en)}</loc>${lm}<priority>0.6</priority></url>`);
    }
  }

  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join('\n')}\n</urlset>\n`,
    { headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=1800' } });
}
