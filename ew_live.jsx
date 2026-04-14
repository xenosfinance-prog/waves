import { useState, useEffect, useRef } from "react";

// ─── CONFIG ────────────────────────────────────────────────────────────────
const WORKER = "https://xenos-ai-proxy.xenosfinance.workers.dev";

const INSTRUMENTS = {
  EURUSD: { dp:5, name:'EUR/USD',  assetType:'forex',     fhSym:'OANDA:EUR_USD',    yahooRange:'1y', yahooCf:'1d' },
  GBPUSD: { dp:5, name:'GBP/USD',  assetType:'forex',     fhSym:'OANDA:GBP_USD',    yahooRange:'1y', yahooCf:'1d' },
  XAUUSD: { dp:2, name:'XAU/USD',  assetType:'forex',     fhSym:'OANDA:XAU_USD',    yahooRange:'1y', yahooCf:'1d' },
  USOIL:  { dp:2, name:'WTI Oil',  assetType:'commodity', fhSym:'',                  yahooRange:'1y', yahooCf:'1d' },
  BTCUSD: { dp:0, name:'BTC/USD',  assetType:'crypto',    fhSym:'BINANCE:BTCUSDT',  yahooRange:'1y', yahooCf:'1d' },
};

// TF → Yahoo interval + range
const TF_YAHOO = {
  '1H':  { interval:'1h',  range:'60d'  },
  '4H':  { interval:'1h',  range:'60d'  }, // 4h not available free; use 1h and downsample
  'D1':  { interval:'1d',  range:'1y'   },
  'W1':  { interval:'1wk', range:'5y'   },
};

// TF → Finnhub resolution
const TF_FH = { '1H':'60', '4H':'240', 'D1':'D', 'W1':'W' };

// ─── PIVOT DETECTION ────────────────────────────────────────────────────────
function findPivots(candles, win=4) {
  const raw = [];
  for (let i=win; i<candles.length-win; i++) {
    let isH=true, isL=true;
    for (let j=1;j<=win;j++) {
      if (candles[i].high<=candles[i-j].high||candles[i].high<=candles[i+j].high) isH=false;
      if (candles[i].low >=candles[i-j].low ||candles[i].low >=candles[i+j].low)  isL=false;
    }
    if (isH) raw.push({i, price:candles[i].high, type:'high'});
    if (isL) raw.push({i, price:candles[i].low,  type:'low'});
  }
  const alt = [];
  for (const p of raw.sort((a,b)=>a.i-b.i)) {
    if (!alt.length || alt[alt.length-1].type!==p.type) alt.push({...p});
    else if (p.type==='high'&&p.price>alt[alt.length-1].price) alt[alt.length-1]={...p};
    else if (p.type==='low' &&p.price<alt[alt.length-1].price) alt[alt.length-1]={...p};
  }
  return alt.slice(-7);
}

// Downsample 1h candles to 4h
function resampleTo4H(candles) {
  const out = [];
  for (let i=0; i+3<candles.length; i+=4) {
    const slice = candles.slice(i, i+4);
    out.push({
      date: slice[0].date,
      open:  slice[0].open,
      high:  Math.max(...slice.map(c=>c.high)),
      low:   Math.min(...slice.map(c=>c.low)),
      close: slice[slice.length-1].close,
    });
  }
  return out;
}

// Mock fallback candles
function generateMockCandles(base, n=80) {
  const candles = [];
  let price = base * (0.97 + Math.random()*0.06);
  const dt = new Date(); dt.setDate(dt.getDate() - n);
  for (let i=0; i<n; i++) {
    const chg = (Math.random()-0.48) * base * 0.007;
    const open = price, close = price + chg;
    const high = Math.max(open,close) + Math.random()*base*0.003;
    const low  = Math.min(open,close) - Math.random()*base*0.003;
    const d = new Date(dt); d.setDate(d.getDate()+i);
    candles.push({ date: d.toISOString().slice(0,10), open, high, low, close });
    price = close;
  }
  return candles;
}

// ─── DATA FETCHING ──────────────────────────────────────────────────────────
async function fetchCandlesYahoo(ticker, tf) {
  const cfg = TF_YAHOO[tf] || TF_YAHOO['D1'];
  let { interval, range } = cfg;
  const res = await fetch(WORKER, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ type:'yahoocandles', symbol:ticker, interval, range })
  });
  if (!res.ok) throw new Error(`Yahoo worker ${res.status}`);
  const data = await res.json();
  if (!data.candles || data.candles.length < 10) throw new Error('Yahoo: insufficient candles');
  let candles = data.candles.map(c => ({
    date:  c.datetime ? c.datetime.slice(0,10) : '',
    open:  c.open, high: c.high, low: c.low, close: c.close
  }));
  if (tf === '4H') candles = resampleTo4H(candles);
  return candles.slice(-80);
}

async function fetchCandlesFinnhub(ticker, tf) {
  const cfg = INSTRUMENTS[ticker];
  if (!cfg.fhSym) throw new Error('No Finnhub symbol');
  const resolution = TF_FH[tf] || 'D';
  const to   = Math.floor(Date.now()/1000);
  const from = to - (tf==='W1' ? 86400*365*3 : tf==='D1' ? 86400*300 : tf==='4H' ? 86400*120 : 86400*60);
  const res = await fetch(WORKER, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ type:'finnhub', action:'candles', symbol:cfg.fhSym, assetType:cfg.assetType, resolution, from, to })
  });
  if (!res.ok) throw new Error(`Finnhub worker ${res.status}`);
  const data = await res.json();
  if (!data.candles || data.candles.length < 10) throw new Error('Finnhub: insufficient candles');
  return data.candles.map(c => ({
    date:  c.datetime.slice(0,10),
    open:  c.open, high: c.high, low: c.low, close: c.close
  })).slice(-80);
}

async function fetchLivePrice(ticker) {
  const res = await fetch(WORKER, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ type:'prices', pairs:[ticker] })
  });
  if (!res.ok) throw new Error(`Price worker ${res.status}`);
  const data = await res.json();
  return data.prices?.[ticker]?.price || null;
}

async function fetchAIAnalysis(cfg, tf, pattern, isBull, wavePts, sl, tp1, tp2, livePrice) {
  const dp = cfg.dp;
  const waveList = wavePts.map(p=>`Wave(${p.label}) @ ${p.price.toFixed(dp)}`).join(', ');
  const prompt = `You are a senior Elliott Wave analyst. Analyze this chart setup and write a concise professional narrative (3-4 sentences, no markdown, no bullet points).

Instrument: ${cfg.name}
Timeframe: ${tf}
Pattern: ${pattern === 'corrective' ? 'A-B-C Corrective' : '1-2-3-4-5 Impulse'}
Bias: ${isBull ? 'Bullish' : 'Bearish'}
Active wave: (${wavePts[wavePts.length-1].label})
Wave pivots: ${waveList}
Live price: ${livePrice.toFixed(dp)}
Stop Loss: ${sl.toFixed(dp)}
TP1: ${tp1.toFixed(dp)}
TP2: ${tp2.toFixed(dp)}

Write a 3-4 sentence Elliott Wave analysis covering: current wave position, key invalidation level, and primary price targets. Be specific with numbers. No markdown.`;

  const res = await fetch(WORKER, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      model:'claude-sonnet-4-20250514',
      max_tokens:300,
      messages:[{ role:'user', content:prompt }]
    })
  });
  if (!res.ok) throw new Error(`AI worker ${res.status}`);
  const data = await res.json();
  return data?.content?.[0]?.text || null;
}

// ─── CHART DRAW ─────────────────────────────────────────────────────────────
function drawChart(canvas, { candles, wavePts, cfg, isBull, sl, tp1, tp2, livePrice, curWave }, tf) {
  const W = canvas.offsetWidth || 800;
  const H = 420;
  canvas.width = W*2; canvas.height = H*2;
  canvas.style.width = W+'px'; canvas.style.height = H+'px';
  const ctx = canvas.getContext('2d'); ctx.scale(2,2);
  const ML=62, MR=105, MT=32, MB=44, CW=W-ML-MR, CH=H-MT-MB;

  const allP = [];
  candles.forEach(c=>{allP.push(c.high,c.low);});
  wavePts.forEach(p=>allP.push(p.price));
  [sl,tp1,tp2,livePrice].forEach(v=>{if(v)allP.push(v);});
  const minP=Math.min(...allP)*0.9992, maxP=Math.max(...allP)*1.0008;
  const pR=maxP-minP||1;
  const toY=p=>MT+CH-((p-minP)/pR)*CH;
  const barW=CW/candles.length;
  const toX=i=>ML+(i+0.5)*barW;

  ctx.fillStyle='#090f1a'; ctx.fillRect(0,0,W,H);

  // Grid
  for(let i=0;i<=7;i++){
    const y=MT+(i/7)*CH;
    ctx.strokeStyle='#1a2a40'; ctx.lineWidth=0.5; ctx.globalAlpha=0.5;
    ctx.beginPath(); ctx.moveTo(ML,y); ctx.lineTo(W-MR,y); ctx.stroke();
    const pr=maxP-(i/7)*pR;
    ctx.fillStyle='#4a6a8a'; ctx.font='8px monospace'; ctx.textAlign='right'; ctx.globalAlpha=0.9;
    ctx.fillText(pr.toFixed(pr>100?2:5), ML-3, y+3);
  }
  const step=Math.max(1,Math.floor(candles.length/8));
  for(let i=0;i<candles.length;i+=step){
    ctx.globalAlpha=0.2; ctx.strokeStyle='#1a2a40'; ctx.lineWidth=0.5;
    const x=toX(i); ctx.beginPath(); ctx.moveTo(x,MT); ctx.lineTo(x,MT+CH); ctx.stroke();
    ctx.fillStyle='#2a4060'; ctx.globalAlpha=0.7; ctx.font='8px monospace'; ctx.textAlign='center';
    ctx.fillText((candles[i].date||'').slice(5), x, H-MB+16);
  }
  ctx.globalAlpha=1;

  function drawHL(price, color, label) {
    if(!price||price<minP*0.97||price>maxP*1.03) return;
    const y=toY(price);
    ctx.strokeStyle=color; ctx.lineWidth=1; ctx.globalAlpha=0.55; ctx.setLineDash([5,4]);
    ctx.beginPath(); ctx.moveTo(ML,y); ctx.lineTo(W-MR,y); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha=0.9; ctx.fillStyle=color;
    ctx.font='bold 9px monospace'; ctx.textAlign='left';
    ctx.fillText(label+' '+price.toFixed(price>100?2:5), W-MR+3, y+3);
    ctx.globalAlpha=1;
  }
  drawHL(livePrice,'#00d4ff','NOW');
  drawHL(sl,'#ef4444','SL ');
  drawHL(tp1,'#10b981','TP1');
  drawHL(tp2,'#059669','TP2');

  // Candles
  const cW=Math.max(2,barW*0.72);
  candles.forEach((c,i)=>{
    const x=toX(i), isUp=c.close>=c.open;
    ctx.strokeStyle=isUp?'#10b981':'#ef4444'; ctx.lineWidth=0.8; ctx.globalAlpha=0.75;
    ctx.beginPath(); ctx.moveTo(x,toY(c.high)); ctx.lineTo(x,toY(c.low)); ctx.stroke();
    const yO=toY(c.open), yC=toY(c.close);
    ctx.fillStyle=isUp?'rgba(16,185,129,0.75)':'rgba(239,68,68,0.75)'; ctx.globalAlpha=0.88;
    ctx.fillRect(x-cW/2, Math.min(yO,yC), cW, Math.max(1,Math.abs(yC-yO)));
    ctx.globalAlpha=1;
  });

  const wCol  = isBull?'#3b82f6':'#f59e0b';
  const wCol2 = isBull?'#60a5fa':'#fcd34d';

  // Zigzag
  ctx.strokeStyle=wCol; ctx.lineWidth=2.5; ctx.globalAlpha=0.92;
  ctx.lineJoin='round'; ctx.lineCap='round';
  ctx.beginPath();
  wavePts.forEach((p,idx)=>{
    const x=toX(p.i), y=toY(p.price);
    idx===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  });
  ctx.stroke();
  ctx.globalAlpha=1; ctx.lineJoin='miter'; ctx.lineCap='butt';

  // Dots + labels
  wavePts.forEach(p=>{
    const x=toX(p.i), y=toY(p.price);
    const isCur=p.label===curWave;
    ctx.fillStyle='rgba(6,12,22,0.92)';
    ctx.beginPath(); ctx.arc(x,y,isCur?7:5.5,0,Math.PI*2); ctx.fill();
    ctx.fillStyle=wCol2;
    ctx.beginPath(); ctx.arc(x,y,isCur?5:3.5,0,Math.PI*2); ctx.fill();
    const isHigh=p.type==='high';
    const ly=Math.max(MT+12,Math.min(isHigh?y-16:y+16, MT+CH-12));
    ctx.font=`bold ${isCur?14:12}px Arial`; ctx.textAlign='center'; ctx.textBaseline='middle';
    ctx.lineWidth=3.5; ctx.lineJoin='round'; ctx.strokeStyle='rgba(6,12,22,0.96)';
    ctx.strokeText('('+p.label+')', x, ly);
    ctx.fillStyle=wCol2; ctx.fillText('('+p.label+')', x, ly);
    ctx.lineJoin='miter'; ctx.textBaseline='alphabetic';
  });

  // Header bar
  ctx.textAlign='left'; ctx.font='bold 11px monospace'; ctx.fillStyle='#3b82f6'; ctx.fillText('XENOS',ML,24);
  ctx.fillStyle='#c8d8ea'; ctx.fillText('FINANCE',ML+46,24);
  ctx.font='9px monospace'; ctx.fillStyle='#4a6a8a';
  ctx.fillText('· EW · '+cfg.name+' · '+tf, ML+100, 24);
  ctx.textAlign='center'; ctx.font='bold 10px monospace';
  ctx.fillStyle=isBull?'#34d399':'#f87171';
  ctx.fillText(isBull?'▲ TREND UP':'▼ TREND DOWN', W/2, 24);
  ctx.textAlign='right'; ctx.font='bold 10px monospace';
  ctx.fillStyle=isBull?'#00e676':'#ff3d5a';
  ctx.fillText(isBull?'▲ LONG':'▼ SHORT', W-MR, 24);
  ctx.textAlign='left'; ctx.font='9px monospace'; ctx.fillStyle='#3a5070';
  ctx.fillText('Wave ('+curWave+') active · '+(isBull?'Bullish':'Bearish')+' structure', ML, H-MB+28);
}

// ─── COMPONENT ───────────────────────────────────────────────────────────────
export default function App() {
  const canvasRef = useRef(null);
  const [ticker,  setTicker]  = useState('EURUSD');
  const [tf,      setTf]      = useState('4H');
  const [pattern, setPattern] = useState('impulse');
  const [loading, setLoading] = useState(false);
  const [status,  setStatus]  = useState('');
  const [result,  setResult]  = useState(null);
  const [aiText,  setAiText]  = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [dataSource, setDataSource] = useState('');

  async function generate() {
    setLoading(true);
    setAiText('');
    setStatus('Fetching live candles…');
    const cfg = INSTRUMENTS[ticker];

    try {
      let candles, source;

      // 1) Try Yahoo Finance via Worker
      try {
        candles = await fetchCandlesYahoo(ticker, tf);
        source = 'Yahoo Finance';
      } catch(e1) {
        setStatus('Yahoo failed, trying Finnhub…');
        try {
          candles = await fetchCandlesFinnhub(ticker, tf);
          source = 'Finnhub';
        } catch(e2) {
          setStatus('Live data unavailable — using demo data');
          const base = { EURUSD:1.085, GBPUSD:1.265, XAUUSD:2320, USOIL:83, BTCUSD:68000 }[ticker] || 1;
          candles = generateMockCandles(base, 80);
          source = 'Demo (offline)';
        }
      }

      setDataSource(source);
      setStatus('Detecting wave pivots…');

      // Pivot detection
      const pivots = findPivots(candles, 4);
      if (pivots.length < 3) throw new Error('Not enough pivots detected. Try a different timeframe.');

      // Determine bias from last two pivots
      const last = pivots[pivots.length-1];
      const prev = pivots[pivots.length-2];
      const isBull = last.type === 'high' ? last.price > prev.price : prev.price < last.price;

      // Build wave points — show only confirmed pivots + active wave tip
      // Impulse: up to 5 labeled points (1→5), last one is the active/forming wave
      // Corrective: up to 3 labeled points (A→C), last one is active
      let wavePts;
      if (pattern === 'corrective') {
        // Take last 2 or 3 alternating pivots → label A, B, C
        const abc = pivots.slice(-3);
        const labels = ['A','B','C'];
        wavePts = abc.map((p,i)=>({label:labels[i],...p}));
      } else {
        // Take last N pivots, max 5, label 1→N  (last = active wave)
        const impulseLabels = ['1','2','3','4','5'];
        const pts = pivots.slice(-5); // at most 5
        if (pts.length < 2) throw new Error('Need at least 2 pivots for impulse. Try D1 or W1.');
        wavePts = pts.map((p,i)=>({label:impulseLabels[i],...p}));
      }

      setStatus('Fetching live price…');
      let livePrice;
      try {
        livePrice = await fetchLivePrice(ticker);
      } catch(e) {}
      if (!livePrice) livePrice = candles[candles.length-1].close;

      // SL / TP from actual wave structure
      const prices = wavePts.map(p=>p.price);
      const pMin = Math.min(...prices), pMax = Math.max(...prices);
      const sl  = isBull ? +(pMin*0.997).toFixed(cfg.dp)  : +(pMax*1.003).toFixed(cfg.dp);
      const tp1 = isBull ? +(pMax*1.012).toFixed(cfg.dp)  : +(pMin*0.988).toFixed(cfg.dp);
      const tp2 = isBull ? +(pMax*1.025).toFixed(cfg.dp)  : +(pMin*0.975).toFixed(cfg.dp);
      const curWave = wavePts[wavePts.length-1].label;

      setResult({ candles, wavePts, cfg, isBull, sl, tp1, tp2, livePrice, curWave });
      setStatus('');

      // AI analysis async after chart renders
      setAiLoading(true);
      fetchAIAnalysis(cfg, tf, pattern, isBull, wavePts, sl, tp1, tp2, livePrice)
        .then(text => { if(text) setAiText(text); })
        .catch(() => {})
        .finally(() => setAiLoading(false));

    } catch(err) {
      setStatus('⚠ ' + err.message);
      setLoading(false);
      return;
    }
    setLoading(false);
  }

  // Auto-generate on mount and when ticker/tf/pattern change
  useEffect(() => { generate(); }, [ticker, tf, pattern]);

  useEffect(() => {
    if (!result || !canvasRef.current) return;
    drawChart(canvasRef.current, result, tf);
  }, [result, tf]);

  const r = result;
  const dp = r ? r.cfg.dp : 5;

  const S = {
    root:    { background:'#0f1724', minHeight:'100vh', fontFamily:"'IBM Plex Mono',monospace", color:'#c8d8ea', padding:0 },
    header:  { borderBottom:'1px solid #1e3050', padding:'12px 24px', display:'flex', alignItems:'center', gap:12 },
    logo:    { width:34, height:34, background:'#1d4ed8', borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center', color:'#fff', fontWeight:900, fontSize:16, fontFamily:'serif' },
    wrap:    { maxWidth:1060, margin:'0 auto', padding:'24px 20px' },
    ctrl:    { display:'flex', gap:10, flexWrap:'wrap', marginBottom:20, alignItems:'flex-end' },
    label:   { fontSize:9, letterSpacing:'.14em', color:'#5a7a9a', textTransform:'uppercase' },
    select:  { background:'#131f2e', border:'1px solid #1e3050', color:'#c8d8ea', fontFamily:'inherit', fontSize:12, padding:'8px 12px', outline:'none', cursor:'pointer' },
    btn:     (disabled) => ({ background:disabled?'#1a2535':'#1d4ed8', border:'none', color:'#fff', fontFamily:'inherit', fontSize:11, letterSpacing:'.1em', textTransform:'uppercase', padding:'8px 22px', cursor:disabled?'not-allowed':'pointer', alignSelf:'flex-end' }),
    chartBox:{ background:'#131f2e', border:'1px solid #1e3050', marginBottom:12 },
    chartHdr:{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'10px 14px', borderBottom:'1px solid #1e3050', fontSize:10 },
    badge:   (bull) => ({ padding:'3px 10px', fontSize:9, letterSpacing:'.1em', background:bull?'rgba(16,185,129,.15)':'rgba(239,68,68,.15)', color:bull?'#10b981':'#ef4444', border:`1px solid ${bull?'rgba(16,185,129,.3)':'rgba(239,68,68,.3)'}` }),
    badgeN:  { padding:'3px 10px', fontSize:9, border:'1px solid #1e3050', color:'#5a7a9a' },
    metrics: { display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:8, marginBottom:12 },
    metricC: { background:'#131f2e', border:'1px solid #1e3050', padding:'12px 14px' },
    aiBox:   { background:'#131f2e', border:'1px solid #1e3050', padding:'18px 20px', fontSize:12, lineHeight:1.8, color:'#8aaccc' },
    aiHdr:   { fontSize:9, letterSpacing:'.14em', color:'#3b82f6', textTransform:'uppercase', marginBottom:10 },
    srcBadge:{ fontSize:9, color:'#2a5080', letterSpacing:'.1em', marginLeft:8 },
  };

  return (
    <div style={S.root}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.logo}>𝕏</div>
        <div>
          <div style={{fontSize:13,fontWeight:500}}>XenosFinance</div>
          <div style={{fontSize:9,color:'#5a7a9a',letterSpacing:'.14em',textTransform:'uppercase'}}>Elliott Wave · Live Market Analysis</div>
        </div>
        {dataSource && <span style={S.srcBadge}>● {dataSource}</span>}
      </div>

      <div style={S.wrap}>
        {/* Controls */}
        <div style={S.ctrl}>
          {[
            {id:'ticker', label:'Instrument', opts:[['EURUSD','EUR/USD'],['GBPUSD','GBP/USD'],['XAUUSD','XAU/USD'],['USOIL','WTI Oil'],['BTCUSD','BTC/USD']], val:ticker, set:setTicker},
            {id:'tf',     label:'Timeframe',  opts:[['1H','H1'],['4H','H4'],['D1','D1'],['W1','W1']], val:tf, set:setTf},
            {id:'pat',    label:'Pattern',    opts:[['impulse','Impulse 1-2-3-4-5'],['corrective','Corrective A-B-C']], val:pattern, set:setPattern},
          ].map(ctrl => (
            <div key={ctrl.id} style={{display:'flex',flexDirection:'column',gap:4}}>
              <label style={S.label}>{ctrl.label}</label>
              <select value={ctrl.val} onChange={e=>{ctrl.set(e.target.value);}} style={S.select}>
                {ctrl.opts.map(([v,l])=><option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          ))}
          <button onClick={generate} disabled={loading} style={S.btn(loading)}>
            {loading ? '⟳ Loading…' : '⚡ Refresh'}
          </button>
        </div>

        {/* Status bar */}
        {status && (
          <div style={{fontSize:10,color:'#3b6090',marginBottom:10,letterSpacing:'.08em'}}>
            {status}
          </div>
        )}

        {/* Chart */}
        <div style={S.chartBox}>
          <div style={S.chartHdr}>
            <span style={{color:'#c8d8ea',fontSize:11}}>
              {r ? `${r.cfg.name} · ${tf} · Elliott Wave` : '—'}
            </span>
            <div style={{display:'flex',gap:8,alignItems:'center'}}>
              {r && <span style={S.badge(r.isBull)}>{r.isBull?'▲ LONG':'▼ SHORT'}</span>}
              {r && <span style={S.badgeN}>Wave ({r.curWave}) · {tf}</span>}
            </div>
          </div>
          <canvas ref={canvasRef} style={{display:'block',width:'100%',background:'#090f1a'}} />
          {loading && !r && (
            <div style={{padding:'60px 0',textAlign:'center',color:'#2a4060',fontSize:11,letterSpacing:'.1em'}}>
              LOADING MARKET DATA…
            </div>
          )}
        </div>

        {/* Metrics */}
        {r && (
          <div style={S.metrics}>
            {[
              {label:'Live Price',  val:r.livePrice.toFixed(dp), color:'#3b82f6'},
              {label:'Wave Active', val:`(${r.curWave})`,         color:'#60a5fa'},
              {label:'Stop Loss',   val:r.sl.toFixed(dp),         color:'#ef4444'},
              {label:'Target 1',    val:r.tp1.toFixed(dp),        color:'#10b981'},
              {label:'Target 2',    val:r.tp2.toFixed(dp),        color:'#059669'},
            ].map(m=>(
              <div key={m.label} style={S.metricC}>
                <div style={{fontSize:9,letterSpacing:'.12em',color:'#5a7a9a',textTransform:'uppercase',marginBottom:6}}>{m.label}</div>
                <div style={{fontSize:15,fontWeight:500,color:m.color}}>{m.val}</div>
              </div>
            ))}
          </div>
        )}

        {/* AI Analysis */}
        {r && (
          <div style={S.aiBox}>
            <div style={S.aiHdr}>
              ⬡ AI Analysis
              {aiLoading && <span style={{color:'#2a5080',marginLeft:8,fontWeight:400}}>generating…</span>}
            </div>
            {aiText
              ? aiText
              : aiLoading
                ? <span style={{color:'#2a4060'}}>Claude is analyzing wave structure…</span>
                : (r.isBull
                    ? `${r.cfg.name} is developing a bullish impulse on the ${tf} timeframe. Wave (${r.curWave}) is currently active with price structure intact. Invalidation at ${r.sl.toFixed(dp)} — a break below negates the count. Primary target ${r.tp1.toFixed(dp)}, extended upside toward ${r.tp2.toFixed(dp)}.`
                    : `${r.cfg.name} shows a bearish impulse on ${tf}. Wave (${r.curWave}) is the active leg with downside momentum building. Invalidation above ${r.sl.toFixed(dp)} signals a failed count. Watch support near ${r.tp1.toFixed(dp)}, deeper extension to ${r.tp2.toFixed(dp)}.`)
            }
          </div>
        )}
      </div>
    </div>
  );
}
