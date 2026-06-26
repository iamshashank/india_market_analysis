"""Paper-trading simulator (Option A) — no real broker orders.

Uses the premarket predictor to pick stocks, allocates a configurable budget,
logs every simulated trade to the database, and settles against Yahoo Finance
OHLC once the session has traded.

Exit model (MIS-style intraday):
  * Enter at the actual open
  * Exit at stop, target, or first-hour close — whichever comes first on 5m bars
"""

from __future__ import annotations

import datetime as _dt
import os
import warnings
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import paper_db

DEFAULT_SETTINGS: Dict[str, Any] = {
    "budget_inr": 10_000,
    "min_score": 54,
    "min_market_bias": 50,
    "max_stocks": 3,
}

IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
MARKET_OPEN = _dt.time(9, 15)
FIRST_HOUR_EXIT = _dt.time(10, 15)
BROKERAGE_PER_SIDE = float(os.environ.get("PAPER_BROKERAGE", "20"))


def get_settings() -> dict:
    stored = paper_db.load_settings()
    out = dict(DEFAULT_SETTINGS)
    if stored:
        out.update({k: stored[k] for k in DEFAULT_SETTINGS if k in stored})
    return out


def save_settings(data: dict) -> dict:
    merged = get_settings()
    for key in DEFAULT_SETTINGS:
        if key in data:
            merged[key] = _coerce_setting(key, data[key])
    paper_db.save_settings(merged)
    return merged


def _coerce_setting(key: str, val: Any) -> Any:
    if key == "max_stocks":
        return max(1, min(10, int(val)))
    if key in ("budget_inr", "min_score", "min_market_bias"):
        return max(0, int(val))
    return val


def _all_candidates(premarket: dict) -> List[dict]:
    return list(premarket.get("high_confidence") or []) + list(premarket.get("watchlist") or [])


def select_picks(premarket: dict, settings: Optional[dict] = None) -> tuple[List[dict], Optional[str]]:
    """Return stocks that pass filters, or ( [], skip_reason )."""
    settings = settings or get_settings()
    bias = (premarket.get("market_bias") or {}).get("score")
    if bias is not None and bias < settings["min_market_bias"]:
        return [], f"Market bias {bias} below minimum {settings['min_market_bias']}"

    min_score = settings["min_score"]
    picks = [s for s in _all_candidates(premarket) if s.get("score", 0) >= min_score]
    picks.sort(key=lambda x: x.get("score", 0), reverse=True)
    picks = picks[: settings["max_stocks"]]
    if not picks:
        return [], f"No stocks with score ≥ {min_score}"
    return picks, None


def _qty_for_budget(price: float, allocation: float) -> int:
    if not price or price <= 0:
        return 0
    return int(allocation // price)


def create_session(premarket: dict, settings: Optional[dict] = None, force: bool = False) -> dict:
    """Create paper trades for ``predict_for`` if none exist yet."""
    settings = settings or get_settings()
    trade_date = premarket.get("predict_for")
    if not trade_date:
        return {"ok": False, "error": "No predict_for date in premarket payload"}

    if not force and paper_db.has_session(trade_date):
        existing = paper_db.list_trades(limit=500)
        day_trades = [t for t in existing if t.get("trade_date") == trade_date]
        return {
            "ok": True,
            "skipped": True,
            "trade_date": trade_date,
            "trades": day_trades,
            "message": f"Paper session already exists for {trade_date}",
        }

    picks, skip = select_picks(premarket, settings)
    if skip:
        paper_db.log_skip(
            trade_date=trade_date,
            reason=skip,
            market_bias=(premarket.get("market_bias") or {}).get("score"),
            settings=settings,
        )
        return {"ok": True, "skipped": True, "trade_date": trade_date, "reason": skip, "trades": []}

    n = len(picks)
    per_stock = settings["budget_inr"] / n
    market_bias = (premarket.get("market_bias") or {}).get("score")
    rows: List[dict] = []

    for stock in picks:
        price = float(stock.get("price") or 0)
        qty = _qty_for_budget(price, per_stock)
        if qty < 1:
            continue
        allocated = round(qty * price, 2)
        rows.append({
            "trade_date": trade_date,
            "ticker": stock["ticker"],
            "name": stock.get("name"),
            "confidence": stock.get("confidence"),
            "stock_score": stock.get("score"),
            "market_bias_score": market_bias,
            "qty": qty,
            "signal_entry_price": price,
            "stop_pct": stock.get("stop_pct"),
            "target_pct": stock.get("target_pct"),
            "stop_price": stock.get("stop_price"),
            "target_price": stock.get("target_price"),
            "budget_allocated": allocated,
            "status": "pending",
            "settings_snapshot": dict(settings),
            "signal_snapshot": {
                "verdict": stock.get("verdict"),
                "sector": stock.get("sector"),
                "atr_pct": stock.get("atr_pct"),
            },
        })

    if not rows:
        return {"ok": False, "error": "Budget too small for any pick at current prices"}

    if force:
        paper_db.delete_session(trade_date)
    inserted = paper_db.insert_trades(rows)
    return {
        "ok": True,
        "skipped": False,
        "trade_date": trade_date,
        "trades": inserted,
        "settings": settings,
    }


def _parse_trade_date(s: str) -> _dt.date:
    return _dt.date.fromisoformat(s[:10])


def _fetch_day_bars(ticker: str, trade_date: _dt.date):
    if yf is None:
        return None, None
    start = trade_date.isoformat()
    end = (trade_date + _dt.timedelta(days=1)).isoformat()
    try:
        t = yf.Ticker(ticker)
        daily = t.history(start=start, end=end, interval="1d", auto_adjust=True)
        intraday = t.history(start=start, end=end, interval="5m", auto_adjust=True)
        return daily, intraday
    except Exception:  # noqa: BLE001
        return None, None


def _simulate_exit(
    entry: float,
    stop_pct: float,
    target_pct: float,
    intraday,
) -> tuple[float, str, Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Walk 5m bars; return exit_price, reason, open, high, low, close."""
    stop = entry * (1 - stop_pct / 100.0)
    target = entry * (1 + target_pct / 100.0)

    if intraday is None or intraday.empty:
        return entry, "no_data", None, None, None, None

    df = intraday.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(IST)

    day_bars = df[df.index.map(lambda x: x.date()) == td]
    if day_bars.empty:
        day_bars = df

    actual_open = float(day_bars.iloc[0]["Open"])
    actual_high = float(day_bars["High"].max())
    actual_low = float(day_bars["Low"].min())
    actual_close = float(day_bars.iloc[-1]["Close"])
    entry = actual_open

    stop = entry * (1 - stop_pct / 100.0)
    target = entry * (1 + target_pct / 100.0)

    exit_price = entry
    exit_reason = "time_exit"
    time_exit_bar = None

    for ts, row in day_bars.iterrows():
        t = ts.time()
        if t < MARKET_OPEN:
            continue
        low = float(row["Low"])
        high = float(row["High"])
        if low <= stop:
            return stop, "stop", actual_open, actual_high, actual_low, actual_close
        if high >= target:
            return target, "target", actual_open, actual_high, actual_low, actual_close
        if t >= FIRST_HOUR_EXIT:
            time_exit_bar = float(row["Close"])
            break

    if time_exit_bar is not None:
        exit_price = time_exit_bar
    elif not day_bars.empty:
        # Use last bar before/at first hour if session was short
        mask = day_bars.index.time >= MARKET_OPEN
        subset = day_bars[mask]
        if not subset.empty:
            exit_price = float(subset.iloc[min(len(subset) - 1, 11)]["Close"])

    return exit_price, exit_reason, actual_open, actual_high, actual_low, actual_close


def settle_pending(as_of: Optional[_dt.date] = None) -> dict:
    """Settle all pending trades whose trade_date is strictly before today (IST)."""
    as_of = as_of or _dt.datetime.now(IST).date()
    pending = paper_db.list_trades(status="pending", limit=500)
    settled = []
    errors = []

    for trade in pending:
        td = _parse_trade_date(trade["trade_date"])
        if td >= as_of:
            continue
        try:
            result = _settle_one(trade)
            settled.append(result)
        except Exception as e:  # noqa: BLE001
            errors.append({"id": trade.get("id"), "ticker": trade.get("ticker"), "error": str(e)})

    return {"settled": len(settled), "trades": settled, "errors": errors}


def _settle_one(trade: dict) -> dict:
    td = _parse_trade_date(trade["trade_date"])
    ticker = trade["ticker"]
    qty = int(trade["qty"])
    stop_pct = float(trade.get("stop_pct") or 1.5)
    target_pct = float(trade.get("target_pct") or 2.25)

    daily, intraday = _fetch_day_bars(ticker, td)
    if daily is None or daily.empty:
        paper_db.update_trade(trade["id"], {
            "status": "failed",
            "exit_reason": "no_market_data",
            "settled_at": _dt.datetime.now(IST).isoformat(),
        })
        return {"id": trade["id"], "status": "failed", "reason": "no_market_data"}

    signal_entry = float(trade.get("signal_entry_price") or daily.iloc[0]["Open"])
    exit_px, reason, o, h, l, c = _simulate_exit(signal_entry, stop_pct, target_pct, intraday)

    if o is None:
        o = float(daily.iloc[0]["Open"])
        h = float(daily.iloc[0]["High"])
        l = float(daily.iloc[0]["Low"])
        c = float(daily.iloc[0]["Close"])
        exit_px = c
        reason = "daily_fallback"

    gross = (exit_px - o) * qty
    charges = BROKERAGE_PER_SIDE * 2
    pnl = round(gross - charges, 2)
    pnl_pct = round((exit_px / o - 1) * 100, 2) if o else 0

    update = {
        "status": "settled",
        "actual_open": round(o, 2),
        "actual_high": round(h, 2),
        "actual_low": round(l, 2),
        "actual_close": round(c, 2),
        "entry_price": round(o, 2),
        "exit_price": round(exit_px, 2),
        "exit_reason": reason,
        "pnl_inr": pnl,
        "pnl_pct": pnl_pct,
        "charges_inr": charges,
        "settled_at": _dt.datetime.now(IST).isoformat(),
    }
    paper_db.update_trade(trade["id"], update)
    return {"id": trade["id"], "ticker": ticker, **update}


def compute_stats(trades: Optional[List[dict]] = None) -> dict:
    trades = trades if trades is not None else paper_db.list_trades(limit=2000)
    settled = [t for t in trades if t.get("status") == "settled"]
    pending = [t for t in trades if t.get("status") == "pending"]
    skipped = [t for t in trades if t.get("status") == "skipped"]
    failed = [t for t in trades if t.get("status") == "failed"]

    total_pnl = sum(float(t.get("pnl_inr") or 0) for t in settled)
    wins = [t for t in settled if (t.get("pnl_inr") or 0) > 0]
    losses = [t for t in settled if (t.get("pnl_inr") or 0) < 0]

    # Cumulative P&L by trade_date
    by_date: Dict[str, float] = {}
    for t in sorted(settled, key=lambda x: x.get("trade_date", "")):
        d = t.get("trade_date", "")
        by_date[d] = by_date.get(d, 0) + float(t.get("pnl_inr") or 0)

    cumulative = []
    running = 0.0
    for d in sorted(by_date.keys()):
        running += by_date[d]
        cumulative.append({"date": d, "daily_pnl": round(by_date[d], 2), "cumulative_pnl": round(running, 2)})

    # Per-stock aggregate
    by_ticker: Dict[str, dict] = {}
    for t in settled:
        tk = t.get("ticker", "")
        if tk not in by_ticker:
            by_ticker[tk] = {"ticker": tk, "name": t.get("name"), "trades": 0, "pnl": 0.0, "wins": 0}
        by_ticker[tk]["trades"] += 1
        by_ticker[tk]["pnl"] += float(t.get("pnl_inr") or 0)
        if (t.get("pnl_inr") or 0) > 0:
            by_ticker[tk]["wins"] += 1

    top_stocks = sorted(by_ticker.values(), key=lambda x: x["pnl"], reverse=True)[:8]

    exit_breakdown: Dict[str, int] = {}
    for t in settled:
        r = t.get("exit_reason") or "unknown"
        exit_breakdown[r] = exit_breakdown.get(r, 0) + 1

    n_settled = len(settled)
    return {
        "total_trades": len(trades),
        "settled": n_settled,
        "pending": len(pending),
        "skipped_days": len(skipped),
        "failed": len(failed),
        "win_rate": round(len(wins) / n_settled * 100, 1) if n_settled else None,
        "total_pnl_inr": round(total_pnl, 2),
        "avg_pnl_inr": round(total_pnl / n_settled, 2) if n_settled else None,
        "wins": len(wins),
        "losses": len(losses),
        "cumulative": cumulative,
        "top_stocks": top_stocks,
        "exit_breakdown": exit_breakdown,
    }
