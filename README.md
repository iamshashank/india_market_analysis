# Market Intelligence — Multibagger Finder + Next-Day Predictor

A self-contained Python + Flask app with two engines:

1. **Multibagger Finder** *(primary)* — a rules-based screen across **India (NSE)
   and US** markets that surfaces under-the-radar small-cap compounders and
   concentrates the best ideas into a high-conviction portfolio.
2. **Next-Day Predictor** *(kept)* — estimates which liquid NSE stocks are most
   likely to **open higher tomorrow** from overnight global cues, with a paper-
   trading lab that tracks how those signals would have performed.

> ⚠️ **EDUCATIONAL / RESEARCH TOOL — NOT INVESTMENT ADVICE.** This is an
> automated screen of public data (Yahoo Finance, unofficial & delayed).
> Small-cap and low-coverage stocks are illiquid and high-risk. Do your own
> research and consult a SEBI/SEC-registered adviser before investing.

## The multibagger strategy

The screen encodes four ideas, plus the supporting fundamentals a real
compounder needs. Each pillar is a 0-100 score (percentile-ranked within the
universe where relative); the weighted blend is the composite.

| Pillar | Weight | What it rewards |
|--------|:------:|-----------------|
| **Small base** | 18% | Genuinely small market cap (with a liquidity floor) — room to compound |
| **Earnings consistency** | 20% | Steady / rising quarterly earnings, low volatility, few loss quarters |
| **Limited coverage** | 15% | Few analysts + little news + lower institutional ownership = overlooked |
| **Growth** | 15% | Revenue & earnings growth runway |
| **Quality** | 14% | ROE, margins, free cash flow, low debt |
| **Valuation** | 8% | Not paying an absurd price (PEG, P/B) |
| **News catalyst** | 10% | Recent events (orders, approvals, expansion…) scored by a finance lexicon |

**Concentration (high conviction):** `build_portfolio` takes the top names above
`MIN_SCORE`, applies a per-sector cap, and tilts weights toward the best ideas
(weight ∝ score², clipped to a sane band). Each pick gets a conviction tier,
suggested weight, position-size tier, a thesis, key risks and recent headlines.

All thresholds live in `config.py`, so the output is explainable and
reproducible.

## Repository layout

```
backend/      Flask app + all Python modules (flat imports) + static/ + templates/
frontend/     React + Vite SPA (builds into ../backend/static/spa)
pipelines/    Scheduled data-accumulation jobs
  nightly/    scan.py — broad-market multibagger scan → MySQL
  preopen/    cron_refresh.py — refresh the next-day predictor (~08:40 IST)
  weekly/     (planned)
Dockerfile · Procfile · render.yaml   deploy config
```

The backend modules import each other by flat name, so the app runs **from the
`backend/` directory** (`gunicorn --chdir backend web:app`). Pipeline scripts add
`backend/` to `sys.path` via a 2-line bootstrap, so they reuse the same code.

## Frontend (React SPA)

The UI is a **React + Vite single-page app** in `frontend/`, built to
`backend/static/spa/` and served by Flask. Five tabs + a searchable **glossary drawer**:

| Tab | What it shows |
|-----|---------------|
| 🚀 Multibagger Finder | Concentrated portfolio + full ranked shortlist (with a candlestick badge per name) |
| 🔥 Themes | Theme & sentiment heatmap (AI/deep-tech, semis, renewables, EV, defense…) |
| 📊 Options / F&O | Put/call ratio, max-pain, ATM IV, support/resistance — US (yfinance) + India (NSE best-effort) |
| 🔔 Next-Day Predictor | Overnight-cue open prediction (unchanged) |
| 🧪 Paper Trading | Simulated tracking of the next-day signals |

```bash
cd frontend && npm install
npm run dev      # Vite dev server :5173, proxies /api + /static to Flask :8000
npm run build    # outputs to ../backend/static/spa (what Flask serves in production)
```

The 📖 **Glossary** button opens a slide-out drawer with plain-English
definitions for every metric, acronym and candlestick pattern.

## Architecture (`backend/`)

| File | Purpose |
|------|---------|
| `config.py` | All tunable weights / bands / env config |
| `universe.py` · `universe_extended.py` | Curated + extended India/US small-cap universe |
| `fundamentals.py` | yfinance fetch: ratios, quarterly earnings series, analyst count, FCF; plus `fetch_full` (all ratios + income/balance/cashflow + health scores) |
| `quality_scores.py` | Piotroski F, Altman Z, Beneish M, Graham number, Magic Formula |
| `earnings_quality.py` | Earnings-consistency score (CV + trend + profitability) |
| `news.py` | Multi-source headlines (Google News: Moneycontrol/ET/Mint/BS + Yahoo) + sentiment/event tagging |
| `candles.py` | Candlestick pattern detection from OHLC (no TA-Lib) |
| `themes.py` | Theme & sentiment heatmap |
| `options.py` | Options/F&O analytics (US via yfinance, India via NSE best-effort) |
| `multibagger.py` | Composite scoring + conviction + concentrated portfolio |
| `screener.py` | Orchestrates fetch → news → candles → score → portfolio → themes → industry P/E → payload |
| `store.py` | **MySQL** persistence (SQLAlchemy + PyMySQL), graceful local-JSON fallback |
| `web.py` | Flask app: serves the SPA + screen/predictor/options/fundamentals/paper APIs |
| `market_sentiment.py`, `metrics.py`, `backtest.py`, `stock_universe.py` | Next-day predictor engine |
| `paper_trading.py`, `paper_db.py` | Paper-trading simulator + storage |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
```

### MySQL

Persistence uses a single JSON key/value table (`app_store`). Point the app at
your MySQL via a SQLAlchemy URL:

```bash
export MYSQL_URL="mysql+pymysql://root@127.0.0.1:3306/market_intelligence"
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS market_intelligence CHARACTER SET utf8mb4;"
```

If `MYSQL_URL` is unset or the DB is unreachable, the app degrades gracefully to
a local JSON cache (`cache/store.json`) — local dev needs no database.

## Run

```bash
# dev
(cd backend && ../.venv/bin/python web.py)     # http://localhost:8000

# production-style (what the container runs)
./.venv/bin/gunicorn --chdir backend web:app --bind 0.0.0.0:8000 \
    --worker-class gthread --workers 1 --threads 8 --timeout 300
```

Both engines build in a background thread (the screen takes ~30s live) and the
browser polls until ready; results cache in memory + MySQL for warm restarts.

**Endpoints:** `/` (UI) · `GET /api/screen` · `POST /api/screen/refresh` ·
`GET /api/premarket` · `POST /api/refresh` · `GET /api/options` ·
`GET /api/fundamentals` · `/api/paper/*` · `/healthz`.

> Use **1 worker** (the cache + background threads live in-process); scale with
> threads, not workers.

## Customising

- **Universe:** edit `universe.py` (add NSE `.NS` tickers or US symbols).
- **Strategy weights & bands:** edit `config.py` (`WEIGHTS`, small-cap band,
  liquidity floor, portfolio size, per-sector cap, score threshold).
- **News lexicon:** edit `EVENT_LEXICON` in `news.py` to tune event detection.

## Deploy (containerised)

The `Dockerfile` binds to `$PORT`. On Render, set `MYSQL_URL` in the dashboard
(or use `render.yaml`). Health check path is `/healthz`.

```bash
docker build -t market-intel .
docker run -p 8000:8000 -e PORT=8000 -e MYSQL_URL="mysql+pymysql://…" market-intel
```

## Notes & limitations

- Yahoo Finance (`yfinance`) is unofficial and rate-limited; some tickers may
  occasionally fail (they're skipped, never fatal).
- Fundamentals are point-in-time snapshots, not audited filings.
- The news catalyst layer uses a transparent keyword lexicon (no API key). Plug
  in a stronger provider in `news.py` if you want deeper coverage.
- This is a *screen*, not a valuation model — always read the filings first.
