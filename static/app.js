"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

let POLL = null;

const fmtNum = (x, nd = 1) => (x === null || x === undefined ? "n/a" : Number(x).toFixed(nd));
const signClass = (x) => (x === null || x === undefined ? "" : x >= 0 ? "pos" : "neg");
const fmtPct = (v) => (v === null || v === undefined ? "n/a" : (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%");

function escapeHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function yahooLink(ticker, innerHtml) {
  const url = ticker ? `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}` : "#";
  return `<a class="stock-link" href="${url}" target="_blank" rel="noopener noreferrer" title="Open on Yahoo Finance">${innerHtml}</a>`;
}

function showBanner(msg) {
  const b = $("#banner");
  b.textContent = msg;
  b.classList.remove("hidden");
}
function hideBanner() {
  $("#banner").classList.add("hidden");
}
function showLoading(text) {
  $("#content").innerHTML =
    `<div class="loading"><div class="spinner"></div><p id="loadingText">${text}</p></div>`;
}

// ---------- data ----------
async function load() {
  try {
    const j = await fetch("/api/premarket").then((r) => r.json());

    if (j.status === "running" && !j.data) {
      showLoading("Reading global markets, futures &amp; commodities… (~30–60s)");
      ensurePolling();
      return;
    }
    if (j.status === "error" && !j.data) {
      stopPolling();
      showBanner("Could not build prediction: " + (j.error || "unknown error") + ". Try Refresh.");
      return;
    }
    if (j.data) {
      render(j.data);
      if (j.status === "running") {
        showBanner("Updating with the latest cues…");
        ensurePolling();
      } else {
        hideBanner();
        stopPolling();
      }
      return;
    }
    ensurePolling();
  } catch (e) {
    showBanner("Could not reach server. Retrying…");
    ensurePolling();
  }
}

function ensurePolling() {
  if (!POLL) POLL = setInterval(load, 4000);
}
function stopPolling() {
  if (POLL) { clearInterval(POLL); POLL = null; }
}

async function refresh() {
  const btn = $("#refreshBtn");
  btn.disabled = true;
  btn.textContent = "↻ Running…";
  try {
    await fetch("/api/refresh", { method: "POST" });
    showLoading("Refreshing with the latest cues… (~30–60s)");
    ensurePolling();
  } catch (e) {
    showBanner("Could not reach server. Try again.");
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = "↻ Refresh"; }, 3000);
}

// ---------- render ----------
function render(pm) {
  hideBanner();
  $("#generated").textContent = pm.as_of ? "As of " + pm.as_of : "";
  $("#disclaimer").textContent = pm.disclaimer || "";

  const c = $("#content");
  c.innerHTML = "";
  c.appendChild(biasSection(pm));
  c.appendChild(predictionSection(pm));
  if (pm.gold_etf) c.appendChild(goldSection(pm.gold_etf));
  if (pm.validation) c.appendChild(validationSection(pm.validation));
  if (pm.sources) c.appendChild(sourcesSection(pm.sources));
}

// ---------- market bias + cue strip ----------
function biasSection(pm) {
  const s = el("section", "section");
  const b = pm.market_bias || {};
  const cls = b.score >= 60 ? "pos" : b.score <= 40 ? "neg" : "";
  const cueCards = (pm.cue_strip || []).map((cu) =>
    `<div class="cue-card"><span class="cue-lbl">${escapeHtml(cu.label)}</span><b class="${signClass(cu.change_pct)}">${fmtPct(cu.change_pct)}</b></div>`
  ).join("");

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

// ---------- stock prediction (two confidence buckets) ----------
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
    entry: "Entry: the price to buy at (≈ expected open). Your reference/start point for the trade.",
    stop: "Stop-loss: exit here if you're wrong, to cap the loss. Sized to this stock's volatility (ATR). The most important number for survival.",
    target: "Target: take-profit price. Book the gain here instead of getting greedy.",
    rr: "Risk:Reward — potential gain vs potential loss. 1:1.5 means risking ₹1 to make ₹1.5, so you can profit even when right less than half the time.",
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
    `Liquid NSE names (≥ ₹${fmtNum(pm.liquidity_floor_cr, 0)} cr/day) ranked by overnight cues, sector sensitivity & beta. ` +
    `ADR-linked names are intentionally excluded. Every idea includes an ATR-based stop & target — not a guarantee.`));

  if (!high.length && !watch.length) {
    s.appendChild(el("p", "muted callout",
      "Overnight cues are weak or mixed — no liquid NSE names show a clear up-bias for the open. On days like this, the disciplined move is often to stay out."));
    return s;
  }

  if (high.length) {
    s.appendChild(el("h3", "bucket-title pos", "Higher-confidence (liquid · clear bias)"));
    const wrap = el("div", "premkt-list");
    high.forEach((it, i) => wrap.appendChild(stockCard(it, i + 1)));
    s.appendChild(wrap);
  }

  if (watch.length) {
    s.appendChild(el("h3", "bucket-title",
      "Watchlist (lower confidence — sector/beta only)"));
    const wrap = el("div", "premkt-list");
    watch.forEach((it, i) => wrap.appendChild(stockCard(it, i + 1)));
    s.appendChild(wrap);
  }
  return s;
}

// ---------- gold ETF prediction (with range) ----------
function goldSection(g) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Gold ETF prediction (next day)"));

  const impl = g.implied_move_pct;
  const dirCls = impl === null || impl === undefined ? "" : impl > 0.3 ? "pos" : impl < -0.3 ? "neg" : "";
  const rangeTxt = (g.range_low_pct != null && g.range_high_pct != null)
    ? `${fmtPct(g.range_low_pct)} to ${fmtPct(g.range_high_pct)}`
    : (impl != null ? fmtPct(impl) : "n/a");
  const drivers = (g.drivers || []).map((d) =>
    `<li><b>${escapeHtml(d.label)}</b> ${fmtPct(d.change_pct)} — ${escapeHtml(d.effect)}</li>`
  ).join("");

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
    let html = `<table><thead><tr>
      <th class="l">Gold ETF</th><th>Last close</th><th>Prev chg</th>
      <th>Est. next range</th></tr></thead><tbody>`;
    etfs.forEach((e) => {
      const range = (e.est_low != null && e.est_high != null)
        ? `₹${fmtNum(e.est_low, 2)} – ₹${fmtNum(e.est_high, 2)}`
        : "n/a";
      html += `<tr>
        <td class="l">${yahooLink(e.ticker, escapeHtml(e.name))}<div class="hl-meta">${escapeHtml(e.ticker)}</div></td>
        <td>₹${fmtNum(e.last_close, 2)}</td>
        <td class="${signClass(e.last_change_pct)}">${fmtPct(e.last_change_pct)}</td>
        <td><b>${range}</b></td>
      </tr>`;
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

// ---------- backtest / accuracy ----------
function rateChip(label, r) {
  if (!r) return `<div class="bt-card"><span class="bt-lbl">${escapeHtml(label)}</span><b>n/a</b></div>`;
  const cls = r.hit_rate >= 55 ? "pos" : r.hit_rate <= 45 ? "neg" : "";
  return `<div class="bt-card">
    <span class="bt-lbl">${escapeHtml(label)}</span>
    <b class="${cls}">${fmtNum(r.hit_rate, 1)}%</b>
    <span class="bt-n">${r.n} samples</span>
  </div>`;
}

function validationSection(v) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Model accuracy (backtested)"));
  s.appendChild(el("p", "muted",
    "Honest, out-of-sample check at the Nifty-50 level: does a positive overnight (US) lead actually precede a higher open — and does that gap hold the first hour?"));

  const gap = v.gap || {};
  const fh = v.first_hour || {};

  const cards = el("div", "bt-grid");
  cards.innerHTML =
    rateChip("Baseline: any day opens up", gap.overall_gap_up_pct != null ? { hit_rate: gap.overall_gap_up_pct, n: gap.sample_days } : null) +
    rateChip("Opens up · overnight UP", gap.gap_up_when_overnight_up) +
    rateChip("Opens up · overnight DOWN", gap.gap_up_when_overnight_down) +
    rateChip("Gap holds 1st hour (after gap-up)", fh.first_hour_up_when_gap_up);
  s.appendChild(cards);

  // calibration table
  const cal = gap.calibration || [];
  if (cal.length) {
    const wrap = el("div", "table-wrap");
    let html = `<table><thead><tr><th class="l">Overnight S&P 500 lead</th><th>Next-day gap-up rate</th><th>Avg gap</th><th>Samples</th></tr></thead><tbody>`;
    cal.forEach((b) => {
      const cls = b.hit_rate >= 55 ? "pos" : b.hit_rate <= 45 ? "neg" : "";
      html += `<tr>
        <td class="l">${escapeHtml(b.bucket)}</td>
        <td class="${cls}"><b>${fmtNum(b.hit_rate, 1)}%</b></td>
        <td class="${signClass(b.avg_gap_pct)}">${fmtPct(b.avg_gap_pct)}</td>
        <td>${b.n}</td>
      </tr>`;
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

// ---------- sources ----------
function sourcesSection(src) {
  const s = el("section", "section");
  s.appendChild(el("h2", null, "Sources & references"));
  s.appendChild(el("p", "muted",
    "Every data feed used to curate the lists above. Click any source to verify it yourself."));

  const provider = src.provider
    ? `<p class="src-provider">Primary data provider: <a class="src-ref" href="${src.provider.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(src.provider.name)} ↗</a></p>`
    : "";

  const linkChips = (items) => (items || []).map((it) =>
    `<a class="src-ref" href="${it.url}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(it.symbol || "")}">${escapeHtml(it.label)} ↗</a>`
  ).join("");

  const card = el("div", "card");
  card.innerHTML = `
    ${provider}
    <h3 class="src-h">Global market cues</h3>
    <div class="src-refs">${linkChips(src.global_cues)}</div>
    <h3 class="src-h">Gold ETFs (NSE)</h3>
    <div class="src-refs">${linkChips(src.gold_etfs)}</div>
    <h3 class="src-h">Per-stock fundamentals</h3>
    <div class="src-refs">
      <a class="src-ref" href="${(src.fundamentals && src.fundamentals.url) || "#"}" target="_blank" rel="noopener noreferrer">${escapeHtml((src.fundamentals && src.fundamentals.label) || "Stock fundamentals")} ↗</a>
    </div>
    ${src.note ? `<p class="muted src-note">${escapeHtml(src.note)}</p>` : ""}`;
  s.appendChild(card);
  return s;
}

// ---------- boot ----------
$("#refreshBtn").addEventListener("click", refresh);
load();
