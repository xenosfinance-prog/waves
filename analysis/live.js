/* XenosFinance — /analysis live levels (2026-10-16)
 * Le pagine /analysis sono statiche (commento AI 2 volte al giorno, testo indicizzato da Google).
 * Questo script aggiorna dal vivo prezzo, bias, zone, indicatori, struttura, scenari e trigger
 * chiedendo i numeri al server ew_server (stesso motore H1 + contesto H4, cache 15 minuti).
 * Nessun commit, nessun deploy, nessuna chiamata AI. Se il server non risponde resta la pagina statica.
 */
(function () {
  var API = "https://waves-production-ddbf.up.railway.app/analysis-live";
  var REFRESH_MS = 15 * 60 * 1000;
  var SCEN = { long_pullback: "Bullish aggressive (pullback)", long_breakout: "Bullish conservative (breakout)",
    short_rejection: "Bearish aggressive (rejection)", short_breakdown: "Bearish conservative (breakdown)" };
  var MEMBER = { prev_high: "Previous-day high", prev_low: "Previous-day low", swing_high: "Swing high",
    swing_low: "Swing low", ew_inv: "Elliott invalidation" };
  var REGIME = { above_cloud: "above the cloud", below_cloud: "below the cloud", inside_cloud: "inside the cloud" };
  var QL = { good: "good", ok: "acceptable", poor: "unfavourable" };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(v, dec) {
    if (v == null || isNaN(v)) return "—";
    if (dec <= 2 && Math.abs(v) >= 1000)
      return Number(v).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    return Number(v).toFixed(dec);
  }
  function ztxt(z, dec) { return z.low === z.high ? fmt(z.low, dec) : fmt(z.low, dec) + "–" + fmt(z.high, dec); }
  function hhmm(iso) { var d = new Date(iso); return isNaN(d) ? "" : d.toISOString().slice(11, 16); }
  function set(id, html) { var el = document.getElementById(id); if (el) el.innerHTML = html; return el; }

  function get(yf, dec) {
    return fetch(API + "?yf=" + encodeURIComponent(yf) + "&dec=" + dec, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { return d && !d.error ? d : null; })
      .catch(function () { return null; });
  }

  // ── Pagina strumento ──────────────────────────────────────────
  function renderPage(cfg, d) {
    var dec = +cfg.dec, f = function (v) { return fmt(v, dec); };
    var chg = d.change_pct_day;
    set("lv-px", esc(cfg.short) + " <b>" + f(d.live) + "</b>" +
      (chg != null ? ' <span class="' + (chg >= 0 ? "up" : "dn") + '">' + (chg >= 0 ? "+" : "") + chg.toFixed(2) + "%</span>" : "") +
      " · ATR(14) " + f(d.atr));

    var dir = d.bias.direction, bw = dir.charAt(0).toUpperCase() + dir.slice(1);
    var be = set("lv-bias", "<span>Bias</span><b>" + bw + "</b><span>Confidence " + esc(d.bias.confidence) +
      " · score " + (d.bias.score >= 0 ? "+" : "") + d.bias.score + "/7</span>");
    if (be) be.className = "bias " + dir;

    function zrows(zs) {
      if (!zs || !zs.length) return '<tr><td colspan="3" class="m">No level within range</td></tr>';
      return zs.map(function (z) {
        return "<tr><td>" + ztxt(z, dec) + '</td><td class="m">' + esc(z.members.map(function (m) { return MEMBER[m] || m; }).join(" + ")) +
          "</td><td>" + "●".repeat(Math.min(z.strength, 4)) + "</td></tr>";
      }).join("");
    }
    set("lv-zones", "<div><table><tr><th>Resistance</th><th>Levels</th><th>Strength</th></tr>" + zrows(d.zones.resistances) +
      "</table></div><div><table><tr><th>Support</th><th>Levels</th><th>Strength</th></tr>" + zrows(d.zones.supports) + "</table></div>");

    var ind = d.indicators;
    function pos(v) { return v && d.live > v ? "price above" : "price below"; }
    var h1 = d.h1;
    set("lv-trend", "<table><tr><th>Indicator</th><th>Value</th><th>Reading</th></tr>" +
      "<tr><td>SMA 20</td><td>" + f(ind.sma20) + '</td><td class="m">' + pos(ind.sma20) + "</td></tr>" +
      "<tr><td>SMA 50</td><td>" + f(ind.sma50) + '</td><td class="m">' + pos(ind.sma50) + "</td></tr>" +
      "<tr><td>SMA 200</td><td>" + f(ind.sma200) + '</td><td class="m">' + pos(ind.sma200) + "</td></tr>" +
      "<tr><td>SuperTrend (10,3)</td><td>" + f(ind.supertrend) + '</td><td class="m">' + (ind.supertrend_dir === "up" ? "bullish" : "bearish") + "</td></tr>" +
      (h1 ? "<tr><td>Ichimoku 4H</td><td>" + esc(REGIME[h1.regime] || h1.regime) + '</td><td class="m">' + h1.bull_score + "/4 bullish · " + h1.bear_score + "/4 bearish</td></tr>" : "") +
      "</table>");

    set("lv-mom", "<table><tr><th>Indicator</th><th>Value</th></tr>" +
      "<tr><td>RSI (14)</td><td>" + ind.rsi + "</td></tr>" +
      "<tr><td>MACD / signal</td><td>" + ind.macd + " / " + ind.macd_signal + "</td></tr>" +
      (ind.volume_ratio ? "<tr><td>Volume vs 40-bar average</td><td>×" + ind.volume_ratio + "</td></tr>" : "") +
      "</table>");

    var rows = "";
    if (d.swing) rows += "<tr><td>Last swing</td><td>" + f(d.swing.from) + " → " + f(d.swing.to) + " (" + d.swing.dir + ")</td></tr>";
    Object.keys(d.fib || {}).forEach(function (k) { rows += "<tr><td>Fibonacci " + k + "%</td><td>" + f(d.fib[k]) + "</td></tr>"; });
    if (d.elliott) {
      var ew = d.elliott;
      rows += "<tr><td>Elliott Wave</td><td>" + esc(ew.desc) + "</td></tr>";
      if (ew.invalidation != null) rows += "<tr><td>Elliott invalidation</td><td>" + f(ew.invalidation) + "</td></tr>";
      var tps = [ew.tp1, ew.tp2].filter(function (t) { return t != null; }).map(f);
      if (tps.length) rows += "<tr><td>Elliott targets</td><td>" + tps.join(" · ") + "</td></tr>";
    }
    var pd = d.prev_day || {};
    if (pd.high != null && pd.low != null) rows += "<tr><td>Previous-day range</td><td>" + f(pd.low) + " – " + f(pd.high) + "</td></tr>";
    set("lv-struct", rows ? "<table><tr><th>Element</th><th>Level</th></tr>" + rows + "</table>" : "");

    if (d.scenarios && d.scenarios.length) {
      set("lv-scen", "<table><tr><th>Scenario</th><th>Entry</th><th>Stop</th><th>Target</th><th>R:R</th><th>Quality</th></tr>" +
        d.scenarios.map(function (sc) {
          return '<tr class="' + sc.quality + '"><td>' + (SCEN[sc.key] || sc.key) + "</td><td>" + f(sc.entry) + "</td><td>" + f(sc.stop) +
            "</td><td>" + f(sc.target) + "</td><td>" + sc.rr.toFixed(2) + ':1</td><td><span class="q ' + sc.quality + '">' + QL[sc.quality] + "</span></td></tr>";
        }).join("") + "</table>");
    } else {
      set("lv-scen", "<p>No scenario with valid levels at the moment.</p>");
    }

    var tr = d.trigger || {}, t = "";
    if (tr.bull != null) t += '<div class="trig up">▲ Bullish confirmation: hourly close above ' + f(tr.bull) + "</div>";
    if (tr.bear != null) t += '<div class="trig dn">▼ Bearish confirmation: hourly close below ' + f(tr.bear) + "</div>";
    set("lv-trig", t);

    stamp(d.computed_at);
  }

  // ── Indice /analysis ─────────────────────────────────────────
  function renderRow(tr, d) {
    var dec = +tr.getAttribute("data-dec");
    var dir = d.bias.direction;
    var s = d.zones.supports[0], r = d.zones.resistances[0];
    var c;
    if ((c = tr.querySelector(".lv-price"))) c.textContent = fmt(d.live, dec);
    if ((c = tr.querySelector(".lv-b"))) {
      c.textContent = dir.charAt(0).toUpperCase() + dir.slice(1);
      c.className = "lv-b " + ({ bullish: "up", bearish: "dn" }[dir] || "");
    }
    if ((c = tr.querySelector(".lv-s1"))) c.textContent = s ? ztxt(s, dec) : "—";
    if ((c = tr.querySelector(".lv-r1"))) c.textContent = r ? ztxt(r, dec) : "—";
  }

  var stampEl = null;
  function stamp(iso) {
    var upd = document.getElementById("lv-upd");
    if (!upd || !iso) return;
    if (!stampEl) {
      stampEl = document.createElement("div");
      stampEl.className = "upd";
      upd.parentNode.insertBefore(stampEl, upd.nextSibling);
    }
    stampEl.textContent = "Live levels: " + hhmm(iso) + " UTC (refresh every 15 min) · written commentary from the update above";
  }

  function runPage(cfg) {
    get(cfg.yf, cfg.dec).then(function (d) { if (d) renderPage(cfg, d); });
  }
  function runIndex(rows) {
    var latest = null;
    // una richiesta alla volta: il server calcola un simbolo per volta
    rows.reduce(function (p, tr) {
      return p.then(function () {
        return get(tr.getAttribute("data-yf"), tr.getAttribute("data-dec")).then(function (d) {
          if (!d) return;
          renderRow(tr, d);
          if (!latest || d.computed_at > latest) latest = d.computed_at;
          stamp(latest);
        });
      });
    }, Promise.resolve());
  }

  function run() {
    var cfgEl = document.getElementById("lv-cfg");
    if (cfgEl) {
      var cfg = { yf: cfgEl.getAttribute("data-yf"), dec: cfgEl.getAttribute("data-dec"), short: cfgEl.getAttribute("data-short") };
      runPage(cfg);
      setInterval(function () { runPage(cfg); }, REFRESH_MS);
      return;
    }
    var rows = Array.prototype.slice.call(document.querySelectorAll("tr.lv-row"));
    if (rows.length) {
      runIndex(rows);
      setInterval(function () { runIndex(rows); }, REFRESH_MS);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
