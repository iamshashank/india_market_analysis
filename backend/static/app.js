"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

let ACTIVE_TAB = "screen";
let SCREEN_POLL = null;
let PRED_POLL = null;
let PAPER_CHART = null;

const fmtNum = (x, nd = 1) => (x === null || x === undefined ? "n/a" : Number(x).toFixed(nd));
const signClass = (x) => (x === null || x === undefined ? "" : x >= 0 ? "pos" : "neg");
const fmtPct = (v) => (v === null || v === undefined ? "n/a" : (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%");
const fmtPctFrac = (v) => (v === null || v === undefined ? "n/a" : (v * 100).toFixed(0) + "%");

function fmtUsd(v) {
  if (v === null || v === undefined) return "n/a";
  const n = Number(v);
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(0) + "M";
  return "$" + n.toFixed(0);
}

function escapeHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function yahooLink(ticker, innerHtml) {
  const url = ticker ? `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}` : "#";
  return `<a class="stock-link" href="${url}" target="_blank" rel="noopener noreferrer" title="Open on Yahoo Finance">${innerHtml}</a>`;
}

function showBanner(msg) { const b = $("#banner"); b.textContent = msg; b.classList.remove("hidden"); }
function hideBanner() { $("#banner").classList.add("hidden"); }

// ---------------- tabs ----------------
function switchTab(name) {
  ACTIVE_TAB = name;
  $$("#tabs .tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("#tab-screen").classList.toggle("hidden", name !== "screen");
  $("#tab-predictor").classList.toggle("hidden", name !== "predictor");
  $("#tab-paper").classList.toggle("hidden", name !== "paper");
  hideBanner();
  updateRefreshLabel();
  if (name === "screen") loadScreen();
  else if (name === "predictor") loadPredictor();
  else if (name === "paper") loadPaperDashboard();
}

function updateRefreshLabel() {
  const btn = $("#refreshBtn");
  if (ACTIVE_TAB === "paper") { btn.classList.add("hidden"); return; }
  btn.classList.remove("hidden");
  btn.textContent = ACTIVE_TAB === "screen" ? "↻ Re-screen" : "↻ Refresh";
}

function refreshActive() {
  if (ACTIVE_TAB === "screen") refreshScreen();
  else if (ACTIVE_TAB === "predictor") refreshPredictor();
}

// ================= MULTIBAGGER SCREEN =================
async function loadScreen() {
  try {
    const j = await fetch("/api/screen").then((r) => r.json());
    if (j.data) {
      renderScreen(j.data);
      if (j.status === "running") { showBanner("Refreshing the screen with the latest data…"); ensureScreenPoll(); }
      else { if (ACTIVE_TAB === "screen") hideBanner(); stopScreenPoll(); }
      return;
    }
    if (j.status === "error") { stopScreenPoll(); showBanner("Could not build the screen: " + (j.error || "unknown") + "."); return; }
    $("#screenContent").innerHTML = `<div class="loading"><div class="spinner"></div>
      <p>Scanning India + US small-caps, earnings history &amp; news… (~1–2 min the first time)</p></div>`;
    ensureScreenPoll();
  } catch (e) {
    if (ACTIVE_TAB === "screen") showBanner("Could not reach server. Retrying…");
    ensureScreenPoll();
  }
}
function ensureScreenPoll() { if (!SCREEN_POLL) SCREEN_POLL = setInterval(loadScreen, 5000); }
function stopScreenPoll() { if (SCREEN_POLL) { clearInterval(SCREEN_POLL); SCREEN_POLL = null; } }

async function refreshScreen() {
  const btn = $("#refreshBtn");
  btn.disabled = true; btn.textContent = "↻ Running…";
  try {
    await fetch("/api/screen/refresh", { method: "POST" });
    showBanner("Re-screening India + US universe… (~1–2 min)");
    ensureScreenPoll();
  } catch (e) { showBanner("Could not reach server."); }
  setTimeout(() => { btn.disabled = false; updateRefreshLabel(); }, 3000);
}

const PILLAR_LABELS = {
  small_base: "Small base", consistency: "Earnings consistency",
  under_covered: "Low coverage", growth: "Growth", quality: "Quality",
  valuation: "Valuation", catalyst: "News catalyst",
};

function renderScreen(d) {
  if (ACTIVE_TAB === "screen") {
    $("#generated").textContent = d.as_of ? `as of ${d.as_of}` : "";
    $("#disclaimer").textContent = d.disclaimer || "";
  }
  const c = $("#screenContent");
  c.innerHTML = "";
  c.appendChild(strategySection(d));
  c.appendChild(portfolioSection(d));
  c.appendChild(shortlistSection(d));
}

function strategySection(d) {
  const s = el("section", "section");
  const crit = (d.strategy?.criteria || []).map((x) =>
    `<div class="crit-chip"><b>${escapeHtml(x.label)}</b><span>${escapeHtml(x.desc)}</span></div>`).join("");
  const w = d.weights || {};
  const wbars = Object.keys(w).map((k) =>
    `<span class="wchip">${escapeHtml(PILLAR_LABELS[k] || k)} <b>${Math.round(w[k] * 100)}%</b></span>`).join("");
  s.innerHTML = `
    <div class="card strategy-card">
      <h2 class="strat-title">${escapeHtml(d.strategy?.title || "Multibagger screen")}</h2>
      <div class="crit-grid">${crit}</div>
      <div class="strat-weights"><span class="muted">Score weights:</span> ${wbars}</div>
      <p class="muted strat-meta">Scanned <b>${d.universe_size}</b> names · <b>${d.scored_count}</b> passed data checks${d.build_seconds ? ` · built in ${d.build_seconds}s` : ""}${(d.failed_tickers || []).length ? ` · ${d.failed_tickers.length} fetch failures` : ""}</p>
    </div>`;
  return s;
}

function marketBadge(m) {
  const cls = m === "IN" ? "mkt-in" : "mkt-us";
  return `<span class="mkt-badge ${cls}">${m === "IN" ? "🇮🇳 IN" : "🇺🇸 US"}</span>`;
}

function convBadge(c) {
  const cls = c === "High" ? "conf-high" : c === "Medium" ? "conf-med" : "conf-low";
  return `<span class="conf-badge ${cls}">${escapeHtml(c || "?")} conviction</span>`;
}

function pillarBars(pillars) {
  return Object.keys(PILLAR_LABELS).map((k) => {
    const v = pillars[k];
    if (v === undefined || v === null) return "";
    const cls = v >= 66 ? "mb-fill-hi" : v >= 45 ? "mb-fill-mid" : "mb-fill-lo";
    return `<div class="mb-bar-row">
      <span class="mb-bar-lbl">${escapeHtml(PILLAR_LABELS[k])}</span>
      <span class="mb-track"><span class="mb-fill ${cls}" style="width:${Math.max(3, Math.min(100, v))}%"></span></span>
      <span class="mb-bar-val">${Math.round(v)}</span>
    </div>`;
  }).join("");
}

function headlineList(headlines) {
  if (!headlines || !headlines.length) return "";
  const items = headlines.slice(0, 4).map((h) => {
    const tone = h.tone === "positive" ? "pos" : h.tone === "negative" ? "neg" : "";
    const ev = (h.events || []).length ? ` <span class="ev-tag">${escapeHtml(h.events[0])}</span>` : "";
    const title = h.link
      ? `<a href="${h.link}" target="_blank" rel="noopener noreferrer">${escapeHtml(h.title)}</a>`
      : escapeHtml(h.title);
    return `<li class="mb-news-item"><span class="news-dot ${tone === "pos" ? "pos-dot" : tone === "neg" ? "neg-dot" : ""}"></span>
      <span>${title}${ev}<span class="pn-meta"> ${escapeHtml(h.publisher || "")}${h.date ? " · " + escapeHtml(h.date) : ""}</span></span></li>`;
  }).join("");
  return `<ul class="mb-news-list">${items}</ul>`;
}

function portfolioCard(p, rank) {
  const m = p.metrics || {};
  const events = (p.news?.top_events || []).map((e) => `<span class="ev-chip">${escapeHtml(e)}</span>`).join("");
  const thesis = (p.thesis || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
  const risks = (p.risks || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
  const card = el("div", "card mb-card");
  card.innerHTML = `
    <div class="mb-head">
      <div class="mb-head-left">
        <span class="mb-rank">#${rank}</span>
        <div>
          <div class="mb-name">${yahooLink(p.ticker, escapeHtml(p.name || p.ticker))} ${marketBadge(p.market)}</div>
          <div class="mb-sub">${escapeHtml(p.ticker)} · ${escapeHtml(p.sector || "")} · ${fmtUsd(p.market_cap_usd)} cap</div>
        </div>
      </div>
      <div class="mb-score-wrap">
        <span class="mb-score">${Math.round(p.score)}</span>
        <span class="mb-score-lbl">score</span>
      </div>
    </div>
    <div class="mb-alloc">
      <span class="mb-weight">${fmtNum(p.weight_pct, 1)}%</span>
      <span class="mb-alloc-lbl">suggested weight · ${escapeHtml(p.size_tier)} position</span>
      ${convBadge(p.conviction)}
    </div>
    <div class="mb-pillars">${pillarBars(p.pillars || {})}</div>
    <div class="mb-metrics">
      <span>P/E <b>${fmtNum(m.trailing_pe, 1)}</b></span>
      <span>PEG <b>${fmtNum(m.peg, 2)}</b></span>
      <span>ROE <b>${fmtPctFrac(m.roe)}</b></span>
      <span>Margin <b>${fmtPctFrac(m.profit_margin)}</b></span>
      <span>Rev gr <b>${fmtPctFrac(m.revenue_growth)}</b></span>
      <span>Analysts <b>${p.num_analysts ?? "—"}</b></span>
    </div>
    <div class="mb-block">
      <h4>Why it fits the strategy</h4>
      <ul class="mb-bullets">${thesis}</ul>
    </div>
    <div class="mb-block">
      <h4>Key risks</h4>
      <ul class="mb-bullets mb-risks">${risks}</ul>
    </div>
    ${events ? `<div class="mb-events">${events}</div>` : ""}
    <div class="mb-block">
      <h4>Recent news <span class="muted">(catalyst ${Math.round(p.news?.catalyst_score ?? 50)}/100)</span></h4>
      ${headlineList(p.news?.headlines) || '<p class="news-empty">No recent headlines — that\'s part of the "hidden" thesis.</p>'}
    </div>
    <p class="mb-entry muted">${escapeHtml(p.entry_note || "")}</p>`;
  return card;
}

function portfolioSection(d) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "High-conviction portfolio"));
  const pf = d.portfolio || [];
  if (!pf.length) {
    s.appendChild(el("p", "muted callout",
      "No names clear the conviction threshold right now. The disciplined move is to wait — or loosen MIN_SCORE / expand the universe."));
    return s;
  }
  s.appendChild(el("p", "muted",
    `${pf.length} concentrated ideas across India + US, weighted toward the highest-conviction names. Weights are a suggested allocation of a single sleeve — not advice.`));
  const grid = el("div", "mb-grid");
  pf.forEach((p, i) => grid.appendChild(portfolioCard(p, i + 1)));
  s.appendChild(grid);
  return s;
}

function shortlistSection(d) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Full ranked shortlist"));
  s.appendChild(el("p", "muted", "Everything that passed the screen, ranked by composite score. Click a name to open it on Yahoo Finance."));
  const rows = d.shortlist || [];
  if (!rows.length) { s.appendChild(el("p", "muted", "Nothing to show.")); return s; }
  const wrap = el("div", "table-wrap");
  let html = `<table><thead><tr>
    <th class="l">#</th><th class="l">Stock</th><th>Mkt</th><th class="l">Sector</th>
    <th>Score</th><th>Cap</th><th>Small base</th><th>Consistency</th><th>Low cov.</th>
    <th>Growth</th><th>Quality</th><th>Catalyst</th><th>Analysts</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const pl = r.pillars || {};
    html += `<tr>
      <td class="l">${i + 1}</td>
      <td class="l">${yahooLink(r.ticker, escapeHtml(r.name || r.ticker))}</td>
      <td>${r.market === "IN" ? "IN" : "US"}</td>
      <td class="l">${escapeHtml(r.sector || "")}</td>
      <td><b>${Math.round(r.score)}</b></td>
      <td>${fmtUsd(r.market_cap_usd)}</td>
      <td>${Math.round(pl.small_base ?? 0)}</td>
      <td>${Math.round(pl.consistency ?? 0)}</td>
      <td>${Math.round(pl.under_covered ?? 0)}</td>
      <td>${Math.round(pl.growth ?? 0)}</td>
      <td>${Math.round(pl.quality ?? 0)}</td>
      <td class="${(pl.catalyst ?? 50) >= 55 ? "pos" : (pl.catalyst ?? 50) <= 45 ? "neg" : ""}">${Math.round(pl.catalyst ?? 50)}</td>
      <td>${r.num_analysts ?? "—"}</td>
    </tr>`;
  });
  html += `</tbody></table>`;
  wrap.innerHTML = html;
  s.appendChild(wrap);
  return s;
}

// ================= NEXT-DAY PREDICTOR =================
async function loadPredictor() {
  try {
    const j = await fetch("/api/premarket").then((r) => r.json());
    if (j.status === "running" && !j.data) {
      $("#content").innerHTML = `<div class="loading"><div class="spinner"></div><p>Reading global markets, futures &amp; commodities… (~30–60s)</p></div>`;
      ensurePredPoll(); return;
    }
    if (j.status === "error" && !j.data) { stopPredPoll(); if (ACTIVE_TAB === "predictor") showBanner("Could not build prediction: " + (j.error || "unknown") + "."); return; }
    if (j.data) {
      renderPredictor(j.data);
      if (j.status === "running") { if (ACTIVE_TAB === "predictor") showBanner("Updating with the latest cues…"); ensurePredPoll(); }
      else { if (ACTIVE_TAB === "predictor") hideBanner(); stopPredPoll(); }
      return;
    }
    ensurePredPoll();
  } catch (e) { if (ACTIVE_TAB === "predictor") showBanner("Could not reach server. Retrying…"); ensurePredPoll(); }
}
function ensurePredPoll() { if (!PRED_POLL) PRED_POLL = setInterval(loadPredictor, 4000); }
function stopPredPoll() { if (PRED_POLL) { clearInterval(PRED_POLL); PRED_POLL = null; } }

async function refreshPredictor() {
  const btn = $("#refreshBtn");
  btn.disabled = true; btn.textContent = "↻ Running…";
  try { await fetch("/api/refresh", { method: "POST" }); showBanner("Refreshing with the latest cues… (~30–60s)"); ensurePredPoll(); }
  catch (e) { showBanner("Could not reach server. Try again."); }
  setTimeout(() => { btn.disabled = false; updateRefreshLabel(); }, 3000);
}

function renderPredictor(pm) {
  if (ACTIVE_TAB === "predictor") {
    hideBanner();
    $("#generated").textContent = pm.predict_for_label
      ? `Prediction for ${pm.predict_for_label}` + (pm.as_of ? ` · as of ${pm.as_of}` : "")
      : (pm.as_of ? "As of " + pm.as_of : "");
    $("#disclaimer").textContent = pm.disclaimer || "";
  }
  const c = $("#content");
  c.innerHTML = "";
  c.appendChild(biasSection(pm));
  c.appendChild(predictionSection(pm));
  if (pm.gold_etf) c.appendChild(goldSection(pm.gold_etf));
  if (pm.validation) c.appendChild(validationSection(pm.validation));
  if (pm.sources) c.appendChild(sourcesSection(pm.sources));
}

function biasSection(pm) {
  const s = el("section", "section");
  const b = pm.market_bias || {};
  const cls = b.score >= 60 ? "pos" : b.score <= 40 ? "neg" : "";
  const cueCards = (pm.cue_strip || []).map((cu) =>
    `<div class="cue-card"><span class="cue-lbl">${escapeHtml(cu.label)}</span><b class="${signClass(cu.change_pct)}">${fmtPct(cu.change_pct)}</b></div>`).join("");
  s.innerHTML = `
    <div class="card premkt-head">
      <div class="premkt-gauge">
        <span class="premkt-gauge-lbl">Market open bias</span>
        <span class="premkt-gauge-score ${cls}">${fmtNum(b.score)}<span class="premkt-gauge-scale">/100</span></span>
        <span class="premkt-gauge-verdict">${escapeHtml(b.label || "")}</span>
      </div>
      <div class="cue-strip">${cueCards}</div>
    </div>
    <p class="muted premkt-note">${escapeHtml(pm.gift_nifty_note || "")}</p>`;
  return s;
}

function confBadge(conf) {
  const c = (conf || "").toLowerCase();
  const cls = c === "high" ? "conf-high" : c === "medium" ? "conf-med" : "conf-low";
  return `<span class="conf-badge ${cls}">${escapeHtml(conf || "?")} conf</span>`;
}

function stockCard(it, rank) {
  const sc = Math.round(Number(it.score));
  const reasons = (it.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
  const earn = it.earnings_warn ? `<span class="warn-tag" title="Earnings within ~3 days">⚠ earnings soon</span>` : "";
  const adv = it.adv_cr != null ? `₹${fmtNum(it.adv_cr, 0)} cr/day` : "liquidity n/a";
  const atr = it.atr_pct != null ? `${fmtNum(it.atr_pct, 1)}% ATR` : "";
  const TIP = {
    entry: "Entry: the price to buy at (≈ expected open).",
    stop: "Stop-loss: exit here if wrong, sized to this stock's volatility (ATR).",
    target: "Target: take-profit price.",
    rr: "Risk:Reward — potential gain vs potential loss.",
  };
  const tipAttr = (t) => `tabindex="0" data-tip="${escapeHtml(t)}" title="${escapeHtml(t)}"`;
  const risk = `
    <div class="risk-plan">
      <div class="rp-cell"><span class="tip" ${tipAttr(TIP.entry)}>Entry ⓘ</span><b>₹${fmtNum(it.price, 2)}</b></div>
      <div class="rp-cell"><span class="tip" ${tipAttr(TIP.stop)}>Stop ⓘ</span><b class="neg">₹${fmtNum(it.stop_price, 2)} (−${fmtNum(it.stop_pct, 1)}%)</b></div>
      <div class="rp-cell"><span class="tip" ${tipAttr(TIP.target)}>Target ⓘ</span><b class="pos">₹${fmtNum(it.target_price, 2)} (+${fmtNum(it.target_pct, 1)}%)</b></div>
      <div class="rp-cell"><span class="tip" ${tipAttr(TIP.rr)}>R:R ⓘ</span><b>1 : ${fmtNum(it.rr, 1)}</b></div>
    </div>`;
  const item = el("div", "premkt-item");
  item.innerHTML = `
    <div class="premkt-item-head">
      <span class="premkt-rank">#${rank}</span>
      <span class="premkt-name">${yahooLink(it.ticker, escapeHtml(it.name || it.ticker))} ${earn}</span>
      <span class="premkt-score pos">${sc}</span>
    </div>
    <div class="premkt-meta">${escapeHtml(it.verdict || "")} · ${confBadge(it.confidence)} · ${escapeHtml(it.sector || "")} · ${adv}${atr ? " · " + atr : ""}</div>
    ${risk}
    ${reasons ? `<ul class="premkt-reasons">${reasons}</ul>` : ""}`;
  return item;
}

function predictionSection(pm) {
  const s = el("section", "section");
  const high = pm.high_confidence || [];
  const watch = pm.watchlist || [];
  s.appendChild(el("h2", null, "Stocks likely to open higher tomorrow"));
  s.appendChild(el("p", "muted",
    `Liquid NSE names (≥ ₹${fmtNum(pm.liquidity_floor_cr, 0)} cr/day) ranked by overnight cues, sector sensitivity & beta. Every idea includes an ATR-based stop & target — not a guarantee.`));
  if (!high.length && !watch.length) {
    s.appendChild(el("p", "muted callout",
      "Overnight cues are weak or mixed — no liquid NSE names show a clear up-bias. On days like this, staying out is often the disciplined move."));
    return s;
  }
  if (high.length) {
    s.appendChild(el("h3", "bucket-title pos", "Higher-confidence (liquid · clear bias)"));
    const wrap = el("div", "premkt-list");
    high.forEach((it, i) => wrap.appendChild(stockCard(it, i + 1)));
    s.appendChild(wrap);
  }
  if (watch.length) {
    s.appendChild(el("h3", "bucket-title", "Watchlist (lower confidence — sector/beta only)"));
    const wrap = el("div", "premkt-list");
    watch.forEach((it, i) => wrap.appendChild(stockCard(it, i + 1)));
    s.appendChild(wrap);
  }
  return s;
}

function goldSection(g) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Gold ETF prediction (next day)"));
  const impl = g.implied_move_pct;
  const dirCls = impl == null ? "" : impl > 0.3 ? "pos" : impl < -0.3 ? "neg" : "";
  const rangeTxt = (g.range_low_pct != null && g.range_high_pct != null)
    ? `${fmtPct(g.range_low_pct)} to ${fmtPct(g.range_high_pct)}` : (impl != null ? fmtPct(impl) : "n/a");
  const drivers = (g.drivers || []).map((d) =>
    `<li><b>${escapeHtml(d.label)}</b> ${fmtPct(d.change_pct)} — ${escapeHtml(d.effect)}</li>`).join("");
  const head = el("div", "card gold-head");
  head.innerHTML = `
    <div class="gold-dir">
      <span class="gold-dir-lbl">Expected open</span>
      <span class="gold-dir-val ${dirCls}">${escapeHtml(g.direction || "n/a")}</span>
      <span class="gold-impl ${dirCls}">Estimated move: ${rangeTxt}</span>
    </div>
    <ul class="gold-drivers">${drivers}</ul>
    <p class="muted gold-method">${escapeHtml(g.method || "")}</p>`;
  s.appendChild(head);
  const etfs = g.etfs || [];
  if (etfs.length) {
    const wrap = el("div", "table-wrap");
    let html = `<table><thead><tr><th class="l">Gold ETF</th><th>Last close</th><th>Prev chg</th><th>Est. next range</th></tr></thead><tbody>`;
    etfs.forEach((e) => {
      const range = (e.est_low != null && e.est_high != null) ? `₹${fmtNum(e.est_low, 2)} – ₹${fmtNum(e.est_high, 2)}` : "n/a";
      html += `<tr><td class="l">${yahooLink(e.ticker, escapeHtml(e.name))}<div class="hl-meta">${escapeHtml(e.ticker)}</div></td>
        <td>₹${fmtNum(e.last_close, 2)}</td><td class="${signClass(e.last_change_pct)}">${fmtPct(e.last_change_pct)}</td><td><b>${range}</b></td></tr>`;
    });
    html += `</tbody></table>`;
    wrap.innerHTML = html;
    s.appendChild(wrap);
  }
  const disc = el("p", "premkt-disclaimer");
  disc.innerHTML = "⚠️ " + escapeHtml(g.caveat || "");
  s.appendChild(disc);
  return s;
}

function rateChip(label, r) {
  if (!r) return `<div class="bt-card"><span class="bt-lbl">${escapeHtml(label)}</span><b>n/a</b></div>`;
  const cls = r.hit_rate >= 55 ? "pos" : r.hit_rate <= 45 ? "neg" : "";
  return `<div class="bt-card"><span class="bt-lbl">${escapeHtml(label)}</span><b class="${cls}">${fmtNum(r.hit_rate, 1)}%</b><span class="bt-n">${r.n} samples</span></div>`;
}

function validationSection(v) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Model accuracy (backtested)"));
  s.appendChild(el("p", "muted", "Honest, out-of-sample check at the Nifty-50 level: does a positive overnight (US) lead actually precede a higher open?"));
  const gap = v.gap || {}; const fh = v.first_hour || {};
  const cards = el("div", "bt-grid");
  cards.innerHTML =
    rateChip("Baseline: any day opens up", gap.overall_gap_up_pct != null ? { hit_rate: gap.overall_gap_up_pct, n: gap.sample_days } : null) +
    rateChip("Opens up · overnight UP", gap.gap_up_when_overnight_up) +
    rateChip("Opens up · overnight DOWN", gap.gap_up_when_overnight_down) +
    rateChip("Gap holds 1st hour (after gap-up)", fh.first_hour_up_when_gap_up);
  s.appendChild(cards);
  const cal = gap.calibration || [];
  if (cal.length) {
    const wrap = el("div", "table-wrap");
    let html = `<table><thead><tr><th class="l">Overnight S&P 500 lead</th><th>Next-day gap-up rate</th><th>Avg gap</th><th>Samples</th></tr></thead><tbody>`;
    cal.forEach((b) => {
      const cls = b.hit_rate >= 55 ? "pos" : b.hit_rate <= 45 ? "neg" : "";
      html += `<tr><td class="l">${escapeHtml(b.bucket)}</td><td class="${cls}"><b>${fmtNum(b.hit_rate, 1)}%</b></td><td class="${signClass(b.avg_gap_pct)}">${fmtPct(b.avg_gap_pct)}</td><td>${b.n}</td></tr>`;
    });
    html += `</tbody></table>`;
    wrap.innerHTML = html;
    s.appendChild(wrap);
  }
  if (v.method) s.appendChild(el("p", "muted src-note", v.method));
  const disc = el("p", "premkt-disclaimer");
  disc.innerHTML = "⚠️ " + escapeHtml(v.caveat || "");
  s.appendChild(disc);
  return s;
}

function sourcesSection(src) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Sources & references"));
  const provider = src.provider
    ? `<p class="src-provider">Primary data provider: <a class="src-ref" href="${src.provider.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(src.provider.name)} ↗</a></p>` : "";
  const linkChips = (items) => (items || []).map((it) =>
    `<a class="src-ref" href="${it.url}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(it.symbol || "")}">${escapeHtml(it.label)} ↗</a>`).join("");
  const card = el("div", "card");
  card.innerHTML = `${provider}
    <h3 class="src-h">Global market cues</h3><div class="src-refs">${linkChips(src.global_cues)}</div>
    <h3 class="src-h">Gold ETFs (NSE)</h3><div class="src-refs">${linkChips(src.gold_etfs)}</div>
    ${src.note ? `<p class="muted src-note">${escapeHtml(src.note)}</p>` : ""}`;
  s.appendChild(card);
  return s;
}

// ================= PAPER TRADING =================
function initPaperTrading() { wirePaperEvents(); }

function wirePaperEvents() {
  const saveBtn = $("#paperSaveBtn"); const runBtn = $("#paperRunBtn"); const settleBtn = $("#paperSettleBtn");
  if (!saveBtn || saveBtn.dataset.wired) return;
  saveBtn.dataset.wired = "1";
  saveBtn.addEventListener("click", savePaperSettings);
  runBtn.addEventListener("click", () => runPaperSession(false));
  settleBtn.addEventListener("click", settlePaperTrades);
}

function paperMsg(text, kind) { const m = $("#paperMsg"); if (!m) return; m.textContent = text || ""; m.className = "paper-msg" + (kind ? " " + kind : ""); }

function readPaperSettingsForm() {
  return {
    budget_inr: Number($("#paperBudget")?.value || 10000),
    min_score: Number($("#paperMinScore")?.value || 54),
    min_market_bias: Number($("#paperMinBias")?.value || 50),
    max_stocks: Number($("#paperMaxStocks")?.value || 3),
  };
}
function fillPaperSettingsForm(s) {
  if (!s) return;
  [["paperBudget", "budget_inr"], ["paperMinScore", "min_score"], ["paperMinBias", "min_market_bias"], ["paperMaxStocks", "max_stocks"]]
    .forEach(([id, key]) => { const inp = document.getElementById(id); if (inp && s[key] != null) inp.value = s[key]; });
}
async function savePaperSettings() {
  paperMsg("Saving…");
  try {
    const j = await fetch("/api/paper/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(readPaperSettingsForm()) }).then((r) => r.json());
    fillPaperSettingsForm(j.settings); paperMsg("Settings saved.", "ok");
  } catch (e) { paperMsg("Could not save settings.", "err"); }
}
async function runPaperSession(force) {
  paperMsg(force ? "Re-running session…" : "Creating paper session…");
  try {
    const j = await fetch("/api/paper/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: !!force }) }).then((r) => r.json());
    if (!j.ok) { paperMsg(j.error || "Run failed.", "err"); return; }
    if (j.skipped) paperMsg(j.message || j.reason || "Session skipped for today.", "ok");
    else paperMsg(`Logged ${(j.trades || []).length} paper trade(s) for ${j.trade_date}.`, "ok");
    loadPaperDashboard();
  } catch (e) { paperMsg("Run failed — server unreachable.", "err"); }
}
async function settlePaperTrades() {
  paperMsg("Settling past trades against Yahoo OHLC…");
  try { const j = await fetch("/api/paper/settle", { method: "POST" }).then((r) => r.json()); paperMsg(`Settled ${j.settled || 0} trade(s).`, "ok"); loadPaperDashboard(); }
  catch (e) { paperMsg("Settle failed.", "err"); }
}
async function loadPaperDashboard() {
  try {
    const j = await fetch("/api/paper/dashboard").then((r) => r.json());
    fillPaperSettingsForm(j.settings); renderPaperPerformance(j.stats); renderPaperTradesTable(j.trades, j.skips);
  } catch (e) { const card = $("#paperPerfCard"); if (card) card.innerHTML = `<p class="muted">Could not load paper dashboard.</p>`; }
}
function renderPaperPerformance(stats) {
  const card = $("#paperPerfCard");
  if (!card || !stats) return;
  const pnlCls = stats.total_pnl_inr >= 0 ? "pos" : "neg";
  const wr = stats.win_rate != null ? `${fmtNum(stats.win_rate, 1)}%` : "n/a";
  card.innerHTML = `
    <h3 style="margin:0 0 12px;font-size:14px">Performance</h3>
    <div class="paper-stats">
      <div class="paper-stat"><div class="paper-stat-lbl">Total P&amp;L</div><div class="paper-stat-val ${pnlCls}">${stats.total_pnl_inr >= 0 ? "+" : ""}₹${fmtNum(stats.total_pnl_inr, 0)}</div></div>
      <div class="paper-stat"><div class="paper-stat-lbl">Win rate</div><div class="paper-stat-val">${wr}</div></div>
      <div class="paper-stat"><div class="paper-stat-lbl">Settled</div><div class="paper-stat-val">${stats.settled || 0}</div></div>
      <div class="paper-stat"><div class="paper-stat-lbl">Pending</div><div class="paper-stat-val">${stats.pending || 0}</div></div>
      <div class="paper-stat"><div class="paper-stat-lbl">W / L</div><div class="paper-stat-val">${stats.wins || 0} / ${stats.losses || 0}</div></div>
      <div class="paper-stat"><div class="paper-stat-lbl">Avg / trade</div><div class="paper-stat-val">${stats.avg_pnl_inr != null ? "₹" + fmtNum(stats.avg_pnl_inr, 0) : "n/a"}</div></div>
    </div>
    <div class="paper-chart-wrap"><canvas id="paperPnlChart"></canvas></div>
    ${exitBreakdownHtml(stats.exit_breakdown)}`;
  renderPaperChart(stats.cumulative || []);
}
function exitBreakdownHtml(bd) {
  if (!bd || !Object.keys(bd).length) return "";
  const chips = Object.entries(bd).map(([k, n]) => `<span class="conf-badge conf-med">${escapeHtml(k)}: ${n}</span>`).join(" ");
  return `<p class="muted" style="margin:8px 0 0;font-size:11.5px">Exit reasons: ${chips}</p>`;
}
function renderPaperChart(cumulative) {
  const canvas = document.getElementById("paperPnlChart");
  if (!canvas || typeof Chart === "undefined") return;
  if (PAPER_CHART) { PAPER_CHART.destroy(); PAPER_CHART = null; }
  if (!cumulative.length) { const wrap = canvas.parentElement; if (wrap) wrap.innerHTML = `<p class="muted" style="padding:40px 0;text-align:center">No settled trades yet — cumulative P&amp;L will appear here.</p>`; return; }
  const labels = cumulative.map((d) => d.date);
  const values = cumulative.map((d) => d.cumulative_pnl);
  const daily = cumulative.map((d) => d.daily_pnl);
  PAPER_CHART = new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [
      { label: "Cumulative P&L (₹)", data: values, borderColor: "#5b8cff", backgroundColor: "rgba(91,140,255,0.12)", fill: true, tension: 0.25, pointRadius: 4, yAxisID: "y" },
      { label: "Daily P&L (₹)", data: daily, type: "bar", backgroundColor: daily.map((v) => (v >= 0 ? "rgba(47,191,113,0.55)" : "rgba(239,93,108,0.55)")), yAxisID: "y" },
    ] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#93a0c0", boxWidth: 12 } } },
      scales: { x: { ticks: { color: "#93a0c0", maxRotation: 45 }, grid: { color: "rgba(42,51,82,0.5)" } },
        y: { ticks: { color: "#93a0c0", callback: (v) => "₹" + v }, grid: { color: "rgba(42,51,82,0.5)" } } } },
  });
}
function statusPill(status) { const st = (status || "pending").toLowerCase(); return `<span class="status-pill status-${escapeHtml(st)}">${escapeHtml(st)}</span>`; }
function renderPaperTradesTable(trades, skips) {
  const wrap = $("#paperTradesTable");
  if (!wrap) return;
  const rows = trades || [];
  if (!rows.length && !(skips || []).length) { wrap.innerHTML = `<p class="muted">No paper trades logged yet. Save settings and click <b>Run today</b>, or wait for the next prediction refresh.</p>`; return; }
  let html = `<div class="table-wrap"><table class="paper-trades-table"><thead><tr>
    <th class="l">Date</th><th class="l">Stock</th><th>Score</th><th>Qty</th><th>Entry</th><th>Exit</th><th>P&amp;L</th><th>Exit</th><th>Status</th>
  </tr></thead><tbody>`;
  rows.forEach((t) => {
    const pnl = t.pnl_inr; const pnlCls = pnl == null ? "" : pnl >= 0 ? "pos" : "neg";
    const entry = t.entry_price ?? t.signal_entry_price; const exit = t.exit_price;
    html += `<tr><td class="l">${escapeHtml(t.trade_date)}</td><td class="l">${yahooLink(t.ticker, escapeHtml(t.name || t.ticker))}</td>
      <td>${fmtNum(t.stock_score, 0)}</td><td>${t.qty}</td>
      <td>${entry != null ? "₹" + fmtNum(entry, 2) : "—"}</td><td>${exit != null ? "₹" + fmtNum(exit, 2) : "—"}</td>
      <td class="${pnlCls}">${pnl != null ? (pnl >= 0 ? "+" : "") + "₹" + fmtNum(pnl, 0) : "—"}</td>
      <td>${escapeHtml(t.exit_reason || "—")}</td><td>${statusPill(t.status)}</td></tr>`;
  });
  (skips || []).forEach((s) => {
    html += `<tr><td class="l">${escapeHtml(String(s.trade_date).slice(0, 10))}</td><td class="l" colspan="6"><span class="muted">${escapeHtml(s.reason)}</span></td><td>—</td><td>${statusPill("skipped")}</td></tr>`;
  });
  html += `</tbody></table></div>`;
  wrap.innerHTML = html;
}

// ================= boot =================
$("#refreshBtn").addEventListener("click", refreshActive);
$$("#tabs .tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
initPaperTrading();
updateRefreshLabel();
loadScreen();
loadPredictor();   // warm in the background so the tab is instant
loadPaperDashboard();
