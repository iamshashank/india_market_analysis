"""Nightly broad-market scan.

Builds the *dynamic* full universe (NSE + BSE + US, fetched live) and runs the
multibagger screen over it in throttled batches, writing the result to MySQL so
the web app serves broad-market coverage on its next load.

Because the full universe is large (thousands of names) and Yahoo rate-limits,
this is an offline batch job — NOT something the web request does live. News is
skipped for the broad pass (catalyst stays neutral); the live/curated screen
keeps the per-stock news.

Env knobs:
    SCAN_MARKETS   default "IN,BSE,US"   (comma list of IN/BSE/US)
    SCAN_LIMIT     default 0 (all)       cap symbols (for testing)
    SCAN_BATCH     default 300           fundamentals fetched per batch
    SCAN_SLEEP     default 2.0           seconds slept between batches
    SCAN_STORE_KEY default "screen_latest"
    MYSQL_URL      the database to write to

Run:
    ./.venv/bin/python pipelines/nightly/scan.py
Schedule (after close), e.g. cron:
    30 22 * * 1-5  cd /path/to/repo && ./.venv/bin/python pipelines/nightly/scan.py >> scan.log 2>&1
"""

from __future__ import annotations

import os
import sys
import time

# News off by default for the broad pass (far too many names to fetch per-stock).
os.environ.setdefault("INCLUDE_NEWS", "0")

# Make the backend package importable (subpackages live in ../../backend).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))


def _chunks(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main() -> int:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[scan] broad-market scan started {started}")
    try:
        from data.symbols import build_dynamic_universe
        from data.fundamentals import fetch_universe
        from signals.screener import assemble_payload
        from core import store

        markets = tuple(m.strip() for m in os.environ.get("SCAN_MARKETS", "IN,BSE,US").split(",") if m.strip())
        limit = int(os.environ.get("SCAN_LIMIT", "0"))
        batch = int(os.environ.get("SCAN_BATCH", "300"))
        sleep_s = float(os.environ.get("SCAN_SLEEP", "2.0"))
        key = os.environ.get("SCAN_STORE_KEY", "screen_latest")

        universe = build_dynamic_universe(markets)
        items = list(universe.items())
        if limit > 0:
            items = items[:limit]
        total = len(items)
        print(f"[scan] scanning {total} symbols from {markets} in batches of {batch}")

        rows = []
        t0 = time.time()
        for bi, chunk in enumerate(_chunks(items, batch), 1):
            sub = dict(chunk)
            rows.extend(fetch_universe(sub))
            done = len(rows)
            print(f"[scan] batch {bi}: {done}/{total} fetched ({round(time.time()-t0)}s)")
            store.save({"as_of": started, "done": done, "total": total,
                        "markets": list(markets)}, "scan_progress")
            if sleep_s and done < total:
                time.sleep(sleep_s)

        payload = assemble_payload(rows, news_map={}, universe_size=total, t0=t0)
        payload["scan"] = {"broad": True, "markets": list(markets), "symbols": total,
                           "news": False}
        ok = store.save(payload, key)
        print(f"[scan] done: scored={payload.get('scored_count')} "
              f"portfolio={len(payload.get('portfolio', []))} "
              f"saved_to_mysql={ok} key={key} elapsed={round(time.time()-t0)}s")
        return 0 if ok else 1
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[scan] failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
