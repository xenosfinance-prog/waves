// ============================================================
//  XenosFinance — Cloudflare Worker v2.7
//  Changes vs v2.6:
//  - Added type:"notify-email" → sends email via Cloudflare Email Routing
//    (send_email binding), replaces EmailJS in premium.html / premium-support.html
// ============================================================

import { EmailMessage } from "cloudflare:email";

const ALLOWED_ORIGINS = [
  "https://xenosfinance.com",
  "https://www.xenosfinance.com",
  "https://waves-2qc.pages.dev",
  "http://localhost",
  "http://127.0.0.1",
];

const SECURITY_HEADERS = {
  "Strict-Transport-Security":  "max-age=15552000; includeSubDomains; preload",
  "X-Content-Type-Options":     "nosniff",
  "X-Frame-Options":            "DENY",
  "X-XSS-Protection":          "1; mode=block",
  "Referrer-Policy":            "strict-origin-when-cross-origin",
  "Permissions-Policy":         "camera=(), microphone=(), geolocation=(), payment=()",
  "Content-Security-Policy":    "default-src 'self'; connect-src 'self' https://api.anthropic.com https://finnhub.io https://api.twelvedata.com https://api.massive.com https://query1.finance.yahoo.com https://api.frankfurter.app https://api.coingecko.com https://api.github.com https://raw.githubusercontent.com https://api.telegram.org https://nfs.faireconomy.media https://economic-trading-forex-events-calendar.p.rapidapi.com https://sbcharts.investing.com https://www.barchart.com https://feeds.reuters.com; img-src *; font-src *; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
};

const rateLimitMap = new Map();
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMITS = { anthropic: 20, default: 120, "notify-email": 10 };

function checkRateLimit(ip, type) {
  const key = `${ip}:${type}`;
  const limit = RATE_LIMITS[type] || RATE_LIMITS.default;
  const now = Date.now();
  const entry = rateLimitMap.get(key);
  if (!entry || now - entry.ts > RATE_LIMIT_WINDOW_MS) { rateLimitMap.set(key, { ts: now, count: 1 }); return true; }
  if (entry.count >= limit) return false;
  entry.count++;
  return true;
}

function pruneRateLimits() {
  const now = Date.now();
  for (const [k, v] of rateLimitMap) if (now - v.ts > RATE_LIMIT_WINDOW_MS * 2) rateLimitMap.delete(k);
}

const newsCache = new Map();
function getCached(key, ttlMs) {
  const entry = newsCache.get(key);
  if (entry && Date.now() - entry.ts < ttlMs) return entry.data;
  return null;
}
function setCache(key, data) {
  newsCache.set(key, { ts: Date.now(), data });
  if (newsCache.size > 50) {
    const oldest = [...newsCache.entries()].sort((a,b) => a[1].ts - b[1].ts)[0];
    if (oldest) newsCache.delete(oldest[0]);
  }
}

function b64DecodeUTF8(b64) {
  const binary = atob(b64.replace(/\n/g, ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder('utf-8').decode(bytes);
}

function b64EncodeUTF8(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

// ── EMAIL NOTIFY (Cloudflare Email Routing / send_email binding) ──
function escapeHeader(str) {
  return String(str || '').replace(/[\r\n]/g, ' ').slice(0, 200);
}

async function sendNotifyEmail(env, { subject, text, replyTo }) {
  const fromAddr = env.NOTIFY_FROM_EMAIL || "notify@xenosfinance.com";
  const toAddr = env.NOTIFY_TO_EMAIL || "xenosfinance@gmail.com";
  if (!env.SEB) throw new Error("SEB (send_email binding) not configured on this Worker");

  const headers = [
    `From: XenosFinance <${fromAddr}>`,
    `To: ${toAddr}`,
    `Subject: ${escapeHeader(subject)}`,
    replyTo ? `Reply-To: ${escapeHeader(replyTo)}` : null,
    `MIME-Version: 1.0`,
    `Content-Type: text/plain; charset="UTF-8"`,
    `Content-Transfer-Encoding: 8bit`,
  ].filter(Boolean).join("\r\n");

  const raw = `${headers}\r\n\r\n${text || ""}`;
  const msg = new EmailMessage(fromAddr, toAddr, raw);
  await env.SEB.send(msg);
}

async function _deleteFromGitHub(token, repo, file, item_id, commit_msg) {
  const apiUrl = `https://api.github.com/repos/${repo}/contents/${file}`;
  const ghHeaders = {
    "Authorization": `token ${token}`,
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "XenosFinance"
  };
  const readRes = await fetch(apiUrl, { headers: ghHeaders });
  if (!readRes.ok) throw new Error(`GitHub read: ${readRes.status}`);
  const fileData = await readRes.json();
  const sha = fileData.sha;
  let items;
  try { items = JSON.parse(b64DecodeUTF8(fileData.content)); }
  catch(e) { throw new Error(`JSON parse error: ${e.message}`); }
  const updated = items.filter(i => i.id !== item_id);
  if (updated.length === items.length) throw new Error(`Item not found: ${item_id}`);
  const encoded = b64EncodeUTF8(JSON.stringify(updated, null, 2));
  const putRes = await fetch(apiUrl, {
    method: "PUT",
    headers: { ...ghHeaders, "Content-Type": "application/json" },
    body: JSON.stringify({
      message: commit_msg || `Delete ${item_id}`,
      content: encoded,
      sha,
      committer: { name: "XenosFinance Admin", email: "admin@xenosfinance.com" }
    })
  });
  if (!putRes.ok) throw new Error(`GitHub write: ${putRes.status}`);
  return { deleted: item_id, remaining: updated.length };
}

const COINGECKO_IDS = {"BTCUSD":"bitcoin","ETHUSD":"ethereum","XRPUSD":"ripple","SOLUSD":"solana","DOGEUSD":"dogecoin","ZECUSD":"zcash","BNBUSD":"binancecoin","ADAUSD":"cardano","AVAXUSD":"avalanche-2","LINKUSD":"chainlink","MATICUSD":"matic-network","DOTUSD":"polkadot","LTCUSD":"litecoin","ATOMUSD":"cosmos","UNIUSD":"uniswap","XLMUSD":"stellar","TRXUSD":"tron","ETCUSD":"ethereum-classic","NEARUSD":"near"};
const COMMODITY_ESTIMATES = {"XAUUSD":3100,"XAGUSD":34.0,"USOIL":70.0,"UKOIL":73.0,"NGAS":3.80,"COPPER":4.80,"US500":5600,"US30":42000,"NAS100":19500,"UK100":8500,"GER40":22500,"FRA40":8100,"JPN225":37000,"HK50":21000,"AUS200":8300};
const FX_PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURGBP","EURJPY","GBPJPY","CADJPY","AUDNZD","EURCHF","GBPCHF"];
const FX_CROSSES = ["AUDCAD","AUDCHF","AUDJPY","CADCHF","CHFJPY","EURNZD","EURAUD","EURCAD","GBPAUD","GBPCAD","GBPNZD","NZDCAD","NZDCHF","NZDJPY","USDMXN","USDNOK","USDSEK","USDTRY","USDZAR"];
const TD_SYMBOL_MAP = {"EURUSD":"EUR/USD","GBPUSD":"GBP/USD","USDJPY":"USD/JPY","USDCHF":"USD/CHF","AUDUSD":"AUD/USD","NZDUSD":"NZD/USD","USDCAD":"USD/CAD","EURGBP":"EUR/GBP","EURJPY":"EUR/JPY","GBPJPY":"GBP/JPY","CADJPY":"CAD/JPY","AUDNZD":"AUD/NZD","EURCHF":"EUR/CHF","GBPCHF":"GBP/CHF","BTCUSD":"BTC/USD","ETHUSD":"ETH/USD","XRPUSD":"XRP/USD","SOLUSD":"SOL/USD","DOGEUSD":"DOGE/USD","ZECUSD":"ZEC/USD","XAUUSD":"XAU/USD","XAGUSD":"XAG/USD"};
const FH_SYMBOL_MAP = {"EURUSD":"OANDA:EUR_USD","GBPUSD":"OANDA:GBP_USD","USDJPY":"OANDA:USD_JPY","USDCHF":"OANDA:USD_CHF","AUDUSD":"OANDA:AUD_USD","NZDUSD":"OANDA:NZD_USD","USDCAD":"OANDA:USD_CAD","EURGBP":"OANDA:EUR_GBP","EURJPY":"OANDA:EUR_JPY","GBPJPY":"OANDA:GBP_JPY","CADJPY":"OANDA:CAD_JPY","AUDNZD":"OANDA:AUD_NZD","EURCHF":"OANDA:EUR_CHF","GBPCHF":"OANDA:GBP_CHF","BTCUSD":"BINANCE:BTCUSDT","ETHUSD":"BINANCE:ETHUSDT","XRPUSD":"BINANCE:XRPUSDT","SOLUSD":"BINANCE:SOLUSDT","DOGEUSD":"BINANCE:DOGEUSDT","ZECUSD":"BINANCE:ZECUSDT","XAUUSD":"OANDA:XAU_USD","XAGUSD":"OANDA:XAG_USD"};
const YAHOO_SYMBOL_MAP = {"XAGUSD":"SI=F","USOIL":"CL=F","UKOIL":"BZ=F","NGAS":"NG=F","COPPER":"HG=F","XAUUSD":"GC=F","US500":"^GSPC","US30":"^DJI","NAS100":"^IXIC","UK100":"^FTSE","GER40":"^GDAXI","FRA40":"^FCHI","JPN225":"^N225","HK50":"^HSI","AUS200":"^AXJO","SPY":"SPY","QQQ":"QQQ","DIA":"DIA","IWM":"IWM","VTI":"VTI","VOO":"VOO","XLK":"XLK","XLF":"XLF","XLE":"XLE","XLV":"XLV","XLY":"XLY","XLI":"XLI","XLU":"XLU","XLRE":"XLRE","XLP":"XLP","XLB":"XLB","XLC":"XLC","GLD":"GLD","GDX":"GDX","GDXJ":"GDXJ","SLV":"SLV","USO":"USO","OIH":"OIH","UNG":"UNG","TLT":"TLT","IEF":"IEF","SHY":"SHY","LQD":"LQD","HYG":"HYG","AGG":"AGG","BND":"BND","BOTZ":"BOTZ","ARKK":"ARKK","ARKG":"ARKG","ARKW":"ARKW","KRE":"KRE","IAI":"IAI","KBWB":"KBWB","DBA":"DBA","WEAT":"WEAT","CORN":"CORN","SOYB":"SOYB","EWG":"EWG","EWU":"EWU","EWQ":"EWQ","EWJ":"EWJ","EWH":"EWH","EEM":"EEM","IWDA.AS":"IWDA.AS","CSPX.L":"CSPX.L","VUSA.AS":"VUSA.AS","EURUSD=X":"EURUSD=X","GBPUSD=X":"GBPUSD=X","USDJPY=X":"USDJPY=X","USDCHF=X":"USDCHF=X","AUDUSD=X":"AUDUSD=X","NZDUSD=X":"NZDUSD=X","USDCAD=X":"USDCAD=X","GBPJPY=X":"GBPJPY=X","EURJPY=X":"EURJPY=X","BTC-USD":"BTC-USD","ETH-USD":"ETH-USD","SOL-USD":"SOL-USD","XRP-USD":"XRP-USD","DOGE-USD":"DOGE-USD","GC=F":"GC=F","CL=F":"CL=F","SI=F":"SI=F","NG=F":"NG=F","BZ=F":"BZ=F","HG=F":"HG=F","^IXIC":"^IXIC","^GSPC":"^GSPC","^DJI":"^DJI","^GDAXI":"^GDAXI","^FTSE":"^FTSE","^TNX":"^TNX","^VIX":"^VIX","^IRX":"^IRX","^TYX":"^TYX","^N225":"^N225","^FCHI":"^FCHI","^HSI":"^HSI","^AXJO":"^AXJO","AAPL":"AAPL","MSFT":"MSFT","NVDA":"NVDA","TSLA":"TSLA","AMZN":"AMZN","GOOGL":"GOOGL","META":"META","JPM":"JPM","V":"V","BRK-B":"BRK-B","XOM":"XOM","JNJ":"JNJ","GS":"GS","BAC":"BAC","NFLX":"NFLX","CVX":"CVX","WMT":"WMT"};
const YAHOO_SYMBOLS = new Set(Object.keys(YAHOO_SYMBOL_MAP));
const MASSIVE_TICKER_MAP = {"EURUSD":"C:EURUSD","GBPUSD":"C:GBPUSD","USDJPY":"C:USDJPY","USDCHF":"C:USDCHF","AUDUSD":"C:AUDUSD","NZDUSD":"C:NZDUSD","USDCAD":"C:USDCAD","EURGBP":"C:EURGBP","EURJPY":"C:EURJPY","GBPJPY":"C:GBPJPY","CADJPY":"C:CADJPY","AUDNZD":"C:AUDNZD","EURCHF":"C:EURCHF","GBPCHF":"C:GBPCHF","AUDCAD":"C:AUDCAD","AUDCHF":"C:AUDCHF","AUDJPY":"C:AUDJPY","CADCHF":"C:CADCHF","CHFJPY":"C:CHFJPY","EURNZD":"C:EURNZD","EURAUD":"C:EURAUD","EURCAD":"C:EURCAD","GBPAUD":"C:GBPAUD","GBPCAD":"C:GBPCAD","GBPNZD":"C:GBPNZD","NZDCAD":"C:NZDCAD","NZDCHF":"C:NZDCHF","NZDJPY":"C:NZDJPY","USDMXN":"C:USDMXN","USDNOK":"C:USDNOK","USDSEK":"C:USDSEK","USDTRY":"C:USDTRY","USDZAR":"C:USDZAR","XAUUSD":"C:XAUUSD","XAGUSD":"C:XAGUSD","BTCUSD":"X:BTCUSD","ETHUSD":"X:ETHUSD","XRPUSD":"X:XRPUSD","SOLUSD":"X:SOLUSD","DOGEUSD":"X:DOGEUSD","BNBUSD":"X:BNBUSD","ADAUSD":"X:ADAUSD","AVAXUSD":"X:AVAXUSD","LINKUSD":"X:LINKUSD","MATICUSD":"X:MATICUSD","DOTUSD":"X:DOTUSD","LTCUSD":"X:LTCUSD","ATOMUSD":"X:ATOMUSD","UNIUSD":"X:UNIUSD","XLMUSD":"X:XLMUSD","TRXUSD":"X:TRXUSD","ETCUSD":"X:ETCUSD","NEARUSD":"X:NEARUSD"};
const MASSIVE_TF_MAP = {"15":{multiplier:15,timespan:"minute"},"60":{multiplier:1,timespan:"hour"},"240":{multiplier:4,timespan:"hour"},"D":{multiplier:1,timespan:"day"},"15min":{multiplier:15,timespan:"minute"},"1h":{multiplier:1,timespan:"hour"},"4h":{multiplier:4,timespan:"hour"},"1day":{multiplier:1,timespan:"day"}};

async function massiveCandles(ticker,resolution,from,to,apiKey){const tf=MASSIVE_TF_MAP[String(resolution)]||{multiplier:1,timespan:"hour"};const url=`https://api.massive.com/v2/aggs/ticker/${encodeURIComponent(ticker)}/range/${tf.multiplier}/${tf.timespan}/${from*1000}/${to*1000}?adjusted=true&sort=asc&limit=500&apiKey=${apiKey}`;const res=await fetch(url,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Massive HTTP ${res.status}`);const data=await res.json();if(!data.results||data.results.length===0)return[];return data.results.map(r=>({datetime:new Date(r.t).toISOString(),open:r.o,high:r.h,low:r.l,close:r.c,volume:r.v||0}));}
async function massivePrice(ticker,apiKey){const url=`https://api.massive.com/v2/snapshot/locale/global/markets/forex/tickers/${encodeURIComponent(ticker)}?apiKey=${apiKey}`;const res=await fetch(url,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Massive snapshot HTTP ${res.status}`);const d=await res.json();const t=d?.ticker;if(!t)throw new Error("Massive: no ticker data");const price=t.lastTrade?.p||t.lastQuote?.P||t.prevDay?.c;if(!price)throw new Error("Massive: no price");const prev=t.prevDay?.c||price;return{price:parseFloat(price),change_pct:parseFloat(((price-prev)/prev*100).toFixed(3))};}
async function yahooQuote(sym){const ticker=YAHOO_SYMBOL_MAP[sym]||sym;const res=await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=2d`,{headers:{"User-Agent":"Mozilla/5.0 (compatible; XenosFinance/1.0)","Accept":"application/json"}});if(!res.ok)throw new Error(`Yahoo HTTP ${res.status} for ${ticker}`);const data=await res.json();const meta=data?.chart?.result?.[0]?.meta;if(!meta||!meta.regularMarketPrice)throw new Error(`Yahoo: no price for ${ticker}`);const price=meta.regularMarketPrice;const prevClose=meta.chartPreviousClose||meta.previousClose||price;const change=price-prevClose;return{price,open:meta.regularMarketOpen||0,high:meta.regularMarketDayHigh||0,low:meta.regularMarketDayLow||0,prev_close:prevClose,change:parseFloat(change.toFixed(4)),change_pct:parseFloat((prevClose?(change/prevClose)*100:0).toFixed(3)),timestamp:meta.regularMarketTime||null,source:`yahoo:${ticker}`};}
async function tdFetch(endpoint,params,apiKey){const url=new URL(`https://api.twelvedata.com/${endpoint}`);url.searchParams.set("apikey",apiKey);for(const[k,v]of Object.entries(params))url.searchParams.set(k,v);const res=await fetch(url.toString(),{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`TwelveData HTTP ${res.status}`);return res.json();}
async function fhQuote(symbol,apiKey){const res=await fetch(`https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(symbol)}&token=${apiKey}`,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Finnhub HTTP ${res.status}`);const d=await res.json();if(!d.c||d.c===0)throw new Error("Finnhub: no price data");return d;}
async function fhMarketNews(category,apiKey){const res=await fetch(`https://finnhub.io/api/v1/news?category=${category}&token=${apiKey}`,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Finnhub news HTTP ${res.status}`);return res.json();}
async function fhNewsSentiment(symbol,apiKey){const res=await fetch(`https://finnhub.io/api/v1/news-sentiment?symbol=${encodeURIComponent(symbol)}&token=${apiKey}`,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Finnhub sentiment HTTP ${res.status}`);return res.json();}

function getISODate(daysAgo=0){const d=new Date();d.setDate(d.getDate()-daysAgo);return d.toISOString().slice(0,10);}
function fxRateFromData(rates,base,quote){if(base==="EUR"&&rates[quote])return rates[quote];if(quote==="EUR"&&rates[base])return 1/rates[base];if(rates[base]&&rates[quote])return rates[quote]/rates[base];return null;}
async function frankfurterFXWithChange(pair){const base=pair.slice(0,3);const quote=pair.slice(3,6);const today=getISODate(0);const yesterday=getISODate(1);const[resToday,resYesterday]=await Promise.all([fetch(`https://api.frankfurter.app/${today}?base=EUR`,{headers:{"User-Agent":"XenosFinance/1.0"}}),fetch(`https://api.frankfurter.app/${yesterday}?base=EUR`,{headers:{"User-Agent":"XenosFinance/1.0"}})]);const[dataToday,dataYesterday]=await Promise.all([resToday.json(),resYesterday.json()]);const rToday=dataToday.rates||{};const rYesterday=dataYesterday.rates||{};const rateToday=fxRateFromData(rToday,base,quote);const rateYesterday=fxRateFromData(rYesterday,base,quote);if(rateToday==null)throw new Error(`Frankfurter: no rate for ${pair}`);const dec=pair.includes("JPY")?3:5;const change_pct=(rateYesterday&&rateYesterday>0)?parseFloat(((rateToday-rateYesterday)/rateYesterday*100).toFixed(3)):0;return{price:parseFloat(rateToday.toFixed(dec)),change_pct,change:rateYesterday?parseFloat((rateToday-rateYesterday).toFixed(6)):0};}

async function fetchForexFactoryXML(week){const feedUrl=`https://nfs.faireconomy.media/ff_calendar_${week}.xml`;const cache=caches.default;const cacheKey=new Request(`https://xenos-cache.internal/ff_${week}`);const cached=await cache.match(cacheKey);if(cached){const xml=await cached.text();if(xml&&xml.length>200)return parseForexFactoryXML(xml);}const res=await fetch(feedUrl,{headers:{"User-Agent":"Mozilla/5.0 (compatible; XenosFinance/1.0)","Accept":"application/xml, text/xml, */*"}});if(!res.ok)throw new Error(`ForexFactory HTTP ${res.status}`);const xml=await res.text();await cache.put(cacheKey,new Response(xml,{headers:{"Content-Type":"text/xml","Cache-Control":"public, max-age=3600"}}));return parseForexFactoryXML(xml);}
function parseForexFactoryXML(xml){if(!xml||xml.length<200)throw new Error('ForexFactory: empty response');const events=[];const eventBlocks=xml.match(/<event>([\s\S]*?)<\/event>/g)||[];for(const block of eventBlocks){const get=(tag)=>{const m=block.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`));return m?m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g,'$1').trim():'';};const impact=get('impact');if(!['High','Medium'].includes(impact))continue;const dateRaw=get('date');const timeRaw=get('time');const country=get('country');const title=get('title');const dm=dateRaw.match(/^(\d{2})-(\d{2})-(\d{4})$/);if(!dm)continue;const isoDay=`${dm[3]}-${dm[1]}-${dm[2]}`;let timeUTC='T12:00:00Z';const tm=timeRaw.toLowerCase().replace(/\s/g,'').match(/^(\d{1,2}):(\d{2})(am|pm)$/);if(tm){let h=parseInt(tm[1]);const m=parseInt(tm[2]);if(tm[3]==='pm'&&h!==12)h+=12;if(tm[3]==='am'&&h===12)h=0;const hUTC=(h+4)%24;timeUTC=`T${String(hUTC).padStart(2,'0')}:${String(m).padStart(2,'00')}:00Z`;}events.push({id:`ff_${isoDay}_${title.slice(0,20).replace(/\s/g,'_')}`,time:isoDay+timeUTC,country:country.toUpperCase(),event:title,impact:impact.toLowerCase(),actual:get('actual')||null,estimate:get('forecast')||null,prev:get('previous')||null});}return events;}

const RSS_WHITELIST = ['barchart.com', 'reuters.com', 'cnbc.com', 'feeds.reuters.com'];
async function fetchRSSFeed(feedUrl){const isAllowed=RSS_WHITELIST.some(d=>feedUrl.includes(d));if(!isAllowed)throw new Error("Feed URL not whitelisted");const cached=getCached('rss:'+feedUrl,10*60*1000);if(cached)return cached;const res=await fetch(feedUrl,{headers:{"User-Agent":"Mozilla/5.0 (compatible; XenosFinance/1.0)","Accept":"application/rss+xml, application/xml, text/xml, */*","Referer":"https://xenosfinance.com/"},cf:{cacheTtl:600,cacheEverything:true}});if(!res.ok)throw new Error(`RSS HTTP ${res.status}`);const xml=await res.text();if(!xml||xml.length<100)throw new Error("RSS: empty response");const items=[];const itemBlocks=xml.match(/<item>([\s\S]*?)<\/item>/g)||[];for(const block of itemBlocks.slice(0,20)){const get=(tag)=>{const m=block.match(new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`));return m?(m[1]||m[2]||'').trim():'';};const title=get('title');const desc=get('description').replace(/<[^>]+>/g,'').trim();const link=get('link');if(!title||title.length<5)continue;items.push({title,desc:desc.substring(0,300),link});}setCache('rss:'+feedUrl,items);return items;}

async function fhEconomicCalendar(from,to,apiKey){const res=await fetch(`https://finnhub.io/api/v1/calendar/economic?from=${from}&to=${to}&token=${apiKey}`,{headers:{"User-Agent":"XenosFinance/1.0"}});if(!res.ok)throw new Error(`Finnhub calendar HTTP ${res.status}`);const data=await res.json();const raw=data.economicCalendar||data.economic_calendar||data.calendar||[];return raw.map((e,i)=>({id:e.id||'fh_'+i,time:e.time||e.date||'',country:(e.country||'').toUpperCase(),event:e.event||e.name||'',impact:(e.impact||'').toLowerCase()==='high'?'high':(e.impact||'').toLowerCase()==='medium'?'medium':'low',actual:(e.actual!=null&&e.actual!=='')?String(e.actual):null,estimate:(e.estimate!=null&&e.estimate!=='')?String(e.estimate):null,prev:(e.prev!=null&&e.prev!=='')?String(e.prev):null}));}
async function fetchInvestingCalendar(from,to){const fromTs=Math.floor(new Date(from).getTime()/1000);const toTs=Math.floor(new Date(to+'T23:59:59Z').getTime()/1000);const res=await fetch(`https://sbcharts.investing.com/events_charts/us/economic_events_calendar.json?from=${fromTs}&to=${toTs}&significance=2&significance=3`,{headers:{'User-Agent':'Mozilla/5.0 (compatible; XenosFinance/1.0)','Accept':'application/json','Referer':'https://www.investing.com/economic-calendar/','X-Requested-With':'XMLHttpRequest'},cf:{cacheTtl:1800,cacheEverything:true}});if(!res.ok)throw new Error(`Investing.com HTTP ${res.status}`);const data=await res.json();const raw=Array.isArray(data)?data:(data.data||data.events||[]);return raw.map((e,i)=>({id:'inv_'+(e.id||i),time:e.date||e.dateUtc||'',country:(e.currency||e.countryCode||'').toUpperCase(),event:e.name||e.event||'',impact:(e.significance||e.importance||0)>=3?'high':(e.significance||e.importance||0)>=2?'medium':'low',actual:(e.actual!=null&&e.actual!=='')?String(e.actual):null,estimate:(e.forecast!=null&&e.forecast!=='')?String(e.forecast):null,prev:(e.previous!=null&&e.previous!=='')?String(e.previous):null})).filter(e=>e.event);}

// ── STRIPE HELPERS ──────────────────────────────────────────
// Nessuna dipendenza npm: usa fetch puro (stesso stile del resto del Worker)
// e Web Crypto per la verifica firma webhook.

function stripeFormBody(obj, prefix) {
  // Converte un oggetto JS nel formato x-www-form-urlencoded annidato
  // richiesto dall'API di Stripe (es. line_items[0][price]=xxx).
  const parts = [];
  for (const key in obj) {
    if (obj[key] === undefined || obj[key] === null) continue;
    const k = prefix ? `${prefix}[${key}]` : key;
    const val = obj[key];
    if (Array.isArray(val)) {
      val.forEach((item, i) => {
        if (typeof item === "object") parts.push(stripeFormBody(item, `${k}[${i}]`));
        else parts.push(`${encodeURIComponent(`${k}[${i}]`)}=${encodeURIComponent(item)}`);
      });
    } else if (typeof val === "object") {
      parts.push(stripeFormBody(val, k));
    } else {
      parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(val)}`);
    }
  }
  return parts.join("&");
}

async function stripeApi(env, path, params) {
  const secretKey = env.STRIPE_SECRET_KEY;
  if (!secretKey) throw new Error("STRIPE_SECRET_KEY mancante");
  const res = await fetch(`https://api.stripe.com/v1/${path}`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${secretKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: stripeFormBody(params),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || `Stripe API error ${res.status}`);
  return data;
}

async function verifyStripeSignature(rawBody, sigHeader, secret) {
  // Header formato: "t=1699999999,v1=abcdef..."
  const parts = Object.fromEntries(sigHeader.split(",").map(p => p.split("=")));
  const signedPayload = `${parts.t}.${rawBody}`;
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(signedPayload));
  const expectedHex = [...new Uint8Array(sigBuf)].map(b => b.toString(16).padStart(2, "0")).join("");
  return expectedHex === parts.v1;
}

const STRIPE_PRICE_IDS = {
  monthly: "price_1U2n1i3OW2DuOvk5tFPPXxde", // Premium Monthly EUR 9.00
  yearly:  "price_1U2n1p3OW2DuOvk5vnFJKsai", // Premium Yearly  EUR 79.00
};

async function handleStripeWebhook(request, env) {
  const sig = request.headers.get("stripe-signature");
  const rawBody = await request.text();
  const secret = env.STRIPE_WEBHOOK_SECRET;
  if (!secret || !sig) return new Response("Missing signature or secret", { status: 400 });

  let valid;
  try { valid = await verifyStripeSignature(rawBody, sig, secret); }
  catch { return new Response("Signature check failed", { status: 400 }); }
  if (!valid) return new Response("Invalid signature", { status: 400 });

  const event = JSON.parse(rawBody);

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object;
      // TODO: salva { email: session.customer_details?.email, customer_id: session.customer,
      //   subscription_id: session.subscription, plan: session.metadata?.plan, status: "active" }
      // usando lo stesso storage dei codici XENOS-PREMIUM-2026 / XF-PRO-00x (GitHub JSON via env.GITHUB_TOKEN).
      break;
    }
    case "invoice.paid": {
      // rinnovo riuscito — nessuna azione necessaria se già attivo
      break;
    }
    case "invoice.payment_failed": {
      // rinnovo fallito — Stripe Smart Retries ritenta da solo; qui puoi notificare via Telegram/email
      break;
    }
    case "customer.subscription.deleted": {
      const sub = event.data.object;
      // TODO: revoca accesso premium per sub.customer
      break;
    }
    default: break;
  }

  return new Response(JSON.stringify({ received: true }), { status: 200, headers: { "Content-Type": "application/json" } });
}

export default {
  async fetch(request, env) {
    const _url = new URL(request.url);
    if (_url.pathname === "/stripe-webhook" && request.method === "POST") {
      return handleStripeWebhook(request, env);
    }

    pruneRateLimits();
    const origin = request.headers.get("Origin") || "";
    const isAllowed = !origin || ALLOWED_ORIGINS.some(o => origin.startsWith(o));
    const corsHeaders = {
      "Access-Control-Allow-Origin": isAllowed ? origin : ALLOWED_ORIGINS[0],
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    };
    const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { ...corsHeaders, ...SECURITY_HEADERS, "Content-Type": "application/json", "Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache" } });

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...corsHeaders, ...SECURITY_HEADERS } });
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: { ...corsHeaders, ...SECURITY_HEADERS } });
    if (!isAllowed) return new Response("Forbidden", { status: 403, headers: { ...corsHeaders, ...SECURITY_HEADERS } });

    try {
      const body = await request.json();
      const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
      const isAnthropicCall = !body.type || body.type === "anthropic" || body.messages;
      const rlType = isAnthropicCall ? "anthropic" : "default";
      if (!checkRateLimit(clientIP, rlType)) return json({ error: "Rate limit exceeded. Please wait before making more requests." }, 429);

      // ── NOTIFY EMAIL (Cloudflare Email Routing) ───────────────
      if (body.type === "notify-email") {
        if (!checkRateLimit(clientIP, "notify-email")) return json({ ok: false, error: "Too many requests" }, 429);
        const { subject, message, reply_to } = body;
        if (!subject || !message) return json({ ok: false, error: "subject/message mancanti" }, 400);
        try {
          await sendNotifyEmail(env, { subject: String(subject).slice(0, 200), text: String(message).slice(0, 5000), replyTo: reply_to });
          return json({ ok: true });
        } catch(e) { return json({ ok: false, error: e.message }, 500); }
      }

      // ── DELETE TRADING IDEA ───────────────────────────────────
      if (body.type === "delete-idea") {
        const token = env.GITHUB_TOKEN;
        if (!token) return json({ ok: false, error: "GITHUB_TOKEN mancante" }, 500);
        const { idea_id, admin_pwd } = body;
        if (!idea_id) return json({ ok: false, error: "idea_id mancante" }, 400);
        if (!env.ADMIN_PASSWORD || admin_pwd !== env.ADMIN_PASSWORD) return json({ ok: false, error: "Unauthorized" }, 403);
        try {
          const result = await _deleteFromGitHub(token, "xenosfinance-prog/waves", "trading_ideas/ideas.json", idea_id, `Delete idea ${idea_id}`);
          return json({ ok: true, ...result });
        } catch(e) { return json({ ok: false, error: e.message }, e.message.includes("not found") ? 404 : 500); }
      }

      // ── DELETE EW SIGNAL ─────────────────────────────────────
      if (body.type === "delete-ew-signal") {
        const token = env.GITHUB_TOKEN;
        if (!token) return json({ ok: false, error: "GITHUB_TOKEN mancante" }, 500);
        const { signal_id, admin_pwd } = body;
        if (!signal_id) return json({ ok: false, error: "signal_id mancante" }, 400);
        if (!env.ADMIN_PASSWORD || admin_pwd !== env.ADMIN_PASSWORD) return json({ ok: false, error: "Unauthorized" }, 403);
        try {
          const result = await _deleteFromGitHub(token, "xenosfinance-prog/waves", "ew_signals/signals.json", signal_id, `Delete EW signal ${signal_id}`);
          return json({ ok: true, ...result });
        } catch(e) { return json({ ok: false, error: e.message }, e.message.includes("not found") ? 404 : 500); }
      }

      // ── LIBRETRANSLATE PROXY ──────────────────────────────────
      if (body.type === "translate") {
        const ltUrl = env.LIBRETRANSLATE_URL;
        if (!ltUrl) return json({ translatedText: body.q || "", error: "LIBRETRANSLATE_URL not configured" });
        const { q, source, target, format } = body;
        if (!q || !target) return json({ error: "q and target required" }, 400);
        const ltCacheKey = `lt:${target}:${(q||'').slice(0,40)}`;
        const ltCached = getCached(ltCacheKey, 60 * 60 * 1000); // 1h cache
        if (ltCached) return json({ translatedText: ltCached });
        try {
          const ltRes = await fetch(ltUrl.replace(/\/$/, '') + '/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q, source: source || 'en', target, format: format || 'text' })
          });
          if (!ltRes.ok) throw new Error(`LibreTranslate HTTP ${ltRes.status}`);
          const ltData = await ltRes.json();
          if (ltData.translatedText) setCache(ltCacheKey, ltData.translatedText);
          return json(ltData);
        } catch(e) {
          return json({ translatedText: q, error: e.message }); // graceful fallback: return original
        }
      }

      if (body.type === "forexfactory") {
        const week = body.week || "thisweek";
        try { return json({ events: await fetchForexFactoryXML(week), source: "forexfactory", week }); }
        catch(e) { return json({ events: [], error: e.message }); }
      }

      if (body.type === "barchart" || body.type === "rss") {
        const feedUrl = body.url;
        if (!feedUrl) return json({ items: [], error: "Missing feed URL" });
        try { return json({ items: await fetchRSSFeed(feedUrl), source: "rss", url: feedUrl }); }
        catch(e) { return json({ items: [], error: e.message }); }
      }

      if (body.type === "massive") {
        const massiveKey = env.MASSIVE_API_KEY;
        if (!massiveKey) return json({ error: "MASSIVE_API_KEY mancante" }, 500);
        if (body.action === "candles") {
          const { symbol, resolution, from, to } = body;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          const ticker = MASSIVE_TICKER_MAP[symbol];
          if (!ticker) return json({ error: `Simbolo non mappato: ${symbol}`, candles: [] });
          try { return json({ symbol, ticker, resolution, candles: await massiveCandles(ticker, resolution, from, to, massiveKey), source: "massive" }); }
          catch(e) { return json({ error: e.message, candles: [] }, 500); }
        }
        return json({ error: `Azione Massive sconosciuta: "${body.action}"` }, 400);
      }

      if (body.type === "github") {
        const token = env.GITHUB_TOKEN;
        if (!token) return json({ status: 500, error: "GITHUB_TOKEN mancante" });
        const opts = { method: body.method || "GET", headers: { "Authorization": "token " + token, "Accept": "application/vnd.github.v3+json", "User-Agent": "XenosFinance" } };
        if (body.payload && body.method !== "GET") { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body.payload); }
        const r = await fetch(body.url, opts);
        const text = await r.text();
        let data; try { data = JSON.parse(text); } catch { data = { raw: text }; }
        return json({ status: r.status, data });
      }

      if (body.type === "telegram") {
        const botToken = env.TELEGRAM_BOT_TOKEN;
        const channelId = env.TELEGRAM_CHANNEL_ID;
        if (!botToken || !channelId) return json({ ok: false, description: "Telegram env vars not configured" }, 500);
        const r = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: channelId, text: body.text, parse_mode: body.parse_mode || "HTML", disable_web_page_preview: true, reply_markup: body.reply_markup })
        });
        return json(await r.json());
      }

      if (body.type === "telegram_photo") {
        const botToken = env.TELEGRAM_BOT_TOKEN;
        const channelId = env.TELEGRAM_CHANNEL_ID;
        if (!botToken || !channelId) return json({ ok: false, description: "Telegram env vars not configured" }, 500);
        const { image_base64, caption, parse_mode, image_mime } = body;
        const mimeType = image_mime || "image/jpeg";
        const ext = mimeType.includes("png") ? "png" : "jpg";
        const binaryStr = atob(image_base64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);
        const form = new FormData();
        form.append("chat_id", channelId);
        form.append("photo", new Blob([bytes], { type: mimeType }), "signal." + ext);
        form.append("caption", caption || "");
        form.append("parse_mode", parse_mode || "HTML");
        const tgRes = await fetch(`https://api.telegram.org/bot${botToken}/sendPhoto`, { method: "POST", body: form });
        return json(await tgRes.json());
      }

      if (body.type === "prices") {
        const pairs = body.pairs || [];
        const prices = {};
        const fxMajors    = pairs.filter(p => FX_PAIRS.includes(p));
        const fxCrosses   = pairs.filter(p => FX_CROSSES.includes(p));
        const cryptoPairs = pairs.filter(p => COINGECKO_IDS[p]);
        const yahooPairs  = pairs.filter(p => !FX_PAIRS.includes(p) && !FX_CROSSES.includes(p) && !COINGECKO_IDS[p] && YAHOO_SYMBOLS.has(p));
        const restPairs   = pairs.filter(p => !FX_PAIRS.includes(p) && !FX_CROSSES.includes(p) && !COINGECKO_IDS[p] && !YAHOO_SYMBOLS.has(p));
        if (fxMajors.length > 0) {
          const fxApiKey = env.FINNHUB_API_KEY;
          await Promise.all(fxMajors.map(async pair => {
            const fhSym = FH_SYMBOL_MAP[pair];
            if (fhSym && fxApiKey) {
              try { const d = await fhQuote(fhSym, fxApiKey); if (d.c && d.c > 0) { prices[pair] = { price: parseFloat(d.c.toFixed(pair.includes("JPY") ? 3 : 5)), change_pct: d.pc ? parseFloat(((d.c - d.pc) / d.pc * 100).toFixed(3)) : 0, change: parseFloat((d.c - (d.pc||d.c)).toFixed(6)) }; return; } } catch(e) {}
            }
            try { const result = await frankfurterFXWithChange(pair); prices[pair] = result; } catch(e2) {}
          }));
        }
        const massiveKey = env.MASSIVE_API_KEY;
        const massivePairs = [...fxCrosses, ...cryptoPairs.filter(p => !["BTCUSD","ETHUSD","XRPUSD","SOLUSD","DOGEUSD","ZECUSD"].includes(p))].filter(p => MASSIVE_TICKER_MAP[p]);
        if (massivePairs.length > 0 && massiveKey) {
          await Promise.all(massivePairs.map(async p => {
            try { const d = await massivePrice(MASSIVE_TICKER_MAP[p], massiveKey); if (d.price > 0) prices[p] = d; } catch(e) {}
          }));
        }
        const cgPairs = cryptoPairs.filter(p => COINGECKO_IDS[p] && !prices[p]);
        if (cgPairs.length > 0) {
          try {
            const ids = cgPairs.map(p => COINGECKO_IDS[p]).join(",");
            const res = await fetch(`https://api.coingecko.com/api/v3/simple/price?ids=${ids}&vs_currencies=usd&include_24hr_change=true`, { headers: { "Accept": "application/json", "User-Agent": "XenosFinance/1.0" } });
            const data = await res.json();
            for (const pair of cgPairs) { const id = COINGECKO_IDS[pair]; if (data[id]?.usd) prices[pair] = { price: data[id].usd, change_pct: parseFloat((data[id].usd_24h_change || 0).toFixed(3)) }; }
          } catch(e) {}
        }
        if (yahooPairs.length > 0) {
          await Promise.all(yahooPairs.map(async sym => {
            try { const d = await yahooQuote(sym); if (d.price && d.price > 0) prices[sym] = { price: d.price, change_pct: d.change_pct, change: d.change, prev_close: d.prev_close }; } catch(e) {}
          }));
        }
        if (restPairs.length > 0) {
          const apiKey = env.FINNHUB_API_KEY;
          await Promise.all(restPairs.map(async sym => {
            if (prices[sym]) return;
            const fhSym = FH_SYMBOL_MAP[sym];
            if (fhSym && apiKey) {
              try { const d = await fhQuote(fhSym, apiKey); if (d.c && d.c > 0) { prices[sym] = { price: parseFloat(d.c.toFixed(6)), change_pct: d.pc ? parseFloat(((d.c - d.pc) / d.pc * 100).toFixed(3)) : 0 }; return; } } catch(e) {}
            }
            if (COMMODITY_ESTIMATES[sym]) prices[sym] = { price: COMMODITY_ESTIMATES[sym], change_pct: 0 };
          }));
        }
        return json({ prices, ts: Date.now() });
      }

      if (body.type === "twelvedata") {
        const apiKey = env.TWELVE_DATA_API_KEY;
        if (!apiKey) return json({ error: "TWELVE_DATA_API_KEY mancante" }, 500);
        const action = body.action;
        if (action === "quote") {
          const symbols = body.symbols || [];
          if (symbols.length === 0) return json({ error: "Nessun simbolo fornito" }, 400);
          const data = await tdFetch("quote", { symbol: symbols.map(s => TD_SYMBOL_MAP[s] || s).join(",") }, apiKey);
          const entries = Array.isArray(data) ? data : [data];
          const quotes = {};
          for (let i = 0; i < symbols.length; i++) { const d = entries[i] || {}; if (d.status === "error") { quotes[symbols[i]] = { error: d.message }; continue; } quotes[symbols[i]] = { price: parseFloat(d.close || d.price || 0), open: parseFloat(d.open || 0), high: parseFloat(d.high || 0), low: parseFloat(d.low || 0), change: parseFloat(d.change || 0), change_pct: parseFloat(d.percent_change || 0), volume: parseInt(d.volume || 0, 10), timestamp: d.datetime || d.timestamp || null }; }
          return json({ quotes });
        }
        if (action === "ohlcv") {
          const { symbol, interval, outputsize } = body;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          const data = await tdFetch("time_series", { symbol: TD_SYMBOL_MAP[symbol] || symbol, interval: interval || "4h", outputsize: outputsize || 50, format: "JSON" }, apiKey);
          if (data.status === "error") return json({ error: data.message });
          return json({ symbol, interval, candles: (data.values || []).map(v => ({ datetime: v.datetime, open: parseFloat(v.open), high: parseFloat(v.high), low: parseFloat(v.low), close: parseFloat(v.close), volume: parseInt(v.volume || 0, 10) })) });
        }
        if (action === "indicators") {
          const { symbol, interval, indicators } = body;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          const tdSym = TD_SYMBOL_MAP[symbol] || symbol, result = { symbol, interval };
          const fetches = [];
          const ind = indicators || ["rsi","macd","ema"];
          if (ind.includes("rsi")) fetches.push(tdFetch("rsi", { symbol: tdSym, interval: interval || "4h", time_period: 14, outputsize: 1 }, apiKey).then(d => { result.rsi = d.values?.[0]?.rsi ? parseFloat(d.values[0].rsi) : null; }).catch(() => { result.rsi = null; }));
          if (ind.includes("macd")) fetches.push(tdFetch("macd", { symbol: tdSym, interval: interval || "4h", fast_period: 12, slow_period: 26, signal_period: 9, outputsize: 1 }, apiKey).then(d => { const v = d.values?.[0]; result.macd = v ? { macd: parseFloat(v.macd || 0), signal: parseFloat(v.macd_signal || 0), histogram: parseFloat(v.macd_hist || 0) } : null; }).catch(() => { result.macd = null; }));
          if (ind.includes("ema")) {
            for (const p of [20, 50, 200]) fetches.push(tdFetch("ema", { symbol: tdSym, interval: interval || "4h", time_period: p, outputsize: 1 }, apiKey).then(d => { result[`ema_${p}`] = d.values?.[0]?.ema ? parseFloat(d.values[0].ema) : null; }).catch(() => { result[`ema_${p}`] = null; }));
          }
          await Promise.all(fetches);
          return json(result);
        }
        if (action === "ew_confirm") {
          const { symbol, interval } = body;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          const tdSym = TD_SYMBOL_MAP[symbol] || symbol, result = { symbol, interval };
          await Promise.all([
            tdFetch("quote", { symbol: tdSym }, apiKey).then(d => { result.quote = { price: parseFloat(d.close || d.price || 0), open: parseFloat(d.open || 0), high: parseFloat(d.high || 0), low: parseFloat(d.low || 0), change: parseFloat(d.change || 0), change_pct: parseFloat(d.percent_change || 0), timestamp: d.datetime || null }; }).catch(() => { result.quote = null; }),
            tdFetch("time_series", { symbol: tdSym, interval: interval || "4h", outputsize: 50, format: "JSON" }, apiKey).then(d => { result.candles = (d.values || []).map(v => ({ datetime: v.datetime, open: parseFloat(v.open), high: parseFloat(v.high), low: parseFloat(v.low), close: parseFloat(v.close), volume: parseInt(v.volume || 0, 10) })); }).catch(() => { result.candles = []; }),
            tdFetch("rsi", { symbol: tdSym, interval: interval || "4h", time_period: 14, outputsize: 1 }, apiKey).then(d => { result.rsi = d.values?.[0]?.rsi ? parseFloat(d.values[0].rsi) : null; }).catch(() => { result.rsi = null; }),
            tdFetch("macd", { symbol: tdSym, interval: interval || "4h", fast_period: 12, slow_period: 26, signal_period: 9, outputsize: 1 }, apiKey).then(d => { const v = d.values?.[0]; result.macd = v ? { macd: parseFloat(v.macd || 0), signal: parseFloat(v.macd_signal || 0), histogram: parseFloat(v.macd_hist || 0) } : null; }).catch(() => { result.macd = null; }),
            tdFetch("ema", { symbol: tdSym, interval: interval || "4h", time_period: 20, outputsize: 1 }, apiKey).then(d => { result.ema_20 = d.values?.[0]?.ema ? parseFloat(d.values[0].ema) : null; }).catch(() => { result.ema_20 = null; }),
            tdFetch("ema", { symbol: tdSym, interval: interval || "4h", time_period: 50, outputsize: 1 }, apiKey).then(d => { result.ema_50 = d.values?.[0]?.ema ? parseFloat(d.values[0].ema) : null; }).catch(() => { result.ema_50 = null; }),
            tdFetch("ema", { symbol: tdSym, interval: interval || "4h", time_period: 200, outputsize: 1 }, apiKey).then(d => { result.ema_200 = d.values?.[0]?.ema ? parseFloat(d.values[0].ema) : null; }).catch(() => { result.ema_200 = null; }),
          ]);
          return json(result);
        }
        return json({ error: `Azione Twelve Data sconosciuta: "${action}"` }, 400);
      }

      if (body.type === "finnhub") {
        const apiKey = env.FINNHUB_API_KEY;
        if (!apiKey) return json({ error: "FINNHUB_API_KEY mancante" }, 500);
        const action = body.action;
        if (action === "market_news") {
          const category = body.category || "general";
          const cacheKey = 'finnhub_news_' + category;
          const cached = getCached(cacheKey, 5 * 60 * 1000);
          if (cached) return json({ category, news: cached, cached: true });
          try {
            const articles = await fhMarketNews(category, apiKey);
            const news = (Array.isArray(articles) ? articles : []).slice(0, 15).map(a => ({ datetime: a.datetime, headline: a.headline, source: a.source, summary: a.summary, url: a.url, image: a.image || null }));
            setCache(cacheKey, news);
            return json({ category, news });
          } catch(e) { return json({ error: e.message }, 500); }
        }
        if (action === "quote") {
          const symbols = body.symbols || [];
          if (symbols.length === 0) return json({ error: "Nessun simbolo fornito" }, 400);
          const quotes = {};
          const yahooSyms = symbols.filter(s => YAHOO_SYMBOLS.has(s));
          const finnhubSyms = symbols.filter(s => !YAHOO_SYMBOLS.has(s));
          await Promise.all(yahooSyms.map(async sym => { try { const d = await yahooQuote(sym); quotes[sym] = { price: d.price, open: d.open, high: d.high, low: d.low, prev_close: d.prev_close, change: d.change, change_pct: d.change_pct, timestamp: d.timestamp, source: d.source }; } catch(e) { quotes[sym] = { error: e.message }; } }));
          await Promise.all(finnhubSyms.map(async sym => { const fhSym = FH_SYMBOL_MAP[sym]; if (!fhSym) { quotes[sym] = { error: `Simbolo non mappato: ${sym}` }; return; } try { const d = await fhQuote(fhSym, apiKey); quotes[sym] = { price: parseFloat(d.c.toFixed(6)), open: parseFloat(d.o || 0), high: parseFloat(d.h || 0), low: parseFloat(d.l || 0), prev_close: parseFloat(d.pc || 0), change: parseFloat((d.c - d.pc).toFixed(6)), change_pct: d.pc ? parseFloat(((d.c - d.pc) / d.pc * 100).toFixed(3)) : 0, timestamp: d.t || null, source: fhSym }; } catch(e) { quotes[sym] = { error: e.message }; } }));
          return json({ quotes });
        }
        if (action === "sentiment") {
          const symbol = body.symbol;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          try { const d = await fhNewsSentiment(symbol, apiKey); return json({ symbol, buzz: d.buzz || null, sentiment: d.sentiment || null, sector: d.sector || null }); } catch(e) { return json({ error: e.message }, 500); }
        }
        if (action === "news_sentiment_batch") {
          const symbols = body.symbols || [], category = body.category || "general";
          const [newsResult, ...sentimentResults] = await Promise.all([
            fhMarketNews(category, apiKey).then(articles => (Array.isArray(articles) ? articles : []).slice(0, 10).map(a => ({ datetime: a.datetime, headline: a.headline, source: a.source, summary: a.summary, url: a.url }))).catch(() => []),
            ...symbols.map(sym => fhNewsSentiment(sym, apiKey).then(d => ({ sym, data: { buzz: d.buzz, sentiment: d.sentiment, sector: d.sector } })).catch(() => ({ sym, data: null }))),
          ]);
          const sentiments = {};
          sentimentResults.forEach(r => { sentiments[r.sym] = r.data; });
          return json({ sentiments, news: newsResult });
        }
        if (action === "candles") {
          const { symbol, assetType, resolution, from, to } = body;
          if (!symbol) return json({ error: "symbol mancante" }, 400);
          const endpoint = assetType === "crypto" ? "crypto/candle" : assetType === "stock" ? "stock/candle" : "forex/candle";
          try {
            const res = await fetch(`https://finnhub.io/api/v1/${endpoint}?symbol=${encodeURIComponent(symbol)}&resolution=${resolution || "D"}&from=${from}&to=${to}&token=${apiKey}`, { headers: { "User-Agent": "XenosFinance/1.0" } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const d = await res.json();
            if (d.s === "no_data" || !d.t || d.t.length === 0) return json({ candles: [] });
            return json({ candles: d.t.map((t, i) => ({ datetime: new Date(t * 1000).toISOString(), open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i], volume: d.v[i] || 0 })) });
          } catch(e) { return json({ error: e.message }, 500); }
        }
        if (action === "economic_calendar") {
          const { from, to } = body;
          if (!from || !to) return json({ economicCalendar: [], error: "from/to mancanti" }, 400);
          try { return json({ economicCalendar: await fhEconomicCalendar(from, to, apiKey), source: "finnhub" }); } catch(e) { return json({ economicCalendar: [], error: e.message }); }
        }
        return json({ error: `Azione Finnhub sconosciuta: "${action}"` }, 400);
      }

      if (body.type === "yahoocandles") {
        const { symbol, interval, range } = body;
        if (!symbol) return json({ error: "symbol mancante", candles: [] }, 400);
        const YC_MAP = {"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","USDCHF":"USDCHF=X","AUDUSD":"AUDUSD=X","NZDUSD":"NZDUSD=X","USDCAD":"USDCAD=X","EURGBP":"EURGBP=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X","CADJPY":"CADJPY=X","AUDNZD":"AUDNZD=X","EURCHF":"EURCHF=X","GBPCHF":"GBPCHF=X","AUDCAD":"AUDCAD=X","AUDJPY":"AUDJPY=X","CADCHF":"CADCHF=X","CHFJPY":"CHFJPY=X","EURAUD":"EURAUD=X","EURCAD":"EURCAD=X","GBPAUD":"GBPAUD=X","GBPCAD":"GBPCAD=X","NZDJPY":"NZDJPY=X","XAUUSD":"GC=F","XAGUSD":"SI=F","USOIL":"CL=F","UKOIL":"BZ=F","NGAS":"NG=F","COPPER":"HG=F","BTCUSD":"BTC-USD","ETHUSD":"ETH-USD","SOLUSD":"SOL-USD","XRPUSD":"XRP-USD","DOGEUSD":"DOGE-USD","US500":"^GSPC","US30":"^DJI","NAS100":"^IXIC","^GSPC":"^GSPC","^DJI":"^DJI","^IXIC":"^IXIC","^GDAXI":"^GDAXI","^FTSE":"^FTSE"};
        const ySym = YC_MAP[symbol] || symbol;
        try {
          const res = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ySym)}?interval=${interval||'1d'}&range=${range||'1y'}`, {
            headers: { "User-Agent": "Mozilla/5.0 (compatible; XenosFinance/1.0)", "Accept": "application/json" }
          });
          if (!res.ok) throw new Error(`Yahoo HTTP ${res.status}`);
          const data = await res.json();
          const result = data?.chart?.result?.[0];
          const ts = result?.timestamp || [];
          const q = result?.indicators?.quote?.[0] || {};
          if (ts.length < 5) return json({ candles: [], error: `insufficient data for ${ySym} (${ts.length} bars)` });
          const candles = ts.map((t, i) => ({ datetime: new Date(t * 1000).toISOString(), open: q.open?.[i] || q.close?.[i] || 0, high: q.high?.[i] || q.close?.[i] || 0, low: q.low?.[i] || q.close?.[i] || 0, close: q.close?.[i] || 0, volume: q.volume?.[i] || 0 })).filter(r => r.close > 0);
          return json({ symbol: ySym, interval, range, candles });
        } catch(e) { return json({ error: e.message, candles: [] }, 500); }
      }

      if (body.type === "investing") {
        const { from, to } = body;
        if (!from || !to) return json({ events: [], error: "from/to mancanti" }, 400);
        try { return json({ events: await fetchInvestingCalendar(from, to), source: "investing.com" }); } catch(e) { return json({ events: [], error: e.message }); }
      }

      if (body.type === "rapidapi_calendar") {
        const rapidApiKey = env.RAPIDAPI_KEY;
        if (!rapidApiKey) return json({ events: [], error: "RAPIDAPI_KEY not configured in Worker env" }, 500);
        const { countries } = body;
        const countryParam = (countries || ['US','EU','GB','DE','JP','CN','CA','AU']).join('%2C');
        try {
          const res = await fetch(`https://economic-trading-forex-events-calendar.p.rapidapi.com/fxstreet?countries=${countryParam}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json', 'x-rapidapi-host': 'economic-trading-forex-events-calendar.p.rapidapi.com', 'x-rapidapi-key': rapidApiKey }
          });
          if (!res.ok) throw new Error(`RapidAPI HTTP ${res.status}`);
          const data = await res.json();
          const raw = Array.isArray(data) ? data : (data.events || data.data || []);
          return json({ events: raw.map((e, i) => ({ id: e.id || 'ra_' + i, time: e.date || e.dateUtc || e.time || e.datetime || '', country: (e.country || e.currency || '').toUpperCase(), event: e.name || e.title || e.event || '', impact: (e.importance || e.impact || '').toLowerCase() === 'high' ? 'high' : (e.importance || e.impact || '').toLowerCase() === 'medium' ? 'medium' : 'low', actual: (e.actual != null && e.actual !== '') ? String(e.actual) : null, estimate: (e.forecast != null && e.forecast !== '') ? String(e.forecast) : null, prev: (e.previous != null && e.previous !== '') ? String(e.previous) : null })).filter(e => e.event), source: 'rapidapi_fxstreet' });
        } catch(e) { return json({ events: [], error: e.message }); }
      }

      // ── STRIPE: CREATE CHECKOUT SESSION ────────────────────────
      if (body.type === "stripe-create-checkout") {
        const priceId = STRIPE_PRICE_IDS[body.plan];
        if (!priceId) return json({ error: 'Piano non valido (usa "monthly" o "yearly")' }, 400);
        try {
          const session = await stripeApi(env, "checkout/sessions", {
            mode: "subscription",
            line_items: [{ price: priceId, quantity: 1 }],
            customer_email: body.email || undefined,
            success_url: "https://xenosfinance.com/premium-support?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url: "https://xenosfinance.com/premium-support?canceled=true",
            allow_promotion_codes: true,
            subscription_data: { metadata: { source: "xenosfinance_site", plan: body.plan } },
          });
          return json({ url: session.url });
        } catch (e) { return json({ error: e.message }, 500); }
      }

      // ── STRIPE: CUSTOMER PORTAL SESSION ────────────────────────
      if (body.type === "stripe-create-portal") {
        if (!body.customer) return json({ error: 'Manca "customer"' }, 400);
        try {
          const portal = await stripeApi(env, "billing_portal/sessions", {
            customer: body.customer,
            return_url: "https://xenosfinance.com/premium-support",
          });
          return json({ url: portal.url });
        } catch (e) { return json({ error: e.message }, 500); }
      }

      // ── ANTHROPIC ─────────────────────────────────────────────
      const anthropicKey = env.ANTHROPIC_API_KEY;
      if (!anthropicKey) return json({ error: "ANTHROPIC_API_KEY mancante" }, 500);
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": anthropicKey, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({ model: body.model || "claude-sonnet-4-6", max_tokens: body.max_tokens || 2000, messages: body.messages }),
      });
      return json(await r.json(), r.status);

    } catch(err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { ...SECURITY_HEADERS, "Content-Type": "application/json", "Access-Control-Allow-Origin": ALLOWED_ORIGINS[0] } });
    }
  }
};
