/**
 * Cloudflare Pages Function — /calendar  (ADDED 2026-11-19, SEO)
 *
 * Search Console: the page shows for "gold economic calendar" / "economic calendar gold"
 * at positions 35–41, because the crawlable HTML had no events (they load via JS), a
 * stale date in the header and a generic H1. This function, on the way out:
 *  - title with today's date (like the /analysis pages, which rank and get clicks);
 *  - H1 "Gold & Forex Economic Calendar";
 *  - today's date in the header instead of the static one;
 *  - a server-rendered table of this week's high-impact USD events (the ones that move
 *    gold), from the same ForexFactory feed the page uses — real data, no estimates.
 * The rest of the page is untouched. Any error → original page.
 */

const FF_URL = 'https://waves-production-ddbf.up.railway.app/ff-calendar?weeks=thisweek';

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

class SetText { constructor(v) { this.v = v; } element(el) { el.setInnerContent(this.v); } }
class SetAttr { constructor(a, v) { this.a = a; this.v = v; } element(el) { el.setAttribute(this.a, this.v); } }
class Before { constructor(h) { this.h = h; } element(el) { el.before(this.h, { html: true }); } }

async function weekTable() {
  try {
    const r = await fetch(FF_URL, { cf: { cacheTtl: 900, cacheEverything: true }, signal: AbortSignal.timeout(6000) });
    if (!r.ok) return '';
    const d = await r.json();
    const ev = (d.events || [])
      .filter(e => e.country === 'USD' && e.impact === 'high' && e.time)
      .map(e => ({ ...e, t: new Date(e.time) }))
      .filter(e => !isNaN(e.t))
      .sort((a, b) => a.t - b.t);
    if (!ev.length) return '';
    const day = t => t.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
    const hm = t => t.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
    const td = 'style="padding:6px 10px;border-bottom:1px solid var(--border,#1e3050)"';
    const rows = ev.slice(0, 20).map(e =>
      `<tr><td ${td}>${esc(day(e.t))}</td><td ${td}>${esc(hm(e.t))}</td><td ${td}>${esc(e.event)}</td>` +
      `<td ${td}>${esc(e.actual || '—')}</td><td ${td}>${esc(e.estimate || '—')}</td><td ${td}>${esc(e.prev || '—')}</td></tr>`
    ).join('');
    const th = 'style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border,#1e3050);color:var(--ink,#e2e8f0);font-weight:500"';
    return `<h2 style="font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--ink,#e2e8f0);margin:16px 0 6px;font-weight:500">` +
      `High-impact US events for gold this week</h2>` +
      `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-family:var(--mono,monospace);font-size:11px;color:var(--muted)">` +
      `<thead><tr><th ${th}>Day</th><th ${th}>Time (UTC)</th><th ${th}>Event</th><th ${th}>Actual</th><th ${th}>Forecast</th><th ${th}>Previous</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>` +
      `<p style="font-size:10px;margin-top:4px">Source: ForexFactory calendar feed. Times in UTC; full week, all currencies and impact levels in the live calendar below.</p>`;
  } catch (e) {
    return '';
  }
}

export async function onRequest(context) {
  const res = await context.next();
  try {
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('text/html')) return res;
    const now = new Date();
    const short = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
    const long = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).toUpperCase();
    const title = `Gold Economic Calendar This Week (${short}) — NFP, CPI, FOMC | XenosFinance`;
    const desc = `Gold & forex economic calendar for this week: US CPI, NFP, FOMC and Fed events that move XAU/USD, ` +
      `with forecast, previous and official actuals. Updated ${short}.`;
    const table = await weekTable();
    let rw = new HTMLRewriter()
      .on('title', new SetText(title))
      .on('meta[name="description"]', new SetAttr('content', desc))
      .on('meta[property="og:title"]', new SetAttr('content', title))
      .on('#live-date', new SetText(long))
      .on('h1.page-title span', new SetText('🗓 Gold & Forex Economic Calendar'))
      .on('h1.page-title span', new SetAttr('data-i18n', 'h1_gold_forex_calendar'));
    if (table) rw = rw.on('p.cal-mkt-links', new Before(table));
    const out = rw.transform(res);
    const h = new Headers(out.headers);
    h.set('Cache-Control', 'public, max-age=0, s-maxage=900');
    return new Response(out.body, { status: out.status, headers: h });
  } catch (e) {
    return res;
  }
}
