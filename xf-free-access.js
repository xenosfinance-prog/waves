/* 2026-11-02 — Accesso gratuito ai tool AI (email autorizzate).
   Solo le email in elenco possono usare l'accesso gratuito; le altre
   salvate nel browser vengono rimosse al caricamento della pagina. */
(function () {
  var ALLOWED = ['info.galema@gmail.com'];
  window.XF_FREE_ALLOWED = ALLOWED;
  window.xfFreeOk = function (e) {
    return ALLOWED.indexOf(String(e || '').trim().toLowerCase()) >= 0;
  };
  try {
    var cur = localStorage.getItem('xenos_free_email');
    if (cur && !window.xfFreeOk(cur)) localStorage.removeItem('xenos_free_email');
  } catch (_) {}
})();
