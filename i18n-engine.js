// XenosFinance i18n Engine v1.0 
// Lightweight language switcher — no API calls, no dependencies

(function() {
  const LANGS = {
    en: { flag: '🇬🇧', label: 'EN' },
    ru: { flag: '🇷🇺', label: 'RU' },
    pl: { flag: '🇵🇱', label: 'PL' },
    es: { flag: '🇪🇸', label: 'ES' },
  };

  let currentLang = localStorage.getItem('xenos_lang') || 'en';

  // Apply translations to all [data-i18n] elements
  function applyLang(lang) {
    const t = XENOS_I18N[lang] || XENOS_I18N['en'];
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (t[key]) el.textContent = t[key];
    });
    // Update html lang attribute
    document.documentElement.lang = lang;
    // Update switcher button
    const btn = document.getElementById('xenos-lang-btn');
    if (btn) btn.innerHTML = `${LANGS[lang].flag} ${LANGS[lang].label} ▾`;
    currentLang = lang;
    localStorage.setItem('xenos_lang', lang);
    // Close dropdown
    const dd = document.getElementById('xenos-lang-dd');
    if (dd) dd.style.display = 'none';
  }

  // Build the language switcher widget
  function buildSwitcher() {
    const wrap = document.getElementById('xenos-lang-switcher');
    if (!wrap) return;

    wrap.innerHTML = `
      <div style="position:relative;display:inline-block;">
        <button id="xenos-lang-btn"
          onclick="document.getElementById('xenos-lang-dd').style.display=document.getElementById('xenos-lang-dd').style.display==='block'?'none':'block'"
          style="font-family:var(--mono);font-size:10px;letter-spacing:1px;background:none;border:1px solid var(--border);color:var(--muted);padding:3px 10px;cursor:pointer;transition:all 0.2s;"
          onmouseover="this.style.color='var(--gold)';this.style.borderColor='var(--gold)'"
          onmouseout="this.style.color='var(--muted)';this.style.borderColor='var(--border)'">
          ${LANGS[currentLang].flag} ${LANGS[currentLang].label} ▾
        </button>
        <div id="xenos-lang-dd"
          style="display:none;position:absolute;right:0;top:100%;margin-top:4px;background:var(--bg2);border:1px solid var(--border);z-index:9999;min-width:110px;box-shadow:0 4px 20px rgba(0,0,0,0.4);">
          ${Object.entries(LANGS).map(([code, info]) => `
            <div onclick="xenosSetLang('${code}')"
              style="font-family:var(--mono);font-size:10px;letter-spacing:1px;padding:7px 14px;cursor:pointer;color:var(--muted);white-space:nowrap;transition:background 0.15s;"
              onmouseover="this.style.background='var(--bg3)';this.style.color='var(--gold)'"
              onmouseout="this.style.background='transparent';this.style.color='var(--muted)'">
              ${info.flag} ${info.label}
            </div>
          `).join('')}
        </div>
      </div>
    `;

    // Close dropdown when clicking outside
    document.addEventListener('click', e => {
      const dd = document.getElementById('xenos-lang-dd');
      const btn = document.getElementById('xenos-lang-btn');
      if (dd && !dd.contains(e.target) && e.target !== btn) {
        dd.style.display = 'none';
      }
    });
  }

  // Global function called by dropdown items
  window.xenosSetLang = function(lang) {
    if (XENOS_I18N[lang]) applyLang(lang);
  };

  // Init on DOM ready
  function init() {
    buildSwitcher();
    applyLang(currentLang);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
