# Roadmap

## ✅ Phase 1 (V1) — complete

A working, self-serve equity-intelligence web app (Flask + React/MUI SPA,
MySQL persistence). Capabilities shipped:

- **Multibagger Finder** — size-neutral scoring across per-market cap tiers
  (India: Large/Mid/Small · US: Mega→Micro), 7 pillars (room-to-grow,
  earnings consistency, low coverage, growth, quality, valuation, news
  catalyst), per-tier high-conviction portfolios + full ranked shortlist.
- **Analyze a Stock** — search any NSE/BSE/US symbol; full score breakdown,
  price chart (line/candles, SMA-50/200), score-history trend, fundamentals
  dialog (≈34 ratios + income/balance/cashflow + Piotroski/Altman/Graham/
  Magic-Formula/Beneish), news catalysts. BSE→NSE twin fallback.
- **Themes** — per-market sentiment/momentum heatmap.
- **Options / F&O** — US via Yahoo; India best-effort (NSE often blocks).
- **Next-Day Predictor + Paper Trading** — NSE open prediction + simulated book.
- **Score history + forward-return backtest** — every screen build snapshots
  scores to `score_history`; the backtest measures whether high scores preceded
  higher forward returns (strengthens as snapshots accumulate).
- **Platform** — global market selector, react-router deep links, glossary
  page + drawer (with candlestick visuals), dark/light, dynamic NSE+BSE+US
  symbol masters (deduped, prefer NSE).

### Known limitations (carry into V2)
- Yahoo Finance is the only data source (delayed, flaky for BSE/small caps).
- Live screen runs the curated ~89-name universe; the broad ~15k scan
  (`pipelines/nightly/scan.py`) exists but **isn't scheduled yet**.
- News sentiment is a keyword lexicon (not LLM/entity-aware).
- No auth/accounts; no watchlists/alerts yet; US-only F&O; no tests/CI.

## 🔜 Phase 2 — data pipelines & accumulation (NEXT)

Trigger: when you say "build pipeline" (or similar). Detailed design lives in
`pipelines/README.md`. Summary:

- **A — NSE-first scrapers** (`nseindia.com`): corporate announcements, board
  meetings, results calendar, bulk/block deals, insider (SAST) deals, FII/DII,
  delivery %, F&O OI/option chain, index constituents.
- **B — BSE redundant feed** (`bseindia.com` + `api.bseindia.com`) for
  corroborating announcements / fallback.
- **C — Broker API (Zerodha Kite)** for reliable real-time data where scraping
  is too fragile (needs user key; env-only, never committed).
- **F — Schedule the nightly broad scan** so the live screen covers the full
  universe and `score_history` accrues daily (unlocks the real backtest).

Implementation notes: both exchanges block server traffic → use the
browser-session pattern (homepage cookies + real headers + pacing + graceful
fallback); jobs live under `pipelines/<cadence|india>/`, bootstrap `sys.path`
to `backend/`, and persist via `core.store` / `core.score_history`.

## 🗓️ Backlog (deferred from V1 review)

- **Watchlists + alerts** (MySQL-backed) — *next after pipelines unless reprioritised.*
- **Compare view** (2–5 stocks side-by-side) + command palette / keyboard nav.
- **Pluggable real data layer** — abstraction so a broker/paid API replaces
  Yahoo as default (keys later).
- **LLM layer** — entity-aware news, auto-thesis, natural-language screening.
- **Hardening** — tests, CI, error monitoring, retry/resilience.
