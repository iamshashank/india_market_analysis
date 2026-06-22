"""Flask app — Next-Day Market-Open Predictor.

Single feature: predict which NSE stocks are most likely to OPEN HIGHER the
next trading day, from overnight global cues + ADR moves.

Building fetches live data (~30-60s the first time), so it runs in a background
thread; the browser polls until ready. Results are cached in memory with a TTL.

Endpoints:
    GET  /                -> UI
    GET  /api/premarket   -> prediction (kicks off a build if stale/missing)
    POST /api/refresh     -> force a fresh build
    GET  /healthz         -> health check
"""

from __future__ import annotations

import os
import threading
import time
import traceback

from flask import Flask, jsonify, render_template, request

from market_sentiment import build_premarket
import db

app = Flask(__name__)

# How long a built prediction stays fresh before an auto-rebuild (minutes).
TTL = float(os.environ.get("PREMARKET_TTL_MIN", 15)) * 60.0

_state = {"status": "idle", "data": None, "error": None, "ts": 0.0}
_lock = threading.Lock()


def _compute(force: bool):
    try:
        data = build_premarket(force=force)
        _state["data"] = data
        _state["ts"] = time.time()
        _state["status"] = "ready"
        _state["error"] = None
        # Persist the whole payload as JSON under a single key.
        db.save(data)
    except Exception as e:  # noqa: BLE001
        _state["error"] = str(e)
        _state["status"] = "error"
        traceback.print_exc()


def _start(force: bool = False) -> bool:
    with _lock:
        if _state["status"] == "running":
            return False
        _state["status"] = "running"
        if force:
            _state["error"] = None
        t = threading.Thread(target=_compute, args=(force,), daemon=True)
        t.start()
    return True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/premarket")
def api_premarket():
    fresh = _state["data"] is not None and (time.time() - _state["ts"] < TTL)
    if not fresh and _state["status"] != "running":
        _start(force=False)
    return jsonify({
        "status": _state["status"],
        "error": _state["error"],
        "data": _state["data"],
        "ttl_minutes": TTL / 60.0,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    started = _start(force=True)
    return jsonify({"started": started, "status": _state["status"]})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "status": _state["status"]})


# Warm from Postgres first (instant + survives restarts), then refresh live.
db.init_db()
_cached = db.load()
if _cached:
    _state["data"] = _cached
    _state["ts"] = time.time()
    _state["status"] = "ready"
_start(force=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
