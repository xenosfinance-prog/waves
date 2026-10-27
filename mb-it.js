// ══════════════════════════════════════════════════════════════════════════
// Market Brief in italiano (2026-10-27)
// La pagina viene riscritta in inglese a ogni edizione (ogni 2 ore), quindi la
// traduzione avviene nel browser quando la lingua del sito è IT:
//   - etichette fisse (categorie, sentiment, intestazioni) da dizionario;
//   - testo AI e titoli/sommari delle notizie con /xf-translate.js (gratuito, con
//     cache), in poche richieste a blocchi. Se la traduzione fallisce resta l'inglese.
// Caricato dalla Function functions/market-brief.js insieme a xf-translate.js.
// ══════════════════════════════════════════════════════════════════════════
(function () {
  function isIT() {
    try { return localStorage.getItem('xenos_lang') === 'it'; } catch (e) { return false; }
  }
  if (!isIT()) return;

  var CAT = {
    'MACRO & CENTRAL BANKS': 'Macro e banche centrali', 'EQUITIES': 'Azionario',
    'COMMODITIES & ENERGY': 'Materie prime ed energia', 'CRYPTO': 'Crypto',
    'FOREX & RATES': 'Forex e tassi', 'GEOPOLITICAL RISK': 'Rischio geopolitico',
    'EXECUTIVE SUMMARY': 'Sintesi', 'MARKET OUTLOOK': 'Prospettive di mercato'
  };
  var SENT = { 'MIXED': 'MISTO', 'BULLISH': 'RIALZISTA', 'BEARISH': 'RIBASSISTA', 'NEUTRAL': 'NEUTRALE' };
  var SENT_LO = { 'bullish': 'rialzista', 'bearish': 'ribassista', 'neutral': 'neutrale', 'mixed': 'misto' };
  var MONTHS = { January: 'gennaio', February: 'febbraio', March: 'marzo', April: 'aprile', May: 'maggio', June: 'giugno',
    July: 'luglio', August: 'agosto', September: 'settembre', October: 'ottobre', November: 'novembre', December: 'dicembre' };
  var DAYS = { Monday: 'lunedì', Tuesday: 'martedì', Wednesday: 'mercoledì', Thursday: 'giovedì', Friday: 'venerdì',
    Saturday: 'sabato', Sunday: 'domenica' };

  function cat(t) {
    var k = String(t || '').trim().toUpperCase();
    return CAT[k] || null;
  }
  function date(s) {
    return s.replace(/\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b/g, function (m) { return DAYS[m]; })
            .replace(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\b/g,
                     function (m) { return MONTHS[m]; });
  }
  function each(sel, fn) { Array.prototype.forEach.call(document.querySelectorAll(sel), fn); }
  function setText(el, t) { if (el && t) el.textContent = t; }

  function labels() {
    document.documentElement.lang = 'it';
    each('.masthead-top span', function (el) {
      var t = el.textContent;
      if (t === 'AI-Powered Brief') el.textContent = 'Brief generato con AI';
      else if (/\d{4}/.test(t)) el.textContent = date(t);
    });
    setText(document.querySelector('.masthead-sub'), 'Market Intelligence Brief · Generato con AI');
    setText(document.querySelector('.sentiment-label'), 'Sentiment generale del mercato');
    each('.sentiment-value', function (el) {
      el.textContent = el.textContent.replace(/\b(MIXED|BULLISH|BEARISH|NEUTRAL)\b/, function (m) { return SENT[m]; });
    });
    each('.sentiment-stats', function (el) {
      el.textContent = date(el.textContent.replace(/articles analyzed/, 'notizie analizzate'));
    });
    each('.sent-bar-label span', function (el) {
      el.textContent = el.textContent.replace('Bullish', 'Rialzista').replace('Neutral', 'Neutrale').replace('Bearish', 'Ribassista');
    });
    setText(document.querySelector('.ai-badge'), '✦ Analisi AI');
    each('h1, .ai-title', function (el) {
      if (/Daily Pre-Market Brief/.test(el.textContent)) el.textContent = 'Brief pre-mercato giornaliero';
    });
    each('.brief-section-title, .cat-tab, .cat-label, .article-cat', function (el) {
      var t = cat(el.textContent);
      if (t) el.textContent = el.classList.contains('brief-section-title') ? t.toUpperCase() : t;
    });
    each('.cat-sentiment', function (el) {
      el.textContent = el.textContent.replace(/\b(MIXED|BULLISH|BEARISH|NEUTRAL)\b/, function (m) { return SENT[m]; });
    });
    each('.cat-count', function (el) { el.textContent = el.textContent.replace(/articles?/, 'notizie'); });
    each('.article-sent', function (el) {
      el.textContent = el.textContent.replace(/\b(bullish|bearish|neutral|mixed)\b/, function (m) { return SENT_LO[m]; });
    });
    each('.page-footer span', function (el) {
      if (/Not investment advice/.test(el.textContent)) el.textContent = '⚠ Non è consulenza finanziaria';
    });
  }

  // Traduce una lista di elementi in UNA richiesta (una riga per elemento).
  // Se il numero di righe tradotte non torna, gli elementi restano in inglese.
  async function block(els, maxLen) {
    if (!els.length) return;
    var src = els.map(function (el) {
      var t = el.textContent.replace(/\s*\n+\s*/g, ' ').trim();
      return maxLen ? t.slice(0, maxLen) : t;
    });
    var out = await window.xfTranslate(src.join('\n'), 'it');
    var lines = String(out || '').split('\n');
    if (lines.length !== els.length) return;
    els.forEach(function (el, i) {
      var t = lines[i].trim();
      if (!t) return;
      if (el.tagName === 'A' || !el.children.length) el.textContent = t;
    });
  }

  async function content() {
    if (typeof window.xfTranslate !== 'function') return;
    var paras = Array.prototype.slice.call(document.querySelectorAll('.ai-content .brief-p'));
    // il testo AI per paragrafi (sono lunghi: una richiesta ciascuno, in parallelo)
    await Promise.all(paras.map(async function (p) {
      var t = p.textContent.trim();
      if (!t) return;
      var it = await window.xfTranslate(t, 'it');
      if (it && it !== t) p.textContent = it;
    }));
    var titles = Array.prototype.slice.call(document.querySelectorAll('.article-title'));
    var sums = Array.prototype.slice.call(document.querySelectorAll('.article-summary'));
    // a blocchi di 16 per restare sotto il limite di lunghezza di ogni richiesta
    var jobs = [];
    for (var i = 0; i < titles.length; i += 16) jobs.push(block(titles.slice(i, i + 16)));
    for (var j = 0; j < sums.length; j += 8) jobs.push(block(sums.slice(j, j + 8)));
    await Promise.all(jobs.map(function (p) { return p.catch(function () {}); }));
  }

  function run() {
    try { labels(); } catch (e) {}
    content().catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
