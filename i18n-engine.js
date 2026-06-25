// XenosFinance i18n Engine v2.0 
// Rewritten: bulletproof, no IIFE crash, IT added

// ── Prevent flash: hide translated elements immediately ──────────────────
var _xfLang = localStorage.getItem('xenos_lang') || 'en';
if (_xfLang !== 'en') {
  document.write('<style id="xf-foil">[data-i18n]{visibility:hidden!important}</style>');
}

// ── Language definitions ─────────────────────────────────────────────────
var XF_LANGS = {
  en: { flag: '🇬🇧', label: 'EN' },
  it: { flag: '🇮🇹', label: 'IT' },
  ru: { flag: '🇷🇺', label: 'RU' },
  pl: { flag: '🇵🇱', label: 'PL' },
  es: { flag: '🇪🇸', label: 'ES' },
};

// Reset unknown lang to EN
if (!XF_LANGS[_xfLang]) {
  _xfLang = 'en';
  localStorage.setItem('xenos_lang', 'en');
}

// ── Apply translations ───────────────────────────────────────────────────
function xenosApplyLang(lang) {
  // Safety: if i18n.js not loaded yet, abort silently
  if (typeof XENOS_I18N === 'undefined') return;
  if (!XENOS_I18N[lang] && !XENOS_I18N['en']) return;

  var t = XENOS_I18N[lang] || XENOS_I18N['en'];
  var els = document.querySelectorAll('[data-i18n]');
  for (var i = 0; i < els.length; i++) {
    var key = els[i].getAttribute('data-i18n');
    if (t[key] !== undefined) els[i].textContent = t[key];
  }

  document.documentElement.lang = lang;
  _xfLang = lang;
  localStorage.setItem('xenos_lang', lang);

  // Update button label
  var btn = document.getElementById('xenos-lang-btn');
  if (btn && XF_LANGS[lang]) {
    btn.innerHTML = XF_LANGS[lang].flag + ' ' + XF_LANGS[lang].label + ' ▾';
  }

  // Close dropdown
  var dd = document.getElementById('xenos-lang-dd');
  if (dd) dd.style.display = 'none';

  // Remove FOIL style
  var foil = document.getElementById('xf-foil');
  if (foil) foil.remove();
}

// ── Global setter (called by dropdown onclick) ───────────────────────────
window.xenosSetLang = function(lang) {
  if (!XF_LANGS[lang]) return;
  _xfLang = lang;
  localStorage.setItem('xenos_lang', lang);
  xenosApplyLang(lang);
};

// ── Build switcher widget ────────────────────────────────────────────────
function xenosBuildSwitcher() {
  var wrap = document.getElementById('xenos-lang-switcher');
  if (!wrap) return;

  var current = XF_LANGS[_xfLang] || XF_LANGS['en'];
  var items = '';
  for (var code in XF_LANGS) {
    var info = XF_LANGS[code];
    items += '<div onclick="xenosSetLang(\'' + code + '\')" ' +
      'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;padding:7px 14px;cursor:pointer;color:var(--muted);white-space:nowrap;transition:background 0.15s;" ' +
      'onmouseover="this.style.background=\'var(--bg3)\';this.style.color=\'var(--gold)\'" ' +
      'onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--muted)\'">' +
      info.flag + ' ' + info.label +
      '</div>';
  }

  wrap.innerHTML =
    '<div style="position:relative;display:inline-block;">' +
      '<button id="xenos-lang-btn" ' +
        'onclick="var d=document.getElementById(\'xenos-lang-dd\');d.style.display=d.style.display===\'block\'?\'none\':\'block\'" ' +
        'style="font-family:var(--mono);font-size:10px;letter-spacing:1px;background:none;border:1px solid var(--border);color:var(--muted);padding:3px 10px;cursor:pointer;transition:all 0.2s;" ' +
        'onmouseover="this.style.color=\'var(--gold)\';this.style.borderColor=\'var(--gold)\'" ' +
        'onmouseout="this.style.color=\'var(--muted)\';this.style.borderColor=\'var(--border)\'">' +
        current.flag + ' ' + current.label + ' ▾' +
      '</button>' +
      '<div id="xenos-lang-dd" ' +
        'style="display:none;position:absolute;right:0;top:100%;margin-top:4px;background:var(--bg2);border:1px solid var(--border);z-index:9999;min-width:110px;box-shadow:0 4px 20px rgba(0,0,0,0.4);">' +
        items +
      '</div>' +
    '</div>';

  // Close on outside click
  document.addEventListener('click', function(e) {
    var dd = document.getElementById('xenos-lang-dd');
    var btn = document.getElementById('xenos-lang-btn');
    if (dd && e.target !== btn && !dd.contains(e.target)) {
      dd.style.display = 'none';
    }
  });
}

// ── Init ─────────────────────────────────────────────────────────────────
function xenosI18nInit() {
  xenosBuildSwitcher();
  xenosApplyLang(_xfLang);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', xenosI18nInit);
} else {
  xenosI18nInit();
}

// Re-apply on back/forward cache
window.addEventListener('pageshow', function(e) {
  if (e.persisted) xenosApplyLang(_xfLang);
});
