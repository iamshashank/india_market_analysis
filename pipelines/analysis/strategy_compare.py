"""Standalone A/B strategy comparison report.

Scores the curated universe under every registered strategy and prints how well
each separates realised returns (IC / spread / hit-rate), naming the winner.

Run:
    ./.venv/bin/python pipelines/analysis/strategy_compare.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("INCLUDE_NEWS", "0")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))


def main() -> int:
    from signals import strategy_compare
    rep = strategy_compare.compare()
    if not rep.get("available"):
        print("No comparison available (insufficient data).")
        return 1
    print(f"\nStrategy A/B — universe={rep['scored_universe']} · return_mode={rep['return_mode']}\n")
    hdr = f"{'strategy':<24}{'n':>5}{'IC':>8}{'spread%':>10}{'topQ hit%':>11}{'topQ avg%':>11}{'botQ avg%':>11}"
    print(hdr); print("-" * len(hdr))
    for r in rep["results"]:
        def f(v, nd=3):
            return "n/a" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
        star = " *" if r["version"] == rep["best_version"] else ""
        print(f"{r['version']:<24}{r['n']:>5}{f(r['ic']):>8}{f(r['spread_pct'],2):>10}"
              f"{f(r['top_q_hit_pct'],1):>11}{f(r['top_q_avg_pct'],2):>11}{f(r['bottom_q_avg_pct'],2):>11}{star}")
    print(f"\nBest separation: {rep['best_version']}")
    print(f"\n{rep['caveat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
