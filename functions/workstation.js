/**
 * Cloudflare Pages Function — /workstation  (ADDED 2026-11-24)
 *
 * Link previews (Telegram, WhatsApp, X…) don't run JavaScript, so a shared
 * Workstation link showed no card. This function writes Open Graph / Twitter
 * tags into the HTML on the way out, from the link's own parameters:
 *   /workstation?s=TVC:GOLD&tf=60&i=momentum → "Gold · 1H chart — XenosFinance Workstation"
 * with the cover image of the market's category. The page itself is untouched.
 * Any error → original page.
 */

const SITE = 'https://xenosfinance.com';
const IMG = SITE + '/assets/blog/';

// TradingView symbol → [label, cover image]
const MARKETS = {
  'FX:EURUSD': ['EUR/USD', 'forex'], 'FX:GBPUSD': ['GBP/USD', 'forex'], 'FX:USDJPY': ['USD/JPY', 'forex'],
  'FX:AUDUSD': ['AUD/USD', 'forex'], 'FX:NZDUSD': ['NZD/USD', 'forex'], 'FX:USDCHF': ['USD/CHF', 'forex'],
  'FX:USDCAD': ['USD/CAD', 'forex'], 'FX:EURGBP': ['EUR/GBP', 'forex'], 'FX:EURJPY': ['EUR/JPY', 'forex'],
  'FX:GBPJPY': ['GBP/JPY', 'forex'], 'FX:AUDJPY': ['AUD/JPY', 'forex'], 'FX:CADJPY': ['CAD/JPY', 'forex'],
  'FX:EURCHF': ['EUR/CHF', 'forex'], 'FX:AUDCAD': ['AUD/CAD', 'forex'], 'FX:AUDCHF': ['AUD/CHF', 'forex'],
  'CAPITALCOM:DXY': ['US Dollar Index', 'forex'],
  'TVC:GOLD': ['Gold', 'commodities'], 'TVC:SILVER': ['Silver', 'commodities'], 'TVC:USOIL': ['WTI Crude Oil', 'energy'],
  'TVC:UKOIL': ['Brent Crude Oil', 'energy'], 'CAPITALCOM:NATURALGAS': ['Natural Gas', 'energy'], 'CAPITALCOM:COPPER': ['Copper', 'commodities'],
  'CAPITALCOM:US500': ['S&P 500', 'equity'], 'CAPITALCOM:US100': ['Nasdaq 100', 'equity'], 'CAPITALCOM:US30': ['Dow Jones', 'equity'],
  'PEPPERSTONE:GER40': ['DAX 40', 'equity'], 'PEPPERSTONE:UK100': ['FTSE 100', 'equity'], 'PEPPERSTONE:JPN225': ['Nikkei 225', 'equity'],
  'BITSTAMP:BTCUSD': ['Bitcoin', 'crypto'], 'BITSTAMP:ETHUSD': ['Ethereum', 'crypto'], 'COINBASE:SOLUSD': ['Solana', 'crypto'],
  'BITSTAMP:XRPUSD': ['XRP', 'crypto'],
};
const TF = { '15': '15m', '60': '1H', '240': '4H', 'D': 'Daily', 'W': 'Weekly' };
const PRESET = { trend: 'EMA 20/50 · SMA 200', momentum: 'RSI · MACD', volatility: 'Bollinger · ATR',
  ichimoku: 'Ichimoku', volume: 'VWAP · Volume', clean: '' };

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

class AddHead { constructor(h) { this.h = h; } element(el) { el.append(this.h, { html: true }); } }
class SetText { constructor(v) { this.v = v; } element(el) { el.setInnerContent(this.v); } }
class SetAttr { constructor(a, v) { this.a = a; this.v = v; } element(el) { el.setAttribute(this.a, this.v); } }

export async function onRequest(context) {
  const res = await context.next();
  try {
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('text/html')) return res;
    const url = new URL(context.request.url);
    const s = (url.searchParams.get('s') || '').toUpperCase();
    const tf = TF[url.searchParams.get('tf')] || '';
    const ind = PRESET[url.searchParams.get('i')] || '';
    const m = MARKETS[s];
    const label = m ? m[0] : (s ? s.split(':').pop() : '');
    const img = IMG + (m ? m[1] : 'premarket') + '.png';

    const title = label
      ? `${label}${tf ? ' · ' + tf : ''} chart — XenosFinance Workstation`
      : 'XenosFinance Workstation — every market, every indicator';
    const desc = label
      ? `${label}${tf ? ' ' + tf : ''} chart${ind ? ' with ' + ind : ''}, key levels, daily pivots and the macro events that move it. XenosFinance Workstation.`
      : 'Full-screen chart with every market, indicator and drawing tool, key levels, daily pivots and macro events. XenosFinance Workstation.';
    const share = SITE + '/workstation' + (url.search || '');

    const tags =
      `<meta property="og:type" content="website">` +
      `<meta property="og:site_name" content="XenosFinance">` +
      `<meta property="og:title" content="${esc(title)}">` +
      `<meta property="og:description" content="${esc(desc)}">` +
      `<meta property="og:url" content="${esc(share)}">` +
      `<meta property="og:image" content="${esc(img)}">` +
      `<meta property="og:image:width" content="1408"><meta property="og:image:height" content="768">` +
      `<meta name="twitter:card" content="summary_large_image">` +
      `<meta name="twitter:title" content="${esc(title)}">` +
      `<meta name="twitter:description" content="${esc(desc)}">` +
      `<meta name="twitter:image" content="${esc(img)}">`;

    return new HTMLRewriter()
      .on('title', new SetText(title))
      .on('meta[name="description"]', new SetAttr('content', desc))
      .on('head', new AddHead(tags))
      .transform(res);
  } catch (e) {
    return res;
  }
}
