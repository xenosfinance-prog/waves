// XenosFinance — traduttore live EN → IT (2026-10-25)
// Sostituisce LibreTranslate (Railway): il servizio non rispondeva più e le
// chiamate dirette erano comunque bloccate dalla CSP (connect-src).
// Usa l'endpoint pubblico gratuito di Google Translate (nessuna chiave, nessun
// costo), con cache in memoria + localStorage. In caso di errore restituisce
// sempre il testo originale: la pagina non si blocca mai.
// I contenuti salvati (blog, education) NON passano di qui se esiste già la
// versione italiana pre-generata in /i18n/it/ (qualità migliore, zero attese).
(function () {
  var MEM = {};
  var LS_PREFIX = 'xft1:';
  var MAX_CHUNK = 1800;

  // Termini di trading che Google rende male: si correggono dopo la traduzione.
  var FIX_IT = [
    [/\bpregiudizi?o? (rialzista|ribassista|neutrale|neutro)/gi, 'bias $1'],
    [/\bpregiudizio\b/gi, 'bias'],
    [/\bdenaro intelligente\b/gi, 'smart money'],
    [/\bsoldi intelligenti\b/gi, 'smart money'],
    [/\bfermare la perdita\b/gi, 'stop loss'],
    [/\bfermata della perdita\b/gi, 'stop loss'],
    [/\barresto delle perdite\b/gi, 'stop loss'],
    [/\bprendere profitto\b/gi, 'take profit'],
    [/\bprendi profitto\b/gi, 'take profit'],
    [/\bonde di Elliot\b/g, 'onde di Elliott'],
    [/\bOnda di Elliot\b/g, 'Onda di Elliott'],
    [/\bpetrolio greggio WTI\b/gi, 'petrolio WTI'],
    [/\bBuste per il petrolio\b/gi, 'Scorte di petrolio']
  ];

  function hash(s) {
    var h = 5381;
    for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36) + '_' + s.length;
  }

  function lsGet(k) {
    try { return localStorage.getItem(LS_PREFIX + k); } catch (e) { return null; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(LS_PREFIX + k, v); }
    catch (e) {
      // quota piena: si svuota solo la cache delle traduzioni
      try {
        Object.keys(localStorage).forEach(function (key) { if (key.indexOf(LS_PREFIX) === 0) localStorage.removeItem(key); });
        localStorage.setItem(LS_PREFIX + k, v);
      } catch (e2) {}
    }
  }

  // Divide il testo in blocchi ≤ MAX_CHUNK rispettando gli a capo.
  // Ogni blocco porta il separatore che lo seguiva ('\n' o ' ').
  function chunks(text) {
    if (text.length <= MAX_CHUNK) return [[text, '']];
    var out = [], cur = '';
    var lines = text.split('\n');
    lines.forEach(function (line, idx) {
      if (cur && (cur.length + 1 + line.length) > MAX_CHUNK) { out.push([cur, '\n']); cur = line; }
      else cur = idx === 0 ? line : cur + '\n' + line;
      while (cur.length > MAX_CHUNK) {          // riga singola troppo lunga
        var cut = cur.lastIndexOf('. ', MAX_CHUNK);
        cut = cut < 200 ? cur.lastIndexOf(' ', MAX_CHUNK) : cut + 1;
        if (cut < 200) cut = MAX_CHUNK;
        out.push([cur.slice(0, cut), ' ']); cur = cur.slice(cut).replace(/^ /, '');
      }
    });
    if (cur || !out.length) out.push([cur, '']);
    return out;
  }

  function fixTerms(s, target) {
    if (target !== 'it') return s;
    FIX_IT.forEach(function (r) { s = s.replace(r[0], r[1]); });
    return s;
  }

  async function gtx(text, target, source) {
    var url = 'https://translate.googleapis.com/translate_a/single?client=gtx&dt=t' +
      '&sl=' + encodeURIComponent(source || 'en') + '&tl=' + encodeURIComponent(target) +
      '&q=' + encodeURIComponent(text);
    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, 9000);
    try {
      var r = await fetch(url, { signal: ctrl.signal });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var d = await r.json();
      var parts = (d && d[0]) || [];
      var out = parts.map(function (p) { return p && p[0] ? p[0] : ''; }).join('');
      if (!out) throw new Error('empty');
      return out;
    } finally { clearTimeout(tid); }
  }

  // API pubblica: xfTranslate(testo, 'it') → Promise<string>
  window.xfTranslate = async function (text, target, source) {
    if (!text || typeof text !== 'string' || !target || target === (source || 'en')) return text;
    if (!/[A-Za-z]{2,}/.test(text)) return text;       // solo numeri/simboli
    var key = target + '|' + hash(text);
    if (MEM[key]) return MEM[key];
    var cached = lsGet(key);
    if (cached) { MEM[key] = cached; return cached; }
    try {
      var parts = chunks(text);
      var res = '';
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i][0];
        res += (p.trim() ? await gtx(p, target, source) : p) + parts[i][1];
      }
      var out = fixTerms(res, target);
      MEM[key] = out;
      lsSet(key, out);
      return out;
    } catch (e) {
      return text;                                       // fallback: originale
    }
  };

  // Lingua corrente del sito (stessa chiave di i18n-engine.js)
  window.xfLang = function () {
    try { var l = localStorage.getItem('xenos_lang') || 'en'; return l === 'it' ? 'it' : 'en'; }
    catch (e) { return 'en'; }
  };
})();
