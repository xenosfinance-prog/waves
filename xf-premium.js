/**
 * XenosFinance Premium Gate
 * xf-premium.js — include in every page with AI tools
 *
 * FREE users:  1 AI analysis per tool per day
 * PREMIUM:     unlimited
 *
 * Usage:
 *   <script src="xf-premium.js"></script>
 *   if (!XFPremium.canUse('elliott')) return;
 *   // ... run AI call ...
 *   XFPremium.recordUse('elliott');
 */

const XFPremium = (() => {

  const RECIPIENT = '0xC3e577D9b52dAD14a8D333b872f83428a78cA566';
  const FREE_LIMIT = 1; // uses per tool per day for free users

  // ── Premium check ────────────────────────────────────────────────────────────
  const XF_PREMIUM_CODES = ['XENOS-PREMIUM-2026','XF-PRO-001','XF-PRO-002','XF-PRO-003'];
  const XF_ADMIN_PWD     = 'RMG@Manu78';

  function isAdmin() {
    return localStorage.getItem('xf_admin_mode') === 'true' ||
           sessionStorage.getItem('xf_admin') === 'true';
  }

  function isPremiumCode() {
    const code = localStorage.getItem('xf_premium_code') || '';
    return XF_PREMIUM_CODES.includes(code);
  }

  function _getPremiumRecord() {
    try {
      const addr = _getConnectedAddress();
      if (!addr) return null;
      const raw = localStorage.getItem('xf_premium_' + addr.toLowerCase());
      if (!raw) return null;
      const data = JSON.parse(raw);
      return (data.expiry > Date.now()) ? data : null;
    } catch(e) { return null; }
  }

  function isPremium() {
    // Admin always has full access
    if (isAdmin()) return true;
    // Premium code (non-Web3 access)
    if (isPremiumCode()) return true;
    // Web3 payment on Base
    return _getPremiumRecord() !== null;
  }

  function _getConnectedAddress() {
    // Try window.ethereum selectedAddress
    if (window.ethereum && window.ethereum.selectedAddress) {
      return window.ethereum.selectedAddress;
    }
    // Try localStorage cache
    return localStorage.getItem('xf_wallet_addr') || null;
  }

  // ── Free usage tracking ───────────────────────────────────────────────────────
  function _todayKey(tool) {
    const d = new Date();
    const day = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
    return `xf_usage_${tool}_${day}`;
  }

  function _getUsageCount(tool) {
    return parseInt(localStorage.getItem(_todayKey(tool)) || '0', 10);
  }

  function recordUse(tool) {
    const key = _todayKey(tool);
    const count = _getUsageCount(tool);
    localStorage.setItem(key, count + 1);
  }

  // ── Gate check — returns true if allowed ─────────────────────────────────────
  function canUse(tool) {
    if (isPremium()) return true;
    return _getUsageCount(tool) < FREE_LIMIT;
  }

  // ── Show upgrade modal ────────────────────────────────────────────────────────
  function showUpgradeModal(tool) {
    // Remove existing modal
    const existing = document.getElementById('xf-premium-modal');
    if (existing) existing.remove();

    const toolLabels = {
      elliott:      'Elliott Wave Analysis',
      signals:      'AI Trading Signals',
      calendar:     'Economic Calendar AI',
      intermarket:  'Intermarket Analysis',
      ai_blog:      'AI Blog Generation',
      daily_ed:     'Daily Education',
      mko:          'MKO Scanner',
    };
    const label = toolLabels[tool] || 'AI Analysis';

    const modal = document.createElement('div');
    modal.id = 'xf-premium-modal';
    modal.innerHTML = `
      <div id="xf-pm-overlay" style="
        position:fixed;inset:0;background:rgba(0,0,0,0.75);
        backdrop-filter:blur(4px);z-index:9999;
        display:flex;align-items:center;justify-content:center;padding:20px;
      ">
        <div style="
          background:#141e2e;border:1px solid rgba(59,130,246,0.4);
          border-radius:16px;padding:36px;max-width:440px;width:100%;
          box-shadow:0 24px 80px rgba(0,0,0,0.6);text-align:center;
          font-family:'IBM Plex Mono',monospace;
        ">
          <div style="font-size:2rem;margin-bottom:12px">✦</div>
          <div style="
            font-size:0.68rem;letter-spacing:0.14em;text-transform:uppercase;
            color:#3b82f6;margin-bottom:16px;
          ">Premium Required</div>
          <div style="
            font-family:'Playfair Display',Georgia,serif;
            font-size:1.4rem;color:#e8eaf0;margin-bottom:10px;font-weight:700;
          ">Free limit reached</div>
          <div style="font-size:0.82rem;color:#8899aa;margin-bottom:24px;line-height:1.6;font-family:'PT Serif',serif;">
            You've used your free <b style="color:#e8eaf0">${label}</b> for today.<br>
            Upgrade to Premium for unlimited access to all AI tools.
          </div>
          <div style="
            background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);
            border-radius:10px;padding:16px;margin-bottom:24px;
          ">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
              <span style="color:#8899aa;font-size:0.72rem;">Monthly</span>
              <span style="color:#e8eaf0;font-size:0.72rem;font-weight:500;">9 USDC</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:#8899aa;font-size:0.72rem;">Annual</span>
              <span style="color:#f0c040;font-size:0.72rem;font-weight:500;">79 USDC — Best Value</span>
            </div>
          </div>
          <div style="display:flex;gap:10px;justify-content:center;">
            <a href="premium.html" style="
              background:#3b82f6;color:#fff;text-decoration:none;
              font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;
              padding:12px 28px;border-radius:8px;transition:background 0.2s;
              display:inline-block;
            ">✦ Get Premium</a>
            <button onclick="document.getElementById('xf-premium-modal').remove()" style="
              background:transparent;border:1px solid rgba(255,255,255,0.1);
              color:#8899aa;font-family:'IBM Plex Mono',monospace;
              font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;
              padding:12px 20px;border-radius:8px;cursor:pointer;
            ">Later</button>
          </div>
          <div style="margin-top:16px;font-size:0.65rem;color:#8899aa;letter-spacing:0.06em;">
            Resets tomorrow · Pay with USDC on Base
          </div>
        </div>
      </div>`;

    // Close on overlay click
    modal.querySelector('#xf-pm-overlay').addEventListener('click', function(e) {
      if (e.target === this) modal.remove();
    });

    document.body.appendChild(modal);
  }

  // ── Convenience: gate + show modal if blocked ─────────────────────────────────
  function gate(tool) {
    if (canUse(tool)) return true;
    showUpgradeModal(tool);
    return false;
  }

  // ── Show free usage indicator in UI ──────────────────────────────────────────
  function renderBadge(tool, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (isPremium()) {
      const label = isAdmin() ? '⚙ Admin — Unlimited' : '✦ Premium — Unlimited';
      el.innerHTML = `<span style="
        display:inline-flex;align-items:center;gap:6px;
        background:rgba(240,192,64,0.1);border:1px solid rgba(240,192,64,0.3);
        color:#f0c040;font-family:'IBM Plex Mono',monospace;
        font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;
        padding:4px 12px;border-radius:100px;
      ">\${label}</span>`;
    } else {
      const used = _getUsageCount(tool);
      const remaining = Math.max(0, FREE_LIMIT - used);
      const color = remaining > 0 ? '#22c55e' : '#ef4444';
      el.innerHTML = `<span style="
        display:inline-flex;align-items:center;gap:6px;
        background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
        color:${color};font-family:'IBM Plex Mono',monospace;
        font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;
        padding:4px 12px;border-radius:100px;
      ">${remaining > 0 ? `${remaining} free use${remaining !== 1 ? 's' : ''} left today` : 'Free limit reached · <a href="premium.html" style="color:#3b82f6;text-decoration:none;">Upgrade</a>'}</span>`;
    }
  }

  // ── Cache wallet address when user connects ───────────────────────────────────
  if (window.ethereum) {
    window.ethereum.on('accountsChanged', (accounts) => {
      if (accounts[0]) localStorage.setItem('xf_wallet_addr', accounts[0]);
    });
    if (window.ethereum.selectedAddress) {
      localStorage.setItem('xf_wallet_addr', window.ethereum.selectedAddress);
    }
  }

  return { isPremium, canUse, recordUse, gate, showUpgradeModal, renderBadge };

})();
