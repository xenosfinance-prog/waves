/**
 * Cloudflare Pages Function — /XenosBlog  (ADDED 2026-09-24, SEO)
 *
 * Problem it fixes: every article URL (/XenosBlog?slug=...) returned the
 * same static HTML — same <title>, same description and a canonical tag
 * pointing to /XenosBlog. The article itself was only injected later by
 * JavaScript, so Google treated all ~260 articles as duplicates of the
 * blog index and indexed almost none of them.
 *
 * What it does: for requests WITH a valid ?slug=, it loads that article's
 * JSON and rewrites the HTML on the server before it leaves Cloudflare:
 * title, meta description, canonical, Open Graph / Twitter tags, an
 * Article JSON-LD block, and the article title + text pre-filled in
 * #artTitle / #artBody. The page's own JavaScript still runs exactly as
 * before (it re-renders the same article), so users see no difference.
 * Blog index (no ?slug=): the article grid is pre-rendered with real
 * <a href> links to every article (same markup the page's JS builds), so
 * Google can discover articles through internal links, not only the
 * sitemap. Any error falls back to the original page.
 */

import { TOPICS, topicsFor } from './topics/[[path]].js';

const SITE = 'https://xenosfinance.com';
const RAW = 'https://raw.githubusercontent.com/xenosfinance-prog/waves/main/articles/';
const SLUG_RE = /^[A-Za-z0-9_-]{1,120}$/;

// ── Analisi tecniche collegate all'articolo (2026-10-25, SEO) ──────────────
// Stesse regole in XenosBlog.html (relatedAnalysisFor) e in tools/gen_analysis_pages.py
// (_REL_RULES): se cambi le regole qui, cambiale anche lì.
const ANALYSIS_PAGES = {
  'wti-crude-oil':   { en: 'WTI Crude Oil', it: 'Petrolio WTI' },
  'brent-crude-oil': { en: 'Brent Crude Oil', it: 'Petrolio Brent' },
  'natural-gas':     { en: 'Natural Gas', it: 'Gas naturale' },
  'gold':            { en: 'Gold', it: 'Oro' },
  'silver':          { en: 'Silver', it: 'Argento' },
  'copper':          { en: 'Copper', it: 'Rame' },
  'eur-usd':         { en: 'EUR/USD', it: 'EUR/USD' },
  'gbp-usd':         { en: 'GBP/USD', it: 'GBP/USD' },
  'usd-jpy':         { en: 'USD/JPY', it: 'USD/JPY' },
  'usd-chf':         { en: 'USD/CHF', it: 'USD/CHF' },
  'bitcoin':         { en: 'Bitcoin', it: 'Bitcoin' },
  'ethereum':        { en: 'Ethereum', it: 'Ethereum' },
  'sp500':           { en: 'S&P 500', it: 'S&P 500' },
  'nasdaq':          { en: 'Nasdaq 100', it: 'Nasdaq 100' },
  'dax':             { en: 'DAX 40', it: 'DAX 40' },
};

// [regex sul testo dell'articolo, pagine collegate] — in ordine di priorità
const RULES = [
  [/\b(wti|crude|oil|eia|opec\+?|petroleum|gasoline|distillates?|refiner\w*|barrels?)\b/, ['wti-crude-oil', 'brent-crude-oil']],
  [/\bbrent\b/, ['brent-crude-oil', 'wti-crude-oil']],
  [/\b(natural gas|natgas|lng|henry hub)\b/, ['natural-gas']],
  [/\b(gold|xau|bullion)\b/, ['gold']],
  [/\b(silver|xag)\b/, ['silver']],
  [/\bcopper\b/, ['copper']],
  [/\b(bitcoin|btc)\b/, ['bitcoin']],
  [/\b(ethereum|eth)\b/, ['ethereum']],
  [/\bcrypto\w*/, ['bitcoin', 'ethereum']],
  [/\b(eur\/?usd|euro|ecb)\b/, ['eur-usd']],
  [/\b(gbp\/?usd|pound|sterling|boe|bank of england)\b/, ['gbp-usd']],
  [/\b(usd\/?jpy|yen|boj|bank of japan)\b/, ['usd-jpy']],
  [/\b(usd\/?chf|swiss franc|snb)\b/, ['usd-chf']],
  [/\b(nasdaq|ndx|nas100|tech stocks|megacap|mega-cap|semiconductor\w*)\b/, ['nasdaq']],
  [/(s&p|\bspx\b|\bspy\b|wall street|\bequit\w*|\bstocks?\b|\bpre-market\b|\bearnings\b)/, ['sp500', 'nasdaq']],
  [/\b(dax|german\w*|bund|european (stocks|equities))\b/, ['dax']],
  [/\b(dollar|dxy|fed|fomc|forex|\bfx\b|treasur\w*|yields?)\b/, ['eur-usd', 'usd-jpy']],
];
const BY_MARKET = {
  equity: ['sp500', 'nasdaq'], forex: ['eur-usd', 'usd-jpy'], crypto: ['bitcoin', 'ethereum'],
  commodities: ['gold', 'wti-crude-oil'], macro: ['sp500', 'eur-usd', 'gold'], geopolitics: ['wti-crude-oil', 'gold'],
};
const OIL = /\b(wti|crude|oil|eia|opec\+?|brent|petroleum|natural gas)\b/;

// → { pages: [slug…] (max 4), oil: bool } ; oil = collegare anche COT e Futures Flow
function relatedFor(a) {
  const txt = [a.title, a.category, a.categoryLabel, String(a.intro || '').slice(0, 800)]
    .map(x => String(x || '')).join(' ').toLowerCase();
  const out = [];
  for (const [rx, pages] of RULES) {
    if (rx.test(txt)) for (const p of pages) if (!out.includes(p)) out.push(p);
    if (out.length >= 4) break;
  }
  if (!out.length) for (const p of (BY_MARKET[a.market] || ['gold', 'wti-crude-oil', 'sp500'])) if (!out.includes(p)) out.push(p);
  return { pages: out.slice(0, 4), oil: OIL.test(txt) };
}

// Blocco HTML (stesso markup delle sezioni dell'articolo). Etichette con data-i18n:
// il motore lingua del sito le mette in italiano.
// 2026-11-08: lang = 'it' per la versione italiana renderizzata sul server (?lang=it)
function relatedHtml(a, site, esc, lang = 'en') {
  const it = lang === 'it';
  const r = relatedFor(a);
  const links = r.pages.map(p => `<a href="${site}/analysis/${p}"><span data-i18n="label_rel_an_${p.replace(/-/g, '_')}">${esc(ANALYSIS_PAGES[p][it ? 'it' : 'en'])}</span></a>`);
  if (r.oil) {
    links.push(`<a href="${site}/futures-flow/"><span data-i18n="label_rel_futures_flow">Futures Flow</span></a>`);
    links.push(`<a href="${site}/cot/"><span data-i18n="label_rel_cot">${it ? 'Posizionamento COT' : 'COT positioning'}</span></a>`);
  }
  links.push(`<a href="${site}/analysis/"><span data-i18n="label_rel_all_analyses">${it ? 'Tutte le analisi giornaliere' : 'All daily analyses'}</span></a>`);
  return `<div class="edu-section" id="xf-rel-an"><div class="edu-section-title">// <span data-i18n="label_rel_analysis_title">${it ? 'Analisi tecnica di oggi' : "Today's technical analysis"}</span></div>`
    + `<p>${links.join(' · ')}</p></div>`;
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function plain(s) {
  return String(s ?? '').replace(/<[^>]*>/g, ' ').replace(/[*_#`>]+/g, '').replace(/\s+/g, ' ').trim();
}

function clip(s, n) {
  s = plain(s);
  if (s.length <= n) return s;
  const cut = s.slice(0, n - 1);
  const sp = cut.lastIndexOf(' ');
  return (sp > n * 0.6 ? cut.slice(0, sp) : cut) + '…';
}

function paragraphs(text) {
  return String(text ?? '')
    .split(/\n{2,}|\r\n\r\n/)
    .map(p => plain(p))
    .filter(Boolean)
    .map(p => `<p>${esc(p)}</p>`)
    .join('');
}

function asList(v) {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string') { try { const x = JSON.parse(v); return Array.isArray(x) ? x : []; } catch { return []; } }
  return [];
}

async function loadArticle(env, origin, slug, dir = '/articles/') {
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL(`${dir}${slug}.json`, origin));
      if (r.ok) return await r.json();
    }
  } catch (_) { /* fall through */ }
  return null;
}

class SetAttr {
  constructor(attr, value) { this.attr = attr; this.value = value; }
  element(el) { el.setAttribute(this.attr, this.value); }
}
class SetText {
  constructor(value, html = false) { this.value = value; this.html = html; }
  element(el) { el.setInnerContent(this.value, { html: this.html }); }
}
class After {
  constructor(html) { this.html = html; }
  element(el) { if (this.html) el.after(this.html, { html: true }); }
}
class Before {
  constructor(html) { this.html = html; }
  element(el) { if (this.html) el.before(this.html, { html: true }); }
}
class AppendHead {
  constructor(html) { this.html = html; }
  element(el) { el.append(this.html, { html: true }); }
}

async function loadIndex(env, origin) {
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL('/articles/index.json', origin));
      if (r.ok) return await r.json();
    }
  } catch (_) { /* fall through */ }
  try {
    const r = await fetch(RAW + 'index.json', { cf: { cacheTtl: 300, cacheEverything: true } });
    if (r.ok) return await r.json();
  } catch (_) { /* fall through */ }
  return null;
}

// Same markup the page's JavaScript builds (renderGrid), so there is no
// visual jump when the script re-renders the grid — but the article links
// are now in the HTML Google downloads, not only after JS runs.
function gridHtml(list) {
  const BASE = `${SITE}/assets/blog/`;
  return list.filter(a => a && a.slug && SLUG_RE.test(a.slug)).map(a => {
    const title = plain(a.title || 'XenosFinance market analysis');
    const href = `${SITE}/XenosBlog?slug=${encodeURIComponent(a.slug)}`;
    const img = a.imageUrl && /^https?:\/\//.test(a.imageUrl) && a.imageUrl.indexOf('brief-') === -1 ? a.imageUrl : BASE + 'macro.png';
    return `<div class="blog-card"><a href="${href}" class="card-link-wrap" aria-label="${esc(title)}">`
      + `<div class="card-thumb"><img src="${esc(img)}" alt="${esc(title)}" loading="lazy"></div>`
      + `<div class="card-body"><div class="card-cat">${esc(a.category || '')}</div>`
      + `<div class="card-title">${esc(title)}</div>`
      + `<div class="card-excerpt">${esc(plain(a.excerpt || '').slice(0, 120))}...</div>`
      + `<div class="card-footer"><span>${esc(a.readTime || '')}</span><span class="card-read"><span>Read →</span></span></div>`
      + `</div></a></div>`;
  }).join('');
}

// 2026-10-17: barra dei temi sopra la griglia (link reali verso /topics/...)
const TOPIC_BAR = '<div id="xf-topic-bar" style="display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px;font-family:\'IBM Plex Mono\',monospace;font-size:11px">'
  + `<a href="${SITE}/topics" style="padding:5px 10px;border:1px solid currentColor;text-decoration:none">All topics</a>`
  + TOPICS.map(tp => `<a href="${SITE}/topics/${tp.slug}" style="padding:5px 10px;border:1px solid rgba(128,128,128,.4);text-decoration:none">${esc(tp.short)}</a>`).join('')
  + '</div>';
class Prepend { constructor(html) { this.html = html; } element(el) { el.prepend(this.html, { html: true }); } }

async function renderIndex(env, url, res) {
  const list = await loadIndex(env, url.origin);
  if (!Array.isArray(list) || !list.length) return new HTMLRewriter().on('#gridView', new Prepend(TOPIC_BAR)).transform(res);
  return new HTMLRewriter().on('#gridView', new Prepend(TOPIC_BAR)).on('#blogGrid', new SetText(gridHtml(list), true)).transform(res);
}

export async function onRequestGet(context) {
  const { request, env, next } = context;
  const res = await next();
  try {
    const url = new URL(request.url);
    const slug = url.searchParams.get('slug');
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res;
    // Blog index (no slug): pre-render the article grid with real links.
    if (!slug) return await renderIndex(env, url, res);
    if (!SLUG_RE.test(slug)) return res;

    const orig = await loadArticle(env, url.origin, slug);
    if (!orig || !orig.title) return res;
    // 2026-11-08 (SEO): versione italiana con un URL proprio (?slug=…&lang=it), resa sul server
    // dalla traduzione già pronta in i18n/it/articles/ (Action "Italian translations").
    // Senza traduzione → pagina inglese, con canonical inglese.
    // 2026-11-14: stesse versioni per spagnolo, russo e ucraino (i18n/<lingua>/articles/).
    const LANGS = ['it', 'es', 'ru', 'uk'];
    const trs = {};
    await Promise.all(LANGS.map(async l => {
      const t = await loadArticle(env, url.origin, slug, `/i18n/${l}/articles/`);
      if (t && t.title && t.intro) trs[l] = t;
    }));
    const avail = LANGS.filter(l => trs[l]);
    const hasIt = avail.length > 0;
    const reqLang = url.searchParams.get('lang');
    const curLang = trs[reqLang] ? reqLang : 'en';
    const isIt = curLang !== 'en';                 // versione tradotta (qualsiasi lingua)
    const a = isIt ? { ...orig, ...trs[curLang], imageUrl: orig.imageUrl, publishedAt: orig.publishedAt, generatedAt: orig.generatedAt } : orig;
    const W = {
      en: { concl: 'Conclusion', topics: 'Topics', all: 'All topics' },
      it: { concl: 'Conclusione', topics: 'Temi', all: 'Tutti i temi', read: 'Leggi questo articolo in italiano →', loc: 'it_IT' },
      es: { concl: 'Conclusión', topics: 'Temas', all: 'Todos los temas', read: 'Leer este artículo en español →', loc: 'es_ES' },
      ru: { concl: 'Заключение', topics: 'Темы', all: 'Все темы', read: 'Читать эту статью на русском →', loc: 'ru_RU' },
      uk: { concl: 'Висновок', topics: 'Теми', all: 'Усі теми', read: 'Читати цю статтю українською →', loc: 'uk_UA' },
    }[curLang];

    // Some auto-generated articles have a generic title ("Macro Update") and the
    // real headline in the intro — use the headline for search when that happens.
    const rawTitle = plain(a.title);
    const headline = rawTitle.length < 25 && plain(a.intro).length > rawTitle.length
      ? clip(a.intro, 90) : rawTitle;
    const fullTitle = `${clip(headline, 65)} | XenosFinance`;
    const desc = clip(a.excerpt || a.intro || a.conclusion || headline, 158);
    const enUrl = `${SITE}/XenosBlog?slug=${encodeURIComponent(slug)}`;
    const langUrl = l => `${enUrl}&lang=${l}`;
    const canonical = isIt ? langUrl(curLang) : enUrl;
    const hreflang = hasIt
      ? `<link rel="alternate" hreflang="en" href="${esc(enUrl)}">`
        + avail.map(l => `<link rel="alternate" hreflang="${l}" href="${esc(langUrl(l))}">`).join('')
        + `<link rel="alternate" hreflang="x-default" href="${esc(enUrl)}">`
      : '';
    // link visibili alle altre lingue (anche per far trovare a Google le versioni tradotte)
    const READ = { it: 'Leggi questo articolo in italiano →', es: 'Leer este artículo en español →',
      ru: 'Читать эту статью на русском →', uk: 'Читати цю статтю українською →' };
    const langLink = !hasIt ? ''
      : isIt ? `<p style="font-family:'IBM Plex Mono',monospace;font-size:12px;margin:0 0 14px" data-no-xft><a href="${esc(enUrl)}" hreflang="en" lang="en">Read this article in English →</a></p>`
             : `<p style="font-family:'IBM Plex Mono',monospace;font-size:12px;margin:0 0 14px" data-no-xft>`
               + avail.map(l => `<a href="${esc(langUrl(l))}" hreflang="${l}" lang="${l}">${READ[l]}</a>`).join(' &nbsp;·&nbsp; ') + `</p>`;
    const image = a.imageUrl && /^https?:\/\//.test(a.imageUrl) ? a.imageUrl : `${SITE}/assets/blog/macro.png`;

    // 2026-11-13: avviso "analisi superata" in cima agli articoli vecchi (campo notice = {text, url, label})
    const ntc = a.notice && a.notice.text ? a.notice : null;
    let body = ntc ? `<div style="border-left:3px solid #f5c542;background:rgba(245,197,66,.08);padding:12px 16px;margin:0 0 20px;font-family:'IBM Plex Mono',monospace;font-size:13px;line-height:1.6">`
      + `⚠ ${esc(ntc.text)}` + (ntc.url ? ` <a href="${esc(ntc.url)}" style="color:#f5c542;font-weight:600">${esc(ntc.label || 'Read today\'s analysis →')}</a>` : '') + `</div>` : '';
    body += paragraphs(a.intro);
    for (const s of asList(a.sections)) {
      if (!s) continue;
      body += `<div class="edu-section"><div class="edu-section-title">${esc(plain(s.heading))}</div>${paragraphs(s.content)}</div>`;
    }
    if (a.quote) body += `<blockquote>${esc(plain(a.quote))}</blockquote>`;
    if (a.conclusion) body += `<div class="edu-section"><div class="edu-section-title">// ${W.concl}</div>${paragraphs(a.conclusion)}</div>`;
    // 2026-10-17: link alle pagine tema (/topics/...) per collegare gli articoli tra loro
    // (fuori da #artBody: lo script della pagina riscrive #artBody, il blocco temi deve restare)
    const tps = topicsFor(a);
    const topicsHtml = tps.length
      ? `<div class="edu-section" id="xf-topics"><div class="edu-section-title">// ${W.topics}</div><p>`
        + tps.map(tp => `<a href="${SITE}/topics/${tp.slug}">${esc(tp.name)}</a>`).join(' · ')
        + ` · <a href="${SITE}/topics">${W.all}</a></p></div>`
      : '';

    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: clip(headline, 110),
      description: desc,
      image: [image],
      datePublished: a.publishedAt || a.generatedAt || undefined,
      dateModified: a.generatedAt || a.publishedAt || undefined,
      author: { '@type': 'Person', '@id': `${SITE}/about#founder`, name: 'Manolis Evlogimenos', url: `${SITE}/about` }, // 2026-11-17 E-E-A-T: autore reale
      publisher: { '@type': 'Organization', name: 'XenosFinance', logo: { '@type': 'ImageObject', url: `${SITE}/favicon-192.png` } },
      mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
      articleSection: a.categoryLabel || a.category || undefined,
      inLanguage: curLang, // 2026-11-08: prima a.lang ("inglese"/"EN"), valore non valido
    };
    const ldTag = `<script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>`;

    const out = new HTMLRewriter()
      .on('title', new SetText(esc(fullTitle), true))
      .on('meta[name="description"]', new SetAttr('content', desc))
      .on('link[rel="canonical"]', new SetAttr('href', canonical))
      .on('meta[property="og:title"]', new SetAttr('content', fullTitle))
      .on('meta[property="og:description"]', new SetAttr('content', desc))
      .on('meta[property="og:url"]', new SetAttr('content', canonical))
      .on('meta[property="og:type"]', new SetAttr('content', 'article'))
      .on('meta[property="og:image"]', new SetAttr('content', image))
      .on('meta[name="twitter:title"]', new SetAttr('content', fullTitle))
      .on('meta[name="twitter:description"]', new SetAttr('content', desc))
      .on('html', new SetAttr('lang', curLang))
      .on('head', new AppendHead(ldTag + hreflang + (isIt ? `<meta property="og:locale" content="${W.loc}">` : '')))
      .on('#artTitle', new SetText(esc(clip(headline, 140)), true))
      .on('#artCat', new SetText(esc(a.categoryLabel || a.category || ''), true))
      .on('#artBody', new SetText(body, true))
      .on('#artBody', new After(relatedHtml(a, SITE, esc, curLang === 'it' ? 'it' : 'en') + topicsHtml))
      .on('#artBody', new Before(langLink))
      .transform(res);

    const headers = new Headers(out.headers);
    headers.set('Cache-Control', 'public, max-age=300');
    return new Response(out.body, { status: out.status, headers });
  } catch (_) {
    return res; // never break the page
  }
}
