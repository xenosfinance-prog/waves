/* 2026-11-02 — Accesso gratuito ai tool AI (email autorizzate).
   2026-11-19: le email NON sono più scritte qui in chiaro: c'è solo la loro impronta
   SHA-256 (email in minuscolo, senza spazi). Il controllo vero lo fa il Worker
   (tipo gemini-free-chat → "not_authorized"). Per aggiungere un'email: calcolare
   l'impronta SHA-256 e aggiungerla a ALLOWED_SHA256. */
(function () {
  var ALLOWED_SHA256 = ['953104220512b23e35d38fb51180a4b886c7c75043f9ab345c26969b38d9ee8a'];

  function sha256(str) {
    function r(n, x) { return (x >>> n) | (x << (32 - n)); }
    var K = [], H = [], i, j, p = 2, b, w = [];
    for (var c = 0; c < 64; p++) {
      for (b = 2; b * b <= p; b++) if (p % b === 0) break;
      if (b * b > p) { if (c < 8) H[c] = (Math.pow(p, 1 / 2) * 4294967296) | 0; K[c++] = (Math.pow(p, 1 / 3) * 4294967296) | 0; }
    }
    var s = unescape(encodeURIComponent(str)), l = s.length * 8, m = [];
    for (i = 0; i < s.length; i++) m[i >> 2] |= s.charCodeAt(i) << (24 - (i % 4) * 8);
    m[l >> 5] |= 0x80 << (24 - l % 32);
    m[(((l + 64) >> 9) << 4) + 15] = l;
    for (i = 0; i < m.length; i += 16) {
      var a = H.slice(0);
      for (j = 0; j < 64; j++) {
        if (j < 16) w[j] = m[i + j] | 0;
        else {
          var x = w[j - 15], y = w[j - 2];
          w[j] = (w[j - 16] + (r(7, x) ^ r(18, x) ^ (x >>> 3)) + w[j - 7] + (r(17, y) ^ r(19, y) ^ (y >>> 10))) | 0;
        }
        var t1 = (a[7] + (r(6, a[4]) ^ r(11, a[4]) ^ r(25, a[4])) + ((a[4] & a[5]) ^ (~a[4] & a[6])) + K[j] + w[j]) | 0;
        var t2 = ((r(2, a[0]) ^ r(13, a[0]) ^ r(22, a[0])) + ((a[0] & a[1]) ^ (a[0] & a[2]) ^ (a[1] & a[2]))) | 0;
        a = [(t1 + t2) | 0].concat(a);
        a[4] = (a[4] + t1) | 0;
        a.pop();
      }
      for (j = 0; j < 8; j++) H[j] = (H[j] + a[j]) | 0;
    }
    var out = '';
    for (i = 0; i < 8; i++) out += ('00000000' + (H[i] >>> 0).toString(16)).slice(-8);
    return out;
  }

  window.xfFreeOk = function (e) {
    var v = String(e || '').trim().toLowerCase();
    return !!v && ALLOWED_SHA256.indexOf(sha256(v)) >= 0;
  };
  try {
    var cur = localStorage.getItem('xenos_free_email');
    if (cur && !window.xfFreeOk(cur)) localStorage.removeItem('xenos_free_email');
  } catch (_) {}
})();
