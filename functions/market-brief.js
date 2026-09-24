/**
 * Cloudflare Pages Function — /market-brief  (ADDED 2026-09-24, SEO)
 *
 * market-brief.html is regenerated every morning by the
 * market-intelligence-agent pipeline, so SEO edits made directly in the
 * file would be overwritten the next day. This function rewrites the
 * head on the way out instead: a search-friendly title/description that
 * matches what people actually search ("pre-market brief", forex, gold,
 * oil, stocks), a canonical URL, Open Graph tags and a real <h1>.
 * The page content itself is untouched. Any error → original page.
 */

const SITE = 'https://xenosfinance.com';
const TITLE = 'Daily Pre-Market Brief — Forex, Gold, Oil & Stocks | XenosFinance';

function todayLabel() {
  return new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}

class SetAttr { constructor(a, v) { this.a = a; this.v = v; } element(el) { el.setAttribute(this.a, this.v); } }
class SetTitle { constructor(v) { this.v = v; } element(el) { el.setInnerContent(this.v); } }
class HeadTags {
  constructor(html) { this.html = html; this.seen = false; }
  element(el) { el.append(this.html, { html: true }); }
}
class ToH1 {
  constructor(label) { this.label = label; this.done = false; }
  element(el) {
    if (this.done) return;
    this.done = true;
    el.tagName = 'h1';
    el.setAttribute('style', (el.getAttribute('style') || '') + ';margin:0;font-size:inherit;font-weight:inherit;line-height:inherit;display:inline;');
    el.setInnerContent(this.label);
  }
}

export async function onRequestGet(context) {
  const res = await context.next();
  try {
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res;
    const date = todayLabel();
    const desc = `AI pre-market brief for ${date}: market sentiment, macro drivers and key levels for Forex, Gold, Oil, stocks and crypto — updated every morning.`;
    const url = `${SITE}/market-brief`;
    const head = [
      `<link rel="canonical" href="${url}">`,
      `<meta property="og:title" content="${TITLE}">`,
      `<meta property="og:description" content="${desc}">`,
      `<meta property="og:type" content="website">`,
      `<meta property="og:url" content="${url}">`,
      `<meta property="og:image" content="${SITE}/assets/blog/premarket.png">`,
      `<meta property="og:site_name" content="XenosFinance">`,
      `<meta name="twitter:card" content="summary_large_image">`,
      `<meta name="twitter:title" content="${TITLE}">`,
      `<meta name="twitter:description" content="${desc}">`,
    ].join('\n');

    const out = new HTMLRewriter()
      .on('title', new SetTitle(TITLE))
      .on('meta[name="description"]', new SetAttr('content', desc))
      .on('head', new HeadTags(head))
      .on('.ai-title', new ToH1('Daily Pre-Market Brief'))
      .transform(res);
    return out;
  } catch (_) {
    return res;
  }
}
