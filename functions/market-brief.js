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


// 2026-10-26: menu completo con i sotto-menu come nel resto del sito (la pagina viene
// rigenerata ogni mattina dalla pipeline, quindi il menu si sostituisce qui).
const NAV_HTML = `
    <a class="nav-btn" href="${SITE}"><span data-i18n="nav_news">📰 News</span></a>
    <a class="nav-btn active" href="${SITE}/market-brief"><span data-i18n="nav_brief">🤖 Market Brief</span></a>
    <a class="nav-btn" href="${SITE}/intelligence/"><span>🛰 Intelligence</span></a>
    <div class="nav-dropdown">
      <a class="nav-btn nav-trig" href="${SITE}/dashboard"><span data-i18n="nav_dashboard">📊 Dashboard</span><span class="nav-caret">▾</span></a>
      <div class="nav-dropdown-menu">
        <a href="${SITE}/portfolio">📈 Portfolio</a>
        <a href="${SITE}/cot/" data-i18n="nav_cot">🧭 COT Positioning</a>
        <a href="${SITE}/futures-flow/" data-i18n="nav_futures_flow">🛢 Futures Flow</a>
        <a href="${SITE}/oil-options/">🧮 Oil Options</a>
        <a href="${SITE}/analysis/" data-i18n="nav_analysis">📊 Daily Analysis</a>
      </div>
    </div>
    <a class="nav-btn" href="${SITE}/xenoswaves_charts"><span data-i18n="nav_charts">◈ Charts</span></a>
    <a class="nav-btn" href="${SITE}/XenosBlog"><span data-i18n="nav_blog">✦ AI Blog</span></a>
    <div class="nav-dropdown">
      <a class="nav-btn nav-trig" href="${SITE}/trading-ideas"><span data-i18n="nav_ideas">💡 Trading Ideas</span><span class="nav-caret">▾</span></a>
      <div class="nav-dropdown-menu">
        <a href="${SITE}/live-setups" data-i18n="nav_signals">📡 Trade Setups</a>
      </div>
    </div>
    <a class="nav-btn" href="${SITE}/calendar"><span data-i18n="nav_calendar">🗓 Calendar</span></a>
    <a class="nav-btn" href="${SITE}/elliottwave"><span data-i18n="nav_elliott">〜 Elliott Wave</span></a>
    <div class="nav-dropdown">
      <a class="nav-btn nav-trig" href="${SITE}/daily-education"><span data-i18n="nav_education">📚 Education</span><span class="nav-caret">▾</span></a>
      <div class="nav-dropdown-menu">
        <a href="${SITE}/premium-support" data-i18n="nav_premium">✦ Premium</a>
        <a href="${SITE}/topics" data-i18n="nav_topics">🏷 Topics</a>
      </div>
    </div>
`;
const NAV_CSS = `<style>
.masthead-nav .nav-dropdown{position:relative;display:inline-block;}
.masthead-nav .nav-caret{font-size:8px;margin-left:5px;opacity:0.55;}
.masthead-nav .nav-dropdown-menu{display:none;position:absolute;top:100%;left:50%;transform:translateX(-50%);background:var(--bg);border:1px solid var(--border);border-top:2px solid var(--gold);min-width:200px;box-shadow:0 10px 28px rgba(0,0,0,0.5);z-index:200;padding:6px 0;}
.masthead-nav .nav-dropdown:hover .nav-dropdown-menu,.masthead-nav .nav-dropdown.open .nav-dropdown-menu{display:block;}
.masthead-nav .nav-dropdown-menu a{display:block;padding:10px 20px;font-family:var(--mono);font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);text-decoration:none;white-space:nowrap;text-align:left;}
.masthead-nav .nav-dropdown-menu a:hover{color:var(--gold2);background:var(--bg2);}
@media (max-width:768px){.masthead-nav .nav-dropdown-menu{position:static;transform:none;box-shadow:none;border:none;background:var(--bg3);min-width:0;}}
</style>`;
const NAV_JS = `<script>
(function(){document.querySelectorAll('.masthead-nav .nav-dropdown').forEach(function(d){var t=d.querySelector(':scope > .nav-trig');if(!t)return;
t.addEventListener('click',function(e){if(window.matchMedia('(hover: hover)').matches)return;if(!d.classList.contains('open')){e.preventDefault();document.querySelectorAll('.masthead-nav .nav-dropdown.open').forEach(function(o){o.classList.remove('open');});d.classList.add('open');}});});
document.addEventListener('click',function(e){if(!e.target.closest('.masthead-nav .nav-dropdown'))document.querySelectorAll('.masthead-nav .nav-dropdown.open').forEach(function(o){o.classList.remove('open');});});})();
</script>`;
class SetInner { constructor(h) { this.h = h; } element(el) { el.setInnerContent(this.h, { html: true }); } }
class AppendHtml { constructor(h) { this.h = h; } element(el) { el.append(this.h, { html: true }); } }

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
      .on('head', new AppendHtml(NAV_CSS))
      .on('nav.masthead-nav', new SetInner(NAV_HTML))
      .on('body', new AppendHtml(NAV_JS))
      .on('body', new AppendHtml('<script src="/tg-banner.js?v=1" defer></script>'))  // 2026-10-27: banner Telegram
      // 2026-10-27: brief in italiano quando la lingua del sito è IT (traduzione gratuita nel browser)
      .on('body', new AppendHtml('<script src="/xf-translate.js?v=1" defer></script><script src="/mb-it.js?v=1" defer></script>'))
      .on('.ai-title', new ToH1('Daily Pre-Market Brief'))
      .transform(res);
    return out;
  } catch (_) {
    return res;
  }
}
