Access it on https://india-market-analysis.onrender.com/

# India Market Analysis — Event-Aware Stock Screener

A self-contained Python tool that does an **in-depth, rules-based market
analysis** of liquid Indian (NSE) stocks and surfaces a diversified shortlist
of 5–6 ideas for a ~6-month horizon.

It blends three layers:

1. **Quantitative (bottom-up):** live fundamentals + technicals per stock
   (P/E, forward P/E, PEG, P/B, ROE, net margin, debt/equity, earnings &
   revenue growth, 6-month price return, 200-DMA, 52-week-high position).
2. **Macro / event (top-down):** a configurable macro/event calendar (festive
   season, capex/Budget cycle, state elections, global rate path, IT demand,
   commodities, pharma defensiveness) that applies a **sector tilt** to scores.
3. **AI + government policy (thematic):** a per-sector AI-impact knowledge base
   plus **live news headlines** (flagged when AI-relevant). The tool ranks the
   **top 3 sectors** and, for each, prints how AI + policy will drive growth and
   lists the **top 6 stocks** in that sector.

> ⚠️ **EDUCATIONAL / RESEARCH TOOL — NOT INVESTMENT ADVICE.**
> This is an automated screen. It is not a recommendation to buy or sell any
> security, and the author is not a SEBI-registered investment adviser. Data
> from Yahoo Finance can be delayed or wrong. Markets carry risk of loss. Do
> your own research and/or consult a registered adviser before investing.

## How the score works

Each stock gets a **0–100 composite** built from five pillars, each normalised
by **percentile rank within the universe** (robust to outliers/units):

| Pillar      | Weight | Inputs (direction)                                             |
|-------------|:------:|----------------------------------------------------------------|
| Valuation   | 22%    | trailing P/E ↓, PEG ↓, P/B ↓                                   |
| Quality     | 22%    | ROE ↑, net margin ↑, debt/equity ↓                             |
| Growth      | 18%    | earnings growth ↑, revenue growth ↑                            |
| Momentum    | 13%    | 6-month return ↑, distance above 200-DMA ↑                     |
| Event tilt  | 13%    | sector tailwind/headwind from the macro calendar               |
| AI tilt     | 12%    | per-sector AI exposure from `ai_impact.py`                     |

Final picks are chosen top-down by score with a **per-sector cap** (default 2)
for diversification.

### AI-driven sector deep-dive

After the overall picks, the tool ranks sectors (bottom-up quality of names
blended with each sector's AI tilt), selects the **top 3**, and for each prints:

- an **AI impact / news thesis** (opportunity *and* risk),
- a **growth outlook**,
- the **government-policy backdrop** (IndiaAI Mission, Semiconductor Mission,
  RBI FREE-AI, PLI schemes, DPDP Act, FAME/EV, power-transition targets, ...),
- the **top stocks** in the sector with valuation/quality metrics,
- **recent live headlines** per stock (AI-relevant ones flagged `[AI]`), and
- an **expert analyst note** per stock (see below).

### Expert analyst overlay (`analyst.py`)

A transparent rules engine converts each stock's scores + metrics into a
broker-style note:

- **Call / role** — Contrarian value, Value, Growth, Quality compounder
  (premium), Momentum/Tactical, or Core/balanced.
- **Conviction** — High / Medium / Speculative (downgraded when risk is high).
- **Position-size tier** — Core / Half / Starter, by conviction × risk.
- **Risk management** — a **stop-loss %** (tighter for high-beta/expensive
  names, wider for low-beta value) with the implied stop **price**, plus a
  trim/review level.
- **Thesis & key risks** — assembled from the actual numbers.
- **Entry plan** — staggered-tranche guidance tailored to the role.
- **Macro flags** — e.g. crude/Hormuz sensitivity inferred from the company's
  *industry* (upstream benefits vs oil-marketing margin squeeze), rate
  sensitivity for leveraged utilities, USD/INR for IT, dividend cushion,
  governance/headline risk.

Every output is derived from stated thresholds, so it is explainable and
reproducible. It is **not** investment advice.

## Setup

```bash
cd india_market_analysis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Web app (browser UI)

A Flask app serves a simple, responsive dashboard. Because a full run pulls
live data + news (~30–60s), the analysis runs in a **background thread** and the
browser polls until it's ready; the result is cached in memory and on disk
(`cache/latest.json`) for warm restarts. A **Refresh** button forces a new run.

Run locally:

```bash
# dev server
./.venv/bin/python web.py                      # http://localhost:8000

# production-style (what the container runs)
./.venv/bin/gunicorn web:app --bind 0.0.0.0:8000 \
    --worker-class gthread --workers 1 --threads 8 --timeout 300
```

Endpoints: `/` (UI), `/api/report`, `POST /api/refresh`, `/api/status`,
`/healthz`. Tunable via env vars: `PICKS`, `TOP_SECTORS`, `PER_SECTOR`,
`INCLUDE_NEWS`, `CACHE_DIR`, `PORT`, `REFRESH_INTERVAL_HOURS`.

> Use **1 worker** (the cache + background thread live in-process); scale with
> threads, not workers.

### Refresh limit & single-job guard

- **Rate limit:** a user **Refresh** is allowed at most **once every
  `REFRESH_INTERVAL_HOURS` (default 3h)**. The cooldown clock is seeded from the
  last successful run stored on disk, so restarting the app can't bypass it.
  The UI disables the button and shows a live "Refresh in `Hh Mm`" countdown;
  the API returns `{"started": false, "reason": "cooldown", ...}`.
- **Single job:** if many users click Refresh at once, the check-and-launch is
  done atomically under a lock, so **only one** background analysis ever runs;
  the rest get `{"started": false, "reason": "running"}`.
- The very first load (cold cache) computes immediately and is exempt from the
  cooldown.

## Deploy (containerised)

The included `Dockerfile` works on any container platform. It binds to `$PORT`
(set automatically by Render/Railway/Fly/Cloud Run).

**Render.com** — commit the repo and either point Render at the `Dockerfile`
(Web Service → Docker) or use the included `render.yaml` (Blueprint). Health
check path is `/healthz`.

```bash
# build & run locally to test the image
docker build -t india-market-analysis .
docker run -p 8000:8000 -e PORT=8000 india-market-analysis
```

Buildpack platforms (Heroku/Railway) can use the included `Procfile` instead.

## Usage

```bash
python main.py                      # full live run, 6 diversified picks + AI deep-dive
python main.py --picks 5            # 5 picks
python main.py --max-per-sector 1   # stricter diversification
python main.py --top-sectors 3      # sectors in the AI deep-dive
python main.py --per-sector 6       # stocks listed per sector
python main.py --no-news            # skip live headline fetch (faster)
python main.py --no-analyst         # skip the expert analyst notes
python main.py --csv scored.csv     # also dump the full ranked table
python main.py --raw-csv raw.csv    # cache raw fetched metrics
python main.py --offline raw.csv    # re-score from cached metrics (no network)
```

## Customising

- **Universe:** edit `stock_universe.py` (add/remove NSE tickers, `.NS` suffix).
- **Macro view:** edit `events_calendar.py` — change events, dates and the
  per-sector `tilt` values to match your own read of the next 6 months.
- **AI / policy view:** edit `ai_impact.py` — update each sector's `ai_tilt`,
  thesis, growth outlook, government-policy note and news keywords.
- **Pillar weights:** edit `WEIGHTS` in `scoring.py`.

## Files

| File                 | Purpose                                            |
|----------------------|----------------------------------------------------|
| `main.py`            | CLI + report generation                            |
| `web.py`             | Flask web app (background compute + cache + API)   |
| `report.py`          | shared service layer → JSON-serializable report    |
| `templates/index.html` · `static/`| responsive browser UI (HTML/CSS/JS)  |
| `metrics.py`         | yfinance fetch (parallel) + technicals + news      |
| `scoring.py`         | composite scoring + sector ranking + diversification|
| `stock_universe.py`  | candidate NSE tickers (>=6 per major sector)       |
| `events_calendar.py` | macro/event calendar + sector tilts (incl. crude/Hormuz)|
| `ai_impact.py`       | per-sector AI thesis, growth, gov policy, AI tilt  |
| `analyst.py`         | expert overlay: role/conviction/sizing/stop-loss/thesis|
| `Dockerfile` · `render.yaml` · `Procfile` | container & deploy config     |

## Notes & limitations

- Uses Yahoo Finance (`yfinance`), which is **unofficial** and rate-limited;
  the tool paces requests and retries, but some tickers may occasionally fail.
- Fundamentals are point-in-time snapshots, not audited filings.
- The event layer is a set of **editable assumptions**, not forecasts.
- This is a *screen*, not a valuation model — always read the company's
  filings, results and risks before acting.
