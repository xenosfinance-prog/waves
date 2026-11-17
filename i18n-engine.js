// XenosFinance i18n Engine v3.0 — definitive fix

// Prevent flash immediately
// 2026-11-08 (SEO): ?lang=it / ?lang=en nell'URL sceglie la lingua (pagine italiane indicizzabili, es. /XenosBlog?slug=…&lang=it)
// 2026-11-14: lingue EN, IT, ES, RU, UK. ES/RU/UK: etichette da /i18n/ui/<lingua>.js
// (GitHub Action "translations"), il resto tradotto da /xf-translate.js.
var XF_SITE_LANGS = ['en', 'it', 'es', 'ru', 'uk'];
var XF_EXTRA_LANGS = ['es', 'ru', 'uk'];
try { var _xfUrlLang = new URLSearchParams(location.search).get('lang'); if (XF_SITE_LANGS.indexOf(_xfUrlLang) >= 0) localStorage.setItem('xenos_lang', _xfUrlLang); } catch (e) {}
var _xfLang = 'en';
try { _xfLang = localStorage.getItem('xenos_lang') || 'en'; } catch (e) {}
if (XF_SITE_LANGS.indexOf(_xfLang) < 0) { _xfLang = 'en'; try { localStorage.setItem('xenos_lang', 'en'); } catch (e) {} }
// script caricato in modo sincrono (non defer/async)? allora document.write funziona
var _xfSync = (function () { try { var c = document.currentScript; return !!c && !c.defer && !c.async && document.readyState === 'loading'; } catch (e) { return false; } })();
if (_xfLang !== 'en') {
  if (_xfSync) document.write('<style id="xf-foil">[data-i18n]{visibility:hidden!important}</style>');
}
// dizionario della lingua aggiuntiva + traduttore automatico (se la pagina non lo carica già)
function _xfLoadScript(src, cb) {
  var el = document.createElement('script');
  el.src = src;
  if (cb) { el.onload = cb; el.onerror = cb; }
  (document.head || document.documentElement).appendChild(el);
}
if (XF_EXTRA_LANGS.indexOf(_xfLang) >= 0) {
  if (_xfSync) document.write('<script src="/i18n/ui/' + _xfLang + '.js"><\/script>');
  else _xfLoadScript('/i18n/ui/' + _xfLang + '.js', function () { if (window.__xfInitDone) xenosApplyLang(_xfLang); });
  if (!document.querySelector('script[src*="xf-translate.js"]')) _xfLoadScript('/xf-translate.js?v=2');
  setTimeout(function () { var f = document.getElementById('xf-foil'); if (f) f.remove(); }, 3000);
}

function xfDict(lang) {
  var base = (typeof XENOS_I18N !== 'undefined') ? XENOS_I18N : {};
  var extra = window.XF_I18N_EXTRA || {};
  return base[lang] || extra[lang] || base['en'] || null;
}

var XF_LANGS = {
  en: { flag: '🇬🇧', label: 'EN' },
  it: { flag: '🇮🇹', label: 'IT' },
  es: { flag: '🇪🇸', label: 'ES' },
  ru: { flag: '🇷🇺', label: 'RU' },
  uk: { flag: '🇺🇦', label: 'UA' },
};

function xenosApplyLang(lang) {
  var t = xfDict(lang);
  if (!t) return;
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    if (t[key] !== undefined) el.textContent = t[key];
  });
  document.documentElement.lang = lang;
  _xfLang = lang;
  localStorage.setItem('xenos_lang', lang);
  var btn = document.getElementById('xenos-lang-btn');
  if (btn && XF_LANGS[lang]) btn.innerHTML = XF_LANGS[lang].flag + ' ' + XF_LANGS[lang].label + ' ▾';
  var dd = document.getElementById('xenos-lang-dd');
  if (dd) dd.style.display = 'none';
  var foil = document.getElementById('xf-foil');
  if (foil) foil.remove();
}

// Global — called by dropdown onclick AND by any page script
window.xenosSetLang = function(lang) {
  if (!XF_LANGS[lang]) return;
  var prev = _xfLang;
  xenosApplyLang(lang);
  // 2026-10-25: i contenuti dinamici (articoli, news, analisi AI) vengono
  // caricati nella lingua attiva: al cambio lingua si ricarica la pagina,
  // così TUTTO il contenuto passa alla nuova lingua, non solo le etichette.
  if (prev !== lang) { try { setTimeout(function () { location.reload(); }, 60); } catch (e) {} }
};

// Helper for JS-generated content
window.t = function(key) {
  try {
    var lang = localStorage.getItem('xenos_lang') || 'en';
    var dict = xfDict(lang);
    if (dict && dict[key]) return dict[key];
    var en = xfDict('en');                       // chiave non ancora tradotta: inglese
    return (en && en[key]) ? en[key] : key;
  } catch(e) { return key; }
};

// 2026-11-17: selettore lingua in giallo (#f5c542) — il blu/grigio non si leggeva
function xenosBuildSwitcher() {
  var wrap = document.getElementById('xenos-lang-switcher');
  if (!wrap) return;
  var cur = XF_LANGS[_xfLang] || XF_LANGS['en'];
  var items = Object.keys(XF_LANGS).map(function(code) {
    var info = XF_LANGS[code];
    return '<div onclick="xenosSetLang(\'' + code + '\')" ' +
      'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;padding:7px 14px;cursor:pointer;color:#f5c542;white-space:nowrap;" ' +
      'onmouseover="this.style.background=\'var(--bg3)\';this.style.color=\'#fff\'" ' +
      'onmouseout="this.style.background=\'transparent\';this.style.color=\'#f5c542\'">' +
      info.flag + ' ' + info.label + '</div>';
  }).join('');
  wrap.innerHTML =
    '<div style="position:relative;display:inline-block;">' +
    '<button id="xenos-lang-btn" ' +
    'onclick="var d=document.getElementById(\'xenos-lang-dd\');d.style.display=d.style.display===\'block\'?\'none\':\'block\'" ' +
    'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;background:none;border:1px solid rgba(245,197,66,.55);color:#f5c542;padding:3px 10px;cursor:pointer;" ' +
    'onmouseover="this.style.color=\'#fff\';this.style.borderColor=\'#f5c542\'" ' +
    'onmouseout="this.style.color=\'#f5c542\';this.style.borderColor=\'rgba(245,197,66,.55)\'">' +
    cur.flag + ' ' + cur.label + ' ▾</button>' +
    '<div id="xenos-lang-dd" style="display:none;position:absolute;right:0;top:100%;margin-top:4px;background:var(--bg2);border:1px solid var(--border);z-index:9999;min-width:110px;box-shadow:0 4px 20px rgba(0,0,0,0.4);">' +
    items + '</div></div>';
  document.addEventListener('click', function(e) {
    var dd = document.getElementById('xenos-lang-dd');
    var btn = document.getElementById('xenos-lang-btn');
    if (dd && e.target !== btn && !dd.contains(e.target)) dd.style.display = 'none';
  });
}

function xenosInit() {
  xenosBuildSwitcher();
  xenosApplyLang(_xfLang);
  window.__xfInitDone = true;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', xenosInit);
} else {
  xenosInit();
}

window.addEventListener('pageshow', function(e) {
  if (e.persisted) xenosApplyLang(_xfLang);
});
