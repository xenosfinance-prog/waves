/**
 * Cloudflare Pages Function — /topics/<slug>  (ADDED 2026-10-17, SEO)
 *
 * Pagine "tema" del blog: raccolgono gli articoli per argomento (azioni, forex,
 * materie prime, petrolio, crypto, macro, outlook settimanale, analisi tecnica…)
 * con link reali verso ogni articolo. Servono a Google per scoprire e collegare
 * i ~300 articoli (molti risultano "Discovered – currently not indexed").
 * Generate al momento della richiesta da articles/index.json: nessun commit,
 * nessun deploy, nessuna AI. L'indice dei temi è /topics (functions/topics.js).
 * TOPICS e topicsFor() sono usati anche da functions/XenosBlog.js per i link
 * "Topics" sotto ogni articolo.
 */

const SITE = 'https://xenosfinance.com';
const RAW = 'https://raw.githubusercontent.com/xenosfinance-prog/waves/main/articles/index.json';

const t = a => String(a.title || '').toLowerCase();
const cat = a => String(a.category || a.categoryLabel || '').toLowerCase();

export const TOPICS = [
  { slug: 'stock-market', name: 'Stock Market Analysis', short: 'Stocks',
    intro: 'Analysis of US and global equities: index trends, sector rotation, earnings season and the macro forces that drive the S&P 500, the Nasdaq 100 and European stock markets.',
    links: [['/analysis/sp500', 'S&P 500 daily analysis'], ['/analysis/nasdaq', 'Nasdaq 100 daily analysis'], ['/analysis/dax', 'DAX daily analysis'], ['/dashboard', 'Live dashboard']],
    match: a => a.market === 'equity' || cat(a).includes('equit') },
  { slug: 'forex', name: 'Forex Analysis', short: 'Forex',
    intro: 'Currency market analysis: the US dollar, the euro, the yen and the pound, central-bank expectations, rate differentials and the technical structure of the main FX pairs.',
    links: [['/analysis/eur-usd', 'EUR/USD daily analysis'], ['/analysis/usd-jpy', 'USD/JPY daily analysis'], ['/analysis/gbp-usd', 'GBP/USD daily analysis'], ['/cot', 'COT positioning']],
    match: a => a.market === 'forex' },
  { slug: 'commodities', name: 'Commodities Analysis — Energy & Metals', short: 'Commodities',
    intro: 'Commodity market analysis across energy and metals: crude oil, natural gas, gold, silver and copper, with supply and demand, inventories, positioning and price structure.',
    links: [['/analysis/gold', 'Gold daily analysis'], ['/analysis/copper', 'Copper daily analysis'], ['/futures-flow', 'Futures flow'], ['/cot', 'COT positioning']],
    match: a => a.market === 'commodities' },
  { slug: 'oil-market', name: 'Oil Market Analysis — WTI, Brent, EIA & OPEC', short: 'Oil',
    intro: 'Crude oil analysis from an oil-trading desk: WTI and Brent, EIA inventory reports, OPEC+ decisions, the futures curve and the geopolitics that move the energy complex.',
    links: [['/analysis/wti-crude-oil', 'WTI daily analysis'], ['/analysis/brent-crude-oil', 'Brent daily analysis'], ['/futures-flow', 'Futures flow & curves'], ['/cot', 'COT positioning']],
    match: a => /\b(oil|crude|wti|brent|eia|opec\+?|petroleum)\b/.test(t(a)) },
  { slug: 'crypto', name: 'Crypto Market Analysis', short: 'Crypto',
    intro: 'Bitcoin, Ethereum and the wider crypto market: trend, liquidity, sentiment and the macro backdrop for digital assets.',
    links: [['/analysis/bitcoin', 'Bitcoin daily analysis'], ['/analysis/ethereum', 'Ethereum daily analysis']],
    match: a => a.market === 'crypto' },
  { slug: 'macro', name: 'Macro & Central Banks', short: 'Macro',
    intro: 'Macroeconomic analysis: inflation, growth, labour market, central-bank policy at the Fed, ECB and BoJ, and how the data calendar shapes every asset class.',
    links: [['/calendar', 'Economic calendar'], ['/market-brief', 'Daily pre-market brief']],
    match: a => a.market === 'macro' },
  { slug: 'geopolitics', name: 'Geopolitics & Markets', short: 'Geopolitics',
    intro: 'How geopolitical events — conflicts, sanctions, trade policy and elections — feed into oil, gold, currencies and equity risk.',
    links: [['/analysis/wti-crude-oil', 'WTI daily analysis'], ['/analysis/gold', 'Gold daily analysis']],
    match: a => a.market === 'geopolitics' || cat(a).includes('geopolit') },
  { slug: 'weekly-market-outlook', name: 'Weekly Market Outlook', short: 'Weekly outlook',
    intro: 'The week ahead for markets: key economic releases, earnings, central-bank events and the levels to watch across futures, FX and commodities.',
    links: [['/calendar', 'Economic calendar'], ['/cot', 'COT positioning']],
    match: a => /weekly|week ahead|week of/.test(t(a)) },
  { slug: 'technical-analysis', name: 'Technical Analysis & Elliott Wave', short: 'Technical analysis',
    intro: 'Technical studies: Elliott Wave counts, Fibonacci levels, order flow, trend and momentum, written for market analysis and trading education.',
    links: [['/analysis', 'Daily technical analysis'], ['/elliottwave', 'Elliott Wave'], ['/trade-setups', 'Trade setups']],
    match: a => ['technical', 'elliott', 'orderflow'].includes(a.tech) || /technical|elliott|fibonacci/.test(t(a)) },
  { slug: 'pre-market-brief', name: 'Pre-Market Brief', short: 'Pre-market',
    intro: 'Pre-market briefs before the US open: futures, overnight moves, catalysts of the day and the market bias.',
    links: [['/market-brief', "Today's pre-market brief"], ['/dashboard', 'Live dashboard']],
    match: a => /pre-market|premarket/.test(t(a) + ' ' + cat(a)) },
  { slug: 'market-sentiment', name: 'Market Sentiment', short: 'Sentiment',
    intro: 'Market sentiment and positioning: risk appetite, volatility, fund flows and the crowd behaviour behind price moves.',
    links: [['/cot', 'COT positioning'], ['/futures-flow', 'Futures flow']],
    match: a => a.tech === 'sentiment' || cat(a).includes('sentiment') },
];

export function topicsFor(a) {
  return TOPICS.filter(tp => { try { return tp.match(a || {}); } catch { return false; } });
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function plain(s) {
  return String(s ?? '').replace(/<[^>]*>/g, ' ').replace(/[*_#`>]+/g, '').replace(/\s+/g, ' ').trim();
}
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function dateH(ts) {   // niente Intl: limite CPU delle Functions
  const d = new Date(ts);
  return isNaN(d) ? '' : `${String(d.getUTCDate()).padStart(2, '0')} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}
const artUrl = a => `/XenosBlog?slug=${encodeURIComponent(a.slug)}`;

export async function loadArticles(env, origin) {
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL('/articles/index.json', origin));
      if (r.ok) { const d = await r.json(); if (Array.isArray(d)) return clean(d); }
    }
  } catch (_) { /* fall through */ }
  try {
    const r = await fetch(RAW, { cf: { cacheTtl: 300, cacheEverything: true } });
    if (r.ok) { const d = await r.json(); if (Array.isArray(d)) return clean(d); }
  } catch (_) { /* fall through */ }
  return [];
}
function clean(list) {
  return list.filter(a => a && a.slug && a.title && /^[A-Za-z0-9_-]{1,120}$/.test(a.slug))
    .sort((x, y) => String(y.publishedAt || '').localeCompare(String(x.publishedAt || '')));
}

const CSS = `:root{--bg:#0f1724;--bg2:#131f2e;--ink:#e2eaf4;--ink2:#b8cce0;--muted:#5a7a9a;--border:#1e3050;--border2:#243a5e;--gold:#3b82f6;--mono:'IBM Plex Mono',monospace;--serif:'Playfair Display',Georgia,serif;--body:'PT Serif',Georgia,serif;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.7;}
a{color:var(--gold);text-decoration:none;} a:hover{text-decoration:underline;}
.top{border-bottom:3px double var(--gold);text-align:center;padding:22px 20px 14px;}
.brand{font-family:var(--serif);font-size:34px;font-weight:900;letter-spacing:-1px;text-transform:uppercase;color:var(--ink);}
.brand span{color:var(--gold);}
.tag{font-family:var(--mono);font-size:9px;letter-spacing:4px;color:var(--muted);text-transform:uppercase;margin-top:4px;}
nav{display:flex;flex-wrap:wrap;justify-content:center;border-bottom:1px solid var(--border);background:var(--bg2);}
nav a{font-family:var(--mono);font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:11px 18px;color:var(--muted);}
nav a.on,nav a:hover{color:var(--gold);text-decoration:none;}
main{max-width:980px;margin:0 auto;padding:26px 22px 60px;}
.crumb{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin-bottom:14px;}
h1{font-family:var(--serif);font-size:32px;line-height:1.2;margin-bottom:6px;}
.upd{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin-bottom:16px;}
h2{font-family:var(--mono);font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin:30px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px;}
p{color:var(--ink2);margin-bottom:10px;font-size:15px;}
.art{border-bottom:1px solid var(--border);padding:12px 0;}
.art a.ttl{font-family:var(--serif);font-size:18px;color:var(--ink);}
.art .meta{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin:2px 0 4px;}
.art p{font-size:14px;margin:0;}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;}
.chips a{font-family:var(--mono);font-size:11px;border:1px solid var(--border2);padding:6px 10px;color:var(--ink2);}
.tp{border:1px solid var(--border2);background:var(--bg2);padding:14px 16px;margin-bottom:10px;}
.tp a{font-family:var(--serif);font-size:19px;color:var(--ink);}
.tp .meta{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;}
.tp p{font-size:14px;margin:4px 0 0;}
.disc{font-family:var(--mono);font-size:10px;color:var(--muted);line-height:1.6;margin-top:34px;border-top:1px solid var(--border);padding-top:14px;}
@media(max-width:720px){h1{font-size:25px;}}`;

const NAV = [['/', 'Home'], ['/dashboard', 'Dashboard'], ['/analysis', 'Daily Analysis'], ['/trade-setups', 'Trade Setups'],
  ['/XenosBlog', 'Blog'], ['/topics', 'Topics'], ['/cot', 'COT Positioning'], ['/calendar', 'Calendar'], ['/elliottwave', 'Elliott Wave']];

function shell({ title, desc, canonical, body, jsonld, robots }) {
  const nav = NAV.map(([h, n]) => `<a href="${h}"${h === '/topics' ? ' class="on"' : ''}>${n}</a>`).join('');
  const ld = (jsonld || []).map(x => `<script type="application/ld+json">${JSON.stringify(x).replace(/</g, '\\u003c')}</script>`).join('\n');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
${robots ? `<meta name="robots" content="${robots}">` : ''}
<link rel="canonical" href="${canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${canonical}">
<meta property="og:site_name" content="XenosFinance">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="192x192" href="/favicon-192.png">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=PT+Serif:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>${CSS}</style>
${ld}
</head>
<body>
<header class="top"><div class="brand">Xenos<span>Finance</span></div><div class="tag">Market analysis &amp; trading education</div></header>
<nav>${nav}</nav>
<main>
${body}
<div class="disc">Educational content only. Articles are market analysis for trading education and do not constitute investment advice or a recommendation to buy or sell any financial instrument. Trading involves a significant risk of loss. © XenosFinance</div>
</main>
</body>
</html>`;
}

function topicPage(tp, arts) {
  const url = `${SITE}/topics/${tp.slug}`;
  const title = `${tp.name} — Articles & Insights | XenosFinance`;
  const desc = `${tp.intro} ${arts.length} articles from the XenosFinance desk.`.slice(0, 158);
  const b = [`<div class="crumb"><a href="/">Home</a> › <a href="/topics">Topics</a> › ${esc(tp.short)}</div>`,
    `<h1>${esc(tp.name)}</h1>`,
    `<div class="upd">${arts.length} articles · latest ${esc(dateH(arts[0] && arts[0].publishedAt))}</div>`,
    `<p>${esc(tp.intro)}</p>`];
  if (tp.links && tp.links.length) b.push('<div class="chips">' + tp.links.map(([h, n]) => `<a href="${h}">${esc(n)}</a>`).join('') + '</div>');
  b.push('<h2>Articles</h2>');
  for (const a of arts) {
    b.push(`<div class="art"><a class="ttl" href="${artUrl(a)}">${esc(plain(a.title))}</a>`
      + `<div class="meta">${esc(dateH(a.publishedAt))}${a.category ? ' · ' + esc(plain(a.category)) : ''}${a.readTime ? ' · ' + esc(plain(a.readTime).replace('lettura', 'read')) : ''}</div>`
      + (a.excerpt ? `<p>${esc(plain(a.excerpt))}</p>` : '') + '</div>');
  }
  const others = TOPICS.filter(x => x.slug !== tp.slug);
  b.push('<h2>Other topics</h2><div class="chips">' + others.map(x => `<a href="/topics/${x.slug}">${esc(x.short)}</a>`).join('') + '</div>');
  const jsonld = [
    { '@context': 'https://schema.org', '@type': 'CollectionPage', name: tp.name, description: tp.intro, url,
      dateModified: arts[0] ? arts[0].publishedAt : undefined },
    { '@context': 'https://schema.org', '@type': 'ItemList', itemListElement: arts.slice(0, 100).map((a, i) => ({
      '@type': 'ListItem', position: i + 1, url: SITE + artUrl(a), name: plain(a.title) })) },
    { '@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE },
      { '@type': 'ListItem', position: 2, name: 'Topics', item: `${SITE}/topics` },
      { '@type': 'ListItem', position: 3, name: tp.name, item: url }] },
  ];
  return shell({ title, desc, canonical: url, body: b.join('\n'), jsonld });
}

export function topicsIndexPage(list) {
  const url = `${SITE}/topics`;
  const title = 'Market Analysis Topics — Stocks, Forex, Oil, Commodities, Crypto & Macro | XenosFinance';
  const desc = 'Browse XenosFinance market analysis by topic: stock market, forex, oil, commodities, crypto, macro and central banks, weekly market outlook, technical analysis and Elliott Wave.';
  const b = ['<div class="crumb"><a href="/">Home</a> › Topics</div>', '<h1>Market Analysis by Topic</h1>',
    `<div class="upd">${list.length} articles · latest ${esc(dateH(list[0] && list[0].publishedAt))}</div>`,
    '<p>Every article from the XenosFinance desk, grouped by market and theme.</p>'];
  for (const tp of TOPICS) {
    const arts = list.filter(a => tp.match(a));
    if (!arts.length) continue;
    b.push(`<div class="tp"><a href="/topics/${tp.slug}">${esc(tp.name)}</a>`
      + `<div class="meta">${arts.length} articles · latest ${esc(dateH(arts[0].publishedAt))}</div><p>${esc(tp.intro)}</p></div>`);
  }
  const jsonld = [{ '@context': 'https://schema.org', '@type': 'CollectionPage', name: 'Market Analysis by Topic', description: desc, url }];
  return shell({ title, desc, canonical: url, body: b.join('\n'), jsonld });
}

export function htmlResponse(body, status = 200) {
  return new Response(body, { status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=600' } });
}

export async function onRequestGet(context) {
  const { request, env, params } = context;
  const url = new URL(request.url);
  const parts = [].concat(params.path || []).filter(Boolean);
  const list = await loadArticles(env, url.origin);
  if (!list.length) return context.next();
  if (!parts.length) return htmlResponse(topicsIndexPage(list));
  const tp = TOPICS.find(x => x.slug === String(parts[0]).toLowerCase());
  if (!tp || parts.length > 1) {
    return htmlResponse(shell({ title: 'Topic not found | XenosFinance', desc: '', canonical: `${SITE}/topics`,
      body: '<h1>Topic not found</h1><p><a href="/topics">All topics</a></p>', robots: 'noindex' }), 404);
  }
  return htmlResponse(topicPage(tp, list.filter(a => tp.match(a))));
}
