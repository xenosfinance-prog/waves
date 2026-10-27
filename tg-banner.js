// ══════════════════════════════════════════════════════════════════════════
// 📲 Banner canale Telegram (2026-10-27) — Market Brief, pagine Analisi, Elliott Wave.
// Inglese di base, italiano se la lingua scelta sul sito (localStorage 'xenos_lang')
// è IT. Posizione: sopra la nota legale delle pagine Analisi (.disc), sotto il testo
// del Market Brief (section.ai-section), sopra il piè di pagina di Elliott Wave.
// ══════════════════════════════════════════════════════════════════════════
(function () {
  var URL = 'https://t.me/xenoswavefinance';
  var TXT = {
    en: { t1: 'XenosWave Finance on Telegram',
          t2: 'Elliott Wave setups, MKO signals and the Market Brief in real time — before they reach the site.',
          bt: 'Join the channel →' },
    it: { t1: 'XenosWave Finance su Telegram',
          t2: 'Setup Elliott Wave, segnali MKO e Market Brief in tempo reale — prima che arrivino sul sito.',
          bt: 'Unisciti al canale →' }
  };
  var CSS =
    '.xtg{margin:28px 0;border:1px solid #243a5e;border-left:3px solid #229ED9;' +
    'background:linear-gradient(90deg,rgba(34,158,217,.10),rgba(19,31,46,.6));border-radius:6px;' +
    'padding:16px 18px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;box-sizing:border-box}' +
    '.xtg .xtg-ic{width:40px;height:40px;border-radius:50%;background:#229ED9;color:#fff;display:flex;' +
    'align-items:center;justify-content:center;flex:none}' +
    '.xtg .xtg-tx{flex:1;min-width:220px}' +
    '.xtg .xtg-t1{font-family:"IBM Plex Mono",monospace;font-size:13px;letter-spacing:.06em;' +
    'text-transform:uppercase;color:#e2eaf4;font-weight:600}' +
    '.xtg .xtg-t2{font-family:"PT Serif",Georgia,serif;font-size:15px;color:#b8cce0;margin-top:4px;line-height:1.45}' +
    '.xtg .xtg-bt{font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;color:#fff !important;' +
    'background:#229ED9;padding:10px 16px;border-radius:4px;text-decoration:none !important;white-space:nowrap}' +
    '.xtg .xtg-bt:hover{background:#1c8cc2}' +
    '@media(max-width:560px){.xtg .xtg-bt{width:100%;text-align:center;box-sizing:border-box}}';
  var PLANE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true">' +
    '<path d="M9.8 15.6 9.6 19c.4 0 .6-.2.8-.4l1.9-1.8 4 2.9c.7.4 1.3.2 1.5-.7l2.7-12.6c.3-1.1-.4-1.6-1.1-1.3' +
    'L3.6 10.9c-1.1.4-1.1 1-.2 1.3l4.1 1.3 9.5-6c.4-.3.9-.1.6.2"/></svg>';

  function lang() {
    try { return localStorage.getItem('xenos_lang') === 'it' ? 'it' : 'en'; } catch (e) { return 'en'; }
  }
  function build() {
    var t = TXT[lang()];
    var d = document.createElement('div');
    d.className = 'xtg';
    d.id = 'xf-tg-banner';
    d.innerHTML = '<div class="xtg-ic">' + PLANE + '</div><div class="xtg-tx"><div class="xtg-t1"></div>' +
      '<div class="xtg-t2"></div></div><a class="xtg-bt" target="_blank" rel="noopener"></a>';
    d.querySelector('.xtg-t1').textContent = t.t1;
    d.querySelector('.xtg-t2').textContent = t.t2;
    var a = d.querySelector('.xtg-bt');
    a.href = URL;
    a.textContent = t.bt;
    return d;
  }
  function place() {
    if (document.getElementById('xf-tg-banner')) return;
    var s = document.createElement('style');
    s.textContent = CSS;
    document.head.appendChild(s);
    var el;
    if ((el = document.querySelector('main .disc'))) { el.parentNode.insertBefore(build(), el); return; }
    if ((el = document.querySelector('section.ai-section'))) { el.parentNode.insertBefore(build(), el.nextSibling); return; }
    if ((el = document.querySelector('.page-footer'))) {
      // pagine a tutta larghezza (Elliott Wave): banner centrato con margini laterali
      var d = build();
      d.style.cssText = 'max-width:1200px;width:calc(100% - 32px);margin:28px auto;';
      el.parentNode.insertBefore(d, el);
      return;
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', place);
  else place();
})();
