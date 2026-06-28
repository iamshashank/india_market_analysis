"""Real-holdings portfolio.

Pluggable holdings *sources* (manual entry, CSV upload, and — once you add your
own API keys — Groww / Zerodha Kite) feed a single analysis that runs the full
multibagger engine (score · health · inflection · emerging) on each holding and
groups it by broker. Equities only.

Security: broker API keys/tokens are read from environment variables / a
git-ignored .env, never committed and never passed through chat. The app runs
locally, so uploaded statements and holdings never leave your machine.
"""

from __future__ import annotations
