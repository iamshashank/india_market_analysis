# Data pipelines

Standalone, scheduled jobs that accumulate / refresh data. They import the
backend modules (via a small `sys.path` bootstrap at the top of each script) and
write results to MySQL, so the web app picks them up on its next load.

Run any job with the project venv, e.g.:

```bash
./.venv/bin/python pipelines/nightly/scan.py
```

## Layout

| Folder | Cadence | Jobs |
|--------|---------|------|
| `nightly/` | after US/India close | `scan.py` — broad-market multibagger scan → MySQL |
| `preopen/` | ~08:40 IST, Mon–Fri | `cron_refresh.py` — refresh the next-day predictor |
| `weekly/` | weekend | _(planned)_ e.g. corporate-actions, fundamentals refresh, theme recompute |

## Scheduling

These need access to the same MySQL as the app. Schedule locally with cron /
launchd (examples in each job's docstring), or run them on a host that can reach
the database. (GitHub Actions can't reach a local MySQL.)

## Adding a job

1. Create `pipelines/<cadence>/<job>.py`.
2. Start it with the bootstrap so backend imports resolve:

   ```python
   import os, sys
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))
   ```
3. Import what you need (`from screener import build_screen`, `import store`, …),
   do the work, and persist via `store.save(data, "<key>")`.

---

## Phase 2 — India market data pipelines (PLANNED, not built yet)

> Build these when asked ("build pipeline" / "build the India scrapers"). This
> section is the agreed design so it's ready to implement.

### NSE vs BSE — which to use
- **NSE is canonical for India.** It carries ~90%+ of cash-equity liquidity and
  virtually all F&O volume; Yahoo data for `.NS` is far more complete (market
  cap, volume, fundamentals) than `.BO`.
- **BSE is secondary** — used only for (a) BSE-exclusive listings and (b) a
  redundant corporate-announcements feed. When a company lists on both, prefer
  the NSE ticker. (The broad scan already dedupes BSE↔NSE by company name,
  preferring `.NS` — see `data/symbols.build_dynamic_universe(dedupe_in=True)`.)

### Scope to build (A + B + C)
- **A — NSE-first scrapers** (`nseindia.com`): corporate announcements / board
  meetings / results calendar, bulk & block deals, insider (SAST) deals,
  FII/DII activity, delivery %, F&O open-interest & option chain, index
  constituents, 52-wk highs/lows, most-active.
- **B — BSE redundant feed** (`bseindia.com`, incl. the semi-public
  `api.bseindia.com`): corporate announcements/filings as a corroborating /
  fallback source when NSE blocks.
- **C — Broker API (Zerodha Kite) fallback** for reliable, real-time India
  data (quotes, F&O, holdings) where scraping is too fragile. Needs user API
  key + daily login token — read from env / a git-ignored file, never committed.

### Implementation notes (important)
- **Both exchanges block non-browser/server traffic.** Use a browser-like
  session: GET the homepage first to obtain cookies, send real
  `User-Agent`/`Referer`/`Accept-Language` headers, pace requests, and retry.
  They rotate protections, so expect maintenance — always degrade gracefully
  (return "unavailable") rather than crash. (`signals/options.analyze_in` and
  `data/symbols` already follow this pattern.)
- Suggested layout: a new `pipelines/india/` package, one job per feed
  (`announcements.py`, `deals.py`, `fii_dii.py`, `oi.py`), each writing to MySQL
  under its own `store` key; the web app reads those keys.
- Schedule per cadence (announcements intraday/EOD; deals + FII/DII EOD; OI
  intraday) on a host that can reach MySQL (cron/launchd). GitHub Actions can't
  reach a local DB.
