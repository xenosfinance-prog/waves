// XenosFinance i18n Engine v3.0 — definitive fix

// Prevent flash immediately
var _xfLang = localStorage.getItem('xenos_lang') || 'en';
if (!['en','it','ru','pl','es'].includes(_xfLang)) _xfLang = 'en';
if (_xfLang !== 'en') {
  document.write('<style id="xf-foil">[data-i18n]{visibility:hidden!important}</style>');
}

var XF_LANGS = {
  en: { flag: '🇬🇧', label: 'EN' },
  it: { flag: '🇮🇹', label: 'IT' },
  ru: { flag: '🇷🇺', label: 'RU' },
  pl: { flag: '🇵🇱', label: 'PL' },
  es: { flag: '🇪🇸', label: 'ES' },
};

function xenosApplyLang(lang) {
  if (typeof XENOS_I18N === 'undefined') return;
  var t = XENOS_I18N[lang] || XENOS_I18N['en'];
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
  xenosApplyLang(lang);
};

// Helper for JS-generated content
window.t = function(key) {
  try {
    var lang = localStorage.getItem('xenos_lang') || 'en';
    if (typeof XENOS_I18N === 'undefined') return key;
    var dict = XENOS_I18N[lang] || XENOS_I18N['en'];
    return (dict && dict[key]) ? dict[key] : key;
  } catch(e) { return key; }
};

function xenosBuildSwitcher() {
  var wrap = document.getElementById('xenos-lang-switcher');
  if (!wrap) return;
  var cur = XF_LANGS[_xfLang] || XF_LANGS['en'];
  var items = Object.keys(XF_LANGS).map(function(code) {
    var info = XF_LANGS[code];
    return '<div onclick="xenosSetLang(\'' + code + '\')" ' +
      'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;padding:7px 14px;cursor:pointer;color:var(--muted);white-space:nowrap;" ' +
      'onmouseover="this.style.background=\'var(--bg3)\';this.style.color=\'var(--gold)\'" ' +
      'onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--muted)\'">' +
      info.flag + ' ' + info.label + '</div>';
  }).join('');
  wrap.innerHTML =
    '<div style="position:relative;display:inline-block;">' +
    '<button id="xenos-lang-btn" ' +
    'onclick="var d=document.getElementById(\'xenos-lang-dd\');d.style.display=d.style.display===\'block\'?\'none\':\'block\'" ' +
    'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;background:none;border:1px solid var(--border);color:var(--muted);padding:3px 10px;cursor:pointer;" ' +
    'onmouseover="this.style.color=\'var(--gold)\';this.style.borderColor=\'var(--gold)\'" ' +
    'onmouseout="this.style.color=\'var(--muted)\';this.style.borderColor=\'var(--border)\'">' +
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
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', xenosInit);
} else {
  xenosInit();
}

window.addEventListener('pageshow', function(e) {
  if (e.persisted) xenosApplyLang(_xfLang);
});
