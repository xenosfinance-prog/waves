/**
 * Cloudflare Pages Function — /daily-education  (ADDED 2026-11-14, SEO / AI search)
 *
 * Problem it fixes: the Daily Education page was built only by JavaScript.
 * Search engines that do not run JS — and the crawlers of AI assistants
 * (ChatGPT, Claude, Perplexity), which generally don't — saw an empty page
 * with skeleton placeholders, so none of the lessons could be found or cited.
 *
 * What it does (the page's own JavaScript still runs exactly as before):
 *   /daily-education            → today's lesson pre-rendered in #todayContent
 *                                 + archive grid with real links to every lesson
 *   /daily-education?d=DATE     → that lesson, with its own title, description,
 *                                 canonical URL and LearningResource JSON-LD
 *   …&lang=it|es|ru|uk          → the pre-translated version (i18n/<lang>/daily_education/)
 * Any error falls back to the original page.
 */

const SITE = 'https://xenosfinance.com';
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const LANGS = ['it', 'es', 'ru', 'uk'];
const LOCALE = { en: 'en_US', it: 'it_IT', es: 'es_ES', ru: 'ru_RU', uk: 'uk_UA' };
const ARCHIVE_MAX = 90;

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function clean(s) {
  return String(s ?? '').replace(/[*_`]+/g, '').replace(/\s+/g, ' ').trim();
}

function clip(s, n) {
  s = clean(s);
  if (s.length <= n) return s;
  const cut = s.slice(0, n - 1);
  const sp = cut.lastIndexOf(' ');
  return (sp > n * 0.6 ? cut.slice(0, sp) : cut) + '…';
}

async function loadJson(env, origin, path) {
  try {
    if (env && env.ASSETS) {
      const r = await env.ASSETS.fetch(new URL(path, origin));
      if (r.ok) return await r.json();
    }
  } catch (_) { /* fall through */ }
  return null;
}

// Prompt leftovers the page also strips (see formatEduContent in daily-education.html)
function tidy(raw) {
  return String(raw || '')
    .replace(/\s*[—–-]+\s*(?:DA\s*)?\d+\s*(?:TO|A|-)\s*\d+\s*(?:SHORT|BREVI)\s*(?:BULLETS|PUNTI)/gi, '')
    .replace(/\s*[—–-]+\s*(?:ONE\s+PRACTICAL\s+DESK-LEVEL\s+INSIGHT|UN\s+INSIGHT\s+PRATICO\s+A\s+LIVELLO\s+DI\s+DESK)/gi, '');
}

const SEP_RE = /^[━─═\-]{3,}$/;
const isPageHeader = line => /^📚/.test(line) || /DAILY MARKET EDUCATION/i.test(line);
const EMOJI_RE = /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE0F}]/gu;
const NUM_HEAD_RE = /^\d+\.\s+\S/;

function isHeading(line) {
  if (NUM_HEAD_RE.test(line)) return true;
  const letters = line.replace(/[^A-Za-zА-Яа-яЁёІіЇїЄєҐґÀ-ÿ]/g, '');
  return letters.length >= 4 && letters === letters.toUpperCase() && line.length <= 90;
}

// Lesson text → simple semantic HTML (headings, paragraphs, lists)
function lessonHtml(raw) {
  const lines = tidy(raw).split('\n');
  let html = '', inList = false;
  const close = () => { if (inList) { html += '</ul>'; inList = false; } };
  const bold = t => esc(t).replace(/\*([^*]+)\*/g, '<b>$1</b>');
  for (let line of lines) {
    line = line.trim();
    if (!line || SEP_RE.test(line)) { close(); continue; }
    if (isPageHeader(line)) continue;   // "📚 DAILY MARKET EDUCATION" (anche tradotto): già nell'H1
    if (/^[-•▪●◦]\s+/.test(line)) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${bold(line.replace(/^[-•▪●◦]\s+/, ''))}</li>`;
      continue;
    }
    close();
    if (isHeading(line)) html += `<h2 class="edu-section-title">${bold(line)}</h2>`;
    else html += `<p>${bold(line)}</p>`;
  }
  close();
  return html;
}

// Lesson title = first short line after the page header
// ("1. CHART ANATOMY: THE BREAKOUT TRAP 🎯" → "Chart Anatomy: The Breakout Trap",
//  "💵 ADVANCED: Dollar Liquidity — …" → "Advanced: Dollar Liquidity — …")
function lessonTitle(raw) {
  for (let line of tidy(raw).split('\n')) {
    line = line.trim();
    if (!line || SEP_RE.test(line) || isPageHeader(line)) continue;
    if (line.length > 120) return '';
    const t = clean(line.replace(/^\d+\.\s+/, '').replace(EMOJI_RE, ''));
    if (!t) continue;
    return t === t.toUpperCase()
      ? t.toLowerCase().replace(/(^|[\s:(/-])(\S)/g, (m, a, b) => a + b.toUpperCase())
      : t;
  }
  return '';
}

function lessonSummary(raw) {
  for (let line of tidy(raw).split('\n')) {
    line = line.trim();
    if (!line || SEP_RE.test(line) || isHeading(line) || /^[-•▪●◦]\s+/.test(line)) continue;
    if (line.length > 60) return clip(line, 158);
  }
  return '';
}

function niceDate(d) {
  const dt = new Date(d + 'T12:00:00Z');
  return isNaN(dt) ? d : dt.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
}

class SetAttr { constructor(a, v) { this.a = a; this.v = v; } element(el) { el.setAttribute(this.a, this.v); } }
class SetInner { constructor(h) { this.h = h; } element(el) { el.setInnerContent(this.h, { html: true }); } }
class SetTitle { constructor(t) { this.t = t; } element(el) { el.setInnerContent(this.t); } }
class AppendHead { constructor(h) { this.h = h; } element(el) { el.append(this.h, { html: true }); } }

export async function onRequestGet(context) {
  const { request, env, next } = context;
  const res = await next();
  try {
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res;
    const url = new URL(request.url);
    const idx = await loadJson(env, url.origin, '/daily_education/index.json');
    const posts = (idx && Array.isArray(idx.posts) ? idx.posts : []).filter(p => p && DATE_RE.test(p.date || ''));
    if (!posts.length) return res;

    const reqDate = url.searchParams.get('d');
    const single = DATE_RE.test(reqDate || '') && posts.some(p => p.date === reqDate);
    const date = single ? reqDate : posts[0].date;

    const en = await loadJson(env, url.origin, `/daily_education/${date}.json`);
    if (!en || !en.content) return res;

    // pre-translated versions available for this lesson
    const trs = {};
    await Promise.all(LANGS.map(async l => {
      const t = await loadJson(env, url.origin, `/i18n/${l}/daily_education/${date}.json`);
      if (t && t.content) trs[l] = t;
    }));
    const reqLang = url.searchParams.get('lang');
    const lang = trs[reqLang] ? reqLang : 'en';
    const lesson = lang === 'en' ? en : trs[lang];

    const title = lessonTitle(en.content) || 'Daily Market Education';
    const summary = lessonSummary(lesson.content) || lessonSummary(en.content);
    const baseUrl = `${SITE}/daily-education`;
    const lessonUrl = `${baseUrl}?d=${date}`;
    const pageUrl = single ? lessonUrl : baseUrl;
    const canonical = lang === 'en' ? pageUrl : `${pageUrl}${single ? '&' : '?'}lang=${lang}`;
    const fullTitle = single
      ? `${clip(lang === 'en' ? title : (lessonTitle(lesson.content) || title), 70)} — Daily Market Education (${date}) | XenosFinance`
      : 'Daily Market Education — Trading Lessons Every Trading Day | XenosFinance';
    const desc = single ? summary
      : `Free daily trading lessons from an independent oil trader: technical analysis, macro, risk management and trading psychology. Today: ${title}.`;

    const alt = Object.keys(trs).length
      ? `<link rel="alternate" hreflang="en" href="${esc(pageUrl)}">`
        + Object.keys(trs).map(l => `<link rel="alternate" hreflang="${l}" href="${esc(pageUrl + (single ? '&' : '?') + 'lang=' + l)}">`).join('')
        + `<link rel="alternate" hreflang="x-default" href="${esc(pageUrl)}">`
      : '';

    const ld = {
      '@context': 'https://schema.org',
      '@type': 'LearningResource',
      name: lang === 'en' ? title : (lessonTitle(lesson.content) || title),
      headline: clip(lang === 'en' ? title : (lessonTitle(lesson.content) || title), 110),
      description: summary || desc,
      url: canonical,
      inLanguage: lang,
      datePublished: en.generated_at || date,
      learningResourceType: 'Lesson',
      educationalLevel: 'Intermediate',
      isAccessibleForFree: true,
      teaches: 'Trading and financial market analysis',
      author: { '@type': 'Person', '@id': `${SITE}/about#founder`, name: 'Ben Carrow', url: `${SITE}/about` }, // 2026-11-17 E-E-A-T
      publisher: { '@type': 'Organization', '@id': `${SITE}/#org`, name: 'XenosFinance', url: `${SITE}/` },
      isPartOf: { '@type': 'Course', name: 'XenosFinance Daily Market Education', url: baseUrl,
        provider: { '@id': `${SITE}/#org` } },
    };
    const ldTag = `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</script>`;

    // today card / single lesson
    const head = `<div class="today-date">${esc(niceDate(date))}</div>`;
    const body = `<article class="today-content" id="todayContent" lang="${lang}"${lang !== 'en' ? ' data-no-xft' : ''}>`
      + lessonHtml(lesson.content) + `</article>`;

    // archive: real links to every lesson (the page script replaces this grid with its own cards)
    const links = posts.slice(0, ARCHIVE_MAX).map(p =>
      `<div class="archive-card"><a href="${baseUrl}?d=${p.date}${lang !== 'en' ? '&lang=' + lang : ''}">`
      + `<div class="archive-date">${esc(p.day_name || '')} · ${esc(p.date)}</div>`
      + `<div class="archive-preview">Daily Market Education — ${esc(p.date)}</div></a></div>`).join('');

    return new HTMLRewriter()
      .on('title', new SetTitle(fullTitle))
      .on('meta[name="description"]', new SetAttr('content', desc))
      .on('link[rel="canonical"]', new SetAttr('href', canonical))
      .on('meta[property="og:title"]', new SetAttr('content', fullTitle))
      .on('meta[property="og:description"]', new SetAttr('content', desc))
      .on('meta[property="og:url"]', new SetAttr('content', canonical))
      .on('html', new SetAttr('lang', lang))
      .on('head', new AppendHead(ldTag + alt + `<meta property="og:locale" content="${LOCALE[lang]}">`))
      .on('#todayCard', new SetInner(head + body))
      .on('#archiveGrid', new SetInner(links))
      .transform(res);
  } catch (_) {
    return res;
  }
}
