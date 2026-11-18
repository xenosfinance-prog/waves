/* XenosFinance — controllo admin unico (2026-11-18)
 * La password admin NON è nel codice del sito: qui c'è solo la sua impronta PBKDF2-SHA256
 * (310.000 iterazioni, sale fisso). Per cambiarla: xenosfinance.com/xf-admin-key.html →
 * nuova impronta → sostituire XF_ADMIN_HASH qui sotto. Stessi SALT/ITER della pagina.
 *
 *   await xfAdminVerify(pw)  → true se pw è la password admin
 *   XF_ADMIN_TOKEN           → valore salvato in localStorage/sessionStorage dopo il login
 *                              (al posto della password, che prima finiva lì in chiaro)
 *   xfIsAdminToken(v)        → true se v è il token admin
 */
(function () {
  var SALT = '56fb78bf0a82b0a4670b30e94db296be';
  var ITER = 310000;
  var XF_ADMIN_HASH = '655c61cb49ff09735048b107488d68403a76a27487fec935bf2f18b7e9b215e9';

  async function pbkdf2(pw) {
    var enc = new TextEncoder();
    var key = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveBits']);
    var bits = await crypto.subtle.deriveBits(
      { name: 'PBKDF2', hash: 'SHA-256', salt: enc.encode(SALT), iterations: ITER }, key, 256);
    return Array.from(new Uint8Array(bits)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  window.XF_ADMIN_TOKEN = 'xf-admin-' + XF_ADMIN_HASH.slice(0, 24);
  window.xfIsAdminToken = function (v) { return v === window.XF_ADMIN_TOKEN; };
  window.xfAdminVerify = async function (pw) {
    pw = String(pw || '').trim();
    if (!pw) return false;
    try { return (await pbkdf2(pw)) === XF_ADMIN_HASH; } catch (e) { return false; }
  };
})();
