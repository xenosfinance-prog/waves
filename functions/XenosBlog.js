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

async function loadArticle(env, origin, slug) {
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL(`/articles/${slug}.json`, origin));
      if (r.ok) return await r.json();
    }
  } catch (_) { /* fall through */ }
  try {
    // Very fresh articles may not be in the Pages deploy yet.
    const r = await fetch(RAW + slug + '.json', { cf: { cacheTtl: 300, cacheEverything: true } });
    if (r.ok) return await r.json();
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
const TOPIC_BAR = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px;font-family:\'IBM Plex Mono\',monospace;font-size:11px">'
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

    const a = await loadArticle(env, url.origin, slug);
    if (!a || !a.title) return res;

    // Some auto-generated articles have a generic title ("Macro Update") and the
    // real headline in the intro — use the headline for search when that happens.
    const rawTitle = plain(a.title);
    const headline = rawTitle.length < 25 && plain(a.intro).length > rawTitle.length
      ? clip(a.intro, 90) : rawTitle;
    const fullTitle = `${clip(headline, 65)} | XenosFinance`;
    const desc = clip(a.excerpt || a.intro || a.conclusion || headline, 158);
    const canonical = `${SITE}/XenosBlog?slug=${encodeURIComponent(slug)}`;
    const image = a.imageUrl && /^https?:\/\//.test(a.imageUrl) ? a.imageUrl : `${SITE}/assets/blog/macro.png`;

    let body = paragraphs(a.intro);
    for (const s of asList(a.sections)) {
      if (!s) continue;
      body += `<div class="edu-section"><div class="edu-section-title">${esc(plain(s.heading))}</div>${paragraphs(s.content)}</div>`;
    }
    if (a.quote) body += `<blockquote>${esc(plain(a.quote))}</blockquote>`;
    if (a.conclusion) body += `<div class="edu-section"><div class="edu-section-title">// Conclusion</div>${paragraphs(a.conclusion)}</div>`;
    // 2026-10-17: link alle pagine tema (/topics/...) per collegare gli articoli tra loro
    // (fuori da #artBody: lo script della pagina riscrive #artBody, il blocco temi deve restare)
    const tps = topicsFor(a);
    const topicsHtml = tps.length
      ? `<div class="edu-section"><div class="edu-section-title">// Topics</div><p>`
        + tps.map(tp => `<a href="${SITE}/topics/${tp.slug}">${esc(tp.name)}</a>`).join(' · ')
        + ` · <a href="${SITE}/topics">All topics</a></p></div>`
      : '';

    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: clip(headline, 110),
      description: desc,
      image: [image],
      datePublished: a.publishedAt || a.generatedAt || undefined,
      dateModified: a.generatedAt || a.publishedAt || undefined,
      author: { '@type': 'Organization', name: 'XenosFinance', url: SITE },
      publisher: { '@type': 'Organization', name: 'XenosFinance', logo: { '@type': 'ImageObject', url: `${SITE}/favicon-192.png` } },
      mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
      articleSection: a.categoryLabel || a.category || undefined,
      inLanguage: a.lang || 'en',
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
      .on('head', new AppendHead(ldTag))
      .on('#artTitle', new SetText(esc(clip(headline, 140)), true))
      .on('#artCat', new SetText(esc(a.categoryLabel || a.category || ''), true))
      .on('#artBody', new SetText(body, true))
      .on('#artBody', new After(topicsHtml))
      .transform(res);

    const headers = new Headers(out.headers);
    headers.set('Cache-Control', 'public, max-age=300');
    return new Response(out.body, { status: out.status, headers });
  } catch (_) {
    return res; // never break the page
  }
}
