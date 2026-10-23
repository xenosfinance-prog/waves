// Profilo CPU della homepage (mobile, CPU 4x più lenta) — funzioni più costose e task lunghi.
const puppeteer = require('puppeteer');
const fs = require('fs');
(async () => {
  const url = process.argv[2] || 'https://xenosfinance.com/';
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 412, height: 823, isMobile: true, deviceScaleFactor: 2 });
  const cdp = await page.target().createCDPSession();
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await page.tracing.start({ path: 'trace.json', categories: ['devtools.timeline', 'disabled-by-default-devtools.timeline', 'disabled-by-default-v8.cpu_profiler', 'v8.execute'] });
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await new Promise(r => setTimeout(r, 10000));
  await page.tracing.stop();
  await browser.close();
  const ev = JSON.parse(fs.readFileSync('trace.json')).traceEvents || JSON.parse(fs.readFileSync('trace.json'));
  const nodes = new Map(), self = new Map(); let lastTs = null;
  for (const e of ev) {
    if (e.name !== 'ProfileChunk') continue;
    const c = e.args.data.cpuProfile || {}; const d = e.args.data.timeDeltas || [];
    for (const n of c.nodes || []) nodes.set(n.id, n.callFrame);
    (c.samples || []).forEach((id, i) => { const cf = nodes.get(id); const dt = (d[i] || 0) / 1000; if (!cf) return;
      const k = `${cf.functionName || '(anon)'} ${(cf.url || '').split('/').pop()}:${(cf.lineNumber || 0) + 1}`; self.set(k, (self.get(k) || 0) + dt); });
  }
  const top = [...self].filter(([k]) => !k.startsWith('(idle)') && !k.startsWith('(program)')).sort((a, b) => b[1] - a[1]).slice(0, 40);
  const tasks = ev.filter(e => e.name === 'RunTask' && e.dur > 50000).map(e => ({ start: e.ts, ms: Math.round(e.dur / 1000) }));
  const t0 = Math.min(...ev.filter(e => e.ts).map(e => e.ts));
  // per ogni task lungo: cosa c'è dentro (eventi figli più grandi)
  const detail = tasks.sort((a, b) => b.ms - a.ms).slice(0, 8).map(t => {
    const inner = ev.filter(e => e.ts >= t.start && e.ts < t.start + t.ms * 1000 && e.dur > 20000 && e.name !== 'RunTask')
      .map(e => `${e.name} ${Math.round(e.dur / 1000)}ms ${(e.args && e.args.data && (e.args.data.url || e.args.data.functionName || e.args.data.type || '')) || ''} ${(e.args && e.args.data && e.args.data.lineNumber) || ''}`).slice(0, 12);
    return { at_ms: Math.round((t.start - t0) / 1000), ms: t.ms, inner };
  });
  fs.writeFileSync('profile.json', JSON.stringify({ top_self_ms: top.map(([k, v]) => [k, Math.round(v)]), long_tasks: detail }, null, 1));
})();
