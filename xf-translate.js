// XenosFinance — traduttore live EN → IT (2026-10-25); ES/RU/UK automatico (2026-11-14, in fondo)
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

  // 2026-11-14: testi già usciti dal traduttore (righe) — il traduttore automatico
  // della pagina non li ritraduce (le pagine traducono da sé news, card, analisi AI).
  var DONE = new Set();
  function markDone(out) {
    try {
      String(out || '').split('\n').forEach(function (l) {
        l = l.trim();
        if (l.length > 1) { DONE.add(l); if (l.length > 60) DONE.add(l.slice(0, 60)); }
      });
    } catch (e) {}
  }
  window.__xfDone = function (t) {
    t = String(t || '').trim();
    return DONE.has(t) || (t.length > 60 && DONE.has(t.slice(0, 60)));
  };

  // API pubblica: xfTranslate(testo, 'it') → Promise<string>
  window.xfTranslate = async function (text, target, source) {
    if (!text || typeof text !== 'string' || !target || target === (source || 'en')) return text;
    if (!/[A-Za-z]{2,}/.test(text)) return text;       // solo numeri/simboli
    var key = target + '|' + hash(text);
    if (MEM[key]) { markDone(MEM[key]); return MEM[key]; }
    var cached = lsGet(key);
    if (cached) { MEM[key] = cached; markDone(cached); return cached; }
    try {
      var parts = chunks(text);
      var res = '';
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i][0];
        res += (p.trim() ? await gtx(p, target, source) : p) + parts[i][1];
      }
      var out = fixTerms(res, target);
      markDone(out);
      MEM[key] = out;
      lsSet(key, out);
      return out;
    } catch (e) {
      return text;                                       // fallback: originale
    }
  };

  // Lingua corrente del sito (stessa chiave di i18n-engine.js)
  // 2026-11-14: lingue del sito EN, IT, ES, RU, UK.
  var SITE_LANGS = ['en', 'it', 'es', 'ru', 'uk'];
  // ?lang=xx nell'URL vale subito (questo script può girare prima di i18n-engine.js, che la salva)
  try {
    var _ul = new URLSearchParams(location.search).get('lang');
    if (SITE_LANGS.indexOf(_ul) >= 0) localStorage.setItem('xenos_lang', _ul);
  } catch (e) {}
  window.xfLang = function () {
    try { var l = localStorage.getItem('xenos_lang') || 'en'; return SITE_LANGS.indexOf(l) >= 0 ? l : 'en'; }
    catch (e) { return 'en'; }
  };

  // ════════════════════════════════════════════════════════════════════════
  // 2026-11-14 — TRADUZIONE AUTOMATICA DELLA PAGINA (ES, RU, UK)
  // L'italiano ha versioni fatte a mano pagina per pagina. Per spagnolo, russo e
  // ucraino: etichette dal dizionario (i18n/ui/<lingua>.js, via i18n-engine.js),
  // blog/education pre-tradotti (i18n/<lingua>/), e TUTTO il testo rimasto in
  // inglese — anche quello che arriva dopo (news, analisi AI, tabelle) — viene
  // tradotto qui, a blocchi, con lo stesso traduttore gratuito e una cache per
  // frase (memoria + localStorage). Numeri, ticker e codice non vengono toccati.
  // Un elemento con class "notranslate", translate="no" o data-no-xft resta com'è.
  // ════════════════════════════════════════════════════════════════════════
  var AUTO_LANGS = ['es', 'ru', 'uk'];
  var AUTO = window.xfLang();
  if (AUTO_LANGS.indexOf(AUTO) < 0 || window.__xfAuto) return;
  window.__xfAuto = true;

  var AMEM = {};
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, CODE: 1, PRE: 1, TEXTAREA: 1, SVG: 1, CANVAS: 1,
    IFRAME: 1, KBD: 1, SAMP: 1, VAR: 1, MATH: 1, INPUT: 1, SELECT: 0 };
  var SKIP_SEL = '.notranslate,[translate="no"],[data-no-xft],#xenos-lang-switcher,.xf-lang,[contenteditable="true"]';
  var TICKER = /^[A-Z0-9&\/\.\-:+%$€£¥()·•|,\s]+$/;
  var seen = new WeakMap();          // nodo di testo → testo che ci abbiamo scritto noi
  var dictVals = null;
  var queue = [], queued = new Set(), timer = null, inflight = 0, failures = 0, pausedUntil = 0;

  function aKey(s) { return 'a' + AUTO + '|' + hash(s); }
  function cacheGet(s) {
    if (AMEM[s] !== undefined) return AMEM[s];
    var v = lsGet(aKey(s));
    if (v !== null) AMEM[s] = v;
    return v;
  }
  function cacheSet(s, v) { AMEM[s] = v; lsSet(aKey(s), v); markDone(v); }

  function knownTranslation(t) {
    if (!dictVals) {
      dictVals = new Set();
      try {
        var d = (window.XF_I18N_EXTRA || {})[AUTO] || {};
        Object.keys(d).forEach(function (k) { dictVals.add(String(d[k]).trim()); });
      } catch (e) {}
    }
    return dictVals.has(t);
  }

  function wanted(t) {
    if (!t || t.length < 2 || t.length > 4000) return false;
    if (!/[A-Za-z]{2,}/.test(t)) return false;                // niente lettere latine: numeri o già tradotto (cirillico)
    if (TICKER.test(t) && t.split(/[\s\/]+/).every(function (w) { return w.length <= 4 || /\d/.test(w); })) return false;
    if (/^(https?:\/\/|www\.)\S+$/.test(t) || /^[\w.+-]+@[\w-]+\.[\w.]+$/.test(t)) return false;
    if (knownTranslation(t) || window.__xfDone(t)) return false;
    return true;
  }

  function skipped(el) {
    for (var e = el; e && e !== document.body; e = e.parentElement) {
      if (SKIP_TAGS[e.tagName] || e.namespaceURI === 'http://www.w3.org/2000/svg') return true;
    }
    return !!(el && el.closest && el.closest(SKIP_SEL));
  }

  function enqueue(item) {
    var key = item.src;
    var hit = cacheGet(key);
    if (hit !== null && hit !== undefined) { apply(item, hit); return; }
    queue.push(item);
    queued.add(key);
    if (!timer) timer = setTimeout(flush, 250);
  }

  function apply(item, out) {
    if (!out || out === item.src) return;
    if (item.node) {
      if (!item.node.parentNode) return;
      var cur = item.node.nodeValue;
      if (cur.trim() !== item.src) return;                     // nel frattempo è cambiato: lo riprende l'observer
      var lead = cur.match(/^\s*/)[0], trail = cur.match(/\s*$/)[0];
      var v = lead + out + trail;
      seen.set(item.node, v);
      item.node.nodeValue = v;
    } else if (item.el) {
      if ((item.el.getAttribute(item.attr) || '').trim() !== item.src) return;
      item.el.setAttribute(item.attr, out);
      item.el.setAttribute('data-xfa-' + item.attr, out);
    } else if (item.title) {
      if (document.title.trim() === item.src) document.title = out;
    }
  }

  function scanText(node) {
    if (seen.get(node) === node.nodeValue) return;            // scritto da noi
    var t = node.nodeValue.trim();
    if (!wanted(t) || skipped(node.parentElement)) return;
    enqueue({ node: node, src: t });
  }

  function scanAttrs(el) {
    ['placeholder', 'title', 'aria-label'].forEach(function (a) {
      if (!el.hasAttribute || !el.hasAttribute(a)) return;
      var v = (el.getAttribute(a) || '').trim();
      if (v === el.getAttribute('data-xfa-' + a)) return;
      if (wanted(v) && !skipped(el)) enqueue({ el: el, attr: a, src: v });
    });
  }

  function scan(root) {
    if (!root) return;
    if (root.nodeType === 3) { scanText(root); return; }
    if (root.nodeType !== 1 || skipped(root)) return;
    scanAttrs(root);
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
    var n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) scanText(n);
      else scanAttrs(n);
    }
  }

  function flush() {
    timer = null;
    if (Date.now() < pausedUntil) { timer = setTimeout(flush, pausedUntil - Date.now()); return; }
    while (queue.length && inflight < 2) {
      // un blocco: frasi uniche fino a ~1500 caratteri, una per riga
      var batch = [], items = [], size = 0, uniq = {};
      while (queue.length && size < 1500 && batch.length < 60) {
        var it = queue.shift();
        if (!uniq[it.src]) {
          var c = cacheGet(it.src);
          if (c !== null && c !== undefined) { apply(it, c); continue; }
          uniq[it.src] = [];
          batch.push(it.src);
          size += it.src.length + 1;
        }
        uniq[it.src].push(it);
        items.push(it);
      }
      if (!batch.length) continue;
      run(batch, uniq);
    }
  }

  function run(batch, uniq) {
    inflight++;
    var src = batch.map(function (s) { return s.replace(/\s*\n\s*/g, ' '); });
    gtx(src.join('\n'), AUTO, 'auto').then(function (out) {
      failures = 0;
      var lines = String(out || '').split('\n');
      if (lines.length === src.length) return lines;
      // allineamento perso: frase per frase
      return Promise.all(src.map(function (s) { return gtx(s, AUTO, 'auto').catch(function () { return s; }); }));
    }).then(function (lines) {
      batch.forEach(function (s, i) {
        var t = (lines[i] || '').trim();
        if (!t) return;
        cacheSet(s, t);
        (uniq[s] || []).forEach(function (it) { apply(it, t); });
      });
    }).catch(function () {
      failures++;
      if (failures >= 3) pausedUntil = Date.now() + 60000;   // il traduttore non risponde: pausa di 1 minuto
      batch.forEach(function (s) { (uniq[s] || []).forEach(function (it) { queue.push(it); }); });
    }).then(function () {
      batch.forEach(function (s) { queued.delete(s); });
      inflight--;
      if (queue.length && !timer) timer = setTimeout(flush, failures ? 3000 : 50);
    });
  }

  function start() {
    try {
      document.documentElement.lang = AUTO;
      var t = (document.title || '').trim();
      if (wanted(t)) enqueue({ title: true, src: t });
      scan(document.body);
      new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.type === 'characterData') scanText(m.target);
          else if (m.type === 'attributes') scanAttrs(m.target);
          else m.addedNodes.forEach(function (n) { scan(n); });
        });
      }).observe(document.body, { childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'] });
    } catch (e) { /* mai bloccare la pagina */ }
  }

  // dopo il motore lingua (dizionario applicato) e gli script della pagina
  function later() { setTimeout(start, 400); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', later);
  else later();
})();
