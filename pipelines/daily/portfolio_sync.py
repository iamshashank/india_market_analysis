"""Daily Portfolio Sync Pipeline.

Syncs portfolio holdings from configured brokers (Groww, Zerodha) and stores them
in the local portfolio. Runs daily to keep holdings up-to-date.

Supports:
  - Groww: TOTP or API Key authentication
  - Zerodha Kite: API key + access token
  - Manual holdings stored locally

Usage:
    python pipelines/daily/portfolio_sync.py
    python pipelines/daily/portfolio_sync.py --debug
    python pipelines/daily/portfolio_sync.py --broker groww
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Load .env file first
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add backend to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from portfolio.sources.groww import GrowwSource
from portfolio.sources.kite import KiteSource
from portfolio import holdings_store
from core import store

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

SOURCES = [
    ("Groww", GrowwSource()),
    ("Zerodha Kite", KiteSource()),
]


def sync_broker(name: str, source) -> dict:
    """Sync holdings from a single broker source.
    
    Returns: {success: bool, count: int, broker: str, error: str|None}
    """
    if not source.is_configured():
        log.info(f"⊘ {name}: not configured (skipped)")
        return {"success": True, "count": 0, "broker": name, "configured": False}
    
    try:
        log.info(f"🔄 Syncing {name}...")
        holdings_list = source.holdings()
        count = len(holdings_list)
        log.info(f"✓ {name}: fetched {count} holdings")
        return {"success": True, "count": count, "broker": name, "holdings": holdings_list}
    except Exception as e:
        log.error(f"✗ {name}: {e}")
        return {"success": False, "count": 0, "broker": name, "error": str(e)}


def run(broker_filter: str | None = None, debug: bool = False) -> dict:
    """Run portfolio sync pipeline.
    
    Args:
        broker_filter: if set, only sync this broker (e.g., 'groww')
        debug: if True, print detailed output
    
    Returns: pipeline result dict
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    log.info("=" * 60)
    log.info("Portfolio Sync Pipeline Started")
    log.info("=" * 60)
    
    start_time = datetime.now()
    results = []
    total_holdings = 0
    
    # Sync each broker
    for name, source in SOURCES:
        if broker_filter and broker_filter.lower() != name.lower().split()[0].lower():
            continue
        result = sync_broker(name, source)
        results.append(result)
        if result["success"]:
            total_holdings += result["count"]
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log.info("=" * 60)
    log.info(f"Portfolio Sync Complete | {total_holdings} holdings | {duration:.1f}s")
    log.info("=" * 60)
    
    return {
        "success": all(r["success"] for r in results),
        "total_holdings": total_holdings,
        "brokers_synced": len([r for r in results if r["count"] > 0]),
        "duration_seconds": duration,
        "results": results,
        "timestamp": start_time.isoformat(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio Sync Pipeline")
    parser.add_argument("--broker", type=str, help="Sync only this broker (e.g., groww)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    result = run(broker_filter=args.broker, debug=args.debug)
    
    # Print JSON result
    print("\n" + json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)
