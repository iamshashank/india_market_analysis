"""Scheduled pre-open refresh (run by Render Cron, ~20 min before NSE open).

Primary mode: ping the live web service's POST /api/refresh so the running app
rebuilds its in-memory cache AND persists to Postgres. Then poll until the
build finishes, so the cron logs show success/failure.

Fallback mode: if APP_URL isn't set, build the prediction in-process and save
it straight to Postgres (requires MASTER_DB). The web service will pick it up
on its next load from the DB.

Env vars:
    APP_URL   e.g. https://india-market-analysis.onrender.com  (preferred)
    MASTER_DB Postgres DSN (used by fallback + by the web app for persistence)
"""

from __future__ import annotations

import os
import sys
import time

# Make the backend package importable (flat modules live in ../../backend).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

APP_URL = os.environ.get("APP_URL", "").rstrip("/")
POLL_TIMEOUT = int(os.environ.get("CRON_POLL_TIMEOUT", "240"))


def _via_http() -> int:
    import requests

    refresh_url = f"{APP_URL}/api/refresh"
    status_url = f"{APP_URL}/api/premarket"
    print(f"[cron] triggering refresh: {refresh_url}")
    r = requests.post(refresh_url, timeout=60)
    print(f"[cron] refresh response: {r.status_code} {r.text[:200]}")
    r.raise_for_status()

    # Poll until the build completes (it's async on the server).
    deadline = time.time() + POLL_TIMEOUT
    last = None
    while time.time() < deadline:
        time.sleep(8)
        try:
            j = requests.get(status_url, timeout=30).json()
        except Exception as e:  # noqa: BLE001
            print(f"[cron] poll error: {e}")
            continue
        status = j.get("status")
        if status != last:
            print(f"[cron] status: {status}")
            last = status
        if status == "ready" and j.get("data"):
            as_of = (j.get("data") or {}).get("as_of")
            print(f"[cron] refresh complete. as_of={as_of}")
            return 0
        if status == "error":
            print(f"[cron] build error: {j.get('error')}")
            return 1
    print("[cron] timed out waiting for build to finish")
    return 1


def _via_db() -> int:
    if not os.environ.get("MYSQL_URL"):
        print("[cron] neither APP_URL nor MYSQL_URL set — nothing to do.")
        return 1
    print("[cron] APP_URL not set — building in-process and saving to MySQL.")
    from predictor.market_sentiment import build_premarket
    from core import db

    data = build_premarket(force=True)
    ok = db.save(data)
    print(f"[cron] built as_of={data.get('as_of')}, saved_to_db={ok}")
    return 0 if ok else 1


def main() -> int:
    started = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"[cron] pre-open refresh started at {started}")
    try:
        if APP_URL:
            return _via_http()
        return _via_db()
    except Exception as e:  # noqa: BLE001
        print(f"[cron] failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
