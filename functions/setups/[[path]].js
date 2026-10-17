/**
 * Cloudflare Pages Function — /setups e /setups/<slug>  (ADDED 2026-10-17, SEO)
 *
 * Le pagine Trade Setups / Trading Ideas caricano i setup con JavaScript da
 * trading_ideas/ideas.json: Google scarica un HTML senza contenuto e senza link.
 * Qui le stesse pagine vengono generate sul server, ad ogni richiesta, dal file
 * pubblicato dal bot (nessun commit, nessun deploy in più, nessuna AI):
 *   /setups          → indice con tutti i setup (link reali, ItemList JSON-LD)
 *   /setups/<slug>   → pagina del singolo setup (titolo, livelli, analisi, grafico)
 * Ogni numero mostrato è quello salvato dal bot nel setup: niente viene ricalcolato.
 */

const SITE = 'https://xenosfinance.com';
const RAW = 'https://raw.githubusercontent.com/xenosfinance-prog/waves/main/trading_ideas/ideas.json';
const SLUG_RE = /^[a-z0-9-]{6,120}$/;

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function plain(s) {
  return String(s ?? '').replace(/<[^>]*>/g, ' ').replace(/[*_#`>]+/g, '').replace(/\s+/g, ' ').trim();
}
function clip(s, n) {
  s = plain(s);
  if (s.length <= n) return s;
  const cut = s.slice(0, n - 1), sp = cut.lastIndexOf(' ');
  return (sp > n * 0.6 ? cut.slice(0, sp) : cut) + '…';
}
function num(v) { const x = parseFloat(v); return isFinite(x) ? x : null; }
function decOf(v) { const m = String(v ?? '').match(/\.(\d+)/); return m ? m[1].length : 0; }

// Decimali: quelli con cui il bot ha salvato target e stop (il prezzo a volte ha 16 decimali grezzi)
function decimals(s) { return Math.min(5, Math.max(decOf(s.target), decOf(s.invalidation), 0)); }
function fmt(v, dec) {
  const x = num(v);
  if (x === null) return '—';
  return dec <= 2 && Math.abs(x) >= 1000
    ? x.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
    : x.toFixed(dec);
}

function isLong(s) { return /^(BUY|LONG|BULL)/i.test(String(s.bias || '')); }
function day(ts) { return String(ts || '').slice(0, 10); }
function dateH(ts) {
  const d = new Date(ts);
  return isNaN(d) ? '' : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
}
function slugOf(s) {
  const t = String(s.ticker || s.name || 'setup').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const id = String(s.id || '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 8);
  return `${t}-${isLong(s) ? 'long' : 'short'}-${day(s.timestamp)}-${id}`;
}
function marketState(v) {
  if (!v) return {};
  if (typeof v === 'object') return v;
  const out = {};
  String(v).replace(/'(\w+)'\s*:\s*'([^']*)'/g, (_, k, x) => { out[k] = x; return ''; });
  return out;
}
function paragraphs(text) {
  return String(text ?? '').split(/\n{2,}|\r\n\r\n/).map(plain).filter(Boolean).map(p => `<p>${esc(p)}</p>`).join('');
}

async function loadSetups(env, origin) {
  // Prima il file su GitHub (aggiornato appena il bot pubblica), poi la copia del deploy.
  try {
    const r = await fetch(RAW, { cf: { cacheTtl: 300, cacheEverything: true } });
    if (r.ok) { const d = await r.json(); if (Array.isArray(d)) return d; }
  } catch (_) { /* fall through */ }
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL('/trading_ideas/ideas.json', origin));
      if (r.ok) { const d = await r.json(); if (Array.isArray(d)) return d; }
    }
  } catch (_) { /* fall through */ }
  return [];
}

const CSS = `:root{--bg:#0f1724;--bg2:#131f2e;--ink:#e2eaf4;--ink2:#b8cce0;--muted:#5a7a9a;--border:#1e3050;--border2:#243a5e;--red2:#f87171;--green2:#34d399;--gold:#3b82f6;--mono:'IBM Plex Mono',monospace;--serif:'Playfair Display',Georgia,serif;--body:'PT Serif',Georgia,serif;}
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
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px;margin:6px 0 4px;}
th{text-align:left;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);font-weight:normal;padding:6px 8px;border-bottom:1px solid var(--border2);}
td{padding:8px;border-bottom:1px solid var(--border);color:var(--ink);}
td.m{color:var(--muted);font-size:11px;}
.up{color:var(--green2);} .dn{color:var(--red2);}
.side{display:inline-block;font-family:var(--mono);font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:3px 10px;border:1px solid currentColor;margin-right:8px;}
.chart{width:100%;border:1px solid var(--border2);margin:8px 0;}
.box{border:1px solid var(--border2);background:var(--bg2);padding:16px 18px;margin-top:26px;}
.box p{font-size:14px;}
.cta a{display:inline-block;margin:6px 10px 0 0;font-family:var(--mono);font-size:11px;letter-spacing:1px;padding:9px 16px;border:1px solid var(--gold);color:var(--ink);}
.disc{font-family:var(--mono);font-size:10px;color:var(--muted);line-height:1.6;margin-top:34px;border-top:1px solid var(--border);padding-top:14px;}
@media(max-width:720px){h1{font-size:25px;}table{font-size:11px;}th,td{padding:5px;}}`;

const NAV = [['/', 'Home'], ['/dashboard', 'Dashboard'], ['/analysis', 'Daily Analysis'], ['/setups', 'Trade Setups'],
  ['/cot', 'COT Positioning'], ['/futures-flow', 'Futures Flow'], ['/calendar', 'Calendar'], ['/elliottwave', 'Elliott Wave'], ['/premium', 'Premium']];

function shell({ title, desc, canonical, body, jsonld, robots }) {
  const nav = NAV.map(([h, t]) => `<a href="${h}"${h === '/setups' ? ' class="on"' : ''}>${t}</a>`).join('');
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
<meta property="og:type" content="article">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${canonical}">
<meta property="og:site_name" content="XenosFinance">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:description" content="${esc(desc)}">
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
<div class="disc">Educational content only. Trade setups are produced by the XenosFinance engine from public market data for market analysis and trading education. They are not investment advice or a recommendation to buy or sell any financial instrument; levels refer to the time of publication and are not updated afterwards. Trading involves a significant risk of loss. © XenosFinance</div>
</main>
</body>
</html>`;
}

function setupPage(s, all) {
  const dec = decimals(s);
  const long = isLong(s);
  const sideW = long ? 'Long' : 'Short';
  const name = plain(s.name || s.ticker);
  const tf = plain(s.timeframe || '');
  const slug = slugOf(s);
  const url = `${SITE}/setups/${slug}`;
  const dh = dateH(s.timestamp);
  const entry = num(s.price), stop = num(s.invalidation), tgt = num(s.target);
  const risk = entry !== null && stop !== null ? Math.abs(entry - stop) : null;
  const reward = entry !== null && tgt !== null ? Math.abs(tgt - entry) : null;
  const ms = marketState(s.market_state);
  const text = plain(s.analysis || s.narrative || '');
  const title = `${name} ${sideW} Setup (${tf}) — ${dh} | XenosFinance`;
  const desc = clip(`${name} ${sideW.toLowerCase()} trade setup on the ${tf} chart, ${dh}: entry ${fmt(s.price, dec)}, stop ${fmt(s.invalidation, dec)}, target ${fmt(s.target, dec)}`
    + (s.rr ? `, risk/reward 1:${plain(s.rr)}` : '') + `. ${text}`, 158);
  const ageDays = (Date.now() - new Date(s.timestamp).getTime()) / 864e5;

  const b = [];
  b.push(`<div class="crumb"><a href="/">Home</a> › <a href="/setups">Trade Setups</a> › ${esc(name)}</div>`);
  b.push(`<h1>${esc(name)} ${sideW} Setup — ${esc(tf)} Chart</h1>`);
  b.push(`<div class="upd">Published ${esc(dh)} ${esc(String(s.timestamp || '').slice(11, 16))} UTC · ${esc(plain(s.ticker))} · source: XenosFinance ${esc(plain(s.source || 'engine'))}</div>`);
  if (ageDays > 2) b.push(`<div class="upd">Historical setup — levels refer to the publication time and are not updated.</div>`);
  b.push(`<p><span class="side ${long ? 'up' : 'dn'}">${sideW}</span>`
    + (s.score ? `<span class="side">Score ${esc(plain(s.score))}/10${s.score_label ? ' · ' + esc(plain(s.score_label)) : ''}</span>` : '') + `</p>`);

  b.push('<h2>Setup levels</h2>');
  b.push('<table><tr><th>Level</th><th>Price</th><th></th></tr>'
    + `<tr><td>Entry (price at publication)</td><td>${fmt(s.price, dec)}</td><td class="m"></td></tr>`
    + `<tr><td>Stop / invalidation</td><td class="dn">${fmt(s.invalidation, dec)}</td><td class="m">${risk !== null ? 'risk ' + fmt(risk, dec) : ''}</td></tr>`
    + `<tr><td>Target</td><td class="up">${fmt(s.target, dec)}</td><td class="m">${reward !== null ? 'reward ' + fmt(reward, dec) : ''}</td></tr>`
    + (s.rr ? `<tr><td>Risk / reward</td><td>1:${esc(plain(s.rr))}</td><td class="m"></td></tr>` : '')
    + '</table>');

  if (Object.keys(ms).length) {
    b.push('<h2>Market state</h2><table><tr><th>Factor</th><th>Reading</th></tr>'
      + Object.entries(ms).map(([k, v]) => `<tr><td>${esc(k.charAt(0).toUpperCase() + k.slice(1))}</td><td>${esc(plain(v))}</td></tr>`).join('')
      + '</table>');
  }
  if (text) {
    b.push('<h2>Analysis</h2>');
    b.push(paragraphs(s.analysis || s.narrative));
  }
  if (s.image_url && /^https:\/\/raw\.githubusercontent\.com\/xenosfinance-prog\//.test(s.image_url)) {
    b.push('<h2>Chart</h2>');
    b.push(`<img class="chart" src="${esc(s.image_url)}" alt="${esc(name)} ${sideW.toLowerCase()} setup chart, ${esc(tf)}, ${esc(dh)}" loading="lazy">`);
  }
  b.push('<div class="box"><p><b>How to use this setup.</b> A setup is a study of where the engine sees a favourable risk/reward, '
    + 'not a call to trade. Check the current price and structure first: the <a href="/analysis">daily technical analysis</a> '
    + 'shows live levels, and the <a href="/dashboard">dashboard</a> a 15-minute read.</p>'
    + `<div class="cta"><a href="/setups">All trade setups</a><a href="/trading-signals">Live setups</a>`
    + (s.tg_url && /^https:\/\/t\.me\//.test(s.tg_url) ? `<a href="${esc(s.tg_url)}">Telegram post</a>` : '') + '</div></div>');

  const same = all.filter(x => x !== s && x.ticker === s.ticker).slice(0, 6);
  if (same.length) {
    b.push(`<h2>Other ${esc(name)} setups</h2><table>` + same.map(x =>
      `<tr><td><a href="/setups/${slugOf(x)}">${esc(dateH(x.timestamp))}</a></td><td class="${isLong(x) ? 'up' : 'dn'}">${isLong(x) ? 'Long' : 'Short'}</td><td class="m">${esc(plain(x.timeframe))}</td></tr>`).join('') + '</table>');
  }

  const jsonld = [
    { '@context': 'https://schema.org', '@type': 'Article', headline: `${name} ${sideW} Setup — ${tf}`, description: desc,
      datePublished: s.timestamp, dateModified: s.timestamp, mainEntityOfPage: url,
      ...(s.image_url ? { image: s.image_url } : {}),
      author: { '@type': 'Organization', name: 'XenosFinance', url: SITE },
      publisher: { '@type': 'Organization', name: 'XenosFinance', logo: { '@type': 'ImageObject', url: `${SITE}/favicon-192.png` } } },
    { '@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE },
      { '@type': 'ListItem', position: 2, name: 'Trade Setups', item: `${SITE}/setups` },
      { '@type': 'ListItem', position: 3, name: `${name} ${sideW} Setup`, item: url }] },
  ];
  return shell({ title, desc, canonical: url, body: b.join('\n'), jsonld });
}

function indexPage(list) {
  const url = `${SITE}/setups`;
  const title = 'Trade Setups — Forex, Gold, Oil, Indices & Crypto | XenosFinance';
  const desc = 'Trade setups from the XenosFinance engine for Forex, Gold, Oil, stock indices, US stocks and crypto: entry, stop, target, risk/reward and the reasoning behind each setup. For market analysis and trading education.';
  const b = ['<div class="crumb"><a href="/">Home</a> › Trade Setups</div>',
    '<h1>Trade Setups</h1>',
    `<div class="upd">${list.length} setups · latest ${esc(dateH(list[0] && list[0].timestamp))} · updated as soon as a setup is published</div>`,
    '<p>Every setup is built by the XenosFinance engine on real market data — trend, momentum, volume profile, order flow and '
    + 'Ichimoku — and published with its entry, stop, target and risk/reward. Levels refer to the publication time. Setups are '
    + 'studies for market analysis and trading education, not recommendations.</p>',
    '<table><tr><th>Date (UTC)</th><th>Market</th><th>Side</th><th>TF</th><th>Entry</th><th>Stop</th><th>Target</th><th>R:R</th></tr>'];
  for (const s of list) {
    const dec = decimals(s), long = isLong(s);
    b.push(`<tr><td class="m">${esc(dateH(s.timestamp))}</td><td><a href="/setups/${slugOf(s)}">${esc(plain(s.name || s.ticker))}</a></td>`
      + `<td class="${long ? 'up' : 'dn'}">${long ? 'Long' : 'Short'}</td><td class="m">${esc(plain(s.timeframe))}</td>`
      + `<td>${fmt(s.price, dec)}</td><td>${fmt(s.invalidation, dec)}</td><td>${fmt(s.target, dec)}</td>`
      + `<td>${s.rr ? '1:' + esc(plain(s.rr)) : '—'}</td></tr>`);
  }
  b.push('</table>');
  b.push('<div class="box"><p><b>Live setups and daily analysis.</b> New setups are posted first on our Telegram channel; '
    + 'the daily analysis pages show live levels for the main markets.</p><div class="cta"><a href="/trading-signals">Live setups</a>'
    + '<a href="/analysis">Daily analysis</a><a href="https://t.me/xenoswavefinance">Telegram channel</a></div></div>');
  const jsonld = [
    { '@context': 'https://schema.org', '@type': 'CollectionPage', name: 'Trade Setups', description: desc, url,
      dateModified: list[0] ? list[0].timestamp : undefined },
    { '@context': 'https://schema.org', '@type': 'ItemList', itemListElement: list.slice(0, 50).map((s, i) => ({
      '@type': 'ListItem', position: i + 1, url: `${SITE}/setups/${slugOf(s)}`,
      name: `${plain(s.name || s.ticker)} ${isLong(s) ? 'Long' : 'Short'} Setup — ${dateH(s.timestamp)}` })) },
  ];
  return shell({ title, desc, canonical: url, body: b.join('\n'), jsonld });
}

function html(body, status = 200) {
  return new Response(body, { status, headers: { 'content-type': 'text/html; charset=utf-8',
    'cache-control': 'public, max-age=300' } });
}

export async function onRequestGet(context) {
  const { request, env, params } = context;
  const url = new URL(request.url);
  const parts = [].concat(params.path || []).filter(Boolean);
  const list = (await loadSetups(env, url.origin))
    .filter(s => s && s.timestamp && s.id && (s.price !== undefined))
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
  if (!parts.length) {
    if (!list.length) return context.next();
    return html(indexPage(list));
  }
  const slug = String(parts[0]).toLowerCase();
  if (parts.length > 1 || !SLUG_RE.test(slug)) return html(shell({ title: 'Setup not found | XenosFinance', desc: '', canonical: `${SITE}/setups`,
    body: '<h1>Setup not found</h1><p><a href="/setups">All trade setups</a></p>', robots: 'noindex' }), 404);
  const s = list.find(x => slugOf(x) === slug);
  if (!s) return html(shell({ title: 'Setup not found | XenosFinance', desc: '', canonical: `${SITE}/setups`,
    body: '<h1>Setup not found</h1><p>This setup is no longer in the archive. <a href="/setups">All trade setups</a></p>', robots: 'noindex' }), 404);
  return html(setupPage(s, list));
}
