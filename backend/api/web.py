"""Flask app — Multibagger Finder + Next-Day Predictor.

Two engines, each built in a background thread (live data takes time) and
cached in memory + MySQL:

  1. Multibagger screen   — hidden small-cap compounders (India + US).
  2. Next-day predictor   — which NSE stocks may open higher tomorrow.
  3. Paper trading        — simulated tracking of the next-day signals.

Endpoints:
    GET  /                     -> UI
    GET  /api/screen           -> multibagger screen (builds if stale)
    POST /api/screen/refresh   -> force a fresh screen
    GET  /api/premarket        -> next-day prediction (builds if stale)
    POST /api/refresh          -> force a fresh prediction
    GET  /healthz              -> health check
    + /api/paper/*             -> paper-trading endpoints
"""

from __future__ import annotations

import os
import threading
import time
import traceback
from typing import Callable

from flask import Flask, jsonify, render_template, request

from core import store
from paper import paper_db
from paper import paper_trading

# backend/ root (web.py lives in backend/api/); static + templates live there.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    static_folder=os.path.join(_BACKEND_DIR, "static"),
    template_folder=os.path.join(_BACKEND_DIR, "templates"),
)

SCREEN_TTL = float(os.environ.get("SCREEN_TTL_HOURS", 12)) * 3600.0
PREMARKET_TTL = float(os.environ.get("PREMARKET_TTL_MIN", 15)) * 60.0

SCREEN_KEY = "screen_latest"
PREMARKET_KEY = "premarket_latest"


class Engine:
    """A background-rebuildable, cached compute job."""

    def __init__(self, name: str, builder: Callable[[bool], dict], ttl: float, store_key: str):
        self.name = name
        self.builder = builder
        self.ttl = ttl
        self.store_key = store_key
        self.state = {"status": "idle", "data": None, "error": None, "ts": 0.0}
        self.lock = threading.Lock()

    def _compute(self, force: bool):
        try:
            data = self.builder(force)
            self.state.update({"data": data, "ts": time.time(),
                               "status": "ready", "error": None})
            store.save(data, self.store_key)
            self._after(data)
        except Exception as e:  # noqa: BLE001
            self.state.update({"error": str(e), "status": "error"})
            traceback.print_exc()

    def _after(self, data: dict):
        pass

    def start(self, force: bool = False) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            self.state["status"] = "running"
            if force:
                self.state["error"] = None
            threading.Thread(target=self._compute, args=(force,), daemon=True).start()
        return True

    def fresh(self) -> bool:
        return self.state["data"] is not None and (time.time() - self.state["ts"] < self.ttl)

    def warm(self):
        cached = store.load(self.store_key)
        if cached:
            self.state.update({"data": cached, "ts": time.time(), "status": "ready"})

    def payload(self, ttl_label: float) -> dict:
        if not self.fresh() and self.state["status"] != "running":
            self.start(force=False)
        return {"status": self.state["status"], "error": self.state["error"],
                "data": self.state["data"], "ttl": ttl_label}


def _build_screen(force: bool) -> dict:
    from signals.screener import build_screen
    return build_screen(force=force)


def _build_premarket(force: bool) -> dict:
    from predictor.market_sentiment import build_premarket
    return build_premarket(force=force)


class PremarketEngine(Engine):
    def _after(self, data: dict):
        try:
            paper_trading.create_session(data)
        except Exception:  # noqa: BLE001
            traceback.print_exc()


screen_engine = Engine("screen", _build_screen, SCREEN_TTL, SCREEN_KEY)
premarket_engine = PremarketEngine("premarket", _build_premarket, PREMARKET_TTL, PREMARKET_KEY)


def _build_portfolio(force: bool) -> dict:
    from portfolio.service import build
    return build(force)


portfolio_engine = Engine("portfolio", _build_portfolio, 1800.0, "portfolio_latest")


_SPA_DIR = os.path.join(_BACKEND_DIR, "static", "spa")
_SPA_INDEX = os.path.join(_SPA_DIR, "index.html")


def _serve_spa():
    if os.path.isfile(_SPA_INDEX):
        with open(_SPA_INDEX, encoding="utf-8") as fh:
            return fh.read()
    return render_template("index.html")


@app.route("/")
def index():
    return _serve_spa()


@app.route("/assets/<path:filename>")
def spa_assets(filename):
    # Vite emits hashed assets under /assets; serve them from the built SPA dir.
    from flask import send_from_directory
    return send_from_directory(os.path.join(_SPA_DIR, "assets"), filename)


# Client-side routes (deep links / refresh) → return the SPA shell. Anything
# that isn't an API call or a real asset falls through to here.
@app.route("/<path:path>")
def spa_catch_all(path):
    if path.startswith("api/") or path == "healthz":
        from flask import abort
        abort(404)
    served = os.path.join(_SPA_DIR, path)
    if os.path.isfile(served):
        from flask import send_from_directory
        return send_from_directory(_SPA_DIR, path)
    return _serve_spa()


# ---------- multibagger screen ----------

@app.route("/api/screen")
def api_screen():
    return jsonify(screen_engine.payload(SCREEN_TTL / 3600.0))


@app.route("/api/screen/refresh", methods=["POST"])
def api_screen_refresh():
    started = screen_engine.start(force=True)
    return jsonify({"started": started, "status": screen_engine.state["status"]})


# ---------- next-day predictor ----------

@app.route("/api/premarket")
def api_premarket():
    return jsonify(premarket_engine.payload(PREMARKET_TTL / 60.0))


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    started = premarket_engine.start(force=True)
    return jsonify({"started": started, "status": premarket_engine.state["status"]})


# ---------- options / F&O ----------

@app.route("/api/options")
def api_options():
    from signals import options
    ticker = request.args.get("ticker", "")
    market = request.args.get("market") or None
    return jsonify(options.analyze(ticker, market))


# ---------- comprehensive per-stock fundamentals (drill-down) ----------

_fund_cache: dict = {}
_FUND_TTL = 1800.0  # 30 min


@app.route("/api/fundamentals")
def api_fundamentals():
    from data import fundamentals
    ticker = (request.args.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"available": False, "reason": "No ticker given"}), 400
    cached = _fund_cache.get(ticker)
    if cached and (time.time() - cached["ts"] < _FUND_TTL):
        return jsonify(cached["data"])
    data = fundamentals.fetch_full(ticker)
    _fund_cache[ticker] = {"data": data, "ts": time.time()}
    return jsonify(data)


# ---------- analyze any company (search + full algo on one stock) ----------

@app.route("/api/symbols/search")
def api_symbols_search():
    from data import symbols
    q = request.args.get("q", "")
    return jsonify({"results": symbols.search(q, limit=12)})


_analyze_cache: dict = {}
_ANALYZE_TTL = 900.0  # 15 min


@app.route("/api/analyze")
def api_analyze():
    from signals.screener import analyze_ticker
    ticker = (request.args.get("ticker") or "").strip()
    strat = (request.args.get("strategy") or "").strip()
    if not ticker:
        return jsonify({"available": False, "reason": "No ticker given"}), 400
    cache_key = f"{ticker}|{strat}"
    cached = _analyze_cache.get(cache_key)
    if cached and (time.time() - cached["ts"] < _ANALYZE_TTL):
        return jsonify(cached["data"])
    data = analyze_ticker(ticker, strat or None)
    _analyze_cache[cache_key] = {"data": data, "ts": time.time()}
    return jsonify(data)


@app.route("/api/history")
def api_history():
    from data import history
    ticker = (request.args.get("ticker") or "").strip()
    rng = request.args.get("range", "1y")
    if not ticker:
        return jsonify({"available": False, "reason": "No ticker given"}), 400
    return jsonify(history.history(ticker, rng))


@app.route("/api/score-history")
def api_score_history():
    from core import score_history
    ticker = (request.args.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"available": False, "reason": "No ticker given"}), 400
    series = score_history.history_for(ticker)
    return jsonify({"available": bool(series), "ticker": ticker, "series": series})


_bt_cache: dict = {}


@app.route("/api/backtest")
def api_backtest():
    from signals import backtest_scores
    now = time.time()
    if _bt_cache.get("data") and now - _bt_cache.get("ts", 0) < 3600:
        return jsonify(_bt_cache["data"])
    data = backtest_scores.run()
    _bt_cache["data"] = data
    _bt_cache["ts"] = now
    return jsonify(data)


_cmp_cache: dict = {}


@app.route("/api/strategy-compare")
def api_strategy_compare():
    from signals import strategy_compare
    now = time.time()
    if _cmp_cache.get("data") and now - _cmp_cache.get("ts", 0) < 3600:
        return jsonify(_cmp_cache["data"])
    data = strategy_compare.compare()
    _cmp_cache["data"] = data
    _cmp_cache["ts"] = now
    return jsonify(data)


# ---------- portfolio (real holdings: manual / CSV / broker API) ----------

@app.route("/api/portfolio")
def api_portfolio():
    return jsonify(portfolio_engine.payload(0.5))


@app.route("/api/portfolio/add", methods=["POST"])
def api_portfolio_add():
    from portfolio import holdings_store
    b = request.get_json(silent=True) or {}
    if not (b.get("symbol") or "").strip():
        return jsonify({"ok": False, "reason": "symbol required"}), 400
    holdings_store.add(b.get("broker", "Manual"), b["symbol"], b.get("market", "IN"),
                       b.get("quantity"), b.get("avg_price"))
    portfolio_engine.start(force=True)
    return jsonify({"ok": True})


@app.route("/api/portfolio/upload", methods=["POST"])
def api_portfolio_upload():
    from portfolio import holdings_store, csv_import
    b = request.get_json(silent=True) or {}
    broker = (b.get("broker") or "CSV").strip() or "CSV"
    market = b.get("market") if b.get("market") in ("IN", "BSE", "US") else "IN"
    items = csv_import.parse_csv(b.get("csv") or "")
    for it in items:
        it["broker"] = broker
        it["market"] = market
    n = holdings_store.add_many(items)
    portfolio_engine.start(force=True)
    return jsonify({"ok": True, "added": n})


@app.route("/api/portfolio/cas", methods=["POST"])
def api_portfolio_cas():
    from portfolio import holdings_store, cas_import
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "reason": "No file uploaded"}), 400
    password = request.form.get("password", "")   # transient — never stored or logged
    res = cas_import.parse_cas(f.read(), password)
    if not res.get("available"):
        return jsonify({"ok": False, "reason": res.get("reason", "Could not parse the CAS")})
    n = holdings_store.add_many(res["holdings"])
    portfolio_engine.start(force=True)
    return jsonify({"ok": True, "added": n, "note": res.get("note"), "sample": res.get("sample")})


@app.route("/api/portfolio/remove", methods=["POST"])
def api_portfolio_remove():
    from portfolio import holdings_store
    b = request.get_json(silent=True) or {}
    if b.get("id"):
        holdings_store.remove(b["id"])
        portfolio_engine.start(force=True)
    return jsonify({"ok": True})


@app.route("/api/portfolio/clear", methods=["POST"])
def api_portfolio_clear():
    from portfolio import holdings_store
    holdings_store.clear()
    portfolio_engine.start(force=True)
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "screen": screen_engine.state["status"],
                    "premarket": premarket_engine.state["status"]})


# ---------- paper trading (simulated, no real orders) ----------

@app.route("/api/paper/settings", methods=["GET"])
def api_paper_settings_get():
    return jsonify({"settings": paper_trading.get_settings(),
                    "defaults": paper_trading.DEFAULT_SETTINGS})


@app.route("/api/paper/settings", methods=["POST"])
def api_paper_settings_post():
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "settings": paper_trading.save_settings(body)})


@app.route("/api/paper/run", methods=["POST"])
def api_paper_run():
    body = request.get_json(silent=True) or {}
    pm = premarket_engine.state.get("data")
    if not pm:
        return jsonify({"ok": False, "error": "No prediction yet — refresh first."}), 400
    return jsonify(paper_trading.create_session(pm, force=bool(body.get("force"))))


@app.route("/api/paper/settle", methods=["POST"])
def api_paper_settle():
    return jsonify({"ok": True, **paper_trading.settle_pending()})


@app.route("/api/paper/dashboard")
def api_paper_dashboard():
    paper_trading.settle_pending()
    trades = paper_db.list_trades(limit=500)
    skips = paper_db.list_skips(limit=30)
    return jsonify({
        "settings": paper_trading.get_settings(),
        "stats": paper_trading.compute_stats(trades),
        "trades": trades,
        "skips": skips,
    })


# ---------- boot: warm from MySQL, then refresh live ----------
paper_db.init_paper_db()
screen_engine.warm()
premarket_engine.warm()
portfolio_engine.warm()
screen_engine.start(force=False)
premarket_engine.start(force=False)


def _warm_symbols():
    try:
        from data import symbols
        symbols.nse_equities(); symbols.us_equities(); symbols.bse_equities()
        symbols._all_symbols_for_search()
    except Exception:  # noqa: BLE001
        pass


threading.Thread(target=_warm_symbols, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
