// XenosFinance — lingua EN/IT per le pagine "editoriali" (2026-10-25)
// /analysis, /cot, /futures-flow, /trade-setups, /setups/*, /topics
// Queste pagine sono HTML statico o generato lato server, in inglese per la SEO.
// Lo script:
//   1. aggiunge le bandierine 🇬🇧 EN / 🇮🇹 IT nell'intestazione;
//   2. con la lingua IT (la stessa scelta sul resto del sito, localStorage
//      'xenos_lang') sostituisce ogni elemento [data-it] con il testo italiano
//      già presente nella pagina, e traduce menu e intestazione comuni.
// Nessuna richiesta esterna, nessuna attesa. Errori → la pagina resta com'è.
(function () {
  var lang = 'en';
  // 2026-11-14: anche ES, RU, UK — menu comune da dizionario, il resto della pagina
  // tradotto in automatico da /xf-translate.js (caricato qui se manca).
  var LANGS = [['en', '🇬🇧 EN'], ['it', '🇮🇹 IT'], ['es', '🇪🇸 ES'], ['ru', '🇷🇺 RU'], ['uk', '🇺🇦 UA']];
  try {
    var _u = new URLSearchParams(location.search).get('lang');
    if (_u && LANGS.some(function (p) { return p[0] === _u; })) localStorage.setItem('xenos_lang', _u);
    var _l = localStorage.getItem('xenos_lang') || 'en';
    lang = LANGS.some(function (p) { return p[0] === _l; }) ? _l : 'en';
  } catch (e) {}

  // Testi comuni dell'intestazione/menu (pagine non ancora rigenerate con data-it)
  var COMMON = {
    'Home': 'Home', 'Dashboard': 'Dashboard', 'Daily Analysis': 'Analisi giornaliera',
    'COT Positioning': 'Posizionamento COT', 'Futures Flow': 'Futures Flow', 'Calendar': 'Calendario',
    'Elliott Wave': 'Onde di Elliott', 'Trade Setups': 'Trade Setups', 'Premium': 'Premium',
    'Topics': 'Temi', 'Blog': 'Blog', 'Intelligence': 'Intelligence',
    'Market analysis & trading education': 'Analisi di mercato & formazione al trading'
  };

  var COMMON_X = {
    es: { 'Daily Analysis': 'Análisis diario', 'COT Positioning': 'Posicionamiento COT', 'Calendar': 'Calendario',
      'Elliott Wave': 'Ondas de Elliott', 'Topics': 'Temas', 'Intelligence': 'Inteligencia',
      'Market analysis & trading education': 'Análisis de mercado y formación en trading' },
    ru: { 'Home': 'Главная', 'Dashboard': 'Панель', 'Daily Analysis': 'Ежедневный анализ', 'COT Positioning': 'Позиции COT',
      'Calendar': 'Календарь', 'Elliott Wave': 'Волны Эллиотта', 'Topics': 'Темы', 'Blog': 'Блог', 'Intelligence': 'Аналитика',
      'Premium': 'Премиум', 'Market analysis & trading education': 'Анализ рынков и обучение трейдингу' },
    uk: { 'Home': 'Головна', 'Dashboard': 'Панель', 'Daily Analysis': 'Щоденний аналіз', 'COT Positioning': 'Позиції COT',
      'Calendar': 'Календар', 'Elliott Wave': 'Хвилі Еліотта', 'Topics': 'Теми', 'Blog': 'Блог', 'Intelligence': 'Аналітика',
      'Premium': 'Преміум', 'Market analysis & trading education': 'Аналіз ринків і навчання трейдингу' }
  };

  // ES/RU/UK: menu comune, poi traduzione automatica di tutto il resto
  function toExtra() {
    document.documentElement.lang = lang;
    var dict = COMMON_X[lang] || {};
    document.querySelectorAll('nav a, header .tag, .crumb a').forEach(function (el) {
      if (el.children.length) return;
      var k = el.textContent.trim();
      if (dict[k]) el.textContent = dict[k];
    });
    if (!document.querySelector('script[src*="xf-translate.js"]')) {
      var sc = document.createElement('script');
      sc.src = '/xf-translate.js?v=2';
      document.head.appendChild(sc);
    }
  }

  function css() {
    if (document.getElementById('xf-pi-css')) return;
    var st = document.createElement('style');
    st.id = 'xf-pi-css';
    st.textContent =
      'header.top{position:relative;}' +
      '.xf-lang{position:absolute;top:14px;right:16px;display:flex;gap:4px;z-index:5;}' +
      '.xf-lang a{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:1px;color:#8aa2bb;' +
      'border:1px solid #2e4570;padding:3px 8px;cursor:pointer;text-decoration:none;background:transparent;}' +
      '.xf-lang a:hover{color:#3b82f6;border-color:#3b82f6;text-decoration:none;}' +
      '.xf-lang a.on{color:#3b82f6;border-color:#3b82f6;}' +
      '.xf-lang.inline{position:static;justify-content:center;margin-top:12px;}' +
      '@media(max-width:720px){.xf-lang{position:static;justify-content:center;margin-bottom:8px;}}';
    document.head.appendChild(st);
  }

  function switcher() {
    // pagine editoriali: <header class="top">; pagine legali: .masthead-center (bandierine centrate)
    var inline = false;
    var top = document.querySelector('header.top');
    if (!top) { top = document.querySelector('.masthead-center'); inline = !!top; }
    if (!top) top = document.querySelector('header');
    if (!top || top.querySelector('.xf-lang')) return;
    var box = document.createElement('div');
    box.className = 'xf-lang' + (inline ? ' inline' : '');
    LANGS.forEach(function (p) {
      var a = document.createElement('a');
      a.setAttribute('data-lang', p[0]);
      a.setAttribute('role', 'button');
      a.textContent = p[1];
      if (p[0] === lang) a.className = 'on';
      a.addEventListener('click', function () {
        if (p[0] === lang) return;
        try { localStorage.setItem('xenos_lang', p[0]); } catch (e) {}
        location.reload();
      });
      box.appendChild(a);
    });
    if (inline) top.appendChild(box); else top.insertBefore(box, top.firstChild);
  }

  function toItalian() {
    document.documentElement.lang = 'it';
    document.querySelectorAll('[data-it]').forEach(function (el) {
      el.innerHTML = el.getAttribute('data-it');
    });
    // menu, tagline e briciole comuni
    document.querySelectorAll('nav a, header .tag, .crumb a').forEach(function (el) {
      if (el.children.length) return;                  // già gestito da data-it
      var k = el.textContent.trim();
      if (COMMON[k] && COMMON[k] !== k) el.textContent = COMMON[k];
    });
    var t = document.querySelector('meta[name="xf-title-it"]');
    if (t && t.content) document.title = t.content;
    liveTranslate();
  }

  // Testi variabili senza versione italiana pronta ([data-xft], es. analisi dei setup):
  // tradotti al volo con /xf-translate.js (gratis, con cache). In errore restano in inglese.
  function liveTranslate() {
    var els = Array.prototype.slice.call(document.querySelectorAll('[data-xft]'));
    if (!els.length || typeof window.xfTranslate !== 'function') return;
    var i = 0;
    function next() {
      if (i >= els.length) return;
      var el = els[i++];
      var src = el.textContent;
      window.xfTranslate(src, 'it').then(function (out) {
        if (out && out !== src) el.textContent = out;
      }).catch(function () {}).then(next);
    }
    next(); next(); next();   // 3 alla volta
  }

  function init() {
    try {
      css();
      switcher();
      if (lang === 'it') toItalian();
      else if (lang !== 'en') toExtra();
    } catch (e) { /* mai bloccare la pagina */ }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
