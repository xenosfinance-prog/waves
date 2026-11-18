/* XenosFinance — controllo admin + premium unico (2026-11-18, v2)
 * La password admin NON è nel codice del sito: qui c'è solo la sua impronta PBKDF2-SHA256
 * (310.000 iterazioni, sale fisso). Per cambiarla: xenosfinance.com/xf-admin-key.html →
 * nuova impronta → sostituire XF_ADMIN_HASH qui sotto. Stessi SALT/ITER della pagina.
 * La stessa password va messa nel secret ADMIN_PASSWORD del Worker.
 *
 * I codici premium NON sono nel codice del sito: sono il secret PREMIUM_CODES del Worker.
 *
 *   await xfAdminVerify(pw)   → true se pw è la password admin (la ricorda per il Worker)
 *   XF_ADMIN_TOKEN            → valore salvato in localStorage/sessionStorage dopo il login
 *   xfIsAdminToken(v)         → true se v è il token admin
 *   await xfPremiumVerify(c)  → true se il Worker conferma il codice premium (lo ricorda)
 *   XF_PREMIUM.includes(c)    → true se c è il codice premium già confermato su questo browser
 *   xfAuthClear()             → dimentica password admin e codice premium (logout)
 *
 * Ogni POST JSON al Worker riceve in automatico admin_pwd / premium_code se presenti:
 * il Worker (v2.20) accetta scritture GitHub, invii Telegram e AI senza limiti solo così.
 */
(function () {
  var SALT = '56fb78bf0a82b0a4670b30e94db296be';
  var ITER = 310000;
  var XF_ADMIN_HASH = '655c61cb49ff09735048b107488d68403a76a27487fec935bf2f18b7e9b215e9';
  var WORKER = 'https://xenos-ai-proxy.xenosfinance.workers.dev';
  var K_PW = 'xf_admin_pw', K_PREM = 'xf_premium_valid', K_BAD = 'xf_premium_bad';

  function lsGet(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function lsDel(k) { try { localStorage.removeItem(k); } catch (e) {} }

  async function pbkdf2(pw) {
    var enc = new TextEncoder();
    var key = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveBits']);
    var bits = await crypto.subtle.deriveBits(
      { name: 'PBKDF2', hash: 'SHA-256', salt: enc.encode(SALT), iterations: ITER }, key, 256);
    return Array.from(new Uint8Array(bits)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  // ── Admin ──────────────────────────────────────────────────────────────
  window.XF_ADMIN_TOKEN = 'xf-admin-' + XF_ADMIN_HASH.slice(0, 24);
  window.xfIsAdminToken = function (v) { return v === window.XF_ADMIN_TOKEN; };
  window.xfAdminVerify = async function (pw) {
    pw = String(pw || '').trim();
    if (!pw) return false;
    var ok = false;
    try { ok = (await pbkdf2(pw)) === XF_ADMIN_HASH; } catch (e) { ok = false; }
    if (ok) { lsSet(K_PW, pw); window._xfAdminPw = pw; }
    return ok;
  };
  if (!window._xfAdminPw && lsGet(K_PW)) window._xfAdminPw = lsGet(K_PW);
  // Sessione admin di prima di questa versione (token senza password): la si chiude,
  // così la pagina richiede il login una volta e il Worker riceve la password.
  if (!lsGet(K_PW)) {
    try { if (sessionStorage.getItem('xf_admin') === 'true') sessionStorage.removeItem('xf_admin'); } catch (e) {}
    try {
      for (var i = localStorage.length - 1; i >= 0; i--) {
        var k = localStorage.key(i);
        if (localStorage.getItem(k) === window.XF_ADMIN_TOKEN) localStorage.removeItem(k);
      }
      if (localStorage.getItem('xf_admin_mode') === 'true') localStorage.removeItem('xf_admin_mode');
    } catch (e) {}
    try {
      for (var j = sessionStorage.length - 1; j >= 0; j--) {
        var k2 = sessionStorage.key(j);
        if (sessionStorage.getItem(k2) === window.XF_ADMIN_TOKEN) sessionStorage.removeItem(k2);
      }
    } catch (e) {}
  }

  // ── Premium ────────────────────────────────────────────────────────────
  window.XF_PREMIUM = {
    includes: function (v) {
      var c = String(v || '').trim().toUpperCase(), ok = lsGet(K_PREM);
      return !!c && !!ok && c === ok;
    }
  };
  window.xfPremiumVerify = async function (code) {
    var c = String(code || '').trim().toUpperCase();
    if (!c || c.length < 6 || c.length > 64) return false;
    if (window.XF_PREMIUM.includes(c)) return true;
    try {
      var r = await _origFetch(WORKER, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'premium-check', code: c })
      });
      var d = await r.json();
      if (d && d.ok === true) {
        lsSet(K_PREM, c); lsDel(K_BAD);
        lsSet('xenos_premium_code', c); lsSet('xf_premium_code', c);
        return true;
      }
    } catch (e) {}
    return false;
  };
  window.xfAuthClear = function () { lsDel(K_PW); lsDel(K_PREM); window._xfAdminPw = ''; };

  // ── Credenziali aggiunte alle chiamate al Worker ───────────────────────
  var _origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    try {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      if (url.indexOf(WORKER) === 0 && init && typeof init.body === 'string' && init.body.charAt(0) === '{') {
        var pw = window._xfAdminPw || lsGet(K_PW), pc = lsGet(K_PREM);
        if (pw || pc) {
          var b = JSON.parse(init.body);
          if (b && typeof b === 'object' && b.type !== 'premium-check') {
            if (pw && !b.admin_pwd) b.admin_pwd = pw;
            if (pc && !b.premium_code) b.premium_code = pc;
            init = Object.assign({}, init, { body: JSON.stringify(b) });
          }
        }
      }
    } catch (e) {}
    return _origFetch(input, init);
  };

  // ── Codice premium arrivato da link ?code= o salvato prima di questa versione ──
  // Viene verificato una volta sul Worker; se valido la pagina si ricarica sbloccata.
  try {
    var q = new URLSearchParams(location.search).get('code');
    var cand = String(q || lsGet('xenos_premium_code') || lsGet('xf_premium_code') || '').trim();
    if (cand && !window.xfIsAdminToken(cand) && !window.XF_PREMIUM.includes(cand) && cand.toUpperCase() !== lsGet(K_BAD)) {
      window.xfPremiumVerify(cand).then(function (ok) {
        if (ok) { location.reload(); }
        else { lsSet(K_BAD, cand.toUpperCase()); }
      });
    }
  } catch (e) {}
})();
